"""Capabilities selection — Pydantic schemas for AI-driven capability selection.

These schemas are the interface between the L6 planner and the
CapabilitySelector. The planner describes the task; the selector
returns a ranked list of capability IDs for L5 invocation.

Import safety: stdlib + pydantic only.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

__all__ = [
    "CapabilityConstraints",
    "CapabilitySelectionInput",
    "CapabilitySelectionOutput",
]


class CapabilityConstraints(BaseModel):
    """Constraints on which capabilities may be selected."""

    model_config = {"frozen": True}

    # If True, may use online-only capabilities
    online_allowed: bool = True

    # Privacy ceiling: only capabilities at this tier or less sensitive
    # P0 = most sensitive (local only), P3 = least sensitive
    max_privacy_tier: str = "P2"

    # Max latency budget (None = no limit)
    max_latency_ms: float | None = None

    # Max cost budget per invocation (None = no limit)
    max_cost_usd: float | None = None

    # Require specific category
    required_category: str | None = None

    # Excluded capability IDs (e.g. previously failed)
    excluded_ids: list[str] = Field(default_factory=list)


class CapabilitySelectionInput(BaseModel):
    """Input to the CapabilitySelector.select() method."""

    model_config = {"frozen": True}

    goal_text: str = Field(description="Natural language task goal")
    task_category: str = Field(
        default="",
        description="Optional coarse category hint (e.g. 'git', 'filesystem')",
    )
    available_capabilities: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Serialized CapabilityRecord summaries for AI context",
    )
    constraints: CapabilityConstraints = Field(default_factory=CapabilityConstraints)
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context (plan_id, user_preferences, etc.)",
    )


class CapabilitySelectionOutput(BaseModel):
    """Output from the CapabilitySelector.select() method."""

    model_config = {"frozen": True}

    selected_ids: list[str] = Field(
        description="Ordered list of selected capability IDs (preferred first)",
    )
    rationale: str = Field(
        default="",
        description="AI reasoning for the selection",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="AI confidence in the selection (0.0 = deterministic fallback)",
    )
    fallback_ids: list[str] = Field(
        default_factory=list,
        description="Alternative capability IDs if primary fails",
    )
    selection_method: str = Field(
        default="deterministic",
        description="'ai' or 'deterministic'",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal warnings about the selection",
    )
