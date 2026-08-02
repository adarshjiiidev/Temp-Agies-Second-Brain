"""L6 Planning Engine — Mission model.

A Mission is the top-level container for a user goal, housing the
parsed intent, objectives, and all plan-level metadata.

Import safety: stdlib + pydantic + l6_planning.types + l6_planning.planning.objective.
"""

from __future__ import annotations

import time
import uuid

from pydantic import BaseModel, Field

from aegis.l6_planning.intent.intent_parser import Intent
from aegis.l6_planning.intent.requirement_extractor import Requirements
from aegis.l6_planning.planning.objective import Objective
from aegis.l6_planning.types import Constraint, PlanningStrategy

__all__ = ["Mission"]


class Mission(BaseModel):
    """Top-level container for a user goal and its decomposition.

    A Mission captures everything about a planning session:
    - The raw user goal text
    - The parsed intent
    - Extracted requirements and constraints
    - The set of objectives to achieve
    - Strategy preference and deadline

    No execution artefacts ever appear in a Mission — it is pure plan.

    Attributes:
        mission_id: Unique identifier.
        title: Short human-readable mission title.
        user_goal_text: Original raw goal string from the user.
        parsed_intent: Typed Intent from IntentParser.
        requirements: Extracted requirements from RequirementExtractor.
        objectives: Ordered list of Objectives (priority ascending).
        constraints: Plan-level constraints (budget, privacy, deadline, etc.).
        strategy: Preferred planning strategy (BALANCED by default).
        deadline: Optional Unix timestamp for the mission deadline.
        version: Monotonically increasing version counter for edits.
        created_at: Unix timestamp when this mission was created.
        updated_at: Unix timestamp of last update.
        notes: Free-text notes from the planner.
    """

    mission_id: str = Field(default_factory=lambda: f"msn-{uuid.uuid4()!s:.8}")
    title: str
    user_goal_text: str
    parsed_intent: Intent
    requirements: Requirements = Field(default_factory=Requirements)
    objectives: list[Objective] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    strategy: PlanningStrategy = PlanningStrategy.BALANCED
    deadline: float | None = None       # Unix timestamp
    version: int = 1
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    notes: list[str] = Field(default_factory=list)

    @property
    def objective_count(self) -> int:
        return len(self.objectives)

    @property
    def has_deadline(self) -> bool:
        return self.deadline is not None

    @property
    def is_internet_required(self) -> bool:
        return self.requirements.internet_required

    @property
    def is_local_only(self) -> bool:
        return self.parsed_intent.requires_local_only

    def primary_objective(self) -> Objective | None:
        """Return the highest-priority objective (lowest priority number)."""
        if not self.objectives:
            return None
        return min(self.objectives, key=lambda o: o.priority)

    def objectives_by_priority(self) -> list[Objective]:
        """Return objectives sorted by priority (lowest number = highest priority)."""
        return sorted(self.objectives, key=lambda o: o.priority)

    def bump_version(self) -> "Mission":
        """Return a new Mission with version incremented and updated_at refreshed."""
        return self.model_copy(update={"version": self.version + 1, "updated_at": time.time()})

    def __repr__(self) -> str:
        return (
            f"Mission(id={self.mission_id!r}, {self.title!r}, "
            f"objectives={self.objective_count}, v={self.version})"
        )
