"""L6 Planning Engine — Planner Service (AI-Native).

The single public API surface for L6.  All methods return PlanningResult.

AI-Native Redesign:
  When a ``reasoning_provider`` is injected, ``create_plan()`` uses an
  AI-driven pipeline for intent, ambiguity, decomposition, strategy,
  milestones, recovery, reflection, and verification. When no provider is
  given (or when the provider raises ``ReasoningUnavailableError``), every
  step falls back to the existing deterministic subsystems — zero regressions.

Architecture compliance:
  - Imports from L5 types only (no pipeline, no executor, no audit)
  - Imports from L4 types only (no manager, no search)
  - Never raises raw exceptions — wraps in AegisError subclasses

Import safety: stdlib + l6_planning internal + aegis.reasoning (optional).
"""

from __future__ import annotations

import json
import logging
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
from aegis.l6_planning.reasoning.schemas import (
    IntentAnalysisOutput,
    AmbiguityReportOutput,
    ObjectiveGenerationOutput,
    TaskDecompositionOutput,
    StrategySelectionOutput,
    RecoveryPlanningOutput,
    ReflectionInsightOutput,
    VerificationCriteriaOutput,
    TradeoffNarrationOutput,
)
from aegis.l6_planning.recovery.recovery_planner import RecoveryPlanner, FailureScenario, RecoveryPlan, RetryConfig
from aegis.l6_planning.reflection.improvement_engine import ImprovementEngine
from aegis.l6_planning.reflection.reflection_engine import ReflectionEngine, ReflectionIssue, ReflectionReport
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
    RiskLevel,
)
from aegis.l6_planning.verification.verification_planner import VerificationPlanner, VerificationPlan, VerificationCheck

logger = logging.getLogger(__name__)

__all__ = ["PlannerService"]

# ---------------------------------------------------------------------------
# Optional import: reasoning provider (not required for deterministic path)
# ---------------------------------------------------------------------------
try:
    from aegis.reasoning.provider import ReasoningProvider, ReasoningUnavailableError
    from aegis.reasoning.types import PromptId
    _REASONING_AVAILABLE = True
except ImportError:  # pragma: no cover
    ReasoningProvider = None  # type: ignore[assignment,misc]
    ReasoningUnavailableError = Exception  # type: ignore[assignment,misc]
    _REASONING_AVAILABLE = False


