"""L5 Execution Engine — Built-in Policy Rules.

Default policy rule set covering the most common verbs.
Rules are evaluated in priority order (lower number = higher priority).
The first matching rule wins.

Rules may be overridden by loading custom YAML policy files through
the PolicyEngine.

Import safety: stdlib + l5_execution.types + l5_execution.contracts ONLY.
"""

from __future__ import annotations

from aegis.l5_execution.contracts import PolicyRule
from aegis.l5_execution.types import PermissionDecision, RiskLevel, SandboxTier

__all__ = ["BUILTIN_RULES", "get_default_rules"]


def get_default_rules() -> list[PolicyRule]:
    """Return the default policy rule set in priority order."""
    return list(BUILTIN_RULES)


# ---------------------------------------------------------------------------
# Built-in rules (ordered by priority — lower = evaluated first)
# ---------------------------------------------------------------------------

BUILTIN_RULES: tuple[PolicyRule, ...] = (

    # --- CRITICAL: aegis core mutation — always deny unless explicit user approval ---
    PolicyRule(
        rule_id="builtin-aegis-core-deny",
        name="Deny aegis.core.mutate without explicit approval",
        priority=1,
        match_verbs=["aegis.core.mutate", "aegis.user.impersonate"],
        decision=PermissionDecision.NEEDS_APPROVAL,
        required_sandbox_tier=SandboxTier.T3_DOCKER,
        reason="aegis TCB mutations require explicit user approval",
    ),

    # --- HIGH: Shell execution — always requires approval + T2 sandbox minimum ---
    # Architecture spec (05_SECURITY_PRIVACY, 07_AI_STRATEGY §4): arbitrary code
    # execution MUST NOT proceed without explicit user confirmation (user_confirmed=True).
    # required_sandbox_tier is retained so that when approval IS granted, the pipeline
    # enforces T2 subprocess isolation for execution.
    PolicyRule(
        rule_id="builtin-shell-sandbox",
        name="Shell execution requires explicit user approval and T2 sandbox",
        priority=10,
        match_verbs=["shell.exec", "proc.spawn"],
        match_risk_levels=[RiskLevel.HIGH, RiskLevel.CRITICAL],
        decision=PermissionDecision.NEEDS_APPROVAL,
        required_sandbox_tier=SandboxTier.T2_SUBPROCESS,
        reason="Shell and process execution require explicit user approval and run in T2 subprocess sandbox",
    ),

    # --- HIGH: Git push — always requires approval ---
    PolicyRule(
        rule_id="builtin-git-push-approval",
        name="git.push always requires approval",
        priority=20,
        match_verbs=["git.push"],
        decision=PermissionDecision.NEEDS_APPROVAL,
        reason="git.push has irreversible remote side effects and always requires explicit user approval",
    ),

    # --- HIGH: Docker exec/run — T3 minimum ---
    PolicyRule(
        rule_id="builtin-docker-t3",
        name="Docker operations require T3 sandbox",
        priority=30,
        match_verbs=["docker.run", "docker.exec", "docker.build"],
        decision=PermissionDecision.SANDBOX_REQUIRED,
        required_sandbox_tier=SandboxTier.T3_DOCKER,
        reason="Docker operations run inside Docker container (T3)",
    ),

    # --- HIGH: File delete — always requires approval ---
    PolicyRule(
        rule_id="builtin-fs-delete-approval",
        name="fs.delete requires user approval",
        priority=40,
        match_verbs=["fs.delete"],
        match_risk_levels=[RiskLevel.HIGH, RiskLevel.CRITICAL],
        decision=PermissionDecision.NEEDS_APPROVAL,
        reason="Filesystem delete is irreversible and requires explicit user confirmation",
    ),

    # --- MEDIUM: Python execution — T1 or T2 depending on risk ---
    PolicyRule(
        rule_id="builtin-python-exec-t1",
        name="Python exec in T1 for LOW risk",
        priority=50,
        match_verbs=["python.exec", "python.eval"],
        match_risk_levels=[RiskLevel.LOW, RiskLevel.MEDIUM],
        decision=PermissionDecision.SANDBOX_REQUIRED,
        required_sandbox_tier=SandboxTier.T1_AST,
        reason="Low-risk Python execution runs in AST jail (T1)",
    ),

    PolicyRule(
        rule_id="builtin-python-exec-t2",
        name="Python exec in T2 for HIGH risk",
        priority=51,
        match_verbs=["python.exec", "python.eval"],
        match_risk_levels=[RiskLevel.HIGH, RiskLevel.CRITICAL],
        decision=PermissionDecision.SANDBOX_REQUIRED,
        required_sandbox_tier=SandboxTier.T2_SUBPROCESS,
        reason="High-risk Python execution runs in subprocess sandbox (T2)",
    ),

    # --- CRITICAL: Any action from generated/untrusted actors — approval required ---
    PolicyRule(
        rule_id="builtin-generated-approval",
        name="Generated tools always require approval for HIGH/CRITICAL",
        priority=60,
        match_actors=["generated:*"],
        match_risk_levels=[RiskLevel.HIGH, RiskLevel.CRITICAL],
        decision=PermissionDecision.NEEDS_APPROVAL,
        reason="Generated tools require approval for high-risk actions",
    ),

    # --- Browser automation — always needs approval for write actions ---
    PolicyRule(
        rule_id="builtin-browser-write-approval",
        name="Browser write actions require approval",
        priority=70,
        match_verbs=["browser.fill_form", "browser.click", "browser.download"],
        decision=PermissionDecision.NEEDS_APPROVAL,
        reason="Browser interaction with forms, clicks, and downloads requires approval",
    ),

    # --- Desktop automation — HIGH minimum, always approval ---
    PolicyRule(
        rule_id="builtin-desktop-approval",
        name="Desktop automation requires approval",
        priority=80,
        match_verbs=["desktop.mouse", "desktop.keyboard", "desktop.window_manage"],
        decision=PermissionDecision.NEEDS_APPROVAL,
        reason="Desktop automation actions (mouse/keyboard/window) require explicit approval",
    ),

    # --- Network requests — T2 sandbox for HIGH risk ---
    PolicyRule(
        rule_id="builtin-net-high-sandbox",
        name="High-risk network requests in T2 sandbox",
        priority=90,
        match_verbs=["net.post", "net.put", "net.delete", "net.patch"],
        match_risk_levels=[RiskLevel.HIGH, RiskLevel.CRITICAL],
        decision=PermissionDecision.SANDBOX_REQUIRED,
        required_sandbox_tier=SandboxTier.T2_SUBPROCESS,
        reason="Mutating network requests run in subprocess sandbox",
    ),

    # --- Default: allow LOW risk actions from trusted actors ---
    PolicyRule(
        rule_id="builtin-allow-low-risk",
        name="Allow LOW risk trusted actor actions",
        priority=900,
        match_risk_levels=[RiskLevel.LOW],
        match_actors=["system:*", "user:primary"],
        decision=PermissionDecision.ALLOW,
        reason="Low-risk actions from trusted actors are allowed",
    ),

    # --- Default catch-all: MEDIUM risk → T2 sandbox ---
    PolicyRule(
        rule_id="builtin-medium-sandbox-default",
        name="Default: MEDIUM risk → T2 sandbox",
        priority=950,
        match_risk_levels=[RiskLevel.MEDIUM],
        decision=PermissionDecision.SANDBOX_REQUIRED,
        required_sandbox_tier=SandboxTier.T2_SUBPROCESS,
        reason="Medium-risk actions run in subprocess sandbox by default",
    ),

    # --- Final fallback: HIGH/CRITICAL → needs approval ---
    PolicyRule(
        rule_id="builtin-high-approval-fallback",
        name="Fallback: HIGH/CRITICAL → needs approval",
        priority=999,
        match_risk_levels=[RiskLevel.HIGH, RiskLevel.CRITICAL],
        decision=PermissionDecision.NEEDS_APPROVAL,
        reason="High and critical risk actions require user approval (fallback rule)",
    ),
)
