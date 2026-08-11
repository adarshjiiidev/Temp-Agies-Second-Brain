"""P07 Inference — Workflow and Preference Candidate Inference.

Sub-modules:
    workflow_inferencer   — Detects repeated event sequences → WorkflowCandidate
    preference_inferencer — Detects frequency-based preferences → PreferenceCandidate
    promotion             — WorkflowAutoPromoter (T4 auto-promotion at 3 repetitions)

Architectural invariants:
    - Import safety: l4_memory.p07.* + stdlib ONLY. Never import from L3/L5/L6.
    - Inference is DETERMINISTIC HEURISTIC — no LLM calls here.
    - All results are CANDIDATES (status=PENDING_REVIEW); never auto-promoted
      unless WorkflowAutoPromoter explicitly promotes T4 after threshold.
    - T5_PERSONAL (preference) candidates NEVER auto-promote.
    - Source is always marked 'heuristic' so callers can distinguish from AI.
"""

from aegis.l4_memory.p07.inference.workflow_inferencer import (
    WorkflowCandidate,
    WorkflowInferencer,
)
from aegis.l4_memory.p07.inference.preference_inferencer import (
    PreferenceCandidate,
    PreferenceInferencer,
)
from aegis.l4_memory.p07.inference.promotion import (
    WorkflowPromotionConfig,
    WorkflowSuccessTracker,
    WorkflowAutoPromoter,
    PromotionResult,
)

__all__ = [
    "WorkflowCandidate",
    "WorkflowInferencer",
    "PreferenceCandidate",
    "PreferenceInferencer",
    "WorkflowPromotionConfig",
    "WorkflowSuccessTracker",
    "WorkflowAutoPromoter",
    "PromotionResult",
]