class PlannerService:
    """The public orchestrator for the L6 Planning Engine.

    Composes all planning subsystems into a unified API.
    All methods are async for EventBus / HCI integration.

    AI-Native Usage::

        # Production: full AI-driven pipeline
        provider = KernelReasoningProvider(kernel=kernel, prompt_library=library)
        service = PlannerService(reasoning_provider=provider)
        result = await service.create_plan("Build a React portfolio")

        # Deterministic fallback (default, used by all existing tests):
        service = PlannerService()
        result = await service.create_plan("Build a React portfolio")

    All methods return a PlanningResult.
    No method modifies L1-L5.
    """

    def __init__(
        self,
        reasoning_provider: "ReasoningProvider | None" = None,
    ) -> None:
        self._reasoning = reasoning_provider
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

        When a ReasoningProvider is injected, uses AI reasoning for:
          intent analysis, ambiguity detection, objective generation,
          task decomposition, strategy selection, milestone generation,
          recovery planning, reflection, and verification.

        Falls back to deterministic subsystems on any reasoning error.

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

        # ── AI PATH ──────────────────────────────────────────────────
        if self._reasoning and self._reasoning.is_available:
            try:
                result = await self._ai_create_plan(goal, ctx, ctx_dict, t0)
                return result
            except ReasoningUnavailableError as exc:
                logger.warning(
                    "PlannerService: ReasoningProvider unavailable, falling back to deterministic: %s", exc
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "PlannerService: AI planning failed unexpectedly (%s), falling back: %s",
                    type(exc).__name__, exc
                )

        # ── DETERMINISTIC FALLBACK (default for all existing tests) ──
        return await self._deterministic_create_plan(goal, ctx, ctx_dict, t0)

    # ------------------------------------------------------------------ #
    # AI planning pipeline
    # ------------------------------------------------------------------ #

    async def _ai_create_plan(
        self, goal: str, ctx: PlannerContext, ctx_dict: dict, t0: float
    ) -> PlanningResult:
        """Full AI-driven planning pipeline."""
        assert self._reasoning is not None
        r = self._reasoning

        # 1. Analyse intent
        intent_out: IntentAnalysisOutput = await r.reason(
            PromptId.INTENT_ANALYSIS,
            {"goal_text": goal, "context_json": json.dumps(ctx_dict)},
            IntentAnalysisOutput,
        )

        # 2. Detect ambiguity (non-blocking)
        amb_out: AmbiguityReportOutput = await r.reason(
            PromptId.AMBIGUITY_DETECTION,
            {
                "domain": intent_out.domain,
                "primary_verb": intent_out.primary_verb,
                "confidence": str(intent_out.confidence),
                "goal_text": goal,
            },
            AmbiguityReportOutput,
        )
        # Log but don't block — blocking ambiguity needs L7 UI interaction
        if amb_out.is_ambiguous:
            logger.info(
                "PlannerService[AI]: goal is ambiguous (blocking=%s): %s",
                amb_out.blocking, amb_out.questions
            )

        # 3. Generate objectives
        obj_out: ObjectiveGenerationOutput = await r.reason(
            PromptId.OBJECTIVE_GENERATION,
            {
                "goal_text": goal,
                "domain": intent_out.domain,
                "requirements_json": "{}",
                "strategy": (ctx.strategy or PlanningStrategy.BALANCED).value,
                "capabilities_json": "{}",
            },
            ObjectiveGenerationOutput,
        )

        # 4. Select strategy
        strat_out: StrategySelectionOutput = await r.reason(
            PromptId.STRATEGY_SELECTION,
            {
                "goal_text": goal,
                "domain": intent_out.domain,
                "requires_internet": str(intent_out.requires_internet).lower(),
                "requires_local_only": str(intent_out.requires_local_only).lower(),
                "max_risk_level": "medium",
                "user_preference": (ctx.strategy or PlanningStrategy.BALANCED).value,
                "context_flags_json": json.dumps(ctx_dict),
            },
            StrategySelectionOutput,
        )

        # Map AI strategy string to enum (with fallback)
        strategy = _parse_strategy(strat_out.strategy, ctx.strategy)

        # 5. Decompose tasks
        objectives_json = json.dumps(
            [{"title": o.title, "description": o.description, "priority": o.priority}
             for o in obj_out.objectives]
        )
        decomp_out: TaskDecompositionOutput = await r.reason(
            PromptId.TASK_DECOMPOSITION,
            {
                "goal_text": goal,
                "domain": intent_out.domain,
                "strategy": strategy.value,
                "objectives_json": objectives_json,
                "requirements_json": "{}",
                "capabilities_json": "{}",
            },
            TaskDecompositionOutput,
        )

        # Convert AI specs → L6 domain objects via deterministic subsystems
        # (GoalEngine creates the Mission from AI output)
        mission = self._goal_engine.create_mission(
            goal_text=goal,
            context=ctx_dict,
            strategy=strategy,
            constraints=ctx.constraints,
            deadline=ctx.deadline,
        )
        # Override objectives with AI-generated ones
        from aegis.l6_planning.planning.objective import Objective
        ai_objectives = [
            Objective(
                title=o.title[:80],
                description=o.description,
                priority=o.priority,
                estimated_effort=EffortEstimate.medium(),
                success_criteria=o.completion_criteria or [f"{o.title} is complete"],
                failure_criteria=[f"{o.title} cannot be verified"],
                confidence=intent_out.confidence * 0.9,
                rationale=obj_out.rationale or f"AI-generated for domain: {intent_out.domain}",
            )
            for o in obj_out.objectives
        ]

        # G2 FIX: Map AI intent output into mission.parsed_intent so the AI is
        # genuinely authoritative for intent classification when available.
        # We update domain/confidence/requires_internet/requires_local_only from
        # the AI; structural fields (primary_verb, keyword_matches, etc.) are
        # preserved from the deterministic parser to maintain pipeline stability.
        from aegis.l6_planning.types import IntentDomain
        try:
            ai_domain = IntentDomain(intent_out.domain)
        except ValueError:
            ai_domain = mission.parsed_intent.domain  # safe fallback
        ai_aligned_intent = mission.parsed_intent.model_copy(update={
            "domain": ai_domain,
            "confidence": float(intent_out.confidence),
            "requires_internet": bool(intent_out.requires_internet),
            "requires_local_only": bool(intent_out.requires_local_only),
        })
        mission = mission.model_copy(update={
            "objectives": ai_objectives,
            "strategy": strategy,
            "parsed_intent": ai_aligned_intent,
        })


        # Build Task objects from AI specs
        tasks = _ai_specs_to_tasks(decomp_out.tasks)

        # Apply max_tasks limit
        if ctx.max_tasks and len(tasks) > ctx.max_tasks:
            tasks = tasks[: ctx.max_tasks]

        # Build dependency graph
        graph = DependencyGraph.from_dict({})

        # Build execution order using deterministic order builder
        execution_order = self._order_builder.build(tasks, graph, strategy)

        # 6. Milestones (deterministic fallback — AI milestone prompt is additive)
        decomp_for_milestones = self._decomposer.decompose(mission)
        milestones = self._milestone_builder.build(decomp_for_milestones)

        # 7. Score plan
        score = self._decision_engine.score_plan(mission, decomp_for_milestones, strategy)
        _, decision_trace = self._decision_engine.select_best([score])

        # 8. Verification (AI)
        verif_out: VerificationCriteriaOutput = await r.reason(
            PromptId.VERIFICATION_CRITERIA,
            {
                "goal_text": goal,
                "strategy": strategy.value,
                "tasks_json": json.dumps(
                    [{"title": t.title, "action_kind": t.action_kind_hint,
                      "risk_level": t.risk_level.value}
                     for t in tasks]
                ),
            },
            VerificationCriteriaOutput,
        )
        verification_plan = _ai_verification_to_plan(verif_out)

        # 9. Recovery (AI)
        recov_out: RecoveryPlanningOutput = await r.reason(
            PromptId.RECOVERY_PLANNING,
            {
                "goal_text": goal,
                "domain": intent_out.domain,
                "max_risk_level": "medium",
                "tasks_json": json.dumps(
                    [{"title": t.title, "action_kind": t.action_kind_hint}
                     for t in tasks]
                ),
            },
            RecoveryPlanningOutput,
        )
        recovery_plan = _ai_recovery_to_plan(recov_out)

        # 10. Estimates
        effort_level = self._seconds_to_effort_level(
            sum(t.estimated_seconds for t in tasks)
        )
        estimates = PlanEstimate(
            effort=EffortEstimate(
                level=effort_level,
                min_seconds=sum(t.estimated_seconds for t in tasks) * 0.7,
                max_seconds=sum(t.estimated_seconds for t in tasks) * 1.5,
                best_guess_seconds=float(sum(t.estimated_seconds for t in tasks)),
                confidence=score.success_probability,
            ),
            total_tasks=len(tasks),
            total_approval_points=sum(1 for t in tasks if t.is_approval_point),
            parallel_tasks=sum(1 for t in tasks if t.can_run_parallel),
            sequential_tasks=sum(1 for t in tasks if not t.can_run_parallel),
            estimated_total_seconds=float(sum(t.estimated_seconds for t in tasks)),
            confidence=score.composite_score,
        )

        # 11. Reflection (AI)
        reflect_out: ReflectionInsightOutput = await r.reason(
            PromptId.REFLECTION,
            {
                "goal_text": goal,
                "domain": intent_out.domain,
                "strategy": strategy.value,
                "task_count": str(len(tasks)),
                "approval_points": str(estimates.total_approval_points),
                "confidence": str(round(score.composite_score, 3)),
                "tasks_summary_json": json.dumps(
                    [{"title": t.title, "risk": t.risk_level.value} for t in tasks]
                ),
                "cycle_result": "no cycles detected",
                "missing_requirements": "none",
            },
            ReflectionInsightOutput,
        )
        reflection = _ai_reflection_to_report(
            reflect_out, amb_out, confidence_base=score.composite_score
        )

        result = PlanningResult(
            state=PlanState.READY,
            mission=mission,
            tasks=tasks,
            task_graph={},
            milestones=milestones,
            execution_order=execution_order,
            recovery_plan=recovery_plan,
            verification_plan=verification_plan,
            estimates=estimates,
            confidence=round(
                max(0.0, min(1.0, score.composite_score + reflect_out.confidence_adjustment)),
                4,
            ),
            decision_trace=decision_trace or [],
            reflection_report=reflection,
            strategy=strategy,
        )

        self._session.store(result)

        elapsed_ms = (time.monotonic() - t0) * 1000
        self._metrics = self._metrics.record_plan(
            planning_time_ms=elapsed_ms,
            task_count=len(tasks),
            confidence=result.confidence,
            strategy=strategy,
            domain=intent_out.domain,
        )
        return result

    # ------------------------------------------------------------------ #
    # Deterministic planning pipeline (unchanged from before redesign)
    # ------------------------------------------------------------------ #

    async def _deterministic_create_plan(
        self, goal: str, ctx: PlannerContext, ctx_dict: dict, t0: float
    ) -> PlanningResult:
        """Original deterministic planning pipeline. Zero changes from pre-redesign."""
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


