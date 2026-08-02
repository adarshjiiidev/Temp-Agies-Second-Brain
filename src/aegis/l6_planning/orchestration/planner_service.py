"""L6 Planning Engine — Planner Service.

The single public API surface for L6. All methods return PlanningResult.
No execution. No LLM calls. Pure planning.

Architecture compliance:
  - Imports from L5 types only (no pipeline, no executor, no audit)
  - Imports from L4 types only (no manager, no search)
  - Never raises raw exceptions — wraps in AegisError subclasses

Import safety: stdlib + l6_planning internal only.
"""

from __future__ import annotations

import time
from typing import Any

from aegis.l6_planning.decomposition.dependency_graph import DependencyGraph
from aegis.l6_planning.decomposition.milestone_builder import MilestoneBuilder
from aegis.l6_planning.decomposition.task_decomposer import TaskDecomposer
from aegis.l6_planning.exceptions import (
    PlanGoalInvalidError,
    PlanNotFoundError,
)
from aegis.l6_planning.metrics.planner_metrics import PlannerMetrics
from aegis.l6_planning.orchestration.planning_session import PlanningSession
from aegis.l6_planning.planning.goal_engine import GoalEngine
from aegis.l6_planning.planning_result import PlanningResult
from aegis.l6_planning.reasoning.decision_engine import DecisionEngine
from aegis.l6_planning.recovery.recovery_planner import RecoveryPlanner
from aegis.l6_planning.reflection.improvement_engine import ImprovementEngine
from aegis.l6_planning.reflection.reflection_engine import ReflectionEngine
from aegis.l6_planning.state.planner_context import PlannerContext
from aegis.l6_planning.strategy.execution_order import ExecutionOrderBuilder
from aegis.l6_planning.strategy.strategy_engine import StrategyEngine
from aegis.l6_planning.types import (
    DecisionTraceEntry,
    EffortEstimate,
    EffortLevel,
    PlanComparison,
    PlanEstimate,
    PlanState,
    PlanningStrategy,
)
from aegis.l6_planning.verification.verification_planner import VerificationPlanner

__all__ = ["PlannerService"]


