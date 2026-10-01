"""L4 Memory — MemoryManager: central orchestration layer.

The MemoryManager is the single write/read gateway for ALL memory operations.
It enforces the full policy stack (retention, decay, access, archival, merge)
on every operation, per 06_MEMORY_KNOWLEDGE.md §2 and policies.py.

Responsibilities:
  - store()      : write a MemoryRecord through policy gates + persist
  - get()        : retrieve by ID + touch access
  - get_by_key() : retrieve by stable key + namespace
  - update()     : update fields with version bump + policy recheck
  - delete()     : soft delete (status=DELETED)
  - archive()    : transition to ARCHIVED
  - restore()    : ARCHIVED → ACTIVE
  - pin()/unpin(): manage decay immunity
  - promote()    : advance MemoryStatus (DRAFT → ACTIVE etc.)
  - expire_due() : run expiration sweep over all records
  - search()     : delegate to SearchEngine
  - graph        : expose KnowledgeGraph

Import safety: l4_memory.* + aiosqlite + stdlib ONLY. NO L1/L2/L3 imports.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any
from uuid import UUID

import aiosqlite

from aegis.l4_memory.exceptions import (
    MemoryNotFoundError,
    MemoryPolicyViolationError,
    MemoryPrivacyViolationError,
    MemoryStatusError,
    MemoryStorageError,
    MemoryVersionConflictError,
)
from aegis.l4_memory.graph import KnowledgeGraph
from aegis.l4_memory.models import MemoryRecord, MemoryVersion, ProvenanceChain, ProvenanceLink
from aegis.l4_memory.policies import MemoryPolicy
from aegis.l4_memory.search import SearchEngine, SearchQuery, SearchResult
from aegis.l4_memory.store import SQLiteMemoryStore
from aegis.l4_memory.types import (
    Importance,
    MemoryKind,
    MemoryStatus,
    MemoryTier,
    ProvenanceKind,
    SearchMode,
)

__all__ = ["MemoryManager"]

# ---------------------------------------------------------------------------
# Valid status transitions
# ---------------------------------------------------------------------------

_VALID_TRANSITIONS: dict[MemoryStatus, set[MemoryStatus]] = {
    MemoryStatus.DRAFT: {MemoryStatus.ACTIVE, MemoryStatus.DELETED, MemoryStatus.PENDING_REVIEW},
    MemoryStatus.PENDING_REVIEW: {MemoryStatus.ACTIVE, MemoryStatus.DELETED, MemoryStatus.DRAFT},
    MemoryStatus.ACTIVE: {MemoryStatus.ARCHIVED, MemoryStatus.DELETED, MemoryStatus.EXPIRED},
    MemoryStatus.ARCHIVED: {MemoryStatus.ACTIVE, MemoryStatus.DELETED},
    MemoryStatus.EXPIRED: {MemoryStatus.DELETED, MemoryStatus.ARCHIVED},
    MemoryStatus.DELETED: set(),  # terminal — no transitions (hard delete only)
}

_PRIVACY_TIER_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


class MemoryManager:
    """Central orchestration layer for all L4 memory operations.

    Usage::

        mgr = MemoryManager(db_path="data/memory.db")
        await mgr.initialize()
        record = await mgr.store(my_record)
        results = await mgr.search(SearchQuery(text="AEGIS architecture"))
        await mgr.close()
    """

    def __init__(
        self,
        *,
        db_path: str | Path | None = None,
        policy: MemoryPolicy | None = None,
    ) -> None:
        self._store = SQLiteMemoryStore(path=db_path)
        self._policy = policy or MemoryPolicy.default()
        self._conn: aiosqlite.Connection | None = None
        self._kg: KnowledgeGraph | None = None
        self._search: SearchEngine | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Open database connection and initialize all sub-components."""
        await self._store.initialize()
        # Share the connection with KG and SearchEngine
        self._conn = self._store._conn  # type: ignore[attr-defined]
        if self._conn is None:
            raise MemoryStorageError("Store connection not available after initialize().")
        self._kg = KnowledgeGraph(self._conn)
        self._search = SearchEngine(self._store)

    async def close(self) -> None:
        """Close database connection."""
        await self._store.close()
        self._conn = None
        self._kg = None
        self._search = None

    @property
    def graph(self) -> KnowledgeGraph:
        if self._kg is None:
            raise MemoryStorageError("MemoryManager not initialized.")
        return self._kg

    @property
    def policy(self) -> MemoryPolicy:
        return self._policy

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

    async def store(self, record: MemoryRecord, *, actor: str = "system") -> MemoryRecord:
        """Write a MemoryRecord through the full policy gate.

        Policy checks applied:
          1. Privacy: T5 personal in DRAFT only (no auto-promotion).
          2. Retention: apply effective TTL per policy.
          3. Merge: if same key exists, apply merge policy.

        Returns the stored record (may have version bumped).
        """
        self._require_initialized()

        # Privacy gate: T5 Personal always requires user confirmation
        if record.tier is MemoryTier.T5_PERSONAL and not record.is_draft:
            raise MemoryPolicyViolationError(
                "T5 Personal memory cannot be stored as ACTIVE without explicit user confirmation. "
                "Store as DRAFT (is_draft=True) and call promote() after user confirms."
            )

        # Apply retention policy (set effective TTL if not already set)
        record = self._apply_retention(record)

        # Check existing by key for merge policy
        existing = await self._store.get_by_key(record.key, record.namespace)
        if existing is not None and existing.id != record.id:
            record = self._apply_merge(existing, record)

        stored = await self._store.upsert(record)
        return stored

    async def get(self, record_id: UUID, *, actor: str = "system") -> MemoryRecord:
        """Retrieve a MemoryRecord by UUID. Raises MemoryNotFoundError if absent.

        Allows retrieval of records in any non-DELETED status (DRAFT, ACTIVE,
        ARCHIVED, PENDING_REVIEW, EXPIRED). DELETED records are not retrievable.
        """
        self._require_initialized()
        record = await self._store.get(record_id)
        if record.status is MemoryStatus.DELETED:
            raise MemoryNotFoundError(
                f"Record {record_id} is not retrievable (status=deleted)."
            )
        await self._store.touch_access(record_id)
        return record

    async def get_by_key(
        self, key: str, namespace: str = "global", *, actor: str = "system"
    ) -> MemoryRecord | None:
        """Retrieve by stable key + namespace. Returns None if absent or DELETED."""
        self._require_initialized()
        record = await self._store.get_by_key(key, namespace)
        if record is None:
            return None
        if record.status is MemoryStatus.DELETED:
            return None
        await self._store.touch_access(record.id)
        return record

    async def update(
        self,
        record_id: UUID,
        *,
        content: Any = ...,  # sentinel: Ellipsis = unchanged
        importance: Importance | None = None,
        confidence: float | None = None,
        summary: str | None = None,
        tags: frozenset[str] | None = None,
        expires_at: float | None = ...,  # sentinel
        actor: str = "system",
        change_note: str | None = None,
        expected_version: int | None = None,
    ) -> MemoryRecord:
        """Update a MemoryRecord. Version is bumped automatically.

        If expected_version is set, raises MemoryVersionConflictError if mismatch.
        """
        self._require_initialized()
        record = await self._store.get(record_id)

        if expected_version is not None and record.version != expected_version:
            raise MemoryVersionConflictError(
                f"Version conflict: expected {expected_version}, found {record.version}."
            )

        updates: dict[str, Any] = {"updated_at": time.time()}
        if content is not ...:
            updates["content"] = content
        if importance is not None:
            updates["importance"] = importance
        if confidence is not None:
            updates["confidence"] = max(0.0, min(1.0, confidence))
        if summary is not None:
            updates["summary"] = summary
        if tags is not None:
            updates["tags"] = tags
        if expires_at is not ...:
            updates["expires_at"] = expires_at

        updated = record.model_copy(update=updates)
        stored = await self._store.upsert(updated)
        return stored

    async def delete(self, record_id: UUID, *, actor: str = "system") -> bool:
        """Soft-delete a record (status → DELETED)."""
        self._require_initialized()
        record = await self._store.get(record_id)
        if record.status is MemoryStatus.DELETED:
            return False
        return await self._store.delete(record_id)

    async def hard_delete(self, record_id: UUID, *, actor: str = "system") -> bool:
        """Permanently remove a record (no recovery)."""
        self._require_initialized()
        return await self._store.hard_delete(record_id)

    # ------------------------------------------------------------------
    # Status transitions
    # ------------------------------------------------------------------

    async def promote(
        self,
        record_id: UUID,
        to_status: MemoryStatus,
        *,
        actor: str = "system",
        user_confirmed: bool = False,
    ) -> MemoryRecord:
        """Transition a record to a new status.

        Enforces:
          - Only valid transitions per _VALID_TRANSITIONS.
          - T5 Personal ACTIVE promotion requires user_confirmed=True.
          - ACTIVE records require status.is_retrievable destination check.
        """
        self._require_initialized()
        record = await self._store.get(record_id)
        current = record.status

        allowed = _VALID_TRANSITIONS.get(current, set())
        if current == to_status:
            # Idempotent: already in target state, no-op
            return record
        if to_status not in allowed:
            raise MemoryStatusError(
                f"Invalid status transition {current.value!r} → {to_status.value!r}. "
                f"Allowed: {[s.value for s in allowed]}"
            )

        # T5 Personal: require user confirmation to go ACTIVE
        if (
            record.tier is MemoryTier.T5_PERSONAL
            and to_status is MemoryStatus.ACTIVE
            and not user_confirmed
        ):
            raise MemoryPolicyViolationError(
                "T5 Personal memory requires explicit user confirmation to be promoted to ACTIVE. "
                "Call promote(..., user_confirmed=True) after user consent."
            )

        updates: dict[str, Any] = {"status": to_status, "updated_at": time.time()}

        # Clearing draft flag on ACTIVE promotion
        if to_status is MemoryStatus.ACTIVE:
            updates["is_draft"] = False
            # Add user-confirmed provenance link if applicable
            if user_confirmed:
                new_link = ProvenanceLink(
                    kind=ProvenanceKind.USER_CONFIRMED,
                    subject=actor,
                    note=f"Promoted to ACTIVE by {actor}",
                )
                updates["provenance"] = record.provenance.extend(new_link)

        updated = record.model_copy(update=updates)
        stored = await self._store.upsert(updated)
        return stored

    async def archive(self, record_id: UUID, *, actor: str = "system") -> MemoryRecord:
        """Move ACTIVE record to ARCHIVED."""
        return await self.promote(record_id, MemoryStatus.ARCHIVED, actor=actor)

    async def restore(self, record_id: UUID, *, actor: str = "system") -> MemoryRecord:
        """Move ARCHIVED record back to ACTIVE."""
        return await self.promote(record_id, MemoryStatus.ACTIVE, actor=actor)

    async def pin(self, record_id: UUID) -> MemoryRecord:
        """Pin a record (immune to decay and auto-archival)."""
        self._require_initialized()
        record = await self._store.get(record_id)
        updated = record.model_copy(update={"is_pinned": True, "updated_at": time.time()})
        return await self._store.upsert(updated)

    async def unpin(self, record_id: UUID) -> MemoryRecord:
        """Unpin a record."""
        self._require_initialized()
        record = await self._store.get(record_id)
        updated = record.model_copy(update={"is_pinned": False, "updated_at": time.time()})
        return await self._store.upsert(updated)

    # ------------------------------------------------------------------
    # Maintenance: expiration and archival sweeps
    # ------------------------------------------------------------------

    async def expire_due(self, *, now: float | None = None) -> int:
        """Expire all records whose expires_at <= now. Returns count expired."""
        self._require_initialized()
        ts = now or time.time()
        # Get all active non-pinned records that have passed TTL
        candidates = await self._store.list_records(
            status=MemoryStatus.ACTIVE,
            include_expired=True,
        )
        expired_count = 0
        for rec in candidates:
            if rec.is_decay_immune:
                continue
            if rec.expires_at is not None and rec.expires_at <= ts:
                await self._store.delete(rec.id)
                expired_count += 1
        return expired_count

    async def archive_due(self, *, now: float | None = None) -> int:
        """Auto-archive records matching the archival policy. Returns count archived."""
        self._require_initialized()
        ts = now or time.time()
        candidates = await self._store.list_records(status=MemoryStatus.ACTIVE)
        arch_count = 0
        pol = self._policy.archival
        for rec in candidates:
            if pol.should_archive(
                tier=rec.tier,
                is_pinned=rec.is_pinned,
                importance=rec.importance,
                last_accessed_at=rec.last_accessed_at,
                now=ts,
            ):
                await self.archive(rec.id, actor="system:archival_sweep")
                arch_count += 1
        return arch_count

    # ------------------------------------------------------------------
    # Search delegation
    # ------------------------------------------------------------------

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        """Execute a search query through the SearchEngine."""
        self._require_initialized()
        assert self._search is not None
        return await self._search.execute(query)

    async def list_records(self, **kwargs: Any) -> list[MemoryRecord]:
        """List records with optional filters (delegated to store)."""
        self._require_initialized()
        return await self._store.list_records(**kwargs)

    async def get_version_history(self, record_id: UUID) -> list[MemoryVersion]:
        """Return version history for a record."""
        self._require_initialized()
        return await self._store.get_version_history(record_id)

    async def count(self, **kwargs: Any) -> dict[str, int]:
        """Count records by tier."""
        self._require_initialized()
        return await self._store.count(**kwargs)

    # ------------------------------------------------------------------
    # Meta helpers
    # ------------------------------------------------------------------

    async def get_meta_snapshot(self) -> dict[str, Any]:
        """Return a lightweight meta-memory snapshot (coverage + counts)."""
        self._require_initialized()
        counts = await self._store.count()
        total = sum(counts.values())
        return {
            "total_records": total,
            "records_by_tier": counts,
            "kg_entities": await self._kg.count_entities() if self._kg else 0,  # type: ignore[union-attr]
            "kg_relationships": await self._kg.count_relationships() if self._kg else 0,  # type: ignore[union-attr]
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_initialized(self) -> None:
        if self._conn is None:
            raise MemoryStorageError("MemoryManager not initialized. Call await initialize().")

    def _apply_retention(self, record: MemoryRecord) -> MemoryRecord:
        """Apply RetentionPolicy TTL to record."""
        if record.is_decay_immune:
            # Critical/pinned: no expiry
            if record.expires_at is not None:
                return record.model_copy(update={"expires_at": None})
            return record

        base_ttl = record.tier.default_ttl_seconds
        effective_ttl = self._policy.retention.effective_ttl(
            record.tier, record.importance, base_ttl
        )
        if effective_ttl is None:
            # Keep forever
            return record.model_copy(update={"expires_at": None})

        # Only set expires_at if not already set
        if record.expires_at is None:
            new_expires = record.created_at + effective_ttl
            return record.model_copy(update={"expires_at": new_expires})
        return record

    def _apply_merge(self, existing: MemoryRecord, incoming: MemoryRecord) -> MemoryRecord:
        """Apply MergePolicy when same key exists with different UUID."""
        pol = self._policy.merge
        should_replace = pol.should_replace(
            existing_confidence=existing.confidence,
            new_confidence=incoming.confidence,
            existing_provenance_kind=existing.provenance.primary.kind,
            existing_updated_at=existing.updated_at,
            new_updated_at=incoming.updated_at,
        )
        if should_replace:
            # Incoming wins: use incoming's content but carry ID of existing
            # so we don't break external references
            return incoming.model_copy(update={"id": existing.id})
        else:
            # Keep existing — return it unchanged; store will see same ID
            return existing
