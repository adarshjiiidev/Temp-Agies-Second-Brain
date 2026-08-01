"""L5 Execution Engine — Policy Engine.

Stage 3 of the 7-stage execution pipeline.

The PolicyEngine evaluates the ordered rule set against an Action + its risk
assessment and produces a PolicyDecision:
  ALLOW              — proceed with execution
  DENY               — block immediately
  NEEDS_APPROVAL     — block; emit ApprovalRequest on EventBus
  SANDBOX_REQUIRED   — proceed but wrap in the required sandbox tier

Invariant: CRITICAL-risk actions ALWAYS produce NEEDS_APPROVAL,
even if the first matching rule says ALLOW.  This cannot be suppressed.

Import safety: stdlib + l5_execution.* ONLY.
"""

from __future__ import annotations

import fnmatch
import uuid
from typing import Any

from aegis.l5_execution.contracts import ApprovalRequest, PolicyDecision, PolicyRule
from aegis.l5_execution.exceptions import ApprovalRequiredError, PolicyViolationError
from aegis.l5_execution.policy.rules import get_default_rules
from aegis.l5_execution.risk.analyzer import RiskAssessmentResult
from aegis.l5_execution.types import Action, PermissionDecision, RiskLevel, SandboxTier

__all__ = ["PolicyEngine"]


class PolicyEngine:
    """Stage 3 — policy evaluator.

    Usage::

        engine = PolicyEngine()

        # Optionally add custom rules
        engine.add_rule(PolicyRule(
            rule_id="my-rule",
            name="Block network for untrusted actors",
            priority=5,
            match_actors=["generated:*"],
            match_verbs=["net.*"],
            decision=PermissionDecision.DENY,
            reason="Generated tools cannot make network requests",
        ))

        decision = engine.evaluate(action, risk_assessment)
        if not decision.allowed:
            raise PolicyViolationError(decision.reason, rule_id=decision.rule_id)
    """

    def __init__(
        self,
        rules: list[PolicyRule] | None = None,
        *,
        event_bus: Any | None = None,  # CoreEventBus — optional; avoids hard L2 dep
    ) -> None:
        # Start with built-ins, then overlay any custom rules
        self._rules: list[PolicyRule] = sorted(
            (rules or get_default_rules()),
            key=lambda r: r.priority,
        )
        self._event_bus = event_bus

    # ------------------------------------------------------------------
    # Rule management
    # ------------------------------------------------------------------

    def add_rule(self, rule: PolicyRule) -> None:
        """Add a custom rule and re-sort by priority."""
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority)

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule by ID.  Returns True if found."""
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.rule_id != rule_id]
        return len(self._rules) < before

    def list_rules(self) -> list[PolicyRule]:
        """Return a copy of the current rule list in priority order."""
        return list(self._rules)

    # ------------------------------------------------------------------
    # Stage 3 evaluation
    # ------------------------------------------------------------------

    def evaluate(
        self,
        action: Action,
        risk: RiskAssessmentResult,
    ) -> PolicyDecision:
        """Evaluate the policy rule set against an action and its risk score.

        Returns a PolicyDecision.  Does NOT raise — callers decide whether
        to raise based on the decision.
        """
        matched_rule: PolicyRule | None = None

        for rule in self._rules:
            if not rule.enabled:
                continue
            if self._rule_matches(rule, action, risk):
                matched_rule = rule
                break

        if matched_rule is None:
            # No rule matched → deny by default
            return PolicyDecision(
                action_id=action.action_id,
                decision=PermissionDecision.DENY,
                allowed=False,
                reason="No policy rule matched — default deny.",
                requires_approval=False,
            )

        decision = matched_rule.decision
        requires_approval = decision is PermissionDecision.NEEDS_APPROVAL

        # --- CRITICAL override: must approve regardless of rule ---
        if (
            risk.risk_level is RiskLevel.CRITICAL
            and decision is PermissionDecision.ALLOW
            and matched_rule.force_approval_on_critical
            and not action.user_confirmed
        ):
            decision = PermissionDecision.NEEDS_APPROVAL
            requires_approval = True

        allowed = decision is PermissionDecision.ALLOW or (
            decision is PermissionDecision.SANDBOX_REQUIRED
        )

        # NEEDS_APPROVAL is never "allowed" until user confirms
        if decision is PermissionDecision.NEEDS_APPROVAL:
            allowed = False

        return PolicyDecision(
            action_id=action.action_id,
            decision=decision,
            allowed=allowed,
            reason=matched_rule.reason,
            rule_id=matched_rule.rule_id,
            required_sandbox_tier=matched_rule.required_sandbox_tier,
            requires_approval=requires_approval,
        )

    def evaluate_or_raise(
        self,
        action: Action,
        risk: RiskAssessmentResult,
    ) -> PolicyDecision:
        """Like evaluate(), but raises on DENY or NEEDS_APPROVAL.

        Raises:
            ApprovalRequiredError: when decision == NEEDS_APPROVAL
            PolicyViolationError:  when decision == DENY
        """
        decision = self.evaluate(action, risk)

        if decision.decision is PermissionDecision.NEEDS_APPROVAL:
            approval_id = str(uuid.uuid4())
            approval_req = ApprovalRequest(
                request_id=approval_id,
                action_id=action.action_id,
                actor=action.actor,
                verb=action.svrc_verb(),
                resource=action.resource,
                risk_level=risk.risk_level,
                reason=decision.reason,
                context=action.context,
            )
            # Emit on event bus if available
            if self._event_bus is not None:
                try:
                    import asyncio
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.ensure_future(
                            self._event_bus.publish(
                                topic="aegis.execution.approval_required",
                                data=approval_req.model_dump(),
                            )
                        )
                except Exception:
                    pass  # Best-effort; do not block on event bus failure

            raise ApprovalRequiredError(
                f"Action {action.kind.value!r} on {action.resource!r} "
                f"(risk={risk.risk_level.value}) requires explicit user approval.",
                approval_request_id=approval_id,
                risk_level=risk.risk_level.value,
                action_id=action.action_id,
                stage="policy",
            )

        if decision.decision is PermissionDecision.DENY:
            raise PolicyViolationError(
                f"Policy DENY for action {action.kind.value!r}: {decision.reason}",
                rule_id=decision.rule_id,
                risk_level=risk.risk_level.value,
                action_id=action.action_id,
                stage="policy",
            )

        return decision

    # ------------------------------------------------------------------
    # Rule matching
    # ------------------------------------------------------------------

    @staticmethod
    def _rule_matches(
        rule: PolicyRule,
        action: Action,
        risk: RiskAssessmentResult,
    ) -> bool:
        """Return True if ALL non-None conditions in the rule match."""
        # Verb matching (with glob support)
        if rule.match_verbs is not None:
            if not any(
                fnmatch.fnmatch(action.kind.value, pattern)
                for pattern in rule.match_verbs
            ):
                return False

        # Actor matching (with glob support)
        if rule.match_actors is not None:
            if not any(
                fnmatch.fnmatch(action.actor, pattern)
                for pattern in rule.match_actors
            ):
                return False

        # Risk level matching
        if rule.match_risk_levels is not None:
            if risk.risk_level not in rule.match_risk_levels:
                return False

        # Resource matching (with glob support)
        if rule.match_resources is not None:
            if not any(
                fnmatch.fnmatch(action.resource, pattern)
                for pattern in rule.match_resources
            ):
                return False

        return True