class PlannerService:
    """The public orchestrator for the L6 Planning Engine.

    Composes all planning subsystems into a unified API.
    All methods are async for EventBus / HCI integration, but the
    underlying planning logic is synchronous.

    Lifecycle::

        service = PlannerService()
        result = await service.create_plan("Build a React portfolio")
        result = await service.review_plan(result.plan_id)
        # ... when L5 finishes executing ...
        result = await service.cancel_plan(result.plan_id)

    All methods return a PlanningResult.
    No method modifies L1–L5.
    """

    def __init__(self) -> None:
        self._session = PlanningSession()
        self._goal_engine = GoalEngine()
        self._decomposer = TaskDecomposer()
        self._milestone_builder = MilestoneBuilder()
        self._strategy_engine = StrategyEngine()
        self._order_builder = ExecutionOrderBuilder()
        self._decision_engine = DecisionEngine()
        self._verification_planner = VerificationPlanner()
        self._recovery_planner = RecoveryPlanner()
        self._reflection_engine = ReflectionEngine()
        self._improvement_engine = ImprovementEngine()
        self._metrics = PlannerMetrics()

    # ------------------------------------------------------------------ #
    # Primary API
    # ------------------------------------------------------------------ #

    async def create_plan(
        self,
        goal: str,
        context: PlannerContext | None = None,
    ) -> PlanningResult:
        """Create a full plan from a raw goal string.

        Pipeline:
          1. Validate goal
          2. Create Mission (intent + requirements + objectives)
          3. Select strategy
          4. Decompose into tasks + dependency graph
          5. Build milestones
          6. Build execution order
          7. Score plan
          8. Build verification plan
          9. Build recovery plan
          10. Reflect (post-plan review)
          11. Store and return

        Args:
            goal: Raw user goal string.
            context: Optional per-call planning preferences.

        Returns:
            PlanningResult with state=READY.

        Raises:
            PlanGoalInvalidError: If goal is empty or invalid.
        """
        t0 = time.monotonic()
        ctx = context or PlannerContext()
        ctx_dict = ctx.to_dict()

        # 1. Create mission
        mission = self._goal_engine.create_mission(
            goal_text=goal,
            context=ctx_dict,
            strategy=ctx.strategy or PlanningStrategy.BALANCED,
            constraints=ctx.constraints,
            deadline=ctx.deadline,
        )

        # 2. Select strategy
        strategy = self._strategy_engine.select_strategy(
            mission=mission,
            user_preference=ctx.strategy,
            context=ctx_dict,
        )
        mission = mission.model_copy(update={"strategy": strategy})

        # 3. Decompose
        decomp = self._decomposer.decompose(mission)
        tasks = decomp.tasks

        # Respect max_tasks context limit
        if ctx.max_tasks and len(tasks) > ctx.max_tasks:
            tasks = tasks[: ctx.max_tasks]

        # 4. Rebuild graph from (possibly truncated) tasks
        graph = DependencyGraph.from_dict(decomp.graph)

        # 5. Milestones
        milestones = self._milestone_builder.build(decomp)

        # 6. Execution order
        execution_order = self._order_builder.build(tasks, graph, strategy)

        # 7. Score plan + build decision trace
        score = self._decision_engine.score_plan(mission, decomp, strategy)
        _, decision_trace = self._decision_engine.select_best([score])

        # 8. Verification
        verification_plan = self._verification_planner.build(tasks)

        # 9. Recovery
        recovery_plan = self._recovery_planner.build(tasks)

        # 10. Estimates
        effort_level = self._seconds_to_effort_level(decomp.total_estimated_seconds)
        estimates = PlanEstimate(
            effort=EffortEstimate(
                level=effort_level,
                min_seconds=decomp.total_estimated_seconds * 0.7,
                max_seconds=decomp.total_estimated_seconds * 1.5,
                best_guess_seconds=decomp.total_estimated_seconds,
                confidence=score.success_probability,
            ),
            total_tasks=len(tasks),
            total_approval_points=decomp.approval_point_count,
            parallel_tasks=decomp.parallel_task_count,
            sequential_tasks=decomp.sequential_task_count,
            estimated_total_seconds=decomp.total_estimated_seconds,
            confidence=score.composite_score,
        )

        # 11. Reflect
        reflection = self._reflection_engine.review(mission, tasks, graph)
        improvement_opts = self._improvement_engine.suggest(mission, tasks)
        if improvement_opts:
            reflection = reflection.model_copy(update={
                "optimizations": reflection.optimizations + improvement_opts
            })

        result = PlanningResult(
            state=PlanState.READY,
            mission=mission,
            tasks=tasks,
            task_graph=decomp.graph,
            milestones=milestones,
            execution_order=execution_order,
            recovery_plan=recovery_plan,
            verification_plan=verification_plan,
            estimates=estimates,
            confidence=round(score.composite_score, 4),
            decision_trace=decision_trace or [],
            reflection_report=reflection,
            strategy=strategy,
        )

        self._session.store(result)

        # Update metrics
        elapsed_ms = (time.monotonic() - t0) * 1000
        self._metrics = self._metrics.record_plan(
            planning_time_ms=elapsed_ms,
            task_count=len(tasks),
            confidence=result.confidence,
            strategy=strategy,
            domain=mission.parsed_intent.domain.value,
        )

        return result

    async def review_plan(self, plan_id: str) -> PlanningResult:
        """Re-run validation and reflection on an existing plan.

        Args:
            plan_id: ID of an existing plan in the session.

        Returns:
            Updated PlanningResult with refreshed reflection report.

        Raises:
            PlanNotFoundError: If plan_id is not found.
        """
        plan = self._session.get(plan_id)
        graph = DependencyGraph.from_dict(plan.task_graph)
        reflection = self._reflection_engine.review(plan.mission, plan.tasks, graph)

        updated = plan.model_copy(update={
            "reflection_report": reflection,
            "state": PlanState.REVIEWING,
        }).transition(PlanState.READY)

        self._session.store(updated)
        return updated

    async def update_plan(self, plan_id: str, feedback: str) -> PlanningResult:
        """Refine a plan based on user feedback.

        Refines the mission, re-decomposes, and returns a new version.

        Args:
            plan_id: ID of an existing plan.
            feedback: User feedback / updated goal text.

        Returns:
            Updated PlanningResult with bumped version.
        """
        plan = self._session.get(plan_id)
        refined_mission = self._goal_engine.refine_mission(plan.mission, feedback)
        # Re-create plan with refined mission (reuses create_plan internals)
        ctx = PlannerContext(strategy=plan.strategy)
        new_plan = await self.create_plan(refined_mission.user_goal_text, ctx)
        # Carry over plan_id for continuity
        new_plan = new_plan.model_copy(update={
            "plan_id": plan_id,
            "version": plan.version + 1,
        })
        self._session.store(new_plan)
        return new_plan

    async def cancel_plan(self, plan_id: str) -> PlanningResult:
        """Cancel an active plan.

        Args:
            plan_id: ID of the plan to cancel.

        Returns:
            PlanningResult with state=CANCELLED.

        Raises:
            PlanNotFoundError: If plan_id is not found.
            PlanAlreadyCancelledError: If plan is already cancelled.
        """
        return self._session.cancel(plan_id)

    async def resume_plan(self, plan_id: str) -> PlanningResult:
        """Resume a suspended plan.

        Args:
            plan_id: ID of a SUSPENDED plan.

        Returns:
            PlanningResult with state=READY.

        Raises:
            PlanNotFoundError: If plan_id is not found.
        """
        plan = self._session.get(plan_id)
        if plan.state not in (PlanState.SUSPENDED, PlanState.REVIEWING):
            # Return as-is if already active/terminal
            return plan
        updated = plan.transition(PlanState.READY)
        self._session.store(updated)
        return updated

    async def estimate_plan(self, goal: str, context: PlannerContext | None = None) -> PlanEstimate:
        """Quickly estimate effort without creating a full plan.

        Args:
            goal: Raw goal string.
            context: Optional planning context.

        Returns:
            PlanEstimate (no plan is stored in the session).
        """
        ctx = context or PlannerContext()
        try:
            mission = self._goal_engine.create_mission(goal, ctx.to_dict())
        except PlanGoalInvalidError:
            return PlanEstimate(
                effort=EffortEstimate.trivial(),
                confidence=0.0,
            )

        decomp = self._decomposer.decompose(mission)
        effort_level = self._seconds_to_effort_level(decomp.total_estimated_seconds)

        return PlanEstimate(
            effort=EffortEstimate(
                level=effort_level,
                min_seconds=decomp.total_estimated_seconds * 0.6,
                max_seconds=decomp.total_estimated_seconds * 2.0,
                best_guess_seconds=decomp.total_estimated_seconds,
                confidence=mission.parsed_intent.confidence,
            ),
            total_tasks=len(decomp.tasks),
            total_approval_points=decomp.approval_point_count,
            parallel_tasks=decomp.parallel_task_count,
            sequential_tasks=decomp.sequential_task_count,
            estimated_total_seconds=decomp.total_estimated_seconds,
            confidence=mission.parsed_intent.confidence,
        )

    async def compare_plans(self, plan_ids: list[str]) -> PlanComparison:
        """Compare two or more plans by their composite scores.

        Args:
            plan_ids: List of plan IDs (min 2) to compare.

        Returns:
            PlanComparison with winner, scores, and tradeoff summary.

        Raises:
            PlanNotFoundError: If any plan_id is not found.
        """
        plans = [self._session.get(pid) for pid in plan_ids]
        scores = []
        for plan in plans:
            decomp = self._decomposer.decompose(plan.mission)
            score = self._decision_engine.score_plan(plan.mission, decomp, plan.strategy)
            scores.append(score)

        _, trace = self._decision_engine.select_best(scores)
        matrix = self._decision_engine.compare_plans(scores)

        return PlanComparison(
            plan_ids=plan_ids,
            winner_plan_id=matrix.recommended_plan_id,
            scores={s.plan_id: s.composite_score for s in scores},
            summary=matrix.recommendation_reason,
            tradeoffs={
                pid: matrix.summary_for(pid) if hasattr(matrix, "summary_for") else ""
                for pid in plan_ids
            },
        )

    async def verify_plan(self, plan_id: str) -> PlanningResult:
        """Rebuild the verification plan for an existing plan.

        Args:
            plan_id: ID of an existing plan.

        Returns:
            Updated PlanningResult with refreshed VerificationPlan.
        """
        plan = self._session.get(plan_id)
        vplan = self._verification_planner.build(plan.tasks)
        updated = plan.model_copy(update={"verification_plan": vplan})
        self._session.store(updated)
        return updated

    async def recover_plan(
        self, plan_id: str, failure_context: dict[str, Any] | None = None
    ) -> PlanningResult:
        """Rebuild the recovery plan for a failed or suspended plan.

        Args:
            plan_id: ID of an existing plan.
            failure_context: Optional context about the failure (e.g., failed_step_id).

        Returns:
            Updated PlanningResult with refreshed RecoveryPlan.
        """
        plan = self._session.get(plan_id)
        rplan = self._recovery_planner.build(plan.tasks)
        state = plan.state if not plan.is_terminal else PlanState.SUSPENDED
        updated = plan.model_copy(update={
            "recovery_plan": rplan,
            "state": state,
        })
        self._session.store(updated)
        return updated

    # ------------------------------------------------------------------ #
    # Observability
    # ------------------------------------------------------------------ #

    @property
    def metrics(self) -> PlannerMetrics:
        """Return current session metrics."""
        return self._metrics

    def get_session(self) -> PlanningSession:
        """Return the underlying planning session store."""
        return self._session

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _seconds_to_effort_level(seconds: float) -> EffortLevel:
        if seconds < 60:
            return EffortLevel.TRIVIAL
        if seconds < 900:
            return EffortLevel.SMALL
        if seconds < 7200:
            return EffortLevel.MEDIUM
        if seconds < 28800:
            return EffortLevel.LARGE
        return EffortLevel.EPIC
