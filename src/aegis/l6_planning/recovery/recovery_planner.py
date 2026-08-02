"""L6 Planning Engine — Recovery Planner.

Generates a RecoveryPlan with failure scenarios, retry policy,
fallback strategies, and escalation conditions.

Import safety: stdlib + pydantic + l6_planning internal only.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from aegis.l6_planning.decomposition.task_decomposer import Task
from aegis.l6_planning.types import RiskLevel

__all__ = ["FailureScenario", "RetryConfig", "RecoveryPlan", "RecoveryPlanner"]


class RetryConfig(BaseModel):
    """Retry policy for a failed task."""

    max_attempts: int = 3
    backoff_seconds: float = 5.0
    backoff_multiplier: float = 2.0
    max_backoff_seconds: float = 120.0
    jitter: bool = True


class FailureScenario(BaseModel):
    """A possible failure mode for a task."""

    scenario_id: str = Field(default_factory=lambda: f"fs-{uuid.uuid4()!s:.8}")
    task_id: str
    failure_mode: str
    probability: float = Field(ge=0.0, le=1.0)
    impact: RiskLevel = RiskLevel.LOW
    fallback_strategy: str
    resume_point: str | None = None     # task_id to resume from
    rollback_required: bool = False
    retry_config: RetryConfig = Field(default_factory=RetryConfig)


class RecoveryPlan(BaseModel):
    """Full recovery plan for a set of tasks."""

    scenarios: list[FailureScenario] = Field(default_factory=list)
    global_retry_config: RetryConfig = Field(default_factory=RetryConfig)
    escalation_conditions: list[str] = Field(default_factory=list)
    alternative_plan_notes: list[str] = Field(default_factory=list)
    total_risk_surface: str = "low"   # "low" | "medium" | "high" | "critical"


_FAILURE_MODES: dict[str, list[tuple[str, float, bool]]] = {
    "fs.write": [
        ("Disk full", 0.05, False),
        ("Permission denied", 0.10, False),
        ("File already exists with conflicts", 0.08, True),
    ],
    "fs.delete": [
        ("File in use", 0.05, False),
        ("Permission denied", 0.10, False),
    ],
    "git.commit": [
        ("Nothing to commit", 0.15, False),
        ("Merge conflict", 0.12, True),
        ("Pre-commit hook failure", 0.08, False),
    ],
    "git.push": [
        ("Remote rejected push", 0.10, False),
        ("Authentication failure", 0.05, False),
    ],
    "shell.exec": [
        ("Command not found", 0.15, False),
        ("Non-zero exit code", 0.20, False),
        ("Timeout", 0.08, False),
    ],
    "net.get": [
        ("Network unreachable", 0.10, False),
        ("Rate limited (429)", 0.08, True),
        ("Server error (5xx)", 0.12, True),
    ],
    "browser.navigate": [
        ("Page not found (404)", 0.08, False),
        ("Navigation timeout", 0.10, True),
    ],
}

_FALLBACK_STRATEGIES: dict[str, str] = {
    "fs.write": "Write to a temporary file and move on success; alert user if disk full",
    "fs.delete": "Skip deletion and flag for manual review",
    "git.commit": "Stage changes and pause for user review before commit",
    "git.push": "Store push command for retry after authentication fix",
    "shell.exec": "Log command and output; prompt user to run manually if needed",
    "net.get": "Retry with exponential backoff; fall back to cached data if available",
    "browser.navigate": "Retry navigation; if persistent, prompt user to check URL",
    "default": "Log failure with full context; pause and await user instruction",
}


class RecoveryPlanner:
    """Generates a RecoveryPlan from a task list.

    Usage::

        planner = RecoveryPlanner()
        rplan = planner.build(tasks)
    """

    def build(self, tasks: list[Task]) -> RecoveryPlan:
        """Build a RecoveryPlan for the given tasks.

        Args:
            tasks: All tasks from TaskDecomposer.

        Returns:
            RecoveryPlan with failure scenarios and recovery strategies.
        """
        scenarios: list[FailureScenario] = []

        for task in tasks:
            task_scenarios = self._generate_scenarios(task)
            scenarios.extend(task_scenarios)

        # Escalation conditions
        escalation_conditions = [
            "Three or more consecutive task failures",
            "Any CRITICAL risk task fails",
            "User-confirmed approval point fails verification",
            "Recovery strategy itself fails after max retries",
        ]

        # Alternative plan notes
        alt_notes = [
            "If the primary plan is blocked at a network step, switch to OFFLINE_FIRST strategy",
            "If the primary plan exceeds budget, switch to CHEAPEST strategy",
        ]

        # Determine overall risk surface
        risk_surface = self._compute_risk_surface(tasks)

        return RecoveryPlan(
            scenarios=scenarios,
            global_retry_config=RetryConfig(max_attempts=3, backoff_seconds=5.0, backoff_multiplier=2.0),
            escalation_conditions=escalation_conditions,
            alternative_plan_notes=alt_notes,
            total_risk_surface=risk_surface,
        )

    def _generate_scenarios(self, task: Task) -> list[FailureScenario]:
        """Generate failure scenarios for a task."""
        scenarios: list[FailureScenario] = []
        hint = task.action_kind_hint or "default"
        modes = _FAILURE_MODES.get(hint, [("Unexpected error", 0.05, False)])
        fallback = _FALLBACK_STRATEGIES.get(hint, _FALLBACK_STRATEGIES["default"])

        for failure_mode, probability, needs_rollback in modes:
            impact = task.risk_level if needs_rollback else RiskLevel(
                list(RiskLevel)[max(0, list(RiskLevel).index(task.risk_level) - 1)].value
            )
            scenarios.append(FailureScenario(
                task_id=task.task_id,
                failure_mode=failure_mode,
                probability=probability,
                impact=impact,
                fallback_strategy=fallback,
                resume_point=task.task_id,
                rollback_required=needs_rollback,
                retry_config=RetryConfig(
                    max_attempts=1 if task.risk_level >= RiskLevel.HIGH else 3,
                    backoff_seconds=30.0 if task.risk_level >= RiskLevel.HIGH else 5.0,
                ),
            ))

        return scenarios

    def _compute_risk_surface(self, tasks: list[Task]) -> str:
        if not tasks:
            return "low"
        max_risk = max((t.risk_level for t in tasks), key=lambda r: r.ordinal, default=RiskLevel.LOW)
        return max_risk.value
