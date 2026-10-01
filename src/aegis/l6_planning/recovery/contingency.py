"""L6 Planning Engine — Contingency builder.

Generates contingency branches (alternative plan notes) for blocked scenarios.
Import safety: stdlib + pydantic + l6_planning internal only.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from aegis.l6_planning.decomposition.task_decomposer import Task
from aegis.l6_planning.types import RiskLevel

__all__ = ["ContingencyBranch", "ContingencyBuilder"]


class ContingencyBranch(BaseModel):
    condition: str
    alternative_action: str
    blocks_task_ids: list[str] = Field(default_factory=list)


class ContingencyBuilder:
    """Generates contingency branches for a task list."""

    def build(self, tasks: list[Task]) -> list[ContingencyBranch]:
        branches: list[ContingencyBranch] = []

        high_risk = [t for t in tasks if t.risk_level >= RiskLevel.HIGH]
        if high_risk:
            branches.append(ContingencyBranch(
                condition="Any HIGH/CRITICAL risk task is denied approval",
                alternative_action="Skip the denied task and continue with remaining tasks; flag for later review",
                blocks_task_ids=[t.task_id for t in high_risk],
            ))

        net_tasks = [t for t in tasks if t.action_kind_hint and t.action_kind_hint.startswith("net.")]
        if net_tasks:
            branches.append(ContingencyBranch(
                condition="Internet is unavailable",
                alternative_action="Switch to OFFLINE_FIRST strategy; defer network tasks to a later session",
                blocks_task_ids=[t.task_id for t in net_tasks],
            ))

        irreversible = [t for t in tasks if not t.reversible]
        if irreversible:
            branches.append(ContingencyBranch(
                condition="Irreversible task fails mid-execution",
                alternative_action="Pause plan, alert user, and await manual recovery instructions",
                blocks_task_ids=[t.task_id for t in irreversible],
            ))

        return branches
