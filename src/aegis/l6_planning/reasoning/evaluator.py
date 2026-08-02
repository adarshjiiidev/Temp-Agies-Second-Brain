"""L6 Planning Engine — Plan Evaluator.

Checks plan quality, completeness, and logical coherence.

Import safety: stdlib + pydantic + l6_planning internal only.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from aegis.l6_planning.decomposition.task_decomposer import Task
from aegis.l6_planning.planning.mission import Mission
from aegis.l6_planning.types import ValidationIssue

__all__ = ["EvaluationReport", "PlanEvaluator"]


class EvaluationReport(BaseModel):
    """Result of a plan quality evaluation."""

    completeness_score: float = Field(ge=0.0, le=1.0)
    coherence_score: float = Field(ge=0.0, le=1.0)
    overall_quality: float = Field(ge=0.0, le=1.0)
    issues: list[ValidationIssue] = Field(default_factory=list)
    summary: str = ""

    @property
    def has_blocking_issues(self) -> bool:
        return any(i.is_blocking() for i in self.issues)


class PlanEvaluator:
    """Evaluates plan completeness and coherence.

    Usage::

        evaluator = PlanEvaluator()
        report = evaluator.evaluate(mission, tasks)
    """

    def evaluate(self, mission: Mission, tasks: list[Task]) -> EvaluationReport:
        issues: list[ValidationIssue] = []

        completeness = self._completeness(mission, tasks, issues)
        coherence = self._coherence(mission, tasks, issues)
        overall = (completeness * 0.6 + coherence * 0.4)

        return EvaluationReport(
            completeness_score=round(completeness, 3),
            coherence_score=round(coherence, 3),
            overall_quality=round(overall, 3),
            issues=issues,
            summary=self._summary(overall, issues),
        )

    def _completeness(self, mission: Mission, tasks: list[Task], issues: list[ValidationIssue]) -> float:
        score = 1.0

        if not mission.objectives:
            issues.append(ValidationIssue(severity="error", code="E001", message="No objectives defined in mission"))
            score -= 0.4

        if not tasks:
            issues.append(ValidationIssue(severity="error", code="E002", message="No tasks generated"))
            return 0.0

        # Check all objectives are covered by tasks
        obj_ids_covered = {t.objective_id for t in tasks}
        for obj in mission.objectives:
            if obj.objective_id not in obj_ids_covered:
                issues.append(ValidationIssue(
                    severity="warning", code="E003",
                    message=f"Objective {obj.objective_id!r} has no tasks",
                    field="tasks",
                ))
                score -= 0.1

        # Check all tasks have titles
        for task in tasks:
            if not task.title.strip():
                issues.append(ValidationIssue(severity="error", code="E004", message=f"Task {task.task_id!r} has empty title"))
                score -= 0.05

        # Missing success criteria
        for obj in mission.objectives:
            if not obj.success_criteria:
                issues.append(ValidationIssue(
                    severity="info", code="E005",
                    message=f"Objective {obj.objective_id!r} has no success criteria",
                ))
                score -= 0.03

        return max(0.0, min(1.0, score))

    def _coherence(self, mission: Mission, tasks: list[Task], issues: list[ValidationIssue]) -> float:
        score = 1.0

        # Check intent confidence
        if mission.parsed_intent.confidence < 0.3:
            issues.append(ValidationIssue(
                severity="warning", code="C001",
                message=f"Very low intent confidence ({mission.parsed_intent.confidence:.0%}). Plan reliability may be low.",
            ))
            score -= 0.2

        # Check for tasks with undefined action hints for risky operations
        for task in tasks:
            if task.risk_level.ordinal >= 2 and not task.action_kind_hint:  # type: ignore[attr-defined]
                issues.append(ValidationIssue(
                    severity="info", code="C002",
                    message=f"High-risk task {task.task_id!r} has no action_kind_hint — executor may not be deterministic",
                ))
                score -= 0.02

        # Constraint conflicts
        if mission.parsed_intent.requires_internet and mission.parsed_intent.requires_local_only:
            issues.append(ValidationIssue(
                severity="warning", code="C003",
                message="Plan requires internet but local-only mode is also requested — conflict detected",
            ))
            score -= 0.15

        return max(0.0, min(1.0, score))

    def _summary(self, overall: float, issues: list[ValidationIssue]) -> str:
        errors = sum(1 for i in issues if i.severity == "error")
        warnings = sum(1 for i in issues if i.severity == "warning")
        if overall >= 0.8:
            return f"Plan quality is HIGH ({overall:.0%}). {errors} errors, {warnings} warnings."
        if overall >= 0.6:
            return f"Plan quality is MEDIUM ({overall:.0%}). {errors} errors, {warnings} warnings."
        return f"Plan quality is LOW ({overall:.0%}). {errors} errors, {warnings} warnings. Review issues before executing."
