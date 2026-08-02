"""L6 Planning Engine — Objective model.

An Objective is a decomposed sub-goal of a Mission with explicit
success/failure criteria, priority, and dependency tracking.

Import safety: stdlib + pydantic + l6_planning.types only.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from aegis.l6_planning.types import Constraint, EffortEstimate, RiskLevel

__all__ = ["Objective"]


class Objective(BaseModel):
    """A typed, verifiable objective derived from a Mission.

    Objectives are the primary decomposition unit between a Mission (top-level
    goal) and Tasks (individual actionable work items).

    Attributes:
        objective_id: Unique identifier.
        title: Short human-readable title.
        description: Full description of what must be accomplished.
        success_criteria: Observable conditions that prove the objective is met.
        failure_criteria: Conditions that definitively indicate failure.
        priority: 1 = highest priority; larger = lower priority.
        estimated_effort: Rough effort estimate.
        risk_level: Maximum risk level expected for tasks under this objective.
        dependencies: IDs of other Objectives that must complete first.
        constraints: Constraints scoped to this objective only.
        confidence: Planner confidence that this objective is correct (0–1).
        rationale: Why this objective was created from the parent mission.
        tags: Arbitrary metadata tags for filtering and categorisation.
    """

    objective_id: str = Field(default_factory=lambda: f"obj-{uuid.uuid4()!s:.8}")
    title: str
    description: str = ""
    success_criteria: list[str] = Field(default_factory=list)
    failure_criteria: list[str] = Field(default_factory=list)
    priority: int = Field(default=5, ge=1, le=10)
    estimated_effort: EffortEstimate = Field(default_factory=EffortEstimate.medium)
    risk_level: RiskLevel = RiskLevel.LOW
    dependencies: list[str] = Field(default_factory=list)  # other objective_id values
    constraints: list[Constraint] = Field(default_factory=list)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    rationale: str = ""
    tags: list[str] = Field(default_factory=list)

    @property
    def has_dependencies(self) -> bool:
        return len(self.dependencies) > 0

    @property
    def is_high_risk(self) -> bool:
        return self.risk_level >= RiskLevel.HIGH

    def __repr__(self) -> str:
        return f"Objective(id={self.objective_id!r}, {self.title!r}, priority={self.priority})"
