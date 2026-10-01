"""L6 Planning Engine — Plan Evaluator.

Checks plan quality, completeness, and logical coherence.

Magic constants remediation (H10): All unnamed penalty and threshold values
have been extracted to ``EvaluatorConfig`` so they can be overridden at
injection time without modifying this module.

Import safety: stdlib + pydantic + l6_planning internal only.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field

from aegis.l6_planning.decomposition.task_decomposer import Task
from aegis.l6_planning.planning.mission import Mission
from aegis.l6_planning.types import ValidationIssue

__all__ = ["EvaluationReport", "PlanEvaluator", "EvaluatorConfig"]


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


@dataclass
class EvaluatorConfig:
    """Named, overridable constants for PlanEvaluator heuristics.

    Every value that was previously a bare magic number is documented
    here with its rationale. Override at injection time to tune evaluation
    without editing this module.

    Usage::

        config = EvaluatorConfig(
            overall_high_threshold=0.9,   # more demanding "high" bar
        )
        evaluator = PlanEvaluator(config=config)

    Architecture: these are ``tunable thresholds``, not intelligence.
    """

    # ── Overall quality thresholds ─────────────────────────────────────────
    # overall >= high_threshold → "HIGH" quality label
    overall_high_threshold: float = 0.80
    # overall >= medium_threshold → "MEDIUM" quality label; else "LOW"
    overall_medium_threshold: float = 0.60

    # ── Completeness: overall dimension weight ─────────────────────────────
    # overall = completeness * completeness_weight + coherence * coherence_weight
    completeness_weight: float = 0.60
    coherence_weight: float = 0.40

    # ── Completeness penalties ─────────────────────────────────────────────
    # No objectives defined
    penalty_no_objectives: float = 0.40
    # Per uncovered objective (objective with no tasks)
    penalty_per_uncovered_objective: float = 0.10
    # Per task with empty title
    penalty_per_empty_title: float = 0.05
    # Per objective missing success criteria
    penalty_per_missing_success_criteria: float = 0.03

    # ── Coherence penalties ────────────────────────────────────────────────
    # Intent confidence below this → "very low confidence" warning
    coherence_min_confidence_threshold: float = 0.30
    # Penalty for very low confidence
    penalty_low_confidence: float = 0.20
    # Risk ordinal at or above this requires action_kind_hint
    coherence_high_risk_ordinal: int = 2
    # Per task missing action_kind_hint at high risk
    penalty_per_missing_action_hint: float = 0.02
    # Penalty for internet+local_only conflict
    penalty_constraint_conflict: float = 0.15

    @classmethod
    def default(cls) -> "EvaluatorConfig":
        """Return the default evaluator config (equivalent to pre-H10 magic numbers)."""
        return cls()


class PlanEvaluator:
    """Evaluates plan completeness and coherence.

    Usage::

        evaluator = PlanEvaluator()
        report = evaluator.evaluate(mission, tasks)

    To customise evaluation thresholds::

        config = EvaluatorConfig(overall_high_threshold=0.9)
        evaluator = PlanEvaluator(config=config)
    """

    def __init__(self, config: EvaluatorConfig | None = None) -> None:
        self._cfg = config or EvaluatorConfig.default()

    def evaluate(self, mission: Mission, tasks: list[Task]) -> EvaluationReport:
        cfg = self._cfg
        issues: list[ValidationIssue] = []

        completeness = self._completeness(mission, tasks, issues)
        coherence = self._coherence(mission, tasks, issues)
        overall = completeness * cfg.completeness_weight + coherence * cfg.coherence_weight

        return EvaluationReport(
            completeness_score=round(completeness, 3),
            coherence_score=round(coherence, 3),
            overall_quality=round(overall, 3),
            issues=issues,
            summary=self._summary(overall, issues),
        )

    def _completeness(self, mission: Mission, tasks: list[Task], issues: list[ValidationIssue]) -> float:
        cfg = self._cfg
        score = 1.0

        if not mission.objectives:
            issues.append(ValidationIssue(severity="error", code="E001", message="No objectives defined in mission"))
            score -= cfg.penalty_no_objectives

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
                score -= cfg.penalty_per_uncovered_objective

        # Check all tasks have titles
        for task in tasks:
            if not task.title.strip():
                issues.append(ValidationIssue(severity="error", code="E004", message=f"Task {task.task_id!r} has empty title"))
                score -= cfg.penalty_per_empty_title

        # Missing success criteria
        for obj in mission.objectives:
            if not obj.success_criteria:
                issues.append(ValidationIssue(
                    severity="info", code="E005",
                    message=f"Objective {obj.objective_id!r} has no success criteria",
                ))
                score -= cfg.penalty_per_missing_success_criteria

        return max(0.0, min(1.0, score))

    def _coherence(self, mission: Mission, tasks: list[Task], issues: list[ValidationIssue]) -> float:
        cfg = self._cfg
        score = 1.0

        # Check intent confidence
        if mission.parsed_intent.confidence < cfg.coherence_min_confidence_threshold:
            issues.append(ValidationIssue(
                severity="warning", code="C001",
                message=f"Very low intent confidence ({mission.parsed_intent.confidence:.0%}). Plan reliability may be low.",
            ))
            score -= cfg.penalty_low_confidence

        # Check for tasks with undefined action hints for risky operations
        for task in tasks:
            if task.risk_level.ordinal >= cfg.coherence_high_risk_ordinal and not task.action_kind_hint:  # type: ignore[attr-defined]
                issues.append(ValidationIssue(
                    severity="info", code="C002",
                    message=f"High-risk task {task.task_id!r} has no action_kind_hint — executor may not be deterministic",
                ))
                score -= cfg.penalty_per_missing_action_hint

        # Constraint conflicts
        if mission.parsed_intent.requires_internet and mission.parsed_intent.requires_local_only:
            issues.append(ValidationIssue(
                severity="warning", code="C003",
                message="Plan requires internet but local-only mode is also requested — conflict detected",
            ))
            score -= cfg.penalty_constraint_conflict

        return max(0.0, min(1.0, score))

    def _summary(self, overall: float, issues: list[ValidationIssue]) -> str:
        cfg = self._cfg
        errors = sum(1 for i in issues if i.severity == "error")
        warnings = sum(1 for i in issues if i.severity == "warning")
        if overall >= cfg.overall_high_threshold:
            return f"Plan quality is HIGH ({overall:.0%}). {errors} errors, {warnings} warnings."
        if overall >= cfg.overall_medium_threshold:
            return f"Plan quality is MEDIUM ({overall:.0%}). {errors} errors, {warnings} warnings."
        return f"Plan quality is LOW ({overall:.0%}). {errors} errors, {warnings} warnings. Review issues before executing."
