"""Capabilities registry v2 — P08 semantic CapabilityRegistry.

The semantic capability registry is the single source of truth for
"what can AEGIS do?" It manages the full lifecycle of CapabilityRecord
objects: discovery, registration, health, metrics, and selection support.

This is distinct from the pre-P08 CapabilityRegistry (env probes) which
is now called EnvironmentProbeRegistry. Both coexist:
- EnvironmentProbeRegistry: "is git installed?"  (env layer)
- CapabilityRegistry (this): "can AEGIS use git?" (semantic layer)

Import safety: stdlib + asyncio + aegis.capabilities.* (model/store/discovery_providers)
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable

from aegis.capabilities.discovery_providers.base import CapabilityDiscoveryProvider
from aegis.capabilities.model.capability import (
    CapabilityCategory,
    CapabilityRecord,
    TrustState,
)
from aegis.capabilities.model.health import CapabilityHealth, HealthStatus
from aegis.capabilities.model.metrics import CapabilityMetrics
from aegis.capabilities.store.capability_store import CapabilityStore

logger = logging.getLogger(__name__)

__all__ = ["CapabilityRegistry"]

_DEFAULT_DISCOVERY_TIMEOUT = 10.0  # seconds for a full discovery run
_DEFAULT_REFRESH_INTERVAL  = 300.0 # seconds between auto-refreshes


class CapabilityRegistry:
    """P08 Semantic Capability Registry.

    Manages the lifecycle of CapabilityRecord objects:
    - discover()  : run all registered discovery providers
    - register()  : manually add/replace a capability
    - query()     : filter capabilities by category/trust/health etc.
    - find_for_task() : filter + rank for AI selection input
    - update_health() / update_metrics(): record invocation results

    Thread-safe. Can be used from asyncio tasks and sync code.

    Usage::

        registry = CapabilityRegistry()
        registry.add_provider(StaticRegistryProvider())
        registry.add_provider(CLIDiscoveryProvider())

        await registry.discover()  # or: registry.discover_sync()

        candidates = registry.find_for_task(
            "commit code changes",
            category=CapabilityCategory.GIT,
            offline_ok=True,
        )
    """

    def __init__(
        self,
        *,
        discovery_timeout: float = _DEFAULT_DISCOVERY_TIMEOUT,
        refresh_interval: float = _DEFAULT_REFRESH_INTERVAL,
    ) -> None:
        self._store = CapabilityStore()
        self._providers: list[CapabilityDiscoveryProvider] = []
        self._discovery_timeout = discovery_timeout
        self._refresh_interval = refresh_interval
        self._last_discovered: float = 0.0
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ #
    # Provider management
    # ------------------------------------------------------------------ #

    def add_provider(self, provider: CapabilityDiscoveryProvider) -> None:
        """Register a discovery provider."""
        self._providers.append(provider)
        logger.debug("CapabilityRegistry: added provider %r", provider.name)

    def remove_provider(self, name: str) -> bool:
        """Remove a provider by name. Returns True if found."""
        before = len(self._providers)
        self._providers = [p for p in self._providers if p.name != name]
        return len(self._providers) < before

    # ------------------------------------------------------------------ #
    # Discovery
    # ------------------------------------------------------------------ #

    async def discover(self, *, force: bool = False, offline_only: bool = False) -> int:
        """Run all discovery providers and update the store.

        Args:
            force:        Re-discover even if within refresh_interval.
            offline_only: Skip providers that require internet access.

        Returns:
            Number of capabilities registered after discovery.
        """
        async with self._lock:
            age = time.monotonic() - self._last_discovered
            if not force and age < self._refresh_interval and self._store.count() > 0:
                logger.debug("CapabilityRegistry: using cached capabilities (age=%.0fs)", age)
                return self._store.count()

            deadline = time.monotonic() + self._discovery_timeout
            providers = [
                p for p in self._providers
                if not (offline_only and p.online_required)
            ]

            loop = asyncio.get_event_loop()
            tasks = [
                loop.run_in_executor(None, p.safe_discover, deadline)
                for p in providers
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            registered = 0
            for provider, result in zip(providers, results):
                if isinstance(result, Exception):
                    logger.warning(
                        "CapabilityRegistry: provider %r raised: %s",
                        provider.name, result,
                    )
                    continue
                for record in result:
                    self._store.register(record)
                    registered += 1

            self._last_discovered = time.monotonic()
            logger.info(
                "CapabilityRegistry: discovery complete — %d capabilities total (%d registered this run)",
                self._store.count(), registered,
            )
            return self._store.count()

    def discover_sync(
        self,
        *,
        force: bool = False,
        offline_only: bool = False,
    ) -> int:
        """Synchronous discovery for use outside async context.

        Runs each provider sequentially (not parallel) to avoid event loop issues.
        """
        age = time.monotonic() - self._last_discovered
        if not force and age < self._refresh_interval and self._store.count() > 0:
            return self._store.count()

        deadline = time.monotonic() + self._discovery_timeout
        providers = [
            p for p in self._providers
            if not (offline_only and p.online_required)
        ]
        for provider in providers:
            records = provider.safe_discover(deadline)
            for record in records:
                self._store.register(record)

        self._last_discovered = time.monotonic()
        logger.info(
            "CapabilityRegistry: sync discovery complete — %d capabilities",
            self._store.count(),
        )
        return self._store.count()

    # ------------------------------------------------------------------ #
    # Registration (manual)
    # ------------------------------------------------------------------ #

    def register(self, record: CapabilityRecord) -> None:
        """Manually add or replace a capability record."""
        self._store.register(record)

    def unregister(self, capability_id: str) -> bool:
        """Remove a capability. Returns True if it existed."""
        return self._store.unregister(capability_id)

    # ------------------------------------------------------------------ #
    # Query
    # ------------------------------------------------------------------ #

    def get(self, capability_id: str) -> CapabilityRecord | None:
        """Return a capability by ID."""
        return self._store.get(capability_id)

    def query(
        self,
        *,
        category: CapabilityCategory | None = None,
        provider_id: str | None = None,
        online_required: bool | None = None,
        trust_state: TrustState | None = None,
        enabled: bool | None = None,
        usable_only: bool = False,
        predicate: Callable[[CapabilityRecord], bool] | None = None,
    ) -> list[CapabilityRecord]:
        """Filter capabilities by criteria. See CapabilityStore.query() for details."""
        return self._store.query(
            category=category,
            provider_id=provider_id,
            online_required=online_required,
            trust_state=trust_state,
            enabled=enabled,
            usable_only=usable_only,
            predicate=predicate,
        )

    def all(self) -> list[CapabilityRecord]:
        """Return all registered capabilities."""
        return self._store.all()

    def count(self) -> int:
        """Total number of registered capabilities."""
        return self._store.count()

    def find_for_task(
        self,
        goal_text: str,
        *,
        category: CapabilityCategory | None = None,
        offline_ok: bool = True,
        privacy_tier: str | None = None,
        usable_only: bool = True,
    ) -> list[CapabilityRecord]:
        """Return capabilities ranked for the given task goal.

        Applies filters then sorts by ranking_score() descending.
        The result is the input to CapabilitySelector.

        Args:
            goal_text:    Natural language description of the task (used for
                          future semantic search — currently keyword-only).
            category:     Restrict to a specific capability category.
            offline_ok:   If False, only return online-capable records.
            privacy_tier: If provided, only return capabilities at this tier
                          or less sensitive (P0 < P1 < P2 < P3).
            usable_only:  Only return capabilities with is_usable=True.

        Returns:
            Ranked list (highest score first).
        """
        online_filter: bool | None = None
        if not offline_ok:
            online_filter = True   # require online

        candidates = self._store.query(
            category=category,
            online_required=online_filter,
            enabled=True,
            usable_only=usable_only,
        )

        # Privacy tier filter
        if privacy_tier is not None:
            _tier_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
            max_sensitivity = _tier_order.get(privacy_tier, 3)
            candidates = [
                c for c in candidates
                if _tier_order.get(c.privacy_tier, 3) >= max_sensitivity
            ]

        # Keyword match boost (simple until vector search is wired in L4)
        goal_lower = goal_text.lower()
        scored = []
        for cap in candidates:
            base_score = cap.ranking_score()
            # Boost for keyword match in name or description
            text = f"{cap.name} {cap.description}".lower()
            keyword_boost = 0.05 if any(w in text for w in goal_lower.split() if len(w) > 3) else 0.0
            scored.append((cap, base_score + keyword_boost))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [cap for cap, _ in scored]

    def to_summary(self) -> dict[str, Any]:
        """Compact summary for prompt injection / logging."""
        all_caps = self._store.all()
        by_category: dict[str, list[str]] = {}
        for cap in all_caps:
            if cap.is_usable:
                cat = cap.category.value
                by_category.setdefault(cat, []).append(cap.capability_id)
        return {
            "total": self._store.count(),
            "usable": sum(1 for c in all_caps if c.is_usable),
            "by_category": {k: len(v) for k, v in by_category.items()},
            "last_discovered_ago_s": int(time.monotonic() - self._last_discovered),
        }

    # ------------------------------------------------------------------ #
    # Health & Metrics updates
    # ------------------------------------------------------------------ #

    def update_health(self, capability_id: str, health: CapabilityHealth) -> bool:
        """Update the health record of a capability after a probe or invocation."""
        return self._store.update_health(capability_id, health)

    def update_metrics(self, capability_id: str, metrics: CapabilityMetrics) -> bool:
        """Update the metrics record of a capability after an invocation."""
        return self._store.update_metrics(capability_id, metrics)

    def update_trust(self, capability_id: str, trust_state: TrustState) -> bool:
        """Update the trust state of a capability."""
        return self._store.update_trust(capability_id, trust_state)

    def set_enabled(self, capability_id: str, enabled: bool) -> bool:
        """Enable or disable a capability."""
        return self._store.set_enabled(capability_id, enabled)

    @property
    def is_stale(self) -> bool:
        """True if discovery hasn't run recently."""
        return (time.monotonic() - self._last_discovered) > self._refresh_interval
