"""L6 Planning Engine — Acceptance Criteria generators.

Generates acceptance test specifications per task type.
Import safety: stdlib + pydantic + l6_planning internal only.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from aegis.l6_planning.decomposition.task_decomposer import Task

__all__ = ["AcceptanceCriterion", "AcceptanceCriteriaGenerator"]


class AcceptanceCriterion(BaseModel):
    task_id: str
    criterion: str
    testable: bool = True
    automated: bool = True


class AcceptanceCriteriaGenerator:
    """Generates acceptance criteria for tasks."""

    def generate(self, tasks: list[Task]) -> list[AcceptanceCriterion]:
        criteria: list[AcceptanceCriterion] = []
        for task in tasks:
            criteria.append(AcceptanceCriterion(
                task_id=task.task_id,
                criterion=f"'{task.title.split('[')[0].strip()}' completes with no unhandled errors",
                testable=True,
                automated=(task.action_kind_hint is not None),
            ))
            if task.is_approval_point:
                criteria.append(AcceptanceCriterion(
                    task_id=task.task_id,
                    criterion=f"User explicitly approves '{task.title.split('[')[0].strip()}'",
                    testable=True,
                    automated=False,
                ))
        return criteria
