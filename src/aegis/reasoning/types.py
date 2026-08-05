"""Reasoning subsystem — shared types.

Defines the data contracts flowing in and out of every ReasoningProvider
implementation.  All types are Pydantic models (serialisable, auditable).

Import safety: stdlib + pydantic only.  No aegis layer imports here.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

__all__ = [
    "ReasoningRequest",
    "ReasoningResponse",
    "PromptId",
]


# ---------------------------------------------------------------------------
# Well-known prompt identifiers (single source of truth)
# ---------------------------------------------------------------------------

class PromptId:
    """Constants for every prompt in the library.

    Using a class of string constants (rather than an Enum) keeps the type
    as ``str`` while still enabling IDE auto-complete and grep-ability.
    """

    # ── L6 Planning ──────────────────────────────────────────────────────
    INTENT_ANALYSIS        = "intent_analysis_v1"
    AMBIGUITY_DETECTION    = "ambiguity_detection_v1"
    REQUIREMENT_EXTRACTION = "requirement_extraction_v1"
    OBJECTIVE_GENERATION   = "objective_generation_v1"
    TASK_DECOMPOSITION     = "task_decomposition_v1"
    STRATEGY_SELECTION     = "strategy_selection_v1"
    MILESTONE_GENERATION   = "milestone_generation_v1"
    TRADEOFF_NARRATION     = "tradeoff_narration_v1"
    RISK_ASSESSMENT        = "risk_assessment_v1"
    RECOVERY_PLANNING      = "recovery_planning_v1"
    REFLECTION             = "reflection_v1"
    VERIFICATION_CRITERIA  = "verification_criteria_v1"

    # ── L4 Memory ────────────────────────────────────────────────────────
    MEMORY_IMPORTANCE      = "memory_importance_v1"
    CONTEXT_SELECTION      = "context_selection_v1"

    # ── L3 Model Selection ───────────────────────────────────────────────
    MODEL_SELECTION        = "model_selection_v1"


# ---------------------------------------------------------------------------
# Request / Response contracts
# ---------------------------------------------------------------------------

class ReasoningRequest(BaseModel):
    """Encapsulates a single AI reasoning request."""

    model_config = {"frozen": True}

    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    prompt_id: str
    variables: dict[str, Any] = Field(default_factory=dict)
    # Human-readable name of the expected output schema (for logging/tracing)
    output_schema_name: str = ""


class ReasoningResponse(BaseModel):
    """Encapsulates a validated AI reasoning response."""

    model_config = {"frozen": True}

    request_id: str
    prompt_id: str
    # The validated structured output object (already parsed by the provider)
    output: Any
    # Observability fields
    model_used: str = "unknown"
    latency_ms: float = 0.0
    tokens_used: int = 0
    from_cache: bool = False
    fallback_used: bool = False
