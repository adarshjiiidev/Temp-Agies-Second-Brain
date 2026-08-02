"""L6 Planning Engine — Planner Metrics.

Session-level planning statistics for observability.
Import safety: stdlib + pydantic + l6_planning.types only.
"""

from __future__ import annotations

import time

from pydantic import BaseModel, Field

from aegis.l6_planning.types import PlanningStrategy

__all__ = ["PlannerMetrics"]


class PlannerMetrics(BaseModel):
    """Accumulated metrics across a planning session."""

    total_plans_created: int = 0
    total_plans_cancelled: int = 0
    total_plans_completed: int = 0
    total_plans_failed: int = 0
    total_planning_time_ms: float = 0.0
    avg_tasks_per_plan: float = 0.0
    avg_confidence: float = 0.0
    strategy_distribution: dict[str, int] = Field(default_factory=dict)
    domain_distribution: dict[str, int] = Field(default_factory=dict)
    session_start: float = Field(default_factory=time.time)

    @property
    def avg_planning_time_ms(self) -> float:
        if self.total_plans_created == 0:
            return 0.0
        return self.total_planning_time_ms / self.total_plans_created

    @property
    def cancellation_rate(self) -> float:
        if self.total_plans_created == 0:
            return 0.0
        return self.total_plans_cancelled / self.total_plans_created

    def record_plan(
        self,
        planning_time_ms: float,
        task_count: int,
        confidence: float,
        strategy: PlanningStrategy,
        domain: str,
    ) -> "PlannerMetrics":
        """Return updated metrics after recording a new plan creation."""
        n = self.total_plans_created + 1
        new_avg_tasks = (self.avg_tasks_per_plan * self.total_plans_created + task_count) / n
        new_avg_conf = (self.avg_confidence * self.total_plans_created + confidence) / n
        strat_dist = dict(self.strategy_distribution)
        strat_dist[strategy.value] = strat_dist.get(strategy.value, 0) + 1
        dom_dist = dict(self.domain_distribution)
        dom_dist[domain] = dom_dist.get(domain, 0) + 1

        return self.model_copy(update={
            "total_plans_created": n,
            "total_planning_time_ms": self.total_planning_time_ms + planning_time_ms,
            "avg_tasks_per_plan": new_avg_tasks,
            "avg_confidence": new_avg_conf,
            "strategy_distribution": strat_dist,
            "domain_distribution": dom_dist,
        })
