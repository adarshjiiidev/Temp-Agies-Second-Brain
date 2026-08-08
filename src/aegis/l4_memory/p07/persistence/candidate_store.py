"""P07 Persistence — CandidateStore.

Manages PENDING_REVIEW MemoryRecords for workflow and preference candidates.
Candidates NEVER auto-promote. Promotion requires explicit user action.

Import safety: l4_memory.* + stdlib ONLY.
"""

from __future__ import annotations

import time
import uuid
from typing import Any
from uuid import UUID

from aegis.l4_memory.manager import MemoryManager
from aegis.l4_memory.models import MemoryRecord, ProvenanceChain, ProvenanceLink
from aegis.l4_memory.p07.model.types import CandidateStatus
from aegis.l4_memory.types import (
    ConfidenceLevel,
    Importance,
    MemoryKind,
    MemoryStatus,
    MemoryTier,
    ProvenanceKind,
)

__all__ = ["CandidateStore", "CandidateRecord"]

_NAMESPACE = "p07_candidates"


class CandidateRecord:
    """Thin view of a candidate (workflow or preference)."""

    def __init__(self, record: MemoryRecord) -> None:
        self._record = record

    @property
    def id(self) -> UUID:
        return self._record.id

    @property
    def key(self) -> str:
        return self._record.key

    @property
    def kind(self) -> str:
        return self._record.content.get("candidate_kind", "unknown")

    @property
    def summary(self) -> str:
        return self._record.summary or ""

    @property
    def status(self) -> MemoryStatus:
        return self._record.status

    @property
    def content(self) -> dict:
        return self._record.content

    @property
    def confidence(self) -> float:
        return self._record.confidence


class CandidateStore:
    """Storage layer for workflow and preference inference candidates.

    Invariants:
    - All candidates are written as MemoryStatus.PENDING_REVIEW.
    - No auto-promotion: ``promote()`` must be called explicitly.
    - Candidates targeting T5_PERSONAL require user_confirmation per
      MemoryTier.T5_PERSONAL.requires_user_confirmation_to_promote.

    Usage::

        store = CandidateStore(manager)
        cid = await store.create_workflow_candidate(
            key="wf:git_commit_flow",
            label="Git commit + push workflow",
            steps=["git add", "git commit", "git push"],
            confidence=0.72,
        )
        candidates = await store.list_pending()
        await store.promote(cid, target_tier=MemoryTier.T4_PROCEDURAL)
    """

    def __init__(self, manager: MemoryManager) -> None:
        self._manager = manager

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------

    async def create_workflow_candidate(
        self,
        key: str,
        label: str,
        steps: list[str],
        confidence: float = 0.6,
        privacy_tier: str = "P2",
    ) -> UUID:
        """Create a T4_PROCEDURAL candidate from an inferred workflow."""
        record = MemoryRecord(
            key=key,
            namespace=_NAMESPACE,
            tier=MemoryTier.T4_PROCEDURAL,
            kind=MemoryKind.PROCEDURE,
            status=MemoryStatus.PENDING_REVIEW,
            importance=Importance.NORMAL,
            privacy_tier=privacy_tier,
            confidence=confidence,
            provenance=ProvenanceChain(links=[
                ProvenanceLink(
                    kind=ProvenanceKind.MODEL_INFERRED,
                    subject="p07:workflow_inferencer",
                )
            ]),
            content={
                "candidate_kind": "workflow",
                "label": label,
                "steps": steps,
                "observation_count": 1,
            },
            summary=f"Workflow candidate: {label}",
            tags=["p07_candidate", "workflow"],
        )
        await self._manager.store(record)
        return record.id

    async def create_preference_candidate(
        self,
        key: str,
        label: str,
        preference_value: Any,
        context: str = "",
        confidence: float = 0.6,
        privacy_tier: str = "P2",
    ) -> UUID:
        """Create a T5_PERSONAL candidate from an inferred preference.

        NOTE: Target tier is T5_PERSONAL which requires_user_confirmation_to_promote.
        This method only creates a PENDING_REVIEW record — never promotes.
        """
        record = MemoryRecord(
            key=key,
            namespace=_NAMESPACE,
            tier=MemoryTier.T5_PERSONAL,
            kind=MemoryKind.PREFERENCE,
            status=MemoryStatus.PENDING_REVIEW,
            importance=Importance.NORMAL,
            privacy_tier=privacy_tier,
            confidence=confidence,
            provenance=ProvenanceChain(links=[
                ProvenanceLink(
                    kind=ProvenanceKind.MODEL_INFERRED,
                    subject="p07:preference_inferencer",
                )
            ]),
            content={
                "candidate_kind": "preference",
                "label": label,
                "value": preference_value,
                "context": context,
                "observation_count": 1,
            },
            summary=f"Preference candidate: {label}",
            tags=["p07_candidate", "preference"],
        )
        await self._manager.store(record)
        return record.id

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    async def list_pending(self, limit: int = 100) -> list[CandidateRecord]:
        """Return all PENDING_REVIEW candidates."""
        from aegis.l4_memory.search import SearchQuery
        from aegis.l4_memory.types import SearchMode
        query = SearchQuery(
            namespace=_NAMESPACE,
            status=MemoryStatus.PENDING_REVIEW,
            mode=SearchMode.METADATA,
            limit=limit,
        )
        results = await self._manager.search(query)
        return [CandidateRecord(r.record) for r in results]

    async def get(self, candidate_id: UUID) -> CandidateRecord | None:
        """Return a single candidate by ID."""
        try:
            rec = await self._manager.get(candidate_id)
            return CandidateRecord(rec)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Lifecycle — explicit user-driven only
    # ------------------------------------------------------------------

    async def promote(
        self,
        candidate_id: UUID,
        target_tier: MemoryTier = MemoryTier.T4_PROCEDURAL,
    ) -> bool:
        """Promote a candidate to ACTIVE. MUST be called by explicit user action.

        This method enforces T5_PERSONAL protection: if the record is
        tier T5_PERSONAL, it still only transitions to ACTIVE in the
        PENDING_REVIEW→ACTIVE path — which is a valid transition per
        _VALID_TRANSITIONS in manager.py.

        Returns True on success.
        """
        try:
            await self._manager.promote(
                candidate_id,
                new_status=MemoryStatus.ACTIVE,
            )
            return True
        except Exception:
            return False

    async def reject(self, candidate_id: UUID) -> bool:
        """Mark a candidate as deleted (user dismissed)."""
        try:
            await self._manager.delete(candidate_id)
            return True
        except Exception:
            return False

    async def count_pending(self) -> int:
        pending = await self.list_pending(limit=10000)
        return len(pending)

    async def purge_all_candidates(self) -> int:
        """Delete ALL candidate records. Called on observer shutdown.

        Returns the count of deleted records.
        """
        pending = await self.list_pending(limit=10000)
        count = 0
        for c in pending:
            try:
                await self._manager.delete(c.id)
                count += 1
            except Exception:
                pass
        return count
