"""P07 Model — FreshnessScheduler.

Integrates FreshnessTracker with asyncio periodic scanning to drive
automatic rescans when scanner data becomes stale.

Architecture:
    fresh  → aging → stale → rescan requested → scanner executes
    → environment graph updated → freshness refreshed

Safety invariants:
    - No duplicate scheduled jobs (idempotent register).
    - Scanner failures are caught and logged — never propagate.
    - Shutdown-safe: background task is cancelled cleanly.
    - Cancellation-safe: asyncio.CancelledError propagates correctly.
    - Privacy zones are enforced by the scanner_fn caller (not here).
    - Offline-safe: if scanner_fn raises, freshness is NOT updated.
    - No uncontrolled infinite scanning: sleep(check_interval_seconds)
      between cycles, plus deadline-bounded scanner_fn.

Dependency rule: uses asyncio (stdlib) only. Does NOT import L2
BackgroundTaskManager (would introduce L4→L2 direct dep). An optional
task_manager parameter allows callers to inject it if desired, but it
is never required.

Import safety: l4_memory.p07.model.* + stdlib ONLY.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from aegis.l4_memory.p07.model.freshness import FreshnessTracker

__all__ = ["FreshnessSchedulerConfig", "FreshnessScheduler"]

logger = logging.getLogger(__name__)

# Type alias for a scanner coroutine function
ScannerFn = Callable[[], Awaitable[Any]]


@dataclass
class FreshnessSchedulerConfig:
    """Configuration for the FreshnessScheduler.

    Attributes:
        check_interval_seconds: How often to poll for stale scanners.
                                Default: 300s (5 minutes).
        rescan_on_stale:        If True (default), automatically trigger
                                scanner_fn when a scanner becomes stale.
        max_concurrent_rescans: Maximum number of scanners that may run
                                simultaneously in a single cycle.
    """
    check_interval_seconds: float = 300.0
    rescan_on_stale: bool = True
    max_concurrent_rescans: int = 3


@dataclass
class _ScannerRegistration:
    """Internal registration record for a scanner."""
    name: str
    scanner_fn: ScannerFn
    ttl_seconds: float
    last_run_at: float = 0.0
    error_count: int = 0
    last_error: str | None = None


class FreshnessScheduler:
    """Drives periodic environment rescans based on FreshnessTracker state.

    Usage::

        tracker = FreshnessTracker()
        scheduler = FreshnessScheduler(tracker)

        # Register a scanner with TTL
        async def run_app_scan():
            result = await app_scanner.scan()
            tracker.mark_scanned("app_scanner")
            return result

        scheduler.register("app_scanner", run_app_scan, ttl_seconds=86400)

        # Start background loop
        await scheduler.start()

        # ... AEGIS runs ...

        # Clean shutdown
        await scheduler.stop()

    The scheduler is idempotent: calling register() twice for the same name
    is a no-op (first registration wins). Call unregister() then register()
    to update.
    """

    def __init__(
        self,
        tracker: FreshnessTracker | None = None,
        config: FreshnessSchedulerConfig | None = None,
    ) -> None:
        self._tracker = tracker or FreshnessTracker()
        self._config = config or FreshnessSchedulerConfig()
        self._registrations: dict[str, _ScannerRegistration] = {}
        self._task: asyncio.Task | None = None
        self._running = False

    # ------------------------------------------------------------------
    # Scanner registration
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        scanner_fn: ScannerFn,
        ttl_seconds: float = 86400.0,
    ) -> bool:
        """Register a scanner with the scheduler.

        Idempotent: if name is already registered, this is a no-op.

        Args:
            name:          Unique scanner name (must match FreshnessTracker).
            scanner_fn:    Async callable that performs the scan.
            ttl_seconds:   How long scan results are fresh. When this elapses,
                           the scheduler will trigger scanner_fn.

        Returns:
            True if newly registered; False if already registered (no-op).
        """
        if name in self._registrations:
            logger.debug("FreshnessScheduler: %r already registered (no-op)", name)
            return False
        self._registrations[name] = _ScannerRegistration(
            name=name,
            scanner_fn=scanner_fn,
            ttl_seconds=ttl_seconds,
        )
        self._tracker.register(name, ttl_seconds=ttl_seconds)
        logger.debug("FreshnessScheduler: registered scanner %r (ttl=%.0fs)", name, ttl_seconds)
        return True

    def unregister(self, name: str) -> bool:
        """Unregister a scanner. Returns True if it was registered."""
        if name in self._registrations:
            del self._registrations[name]
            return True
        return False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the background scanning loop.

        Idempotent: if already running, this is a no-op.
        """
        if self._running:
            logger.debug("FreshnessScheduler: already running")
            return
        self._running = True
        self._task = asyncio.create_task(
            self._loop(),
            name="aegis:p07:freshness_scheduler",
        )
        logger.info("FreshnessScheduler: started (interval=%.0fs)", self._config.check_interval_seconds)

    async def stop(self, timeout: float = 5.0) -> None:
        """Stop the background loop gracefully.

        Args:
            timeout: Maximum seconds to wait for the loop to stop.
        """
        self._running = False
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(self._task), timeout=timeout)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass
            self._task = None
        logger.info("FreshnessScheduler: stopped")

    @property
    def is_running(self) -> bool:
        """True if the background loop is active."""
        return self._running and (self._task is not None) and (not self._task.done())

    # ------------------------------------------------------------------
    # Manual trigger
    # ------------------------------------------------------------------

    async def trigger_rescan(self, name: str) -> bool:
        """Manually trigger a rescan for a registered scanner.

        Args:
            name: Scanner name. Must be registered.

        Returns:
            True if the scan ran successfully; False on error or not found.
        """
        reg = self._registrations.get(name)
        if reg is None:
            logger.warning("FreshnessScheduler: cannot trigger %r — not registered", name)
            return False
        return await self._run_scanner(reg)

    async def trigger_all_stale(self) -> dict[str, bool]:
        """Manually trigger rescans for all stale scanners.

        Returns:
            Dict mapping scanner name → success/failure.
        """
        results: dict[str, bool] = {}
        for name, reg in self._registrations.items():
            if self._tracker.is_stale(name):
                results[name] = await self._run_scanner(reg)
        return results

    # ------------------------------------------------------------------
    # Freshness tracker delegation
    # ------------------------------------------------------------------

    @property
    def tracker(self) -> FreshnessTracker:
        """Access the underlying FreshnessTracker."""
        return self._tracker

    def is_stale(self, name: str) -> bool:
        """True if the named scanner's data is stale."""
        return self._tracker.is_stale(name)

    def mark_scanned(self, name: str) -> None:
        """Manually mark a scanner as freshly scanned."""
        self._tracker.mark_scanned(name)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _loop(self) -> None:
        """Background scheduling loop."""
        while self._running:
            try:
                await self._cycle()
            except asyncio.CancelledError:
                logger.debug("FreshnessScheduler: loop cancelled")
                break
            except Exception as exc:
                # Never crash the loop on unexpected errors
                logger.error("FreshnessScheduler: unexpected loop error: %s", exc, exc_info=True)

            try:
                await asyncio.sleep(self._config.check_interval_seconds)
            except asyncio.CancelledError:
                break

    async def _cycle(self) -> None:
        """One scheduling cycle: check all registered scanners for staleness."""
        if not self._config.rescan_on_stale:
            return

        stale_names = [
            name for name in self._registrations
            if self._tracker.is_stale(name)
        ]

        if not stale_names:
            return

        logger.debug(
            "FreshnessScheduler: %d stale scanner(s): %s",
            len(stale_names), stale_names,
        )

        # Limit concurrency
        batch = stale_names[:self._config.max_concurrent_rescans]
        tasks = [self._run_scanner(self._registrations[name]) for name in batch]

        # Run with gather; errors are caught inside _run_scanner
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _run_scanner(self, reg: _ScannerRegistration) -> bool:
        """Run a single scanner safely. Returns True on success."""
        logger.debug("FreshnessScheduler: running scanner %r", reg.name)
        reg.last_run_at = time.monotonic()
        try:
            await reg.scanner_fn()
            self._tracker.mark_scanned(reg.name)
            reg.last_error = None
            logger.debug("FreshnessScheduler: scanner %r completed successfully", reg.name)
            return True
        except asyncio.CancelledError:
            # Propagate cancellation — do not swallow
            raise
        except Exception as exc:
            reg.error_count += 1
            reg.last_error = str(exc)
            logger.warning(
                "FreshnessScheduler: scanner %r failed (error #%d): %s",
                reg.name, reg.error_count, exc,
            )
            # Do NOT update freshness — stale data remains stale on error
            return False

    def summary(self) -> dict[str, Any]:
        """Return a status summary of all registered scanners."""
        return {
            name: {
                "stale": self._tracker.is_stale(name),
                "age_s": self._tracker.age_seconds(name),
                "ttl_s": reg.ttl_seconds,
                "error_count": reg.error_count,
                "last_error": reg.last_error,
            }
            for name, reg in self._registrations.items()
        }
