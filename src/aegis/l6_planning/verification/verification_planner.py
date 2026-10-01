"""L6 Planning Engine — Verification Planner.

Generates VerificationPlan for a set of tasks: acceptance tests,
manual checks, completion evidence, and checkpoints.

Import safety: stdlib + pydantic + l6_planning internal only.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from aegis.l6_planning.decomposition.task_decomposer import Task
from aegis.l6_planning.types import RiskLevel

__all__ = ["VerificationCheck", "VerificationPlan", "VerificationPlanner"]


class VerificationCheck(BaseModel):
    """A single verification check for a task."""

    check_id: str = Field(default_factory=lambda: f"chk-{uuid.uuid4()!s:.8}")
    task_id: str
    kind: str = "automatic"          # "automatic" | "manual"
    description: str
    expected_output: str | None = None
    evidence_required: list[str] = Field(default_factory=list)
    blocking: bool = True            # if True, task is not complete until this passes


class VerificationPlan(BaseModel):
    """Full verification plan for a set of tasks."""

    checks: list[VerificationCheck] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    completion_evidence: list[str] = Field(default_factory=list)
    manual_check_count: int = 0
    automatic_check_count: int = 0

    @property
    def total_checks(self) -> int:
        return len(self.checks)


class VerificationPlanner:
    """Generates a VerificationPlan from a task list.

    Usage::

        planner = VerificationPlanner()
        vplan = planner.build(tasks)
    """

    def build(self, tasks: list[Task]) -> VerificationPlan:
        """Build a VerificationPlan for the given tasks.

        Args:
            tasks: All tasks from TaskDecomposer.

        Returns:
            VerificationPlan with checks, criteria, and evidence.
        """
        checks: list[VerificationCheck] = []
        acceptance_criteria: list[str] = []
        completion_evidence: list[str] = []

        for task in tasks:
            task_checks = self._generate_checks(task)
            checks.extend(task_checks)
            acceptance_criteria.append(f"Task '{task.title.split('[')[0].strip()}' completes successfully")
            if task.action_kind_hint:
                completion_evidence.append(f"Audit log entry for {task.action_kind_hint} on {task.task_id}")

        # Global acceptance criteria
        acceptance_criteria.append("No unexpected errors or failures in the audit log")
        acceptance_criteria.append("All approval points confirmed by user")
        completion_evidence.append("Final verification check passes all assertions")

        manual_count = sum(1 for c in checks if c.kind == "manual")
        auto_count = sum(1 for c in checks if c.kind == "automatic")

        return VerificationPlan(
            checks=checks,
            acceptance_criteria=acceptance_criteria,
            completion_evidence=completion_evidence,
            manual_check_count=manual_count,
            automatic_check_count=auto_count,
        )

    def _generate_checks(self, task: Task) -> list[VerificationCheck]:
        """Generate verification checks for a single task."""
        checks: list[VerificationCheck] = []

        # Automatic check: task completed
        checks.append(VerificationCheck(
            task_id=task.task_id,
            kind="automatic",
            description=f"Verify task '{task.title.split('[')[0].strip()}' completed without errors",
            expected_output="No exception; audit entry shows SUCCESS",
            evidence_required=["audit_entry"],
            blocking=True,
        ))

        # Manual check for high-risk tasks
        if task.risk_level >= RiskLevel.HIGH:
            checks.append(VerificationCheck(
                task_id=task.task_id,
                kind="manual",
                description=f"Manually review output of high-risk task '{task.title.split('[')[0].strip()}'",
                expected_output="User confirms output is as expected",
                evidence_required=["user_confirmation"],
                blocking=True,
            ))

        # Action-specific checks
        if task.action_kind_hint:
            hint = task.action_kind_hint
            if hint.startswith("fs."):
                checks.append(VerificationCheck(
                    task_id=task.task_id,
                    kind="automatic",
                    description=f"Verify filesystem state after {hint}",
                    expected_output="File/directory exists with expected content",
                    evidence_required=["fs_stat"],
                    blocking=False,
                ))
            elif hint.startswith("git."):
                checks.append(VerificationCheck(
                    task_id=task.task_id,
                    kind="automatic",
                    description=f"Verify git repository state after {hint}",
                    expected_output="git status shows expected state",
                    evidence_required=["git_status"],
                    blocking=False,
                ))

        return checks
