"""L6 Planning Engine — Planner Context.

Per-session planning preferences and constraints passed into PlannerService.
Import safety: stdlib + pydantic + l6_planning.types only.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from aegis.l6_planning.types import Constraint, PlanningStrategy

__all__ = ["PlannerContext"]


class PlannerContext(BaseModel):
    """Per-call planning context: constraints, preferences, and environment hints.

    Passed by the caller to PlannerService.create_plan() to customise
    planning behaviour without modifying L6 internals.
    """

    strategy: PlanningStrategy | None = None
    constraints: list[Constraint] = Field(default_factory=list)
    deadline: float | None = None           # Unix timestamp
    force_offline: bool = False
    battery_low: bool = False
    cost_sensitive: bool = False
    deadline_urgent: bool = False
    domain_hint: str | None = None          # IntentDomain value
    max_tasks: int | None = None            # limit task count
    budget_usd: float | None = None
    user_id: str | None = None
    session_id: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Flatten to a plain dict for passing as context hints."""
        return {
            "force_offline": self.force_offline,
            "battery_low": self.battery_low,
            "cost_sensitive": self.cost_sensitive,
            "deadline_urgent": self.deadline_urgent,
            "domain_hint": self.domain_hint,
            **self.extra,
        }

    @classmethod
    def offline(cls) -> "PlannerContext":
        return cls(force_offline=True, strategy=PlanningStrategy.OFFLINE_FIRST)

    @classmethod
    def fast(cls) -> "PlannerContext":
        return cls(strategy=PlanningStrategy.FASTEST, deadline_urgent=True)

    @classmethod
    def private(cls) -> "PlannerContext":
        return cls(force_offline=True, strategy=PlanningStrategy.PRIVACY_FIRST)
