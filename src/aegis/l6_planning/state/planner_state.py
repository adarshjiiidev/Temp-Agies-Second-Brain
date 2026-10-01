"""L6 Planning Engine — Planner State.

Tracks lifecycle state of active plans in a planning session.
Import safety: stdlib + pydantic + l6_planning.types only.
"""

from __future__ import annotations

import time

from pydantic import BaseModel, Field

from aegis.l6_planning.types import PlanState

__all__ = ["PlannerState"]


class PlannerState(BaseModel):
    """Runtime state of a single plan within a session."""

    plan_id: str
    state: PlanState = PlanState.DRAFTING
    current_step_id: str | None = None
    completed_step_ids: list[str] = Field(default_factory=list)
    failed_step_ids: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    version: int = 1

    def transition(self, new_state: PlanState) -> "PlannerState":
        """Return a new PlannerState with an updated state and timestamp."""
        return self.model_copy(update={
            "state": new_state,
            "updated_at": time.time(),
            "version": self.version + 1,
        })

    @property
    def is_terminal(self) -> bool:
        return self.state in (PlanState.COMPLETED, PlanState.CANCELLED, PlanState.FAILED)

    @property
    def is_active(self) -> bool:
        return self.state in (PlanState.DRAFTING, PlanState.REVIEWING, PlanState.READY, PlanState.EXECUTING)

    def __repr__(self) -> str:
        return f"PlannerState(plan={self.plan_id!r}, state={self.state.value}, v={self.version})"
