"""AEGIS L6 — Cognitive Planning & Agent Orchestration Engine.

Public API surface for the L6 Planning layer.

Usage::

    from aegis.l6_planning import PlannerService, PlannerContext, PlanningResult

    service = PlannerService()
    result = await service.create_plan("Build a React portfolio website")
    print(result.summary())

Architecture:
    L6 is a pure planning layer. It never executes actions.
    It never calls L3 (LLMs) directly in Prompt 06.
    It only imports from L5/L4 as read-only type references.

Layer boundary guarantee:
    - No import from aegis.l5_execution.pipeline
    - No import from aegis.l4_memory.manager
    - No import from aegis.l3_intelligence
    - All output is a typed PlanningResult (no ActionResult)
"""

from aegis.l6_planning.exceptions import (
    PlanAmbiguousIntentError,
    PlanAlreadyCancelledError,
    PlanCircularDependencyError,
    PlanConstraintViolatedError,
    PlanDecompositionFailedError,
    PlanGoalInvalidError,
    PlanningError,
    PlanNoViableStrategyError,
    PlanNotFoundError,
    PlanSessionExpiredError,
)
from aegis.l6_planning.orchestration.planner_service import PlannerService
from aegis.l6_planning.orchestration.planning_session import PlanningSession
from aegis.l6_planning.planning_result import PlanningResult
from aegis.l6_planning.state.planner_context import PlannerContext
from aegis.l6_planning.state.planner_state import PlannerState
from aegis.l6_planning.types import (
    Constraint,
    ConstraintKind,
    DecisionTraceEntry,
    EffortEstimate,
    EffortLevel,
    ExecutionStep,
    IntentDomain,
    Milestone,
    PlanComparison,
    PlanEstimate,
    PlanScore,
    PlanningStrategy,
    PlanState,
    ResourceSpec,
    RiskLevel,
    ScoringWeights,
    ValidationIssue,
)

__all__ = [
    # Primary API
    "PlannerService",
    "PlanningSession",
    "PlanningResult",
    "PlannerContext",
    "PlannerState",
    # Enums
    "PlanState",
    "PlanningStrategy",
    "IntentDomain",
    "ConstraintKind",
    "EffortLevel",
    "RiskLevel",
    # Data models
    "PlanEstimate",
    "PlanComparison",
    "PlanScore",
    "ScoringWeights",
    "Constraint",
    "ResourceSpec",
    "ValidationIssue",
    "Milestone",
    "ExecutionStep",
    "EffortEstimate",
    "DecisionTraceEntry",
    # Exceptions
    "PlanningError",
    "PlanGoalInvalidError",
    "PlanAmbiguousIntentError",
    "PlanCircularDependencyError",
    "PlanDecompositionFailedError",
    "PlanNoViableStrategyError",
    "PlanConstraintViolatedError",
    "PlanNotFoundError",
    "PlanAlreadyCancelledError",
    "PlanSessionExpiredError",
]

__version__ = "0.6.0"
