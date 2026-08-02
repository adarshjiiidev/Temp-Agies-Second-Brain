"""L6 Planning Engine — PlanningResult.

The single output object for all PlannerService operations.
Aggregates mission, tasks, graph, milestones, execution order,
risk assessment, recovery, verification, and reflection.

Import safety: stdlib + pydantic + l6_planning internal only.
No execution artefacts — pure planning output.
"""

from __future__ import annotations

import time
import uuid

from pydantic import BaseModel, Field

from aegis.l6_planning.decomposition.task_decomposer import Task
from aegis.l6_planning.planning.mission import Mission
from aegis.l6_planning.recovery.recovery_planner import RecoveryPlan
from aegis.l6_planning.reflection.reflection_engine import ReflectionReport
from aegis.l6_planning.types import (
    DecisionTraceEntry,
    ExecutionStep,
    Milestone,
    PlanEstimate,
    PlanState,
    PlanningStrategy,
)
from aegis.l6_planning.verification.verification_planner import VerificationPlan

__all__ = ["PlanningResult"]


class PlanningResult(BaseModel):
    """The canonical output of the L6 Planning Engine.

    Created by PlannerService and consumed by L7 (HCI) and higher-layer
    orchestrators. Never contains execution results — it is a pure plan.

    Attributes:
        plan_id:           Unique plan identifier.
        state:             Current lifecycle state.
        mission:           The Mission (goal, intent, objectives, requirements).
        tasks:             Flat list of all Task objects.
        task_graph:        Serialized DependencyGraph (adjacency dict).
        milestones:        Logical milestone groupings with criteria.
        execution_order:   Ordered ExecutionSteps respecting the chosen strategy.
        recovery_plan:     Failure scenarios and recovery strategies.
        verification_plan: Acceptance checks and completion evidence.
        estimates:         Time/cost/token estimates.
        confidence:        Composite planner confidence (0–1).
        decision_trace:    Audit trail of planning decisions.
        reflection_report: Post-plan self-review (None if skipped).
        strategy:          Strategy applied.
        created_at:        Unix timestamp of creation.
        updated_at:        Unix timestamp of last update.
        version:           Monotonically increasing edit counter.
    """

    plan_id: str = Field(default_factory=lambda: f"plan-{uuid.uuid4()!s:.8}")
    state: PlanState = PlanState.READY
    mission: Mission
    tasks: list[Task] = Field(default_factory=list)
    task_graph: dict = Field(default_factory=dict)
    milestones: list[Milestone] = Field(default_factory=list)
    execution_order: list[ExecutionStep] = Field(default_factory=list)
    recovery_plan: RecoveryPlan = Field(default_factory=RecoveryPlan)
    verification_plan: VerificationPlan = Field(default_factory=VerificationPlan)
    estimates: PlanEstimate = Field(default_factory=PlanEstimate)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    decision_trace: list[DecisionTraceEntry] = Field(default_factory=list)
    reflection_report: ReflectionReport | None = None
    strategy: PlanningStrategy = PlanningStrategy.BALANCED
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    version: int = 1

    # ------------------------------------------------------------------ #
    # Convenience accessors
    # ------------------------------------------------------------------ #

    @property
    def task_count(self) -> int:
        return len(self.tasks)

    @property
    def step_count(self) -> int:
        return len(self.execution_order)

    @property
    def approval_point_count(self) -> int:
        return sum(1 for s in self.execution_order if s.is_approval_point)

    @property
    def parallel_step_count(self) -> int:
        return sum(1 for s in self.execution_order if s.parallel_group is not None)

    @property
    def is_ready(self) -> bool:
        return self.state is PlanState.READY

    @property
    def is_terminal(self) -> bool:
        return self.state in (PlanState.COMPLETED, PlanState.CANCELLED, PlanState.FAILED)

    @property
    def reflection_passed(self) -> bool:
        if self.reflection_report is None:
            return True
        return self.reflection_report.passed

    def transition(self, new_state: PlanState) -> "PlanningResult":
        """Return a new PlanningResult with updated state and timestamp."""
        return self.model_copy(update={
            "state": new_state,
            "updated_at": time.time(),
            "version": self.version + 1,
        })

    def summary(self) -> str:
        """Return a human-readable plan summary."""
        return (
            f"Plan {self.plan_id!r} [{self.state.value}] | "
            f"'{self.mission.title}' | "
            f"{self.task_count} tasks, {self.step_count} steps, "
            f"{self.approval_point_count} approval points | "
            f"strategy={self.strategy.value} | "
            f"confidence={self.confidence:.0%}"
        )

    def __repr__(self) -> str:
        return f"PlanningResult(id={self.plan_id!r}, state={self.state.value}, tasks={self.task_count})"