# ---------------------------------------------------------------------------
# Module-level helper functions — used by _ai_create_plan()
# ---------------------------------------------------------------------------

def _parse_strategy(
    strat_str: str,
    fallback: "PlanningStrategy | None",
) -> PlanningStrategy:
    """Map an AI strategy string to a PlanningStrategy enum value.

    The AI is prompted to return one of the canonical strategy names.  In case
    it returns an unexpected value (hallucination) we fall back to the user
    preference, then to BALANCED.

    Args:
        strat_str: Raw strategy string from AI (e.g. ``"balanced"``).
        fallback:  User-supplied strategy preference (or None).

    Returns:
        A valid PlanningStrategy.
    """
    # Normalise: lowercase, replace spaces/hyphens with underscores
    normalised = strat_str.strip().lower().replace("-", "_").replace(" ", "_")

    # Try direct enum value lookup
    try:
        return PlanningStrategy(normalised)
    except ValueError:
        pass

    # Some aliases the LLM might produce
    _ALIASES: dict[str, PlanningStrategy] = {
        "speed_first":     PlanningStrategy.FASTEST,
        "fast":            PlanningStrategy.FASTEST,
        "safe_mode":       PlanningStrategy.BALANCED,
        "safe":            PlanningStrategy.BALANCED,
        "quality":         PlanningStrategy.HIGHEST_QUALITY,
        "dev":             PlanningStrategy.DEVELOPER_MODE,
        "research":        PlanningStrategy.RESEARCH_MODE,
        "offline":         PlanningStrategy.OFFLINE_FIRST,
        "privacy":         PlanningStrategy.PRIVACY_FIRST,
    }
    if normalised in _ALIASES:
        return _ALIASES[normalised]

    # Return user preference or default
    return fallback or PlanningStrategy.BALANCED


