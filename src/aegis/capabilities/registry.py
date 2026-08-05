"""Capabilities subsystem — CapabilityRegistry.

Manages the lifecycle of capability discovery: initial probe, caching,
periodic refresh, and query interface.

The registry is a singleton-like service owned by the runtime.
Planning modules query it to understand what tools are available.

Import safety: stdlib + aegis.capabilities.types + aegis.capabilities.discovery.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable

from aegis.capabilities.types import Capability, CapabilityKind, CapabilitySet, CapabilityStatus

logger = logging.getLogger(__name__)

__all__ = ["CapabilityRegistry"]

# Default re-probe interval: 5 minutes
_DEFAULT_REFRESH_INTERVAL = 300.0


class CapabilityRegistry:
    """Runtime capability registry with automatic discovery and caching.

    Usage::

        registry = CapabilityRegistry()
        await registry.discover()          # initial probe
        caps = registry.snapshot()         # get current CapabilitySet

        if caps.is_available(CapabilityKind.GIT):
            # plan git tasks
            ...

        # For planner prompts:
        summary = caps.to_summary_dict()   # inject into AI prompt

    The registry can be pre-seeded with fixed capabilities for tests::

        registry = CapabilityRegistry()
        registry.seed([
            Capability(kind=CapabilityKind.GIT, name="Git 2.43", status=CapabilityStatus.AVAILABLE),
        ])
    """

    def __init__(self, refresh_interval: float = _DEFAULT_REFRESH_INTERVAL) -> None:
        self._capabilities: list[Capability] = []
        self._last_discovered: float = 0.0
        self._refresh_interval = refresh_interval
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    async def discover(self, *, force: bool = False) -> CapabilitySet:
        """Run capability probes and update the registry.

        Args:
            force: If True, re-probe even if within the refresh interval.

        Returns:
            Current CapabilitySet after discovery.
        """
        async with self._lock:
            age = time.time() - self._last_discovered
            if not force and age < self._refresh_interval and self._capabilities:
                return self.snapshot()

            # Import here to avoid module-level circular import
            from aegis.capabilities.discovery import probe_all
            try:
                self._capabilities = await probe_all()
                self._last_discovered = time.time()
                available = [c for c in self._capabilities if c.is_available]
                logger.info(
                    "CapabilityRegistry: discovered %d capabilities (%d available)",
                    len(self._capabilities), len(available)
                )
            except Exception as exc:
                logger.error("CapabilityRegistry: discovery failed: %s", exc)

        return self.snapshot()

    def seed(self, capabilities: list[Capability]) -> None:
        """Pre-seed the registry (for tests or offline bootstrap).

        Args:
            capabilities: List of capabilities to register directly (no probing).
        """
        self._capabilities = list(capabilities)
        self._last_discovered = time.time()

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def snapshot(self) -> CapabilitySet:
        """Return an immutable snapshot of the current capability state."""
        return CapabilitySet(
            capabilities=list(self._capabilities),
            discovered_at=self._last_discovered,
        )

    def get(self, kind: CapabilityKind) -> Capability | None:
        """Return the capability for ``kind``, or None if not found."""
        for cap in self._capabilities:
            if cap.kind == kind:
                return cap
        return None

    def is_available(self, kind: CapabilityKind) -> bool:
        """True if this capability is currently available."""
        cap = self.get(kind)
        return cap is not None and cap.is_available

    def available_for_action(self, action_kind_prefix: str) -> bool:
        """Check if the capability needed for an L5 action kind is available.

        Maps common action prefixes to CapabilityKind:
          fs.*       → FILESYSTEM (always true)
          shell.*    → SHELL
          docker.*   → DOCKER
          git.*      → GIT
          network.*  → NETWORK
          browser.*  → BROWSER
        """
        prefix = action_kind_prefix.split(".")[0]
        mapping: dict[str, CapabilityKind] = {
            "fs":      CapabilityKind.FILESYSTEM,
            "shell":   CapabilityKind.SHELL,
            "docker":  CapabilityKind.DOCKER,
            "git":     CapabilityKind.GIT,
            "network": CapabilityKind.NETWORK,
            "browser": CapabilityKind.BROWSER,
        }
        kind = mapping.get(prefix)
        if kind is None:
            return True   # Unknown prefix = assume available
        return self.is_available(kind)

    @property
    def is_stale(self) -> bool:
        """True if capabilities haven't been probed recently."""
        return (time.time() - self._last_discovered) > self._refresh_interval

    @property
    def discovery_age_seconds(self) -> float:
        """Seconds since last discovery."""
        return time.time() - self._last_discovered
