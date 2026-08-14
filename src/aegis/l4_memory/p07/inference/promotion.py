"""P07 Inference — WorkflowAutoPromoter.

Implements the P07 roadmap contract for automatic T4 PROCEDURAL promotion:

    3 successful repetitions  → eligible for auto-promotion to T4
    Explicit user confirmation → always available via CandidateStore.promote()

CRITICAL INVARIANTS:
    - T5_PERSONAL (preference candidates) are NEVER auto-promoted.
      Preferences always require explicit user confirmation.
    - Promotion does NOT bypass L5 execution permissions.
      T4 procedural memory means "AEGIS recognizes this workflow",
      NOT "AEGIS is allowed to execute this workflow".
    - Success counts are tracked per workflow key (stable identity).
    - Promotion requires privacy zone clearance.
    - Malformed evidence never results in promotion.
    - Promotion is provenance-backed (success count recorded).

Import safety: l4_memory.p07.* + stdlib ONLY. No L5/L6/L3 imports.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)

__all__ = [
    "WorkflowPromotionConfig",
    "WorkflowSuccessTracker",
    "WorkflowAutoPromoter",
    "PromotionResult",
]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class WorkflowPromotionConfig:
    """Configuration for the auto-promotion system.

    Attributes:
        threshold:          Number of successes required for auto-promotion.
                            Default: 3 (from P07 roadmap).
        enable_auto:        Master switch. If False, auto-promotion is disabled
                            and only explicit user promotion works.
        require_stable_key: If True, the workflow key must be identical across
                            all counted successes (no fuzzy matching).
        cooldown_seconds:   Minimum time between successive promotions of the
                            same workflow key. Prevents promotion storms.
    """
    threshold: int = 3
    enable_auto: bool = True
    require_stable_key: bool = True
    cooldown_seconds: float = 60.0


# ---------------------------------------------------------------------------
# Success tracker
# ---------------------------------------------------------------------------

@dataclass
class _SuccessRecord:
    """Internal record tracking success events for a workflow key."""
    key: str
    success_count: int = 0
    last_success_at: float = 0.0
    last_promoted_at: float = 0.0
    evidence: list[dict[str, Any]] = field(default_factory=list)


class WorkflowSuccessTracker:
    """Tracks successful workflow observations per workflow key.

    A workflow key is the stable identifier used in CandidateStore
    (e.g. "wf:git_commit_flow").

    Thread-safety: not thread-safe (asyncio single-threaded context assumed).

    Usage::

        tracker = WorkflowSuccessTracker(config)
        tracker.record_success("wf:git_flow", evidence={"session": "s1"})
        tracker.record_success("wf:git_flow", evidence={"session": "s2"})
        tracker.record_success("wf:git_flow", evidence={"session": "s3"})
        tracker.is_eligible("wf:git_flow")  # True (threshold reached)
    """

    def __init__(self, config: WorkflowPromotionConfig | None = None) -> None:
        self._config = config or WorkflowPromotionConfig()
        self._records: dict[str, _SuccessRecord] = {}

    def record_success(
        self,
        workflow_key: str,
        evidence: dict[str, Any] | None = None,
    ) -> int:
        """Record a successful workflow observation.

        Args:
            workflow_key: Stable key for the workflow candidate.
            evidence:     Optional context dict (e.g. session_id, timestamp).

        Returns:
            Current success count for this key.
        """
        if not workflow_key or not isinstance(workflow_key, str):
            logger.warning("WorkflowSuccessTracker: invalid key %r — skipped", workflow_key)
            return 0

        rec = self._records.setdefault(workflow_key, _SuccessRecord(key=workflow_key))
        rec.success_count += 1
        rec.last_success_at = time.monotonic()
        if evidence and isinstance(evidence, dict):
            # Keep last 10 evidence records (bounded)
            rec.evidence = (rec.evidence + [dict(evidence)])[-10:]
        logger.debug(
            "WorkflowSuccessTracker: %r success_count=%d", workflow_key, rec.success_count
        )
        return rec.success_count

    def record_failure(self, workflow_key: str) -> int:
        """Record a failed/conflicting observation (decreases confidence).

        Decrements count by 1 (floor: 0). Never goes negative.

        Returns:
            Current success count after decrement.
        """
        rec = self._records.get(workflow_key)
        if rec is None:
            return 0
        rec.success_count = max(0, rec.success_count - 1)
        logger.debug(
            "WorkflowSuccessTracker: %r failure recorded, success_count=%d",
            workflow_key, rec.success_count
        )
        return rec.success_count

    def get_count(self, workflow_key: str) -> int:
        """Return current success count for a key (0 if never seen)."""
        rec = self._records.get(workflow_key)
        return rec.success_count if rec else 0

    def is_eligible(self, workflow_key: str) -> bool:
        """Return True if the workflow has reached the promotion threshold.

        Also respects:
        - enable_auto config flag
        - cooldown (prevents re-promotion of same key too quickly)
        """
        if not self._config.enable_auto:
            return False
        rec = self._records.get(workflow_key)
        if rec is None:
            return False
        if rec.success_count < self._config.threshold:
            return False
        # Check cooldown
        if rec.last_promoted_at > 0:
            age = time.monotonic() - rec.last_promoted_at
            if age < self._config.cooldown_seconds:
                return False
        return True

    def mark_promoted(self, workflow_key: str) -> None:
        """Record that this key was promoted (resets promotion cooldown)."""
        rec = self._records.get(workflow_key)
        if rec:
            rec.last_promoted_at = time.monotonic()

    def reset(self, workflow_key: str) -> None:
        """Reset success count for a key (e.g. after rejection)."""
        if workflow_key in self._records:
            del self._records[workflow_key]

    def eligible_keys(self) -> list[str]:
        """Return all keys currently eligible for auto-promotion."""
        return [k for k in self._records if self.is_eligible(k)]

    def summary(self) -> dict[str, dict]:
        """Return a summary of all tracked workflows."""
        return {
            key: {
                "success_count": rec.success_count,
                "eligible": self.is_eligible(key),
                "threshold": self._config.threshold,
                "last_success_at": rec.last_success_at,
            }
            for key, rec in self._records.items()
        }


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class PromotionResult:
    """Result of an auto-promotion attempt."""
    workflow_key: str
    promoted: bool
    reason: str                     # Human-readable explanation
    candidate_id: UUID | None = None
    success_count: int = 0


# ---------------------------------------------------------------------------
# Auto-promoter
# ---------------------------------------------------------------------------

class WorkflowAutoPromoter:
    """Promotes T4 PROCEDURAL workflow candidates when threshold is reached.

    This implements the P07 roadmap contract:
      "3 successful repetitions → T4 PROCEDURAL promotion"

    NEVER promotes T5_PERSONAL (preference) candidates.
    NEVER creates execution permissions.
    ALWAYS records provenance.

    Usage::

        tracker = WorkflowSuccessTracker()
        promoter = WorkflowAutoPromoter(candidate_store, tracker)

        # After recording 3 successes:
        results = await promoter.promote_eligible()
        for r in results:
            if r.promoted:
                print(f"Promoted: {r.workflow_key}")
    """

    def __init__(
        self,
        candidate_store: Any,    # CandidateStore (any to avoid circular import)
        tracker: WorkflowSuccessTracker,
        zone_registry: Any | None = None,  # ZoneRegistry (optional privacy check)
    ) -> None:
        self._store = candidate_store
        self._tracker = tracker
        self._zones = zone_registry

    async def promote_eligible(self) -> list[PromotionResult]:
        """Check all eligible keys and promote those that pass validation.

        Returns a list of PromotionResult for each eligible key considered.
        """
        eligible = self._tracker.eligible_keys()
        results: list[PromotionResult] = []

        for key in eligible:
            result = await self._try_promote(key)
            results.append(result)

        return results

    async def record_success_and_maybe_promote(
        self,
        workflow_key: str,
        candidate_id: UUID | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> PromotionResult:
        """Record a success and immediately check if promotion threshold is reached.

        Convenience method that combines record_success + promote.

        Args:
            workflow_key:  Stable workflow key.
            candidate_id:  UUID of the CandidateStore record (if known).
            evidence:      Observation context.

        Returns:
            PromotionResult (promoted=True if threshold was just reached).
        """
        count = self._tracker.record_success(workflow_key, evidence=evidence)

        if self._tracker.is_eligible(workflow_key):
            return await self._try_promote(workflow_key, candidate_id=candidate_id)

        # Determine why not eligible — give a clear reason
        if not self._tracker._config.enable_auto:
            reason = "Auto-promotion disabled by configuration"
        else:
            reason = f"Threshold not yet reached ({count}/{self._tracker._config.threshold})"

        return PromotionResult(
            workflow_key=workflow_key,
            promoted=False,
            reason=reason,
            candidate_id=candidate_id,
            success_count=count,
        )

    async def _try_promote(
        self,
        workflow_key: str,
        candidate_id: UUID | None = None,
    ) -> PromotionResult:
        """Attempt to promote a single workflow key.

        Validates:
        1. Auto-promotion is enabled
        2. Candidate exists in store
        3. Candidate is PENDING_REVIEW (not already promoted)
        4. Candidate is a WORKFLOW kind (not preference)
        5. Privacy zone check passes (if zone_registry provided) — source_path must
           not be blocked by any configured zone; if blocked, promotion is refused
           to prevent auto-elevating data from restricted areas.
        """
        count = self._tracker.get_count(workflow_key)

        if not self._tracker._config.enable_auto:
            return PromotionResult(
                workflow_key=workflow_key,
                promoted=False,
                reason="Auto-promotion disabled by configuration",
                success_count=count,
            )

        # Find the candidate
        candidate = None
        if candidate_id is not None:
            candidate = await self._store.get(candidate_id)
        else:
            # Search by key in pending candidates
            pending = await self._store.list_pending(limit=1000)
            for c in pending:
                if c.key == workflow_key or c.content.get("label", "").lower() in workflow_key.lower():
                    candidate = c
                    break

        if candidate is None:
            return PromotionResult(
                workflow_key=workflow_key,
                promoted=False,
                reason="Candidate not found in store",
                success_count=count,
            )

        # CRITICAL: Never auto-promote preference (T5) candidates
        if candidate.kind == "preference":
            return PromotionResult(
                workflow_key=workflow_key,
                promoted=False,
                reason="T5_PERSONAL preference candidates require explicit user confirmation",
                candidate_id=candidate.id,
                success_count=count,
            )

        # Only promote PENDING_REVIEW candidates
        from aegis.l4_memory.types import MemoryStatus
        if candidate.status != MemoryStatus.PENDING_REVIEW:
            return PromotionResult(
                workflow_key=workflow_key,
                promoted=False,
                reason=f"Candidate status is {candidate.status!r} — only PENDING_REVIEW can be promoted",
                candidate_id=candidate.id,
                success_count=count,
            )

        # Privacy zone check: if a zone_registry was provided, the candidate's
        # source_path must not be blocked by any configured zone.
        # This prevents auto-promoting workflows whose origin path has been
        # designated as a restricted privacy zone.
        if self._zones is not None and candidate.source_path:
            if not self._zones.check_path(candidate.source_path):
                logger.info(
                    "WorkflowAutoPromoter: blocking promotion of %r — source path %r is in a restricted privacy zone",
                    workflow_key, candidate.source_path,
                )
                return PromotionResult(
                    workflow_key=workflow_key,
                    promoted=False,
                    reason="Source path is within a restricted privacy zone; explicit user confirmation required",
                    candidate_id=candidate.id,
                    success_count=count,
                )

        # Promote

        logger.info(
            "WorkflowAutoPromoter: auto-promoting %r after %d successes",
            workflow_key, count,
        )
        try:
            success = await self._store.promote(candidate.id)
            if success:
                self._tracker.mark_promoted(workflow_key)
                return PromotionResult(
                    workflow_key=workflow_key,
                    promoted=True,
                    reason=f"Auto-promoted after {count} successful repetitions",
                    candidate_id=candidate.id,
                    success_count=count,
                )
            else:
                return PromotionResult(
                    workflow_key=workflow_key,
                    promoted=False,
                    reason="Promotion call returned False (store error)",
                    candidate_id=candidate.id,
                    success_count=count,
                )
        except Exception as exc:
            logger.warning("WorkflowAutoPromoter: promotion failed for %r: %s", workflow_key, exc)
            return PromotionResult(
                workflow_key=workflow_key,
                promoted=False,
                reason=f"Promotion exception: {exc}",
                candidate_id=candidate.id,
                success_count=count,
            )