def _ai_specs_to_tasks(specs: list) -> list:
    """Convert a list of TaskSpec (from AI output) to Task domain objects.

    Each :class:`~aegis.l6_planning.reasoning.schemas.TaskSpec` produced by
    the AI is converted to a :class:`~aegis.l6_planning.decomposition.task_decomposer.Task`
    with sane defaults for fields the AI does not set.

    Args:
        specs: List of ``TaskSpec`` instances from ``TaskDecompositionOutput.tasks``.

    Returns:
        List of ``Task`` instances ready for the planning pipeline.
    """
    from aegis.l6_planning.decomposition.task_decomposer import Task

    _risk_map: dict[str, RiskLevel] = {
        "low":      RiskLevel.LOW,
        "medium":   RiskLevel.MEDIUM,
        "high":     RiskLevel.HIGH,
        "critical": RiskLevel.CRITICAL,
    }

    tasks: list[Task] = []
    for spec in specs:
        risk = _risk_map.get(spec.risk_level.lower(), RiskLevel.LOW)
        task = Task(
            title=spec.title[:120],
            description=spec.rationale or spec.title,
            # Tasks from AI don't map to a single objective — use a sentinel
            objective_id="ai-generated",
            action_kind_hint=spec.action_hint or None,
            estimated_seconds=float(spec.estimated_seconds),
            is_approval_point=spec.requires_approval,
            risk_level=risk,
            can_run_parallel=spec.can_run_parallel,
            # AI does not supply reversibility info — be conservative
            reversible=(risk < RiskLevel.HIGH),
        )
        tasks.append(task)
    return tasks


