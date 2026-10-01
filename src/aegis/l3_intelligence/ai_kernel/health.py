"""L3 AI Kernel — ProviderHealthMonitor (P07.5).

Asyncio background loop that periodically probes registered providers
via BaseProvider.health_check() and updates the ModelRegistry with
current health status.

Design:
  - Pure asyncio — no L2 BackgroundTaskManager dependency (avoids L4->L2
    upward layer violation; same pattern as FreshnessScheduler in L4).
  - Shutdown-safe: stop() cancels the task with a configurable timeout.
  - Failure-tolerant: individual probe failures are caught and counted;
    only after ``failure_threshold`` consecutive failures is a provider
    marked DOWN.
  - Providers returning UNKNOWN (the BaseProvider default) are ignored so
    providers without health_check overrides don't pollute the registry.
  - Error isolation: one provider probe failure does not affect others.

Layer: L3 (may import L3 types + L1 interfaces + stdlib only).
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from aegis.l1_core.interfaces.llm import ModelHealth

logger = logging.getLogger(__name__)

__all__ = [
    "ProviderHealthConfig",
    "ProviderHealthMonitor",
]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class ProviderHealthConfig:
    """Configuration for ProviderHealthMonitor.

    All fields are injectable; defaults are production-safe conservative values.
    """

    # How often to run a full provider health sweep (seconds).
    check_interval_seconds: float = 60.0
    # Per-provider health probe timeout (seconds).
    timeout_seconds: float = 5.0
    # Number of consecutive failures before marking a provider DOWN.
    failure_threshold: int = 3
    # How long to wait for the background task to stop on shutdown (seconds).
    shutdown_timeout_seconds: float = 5.0


# ---------------------------------------------------------------------------
# Internal per-provider probe state
# ---------------------------------------------------------------------------


@dataclass
class _ProviderProbeState:
    consecutive_failures: int = 0
    last_check_at: float = 0.0
    last_health: ModelHealth = ModelHealth.UNKNOWN


# ---------------------------------------------------------------------------
# ProviderHealthMonitor
# ---------------------------------------------------------------------------


class ProviderHealthMonitor:
    """Background asyncio health monitor for LLM providers.

    Usage::

        monitor = ProviderHealthMonitor(
            provider_registry=prov_registry,
            model_registry=model_registry,
            config=ProviderHealthConfig(check_interval_seconds=60.0),
        )
        await monitor.start()
        # ... AEGIS runs ...
        await monitor.stop()

    Calls ``provider.health_check()`` for each registered provider and
    propagates results to ModelRegistry so the Router can weight candidates
    by health status. Providers returning ``ModelHealth.UNKNOWN`` (the
    BaseProvider default) are NOT written to the registry.
    """

    def __init__(
        self,
        provider_registry: Any,   # ProviderRegistry — typed as Any to avoid circular import
        model_registry: Any,      # ModelRegistry
        config: ProviderHealthConfig | None = None,
        logger_: logging.Logger | None = None,
    ) -> None:
        self._prov_registry = provider_registry
        self._model_registry = model_registry
        self._config = config or ProviderHealthConfig()
        self._log = logger_ or logger
        self._probe_state: dict[str, _ProviderProbeState] = {}
        self._task: asyncio.Task[None] | None = None
        self._running: bool = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the background health monitoring loop (idempotent)."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(
            self._run(), name="aegis-provider-health-monitor"
        )
        self._log.info(
            "ProviderHealthMonitor started (interval=%.1fs threshold=%d)",
            self._config.check_interval_seconds,
            self._config.failure_threshold,
        )

    async def stop(self) -> None:
        """Stop the background loop gracefully."""
        self._running = False
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await asyncio.wait_for(
                    asyncio.shield(self._task),
                    timeout=self._config.shutdown_timeout_seconds,
                )
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        self._task = None
        self._log.info("ProviderHealthMonitor stopped.")

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    async def _run(self) -> None:
        try:
            while self._running:
                await self._sweep()
                await asyncio.sleep(self._config.check_interval_seconds)
        except asyncio.CancelledError:
            self._log.debug("ProviderHealthMonitor loop cancelled.")
            raise

    async def _sweep(self) -> None:
        """Run one health-check sweep over all registered providers.

        May be called directly for manual/one-shot sweeps (e.g. in tests)
        without the ``_running`` flag being True — the flag is only used by
        the background ``_run()`` loop to know when to stop iterating.
        """
        provider_ids = list(self._prov_registry.list_provider_ids())
        for provider_id in provider_ids:
            await self._probe_provider(provider_id)

    async def _probe_provider(self, provider_id: str) -> None:
        """Probe a single provider and update registry health."""
        provider = self._prov_registry.get(provider_id)
        if provider is None:
            return

        state = self._probe_state.setdefault(provider_id, _ProviderProbeState())

        try:
            health = await asyncio.wait_for(
                provider.health_check(),
                timeout=self._config.timeout_seconds,
            )
        except asyncio.TimeoutError:
            self._log.warning(
                "Provider '%s' health probe timed out.", provider_id
            )
            health = ModelHealth.DOWN
        except Exception as exc:  # noqa: BLE001
            self._log.warning(
                "Provider '%s' health probe raised: %s", provider_id, exc
            )
            health = ModelHealth.DOWN

        state.last_check_at = time.monotonic()
        state.last_health = health

        if health == ModelHealth.UNKNOWN:
            # Provider does not override health_check(); skip registry update.
            return

        if health in (ModelHealth.HEALTHY, ModelHealth.DEGRADED):
            state.consecutive_failures = 0
        else:
            state.consecutive_failures += 1

        # Apply threshold: only mark DOWN after N consecutive failures.
        if (
            health == ModelHealth.DOWN
            and state.consecutive_failures < self._config.failure_threshold
        ):
            self._log.debug(
                "Provider '%s' probe failed (%d/%d); not yet marking DOWN.",
                provider_id,
                state.consecutive_failures,
                self._config.failure_threshold,
            )
            return

        self._write_health(provider_id, health)

    def _write_health(self, provider_id: str, health: ModelHealth) -> None:
        """Propagate health to all models belonging to this provider."""
        try:
            all_models = self._model_registry.list_all()
            updated = 0
            for model in all_models:
                if model.provider_id == provider_id:
                    self._model_registry.update_health(
                        model.model_id, model.provider_id, health
                    )
                    updated += 1
            if updated:
                self._log.debug(
                    "Provider '%s' health=%s -> updated %d model(s).",
                    provider_id,
                    health.value,
                    updated,
                )
        except Exception as exc:  # noqa: BLE001
            self._log.warning(
                "ProviderHealthMonitor: failed to write health for '%s': %s",
                provider_id,
                exc,
            )

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def get_probe_state(self, provider_id: str) -> _ProviderProbeState | None:
        """Return current probe state for a provider (for diagnostics)."""
        return self._probe_state.get(provider_id)

    def is_running(self) -> bool:
        return self._running
