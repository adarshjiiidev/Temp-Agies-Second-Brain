"""L6 Planning Engine — Reflection Engine.

Performs post-plan review: missing requirements, logical consistency,
circular dependency detection, risk review, and optimization suggestions.

Import safety: stdlib + pydantic + l6_planning internal only.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from aegis.l6_planning.decomposition.dependency_graph import DependencyGraph
from aegis.l6_planning.decomposition.task_decomposer import Task
from aegis.l6_planning.planning.mission import Mission
from aegis.l6_planning.types import RiskLevel, ValidationIssue

__all__ = ["ReflectionIssue", "ReflectionReport", "ReflectionEngine"]


class ReflectionIssue(BaseModel):
    """An issue identified during reflection."""

    category: str   # "missing_requirement" | "logic" | "cycle" | "risk" | "optimization"
    severity: str   # "error" | "warning" | "suggestion"
    message: str
    suggested_fix: str = ""


class ReflectionReport(BaseModel):
    """Output of the ReflectionEngine."""

    issues: list[ReflectionIssue] = Field(default_factory=list)
    optimizations: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    circular_deps: list[list[str]] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    complexity_score: float = 0.0   # 0.0 = trivial, 1.0 = extremely complex
    confidence_delta: float = 0.0   # positive = reflection increased confidence
    passed: bool = True

    @property
    def blocking_issues(self) -> list[ReflectionIssue]:
        return [i for i in self.issues if i.severity == "error"]


class ReflectionEngine:
    """Reviews a completed plan for issues and optimization opportunities.

    The ReflectionEngine is run automatically after a plan is created.
    It never modifies the plan — it only produces a ReflectionReport
    that the planner can use to update the plan if desired.

    Usage::

        engine = ReflectionEngine()
        report = engine.review(mission, tasks, graph)
    """

    def review(
        self,
        mission: Mission,
        tasks: list[Task],
        graph: DependencyGraph,
    ) -> ReflectionReport:
        """Review a plan for issues and optimizations.

        Args:
            mission: The Mission being planned.
            tasks: All tasks from TaskDecomposer.
            graph: Populated DependencyGraph.

        Returns:
            ReflectionReport with issues, optimizations, and confidence delta.
        """
        issues: list[ReflectionIssue] = []
        optimizations: list[str] = []
        missing: list[str] = []
        risk_flags: list[str] = []

        # 1. Check for cycle in graph
        cycles = graph.detect_cycles()
        if cycles:
            for cycle in cycles:
                issues.append(ReflectionIssue(
                    category="cycle",
                    severity="error",
                    message=f"Circular dependency detected: {' → '.join(cycle)}",
                    suggested_fix="Remove one of the dependency edges to break the cycle.",
                ))

        # 2. Missing requirements check
        req_perms = set(mission.requirements.permissions_needed)
        task_hints = {t.action_kind_hint for t in tasks if t.action_kind_hint}

        for hint in task_hints:
            # Check if permission is covered
            base_verb = hint.split(".")[0] + ".*"
            if hint not in req_perms and base_verb not in req_perms:
                missing.append(f"Permission for '{hint}' is used by tasks but not listed in requirements")
                issues.append(ReflectionIssue(
                    category="missing_requirement",
                    severity="warning",
                    message=f"Action hint '{hint}' used in tasks but '{hint}' not in requirements.permissions_needed",
                    suggested_fix=f"Add '{hint}' or '{base_verb}' to requirements.permissions_needed",
                ))

        # 3. Logical consistency
        if not tasks:
            issues.append(ReflectionIssue(
                category="logic",
                severity="error",
                message="Plan has no tasks — decomposition may have failed",
                suggested_fix="Review the mission objectives and retry decomposition",
            ))

        # 4. Risk review
        high_risk_tasks = [t for t in tasks if t.risk_level >= RiskLevel.HIGH]
        for task in high_risk_tasks:
            if not task.is_approval_point:
                risk_flags.append(f"Task {task.task_id!r} is HIGH+ risk but is not marked as an approval point")
                issues.append(ReflectionIssue(
                    category="risk",
                    severity="warning",
                    message=f"HIGH risk task '{task.title.split('[')[0].strip()}' is not gated with an approval point",
                    suggested_fix="Set is_approval_point=True on this task",
                ))

        # 5. Optimization suggestions
        parallel_groups = graph.parallel_groups()
        max_parallel = max((len(g) for g in parallel_groups), default=0)
        if max_parallel < 2 and len(tasks) > 4:
            optimizations.append("No parallel task groups identified — consider restructuring dependencies to allow parallelism")

        irreversible_tasks = [t for t in tasks if not t.reversible]
        if irreversible_tasks:
            optimizations.append(
                f"{len(irreversible_tasks)} irreversible task(s) detected — ensure recovery plan covers these"
            )

        if len(tasks) > 20:
            optimizations.append("Plan has many tasks — consider splitting into sub-plans or milestones for easier management")

        # 6. Complexity scoring
        complexity = min(1.0, (
            len(tasks) / 30.0 * 0.4
            + len(high_risk_tasks) / max(1, len(tasks)) * 0.3
            + (1 - mission.parsed_intent.confidence) * 0.3
        ))

        # 7. Confidence delta
        n_errors = sum(1 for i in issues if i.severity == "error")
        n_warnings = sum(1 for i in issues if i.severity == "warning")
        confidence_delta = -(n_errors * 0.10 + n_warnings * 0.03)

        passed = n_errors == 0

        return ReflectionReport(
            issues=issues,
            optimizations=optimizations,
            missing_requirements=missing,
            circular_deps=cycles,
            risk_flags=risk_flags,
            complexity_score=round(complexity, 3),
            confidence_delta=round(confidence_delta, 3),
            passed=passed,
        )