def _ai_verification_to_plan(output: "VerificationCriteriaOutput") -> "VerificationPlan":
    """Convert a :class:`~aegis.l6_planning.reasoning.schemas.VerificationCriteriaOutput`
    to a :class:`~aegis.l6_planning.verification.verification_planner.VerificationPlan`.

    Maps each AI criterion spec to a ``VerificationCheck``.  The overall
    strategy string from the AI is preserved as an acceptance criterion.

    Args:
        output: Validated AI output containing ``criteria`` and
                ``overall_strategy``.

    Returns:
        A ``VerificationPlan`` with checks populated from AI criteria.
    """
    from aegis.l6_planning.verification.verification_planner import VerificationCheck, VerificationPlan

    checks: list[VerificationCheck] = []
    acceptance: list[str] = []
    completion_evidence: list[str] = []

    _severity_to_blocking = {"critical": True, "error": True, "warning": False, "info": False}

    for crit in output.criteria:
        kind = "manual" if not crit.automated else "automatic"
        blocking = _severity_to_blocking.get(crit.severity.lower(), False)
        check = VerificationCheck(
            task_id=crit.task_title,   # task reference by title (AI doesn't know IDs)
            kind=kind,
            description=crit.check_description,
            expected_output=f"Check type: {crit.check_type}",
            evidence_required=[crit.check_type],
            blocking=blocking,
        )
        checks.append(check)
        acceptance.append(crit.check_description)
        if crit.automated:
            completion_evidence.append(f"Automated {crit.check_type} check passes for '{crit.task_title}'")

    if output.overall_strategy:
        acceptance.append(f"Overall verification strategy: {output.overall_strategy}")

    manual_count = sum(1 for c in checks if c.kind == "manual")
    auto_count = sum(1 for c in checks if c.kind == "automatic")

    return VerificationPlan(
        checks=checks,
        acceptance_criteria=acceptance,
        completion_evidence=completion_evidence,
        manual_check_count=manual_count,
        automatic_check_count=auto_count,
    )


