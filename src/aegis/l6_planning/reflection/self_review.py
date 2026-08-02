"""L6 Planning Engine — Self-reviewer.

Checks internal plan consistency: objective deps, task references.
Import safety: stdlib + pydantic + l6_planning internal only.
"""

from __future__ import annotations

from aegis.l6_planning.decomposition.task_decomposer import Task
from aegis.l6_planning.planning.mission import Mission
from aegis.l6_planning.types import ValidationIssue

__all__ = ["SelfReviewer"]


class SelfReviewer:
    """Checks plan internal consistency."""

    def review(self, mission: Mission, tasks: list[Task]) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        obj_ids = {o.objective_id for o in mission.objectives}
        task_ids = {t.task_id for t in tasks}

        for task in tasks:
            if task.objective_id not in obj_ids:
                issues.append(ValidationIssue(
                    severity="error", code="SR001",
                    message=f"Task {task.task_id!r} references unknown objective {task.objective_id!r}",
                ))
            for dep_id in task.depends_on:
                if dep_id not in task_ids:
                    issues.append(ValidationIssue(
                        severity="error", code="SR002",
                        message=f"Task {task.task_id!r} depends on unknown task {dep_id!r}",
                    ))

        return issues
