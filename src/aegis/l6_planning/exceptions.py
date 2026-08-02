"""L6 Planning Engine — Exception hierarchy.

All L6 exceptions are AegisError subclasses, using the E60xxx error code range.

Import safety: aegis.l1_core.errors only.
"""

from __future__ import annotations

from aegis.l1_core.errors import AegisError
from aegis.l1_core.errors.codes import ErrorCode

__all__ = [
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


class PlanningError(AegisError):
    """Base class for all L6 Planning Engine errors."""


class PlanGoalInvalidError(PlanningError):
    """Goal text is empty, malformed, or logically invalid."""

    def __init__(self, detail: str = "") -> None:
        super().__init__(
            str(ErrorCode.PLAN_GOAL_INVALID),
            f"Goal is invalid: {detail}" if detail else ErrorCode.PLAN_GOAL_INVALID.message,
            severity="medium",
        )


class PlanAmbiguousIntentError(PlanningError):
    """Intent is ambiguous and requires clarification before planning."""

    def __init__(self, detail: str = "", clarifications: list[str] | None = None) -> None:
        msg = f"Intent is ambiguous: {detail}" if detail else ErrorCode.PLAN_AMBIGUOUS_INTENT.message
        super().__init__(str(ErrorCode.PLAN_AMBIGUOUS_INTENT), msg, severity="low")
        self.clarifications: list[str] = clarifications or []


class PlanCircularDependencyError(PlanningError):
    """Circular dependency detected in the task graph."""

    def __init__(self, cycle: list[str] | None = None) -> None:
        cycle_str = " → ".join(cycle) if cycle else "unknown"
        super().__init__(
            str(ErrorCode.PLAN_CIRCULAR_DEPENDENCY),
            f"{ErrorCode.PLAN_CIRCULAR_DEPENDENCY.message}: {cycle_str}",
            severity="high",
        )
        self.cycle: list[str] = cycle or []


class PlanDecompositionFailedError(PlanningError):
    """Goal could not be decomposed into a valid task structure."""

    def __init__(self, detail: str = "") -> None:
        super().__init__(
            str(ErrorCode.PLAN_DECOMPOSITION_FAILED),
            f"Decomposition failed: {detail}" if detail else ErrorCode.PLAN_DECOMPOSITION_FAILED.message,
            severity="high",
        )


class PlanNoViableStrategyError(PlanningError):
    """No viable planning strategy found given the constraints."""

    def __init__(self, detail: str = "") -> None:
        super().__init__(
            str(ErrorCode.PLAN_NO_VIABLE_STRATEGY),
            f"No viable strategy: {detail}" if detail else ErrorCode.PLAN_NO_VIABLE_STRATEGY.message,
            severity="medium",
        )


class PlanConstraintViolatedError(PlanningError):
    """Plan violates one or more hard constraints."""

    def __init__(self, constraint: str = "", detail: str = "") -> None:
        msg = f"Constraint '{constraint}' violated: {detail}" if constraint else ErrorCode.PLAN_CONSTRAINT_VIOLATED.message
        super().__init__(str(ErrorCode.PLAN_CONSTRAINT_VIOLATED), msg, severity="high")
        self.constraint = constraint


class PlanNotFoundError(PlanningError):
    """Plan ID not found in the active planning session."""

    def __init__(self, plan_id: str = "") -> None:
        super().__init__(
            str(ErrorCode.PLAN_NOT_FOUND),
            f"Plan not found: {plan_id!r}" if plan_id else ErrorCode.PLAN_NOT_FOUND.message,
            severity="low",
        )


class PlanAlreadyCancelledError(PlanningError):
    """Plan is already in CANCELLED state."""

    def __init__(self, plan_id: str = "") -> None:
        super().__init__(
            str(ErrorCode.PLAN_ALREADY_CANCELLED),
            f"Plan {plan_id!r} is already cancelled" if plan_id else ErrorCode.PLAN_ALREADY_CANCELLED.message,
            severity="low",
        )


class PlanSessionExpiredError(PlanningError):
    """Planning session has expired."""

    def __init__(self, session_id: str = "") -> None:
        super().__init__(
            str(ErrorCode.PLAN_SESSION_EXPIRED),
            f"Session {session_id!r} has expired" if session_id else ErrorCode.PLAN_SESSION_EXPIRED.message,
            severity="medium",
        )
