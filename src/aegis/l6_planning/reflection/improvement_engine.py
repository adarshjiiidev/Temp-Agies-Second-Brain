"""L6 Planning Engine — Improvement Engine.

Generates optimization suggestions for a plan based on task analysis.
Import safety: stdlib + pydantic + l6_planning internal only.
"""

from __future__ import annotations

from aegis.l6_planning.decomposition.task_decomposer import Task
from aegis.l6_planning.planning.mission import Mission

__all__ = ["ImprovementEngine"]


class ImprovementEngine:
    """Generates actionable optimization suggestions for a plan."""

    def suggest(self, mission: Mission, tasks: list[Task]) -> list[str]:
        """Return a list of optimization suggestions."""
        suggestions: list[str] = []

        parallel_candidates = [t for t in tasks if not t.can_run_parallel and not t.depends_on]
        if len(parallel_candidates) > 2:
            suggestions.append(
                f"{len(parallel_candidates)} tasks have no dependencies and could potentially run in parallel"
            )

        sequential_count = sum(1 for t in tasks if not t.can_run_parallel)
        if sequential_count > 10:
            suggestions.append("Many sequential tasks — consider batching similar operations to reduce overhead")

        approval_count = sum(1 for t in tasks if t.is_approval_point)
        if approval_count > 5:
            suggestions.append(
                f"{approval_count} approval points may slow execution — review if all are strictly necessary"
            )

        if not mission.requirements.offline_capable and not mission.parsed_intent.requires_internet:
            suggestions.append(
                "Plan doesn't strictly require internet — switch to OFFLINE_FIRST for better privacy"
            )

        long_tasks = [t for t in tasks if t.estimated_seconds > 3600]
        if long_tasks:
            suggestions.append(
                f"{len(long_tasks)} task(s) estimated to take > 1 hour — consider decomposing further"
            )

        return suggestions
