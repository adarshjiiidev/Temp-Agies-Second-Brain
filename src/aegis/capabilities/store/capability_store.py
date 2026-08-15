"""Capabilities store — CapabilityStore.

Thread-safe in-memory store for CapabilityRecord objects.
Indexed by capability_id, category, and provider_id for fast queries.

Import safety: stdlib + aegis.capabilities.model only.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable

from aegis.capabilities.model.capability import (
    CapabilityCategory,
    CapabilityRecord,
    TrustState,
)
from aegis.capabilities.model.health import CapabilityHealth
from aegis.capabilities.model.metrics import CapabilityMetrics

logger = logging.getLogger(__name__)

__all__ = ["CapabilityStore"]


class CapabilityStore:
    """Thread-safe in-memory registry of CapabilityRecord objects.

    All mutations and reads are protected by an RLock so the store is safe
    for concurrent asyncio tasks and background discovery threads.

    Usage::

        store = CapabilityStore()
        store.register(record)
        results = store.query(category=CapabilityCategory.GIT)
        store.update_health(record.capability_id, new_health)
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # Primary index: capability_id → record
        self._records: dict[str, CapabilityRecord] = {}
        # Secondary index: category → set of capability_ids
        self._by_category: dict[CapabilityCategory, set[str]] = {}
        # Secondary index: provider_id → set of capability_ids
        self._by_provider: dict[str, set[str]] = {}

    # ------------------------------------------------------------------ #
    # Mutations
    # ------------------------------------------------------------------ #

    def register(self, record: CapabilityRecord) -> None:
        """Add or replace a capability record.

        If a record with the same capability_id already exists, it is
        replaced entirely (use update_health / update_metrics for partial
        updates to avoid overwriting live health data).
        """
        with self._lock:
            cap_id = record.capability_id
            # Remove from secondary indices if replacing
            if cap_id in self._records:
                self._remove_from_indices(self._records[cap_id])
            self._records[cap_id] = record
            self._add_to_indices(record)
            logger.debug(
                "CapabilityStore: registered %r (category=%s trust=%s)",
                cap_id, record.category.value, record.trust_state.value,
            )

    def unregister(self, capability_id: str) -> bool:
        """Remove a capability. Returns True if it existed."""
        with self._lock:
            record = self._records.pop(capability_id, None)
            if record is None:
                return False
            self._remove_from_indices(record)
            logger.debug("CapabilityStore: unregistered %r", capability_id)
            return True

    def update_health(self, capability_id: str, health: CapabilityHealth) -> bool:
        """Atomically update the health field of an existing record.
        Returns True if the record existed.
        """
        with self._lock:
            record = self._records.get(capability_id)
            if record is None:
                return False
            self._records[capability_id] = record.model_copy(update={"health": health})
            return True

    def update_metrics(self, capability_id: str, metrics: CapabilityMetrics) -> bool:
        """Atomically update the metrics field of an existing record.
        Returns True if the record existed.
        """
        with self._lock:
            record = self._records.get(capability_id)
            if record is None:
                return False
            self._records[capability_id] = record.model_copy(update={"metrics": metrics})
            return True

    def update_trust(self, capability_id: str, trust_state: TrustState) -> bool:
        """Atomically update the trust_state of an existing record.
        Returns True if the record existed.
        """
        with self._lock:
            record = self._records.get(capability_id)
            if record is None:
                return False
            self._records[capability_id] = record.model_copy(update={"trust_state": trust_state})
            logger.info(
                "CapabilityStore: trust updated %r → %s",
                capability_id, trust_state.value,
            )
            return True

    def set_enabled(self, capability_id: str, enabled: bool) -> bool:
        """Enable or disable a capability. Returns True if it existed."""
        with self._lock:
            record = self._records.get(capability_id)
            if record is None:
                return False
            self._records[capability_id] = record.model_copy(update={"enabled": enabled})
            return True

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def get(self, capability_id: str) -> CapabilityRecord | None:
        """Return a capability record by ID, or None."""
        with self._lock:
            return self._records.get(capability_id)

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
        """Filter and return capability records matching all given criteria.

        Args:
            category:       Filter by CapabilityCategory.
            provider_id:    Filter by provider_id exact match.
            online_required: If False, return only offline-capable records.
            trust_state:    Filter by exact TrustState.
            enabled:        Filter by enabled flag.
            usable_only:    If True, return only records where is_usable=True.
            predicate:      Optional additional filter function.

        Returns:
            Matching records (unsorted — callers sort by ranking_score if needed).
        """
        with self._lock:
            # Start with category index for efficiency
            if category is not None:
                ids = self._by_category.get(category, set())
                candidates = [self._records[i] for i in ids if i in self._records]
            elif provider_id is not None:
                ids = self._by_provider.get(provider_id, set())
                candidates = [self._records[i] for i in ids if i in self._records]
            else:
                candidates = list(self._records.values())

            result = []
            for rec in candidates:
                if provider_id is not None and rec.provider_id != provider_id:
                    continue
                if online_required is not None and online_required is False and rec.online_required:
                    continue
                if online_required is not None and online_required is True and not rec.online_required:
                    continue
                if trust_state is not None and rec.trust_state != trust_state:
                    continue
                if enabled is not None and rec.enabled != enabled:
                    continue
                if usable_only and not rec.is_usable:
                    continue
                if predicate is not None and not predicate(rec):
                    continue
                result.append(rec)
            return result

    def all(self) -> list[CapabilityRecord]:
        """Return all registered capability records (unfiltered)."""
        with self._lock:
            return list(self._records.values())

    def count(self) -> int:
        """Return total number of registered capabilities."""
        with self._lock:
            return len(self._records)

    def has(self, capability_id: str) -> bool:
        """True if a capability with this ID is registered."""
        with self._lock:
            return capability_id in self._records

    # ------------------------------------------------------------------ #
    # Internal index helpers
    # ------------------------------------------------------------------ #

    def _add_to_indices(self, record: CapabilityRecord) -> None:
        self._by_category.setdefault(record.category, set()).add(record.capability_id)
        self._by_provider.setdefault(record.provider_id, set()).add(record.capability_id)

    def _remove_from_indices(self, record: CapabilityRecord) -> None:
        self._by_category.get(record.category, set()).discard(record.capability_id)
        self._by_provider.get(record.provider_id, set()).discard(record.capability_id)
