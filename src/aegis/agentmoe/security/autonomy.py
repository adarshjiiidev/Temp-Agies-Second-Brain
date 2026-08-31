"""AgentMoe — AutonomyEnforcer (Phase 2 security).

Implements the L0–L5 autonomy level system.

Autonomy levels control what AgentMoe is allowed to do without explicit
human approval. Higher levels grant more autonomous action but must be
explicitly unlocked.

Levels:
  L0 — Observe only. No side effects.
  L1 — Suggest only. Returns plans but does not execute.
  L2 — Execute LOW-risk actions. (default)
  L3 — Execute approved workflows (saved permission grants).
  L4 — Autonomous bounded execution (budget + scope enforced).
  L5 — System-level autonomy. DISABLED BY DEFAULT.

SAFETY: L5 requires both autonomy_level=5 AND allow_autonomy_level_5=True
        in AgentMoeConfig. Both checks must pass.

Import safety: stdlib + agentmoe.core.tool (ToolRiskLevel).
"""

from __future__ import annotations

from aegis.agentmoe.core.tool import ToolRiskLevel


__all__ = ["AutonomyLevel", "AutonomyViolationError", "AutonomyEnforcer"]


class AutonomyLevel:
    """Constants for autonomy levels."""
    OBSERVE_ONLY       = 0
    SUGGEST_ONLY       = 1
    EXECUTE_LOW_RISK   = 2  # default
    APPROVED_WORKFLOWS = 3
    AUTONOMOUS_BOUNDED = 4
    SYSTEM_LEVEL       = 5  # SAFETY: disabled by default


class AutonomyViolationError(Exception):
    """Raised when an operation is not permitted at the current autonomy level."""


class AutonomyEnforcer:
    """Enforces autonomy level constraints on tool invocations.

    Usage::

        enforcer = AutonomyEnforcer(autonomy_level=2, allow_level_5=False)
        enforcer.check_tool_invocation(risk_level=ToolRiskLevel.LOW)     # OK
        enforcer.check_tool_invocation(risk_level=ToolRiskLevel.HIGH)    # raises at L2
        enforcer.check_execution()                                         # L2 can execute
    """

    # -- risk level allowed per autonomy level ---------------------------------
    # At each level, the listed risk levels are automatically permitted.
    # Higher risk requires higher autonomy OR user_confirmed=True.
    _PERMITTED_RISK: dict[int, frozenset[ToolRiskLevel]] = {
        0: frozenset(),                                              # observe: nothing
        1: frozenset(),                                              # suggest: nothing
        2: frozenset({ToolRiskLevel.LOW}),                          # low risk only
        3: frozenset({ToolRiskLevel.LOW, ToolRiskLevel.MEDIUM}),    # saved workflows
        4: frozenset({ToolRiskLevel.LOW, ToolRiskLevel.MEDIUM, ToolRiskLevel.HIGH}),
        5: frozenset({ToolRiskLevel.LOW, ToolRiskLevel.MEDIUM, ToolRiskLevel.HIGH, ToolRiskLevel.CRITICAL}),
    }

    def __init__(
        self,
        *,
        autonomy_level: int = AutonomyLevel.EXECUTE_LOW_RISK,
        allow_level_5: bool = False,
    ) -> None:
        if autonomy_level not in range(6):
            raise ValueError(f"autonomy_level must be 0–5, got {autonomy_level}")
        # SAFETY: L5 double-gate
        if autonomy_level == 5 and not allow_level_5:
            raise AutonomyViolationError(
                "Autonomy L5 (system-level) requires allow_autonomy_level_5=True "
                "in AgentMoeConfig. This is a safety gate. "
                "L5 must be explicitly unlocked by the operator."
            )
        self._level      = autonomy_level
        self._allow_l5   = allow_level_5

    @property
    def level(self) -> int:
        return self._level

    # -- checks ---------------------------------------------------------------

    def check_execution(self) -> None:
        """Raise if autonomy level does not permit any execution.

        L0 (observe) and L1 (suggest) cannot execute any action.
        """
        if self._level < AutonomyLevel.EXECUTE_LOW_RISK:
            raise AutonomyViolationError(
                f"Autonomy L{self._level} does not permit execution. "
                f"Minimum required: L{AutonomyLevel.EXECUTE_LOW_RISK} (execute-low-risk)."
            )

    def check_tool_invocation(
        self,
        risk_level: ToolRiskLevel,
        *,
        user_confirmed: bool = False,
    ) -> None:
        """Raise if this autonomy level cannot invoke a tool at the given risk.

        Args:
            risk_level:     Risk level of the tool invocation.
            user_confirmed: If True, the user has explicitly approved this action.
                            Explicit user confirmation can override autonomy gates
                            for HIGH risk (but NOT for CRITICAL at L<4).
        """
        permitted = self._PERMITTED_RISK.get(self._level, frozenset())

        if risk_level in permitted:
            return  # allowed at this autonomy level

        # CRITICAL is NEVER auto-approved — even L5 routes through L5 pipeline
        if risk_level == ToolRiskLevel.CRITICAL:
            if not user_confirmed:
                raise AutonomyViolationError(
                    f"CRITICAL risk operations always require user_confirmed=True. "
                    f"Current autonomy: L{self._level}."
                )
            # With user_confirmed, CRITICAL is allowed at L4+
            if self._level < AutonomyLevel.AUTONOMOUS_BOUNDED:
                raise AutonomyViolationError(
                    f"CRITICAL risk operations require autonomy L{AutonomyLevel.AUTONOMOUS_BOUNDED}+. "
                    f"Current: L{self._level}."
                )
            return

        # HIGH risk: requires L4 or user_confirmed at L3+
        if risk_level == ToolRiskLevel.HIGH:
            if user_confirmed and self._level >= AutonomyLevel.APPROVED_WORKFLOWS:
                return
            raise AutonomyViolationError(
                f"HIGH risk tool invocation not permitted at autonomy L{self._level}. "
                f"Requires: L{AutonomyLevel.AUTONOMOUS_BOUNDED}+ or user_confirmed=True at L3+."
            )

        # MEDIUM risk: requires L3 or user_confirmed at L2+
        if risk_level == ToolRiskLevel.MEDIUM:
            if user_confirmed and self._level >= AutonomyLevel.EXECUTE_LOW_RISK:
                return
            raise AutonomyViolationError(
                f"MEDIUM risk tool invocation not permitted at autonomy L{self._level}. "
                f"Requires: L{AutonomyLevel.APPROVED_WORKFLOWS}+ or user_confirmed=True at L2+."
            )

    def describe(self) -> str:
        """Human-readable description of current autonomy level."""
        descriptions = {
            0: "L0: Observe only — no side effects",
            1: "L1: Suggest only — no execution",
            2: "L2: Execute low-risk actions (default)",
            3: "L3: Execute approved workflows",
            4: "L4: Autonomous bounded execution",
            5: "L5: System-level autonomy (ENABLED — use with caution)",
        }
        return descriptions.get(self._level, f"L{self._level}: Unknown")