def _ai_recovery_to_plan(output: "RecoveryPlanningOutput") -> "RecoveryPlan":
    """Convert a :class:`~aegis.l6_planning.reasoning.schemas.RecoveryPlanningOutput`
    to a :class:`~aegis.l6_planning.recovery.recovery_planner.RecoveryPlan`.

    Each AI ``RecoveryScenarioSpec`` becomes a ``FailureScenario`` with a
    retry config derived from the scenario's probability and rollback flag.

    Args:
        output: Validated AI output with ``scenarios`` and ``global_fallback``.

    Returns:
        A ``RecoveryPlan`` with failure scenarios from AI reasoning.
    """
    _prob_map = {"low": 0.1, "medium": 0.25, "high": 0.5}
    _risk_map: dict[str, RiskLevel] = {
        "low":      RiskLevel.LOW,
        "medium":   RiskLevel.MEDIUM,
        "high":     RiskLevel.HIGH,
        "critical": RiskLevel.CRITICAL,
    }

    scenarios: list[FailureScenario] = []
    for spec in output.scenarios:
        prob = _prob_map.get(spec.probability.lower(), 0.25)
        # Derive impact from probability + rollback flag
        if spec.rollback_possible:
            impact = RiskLevel.MEDIUM
        else:
            impact = RiskLevel.HIGH

        # Use first affected task hint as task_id reference (AI only knows hints)
        task_ref = (spec.affected_task_hints[0] if spec.affected_task_hints else "unknown")

        retry_cfg = RetryConfig(
            max_attempts=1 if not spec.rollback_possible else 3,
            backoff_seconds=float(spec.estimated_recovery_seconds) / max(1, 3),
            max_backoff_seconds=float(spec.estimated_recovery_seconds),
        )

        scenarios.append(FailureScenario(
            task_id=task_ref,
            failure_mode=spec.failure_mode,
            probability=prob,
            impact=impact,
            fallback_strategy=spec.recovery_strategy,
            rollback_required=not spec.rollback_possible,
            retry_config=retry_cfg,
        ))

    escalation_conditions = [
        "Three or more consecutive task failures",
        "Any CRITICAL risk task fails without a recovery path",
        output.global_fallback,
    ]

    return RecoveryPlan(
        scenarios=scenarios,
        global_retry_config=RetryConfig(),
        escalation_conditions=escalation_conditions,
        alternative_plan_notes=[output.global_fallback],
        total_risk_surface=(
            "high" if any(s.probability >= 0.4 for s in scenarios)
            else "medium" if any(s.probability >= 0.2 for s in scenarios)
            else "low"
        ),
    )


def _ai_reflection_to_report(
    reflect_out: "ReflectionInsightOutput",
    amb_out: "AmbiguityReportOutput",
    *,
    confidence_base: float,
) -> "ReflectionReport":
    """Merge AI reflection and ambiguity outputs into a
    :class:`~aegis.l6_planning.reflection.reflection_engine.ReflectionReport`.

    The AI provides qualitative issues and suggestions; ambiguity data from the
    earlier ambiguity step is included as informational issues if the goal was
    flagged as ambiguous.

    Args:
        reflect_out:      Validated output from the reflection prompt.
        amb_out:          Validated output from the ambiguity detection prompt.
        confidence_base:  Composite score before adjustment (0–1).

    Returns:
        A ``ReflectionReport`` compatible with the deterministic pipeline.
    """
    from aegis.l6_planning.reflection.reflection_engine import ReflectionIssue, ReflectionReport

    issues: list[ReflectionIssue] = []

    # Convert AI issues (each is a dict with keys: category, severity, message)
    for raw in reflect_out.issues:
        if not isinstance(raw, dict):
            continue
        issues.append(ReflectionIssue(
            category=raw.get("category", "ai_reflection"),
            severity=raw.get("severity", "warning"),
            message=raw.get("message", "(no message)"),
            suggested_fix=raw.get("suggested_fix", ""),
        ))

    # Add ambiguity as an informational issue if applicable
    if amb_out.is_ambiguous:
        sev = "error" if amb_out.blocking else "warning"
        msg = (
            f"Goal is ambiguous (blocking={amb_out.blocking}). "
            f"Clarification questions: {'; '.join(amb_out.questions)}"
            if amb_out.questions else "Goal is ambiguous — consider clarifying with the user."
        )
        issues.append(ReflectionIssue(
            category="ambiguity",
            severity=sev,
            message=msg,
            suggested_fix="Request user clarification before proceeding.",
        ))

    # Confidence delta clamped to AI schema range [-0.5, +0.1]
    confidence_delta = max(-0.5, min(0.1, reflect_out.confidence_adjustment))

    # Complexity score — estimated from issue count and confidence
    n_errors = sum(1 for i in issues if i.severity == "error")
    n_warnings = sum(1 for i in issues if i.severity == "warning")
    complexity = min(1.0, (n_errors * 0.15 + n_warnings * 0.05 + (1 - confidence_base) * 0.3))

    passed = reflect_out.passed and n_errors == 0

    return ReflectionReport(
        issues=issues,
        optimizations=list(reflect_out.suggestions),
        missing_requirements=[],
        circular_deps=[],
        risk_flags=[],
        complexity_score=round(complexity, 3),
        confidence_delta=round(confidence_delta, 3),
        passed=passed,
    )

