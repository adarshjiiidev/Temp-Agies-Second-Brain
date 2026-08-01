"""L5 Execution Engine — Risk Analyzer.

Stage 2 of the 7-stage execution pipeline.

The RiskAnalyzer scores every Action on a 4-tier scale:
  LOW      — read-only, reversible, local, trusted actor
  MEDIUM   — writes, processes, network, semi-trusted actor
  HIGH     — deletes, shell execution, git push, docker, untrusted actor
  CRITICAL — destructive irreversible system-wide operations, any user impersonation

The score is computed by combining weighted factors:
  - Verb severity (most significant)
  - Resource scope (local file vs system vs network)
  - Reversibility
  - Subject trust level
  - Blast radius

Import safety: stdlib + l5_execution.types ONLY.
"""

from __future__ import annotations

from aegis.l5_execution.types import Action, ActionKind, RiskLevel

__all__ = ["RiskAnalyzer", "RiskAssessmentResult"]

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Verb risk table
# ---------------------------------------------------------------------------

# Map each ActionKind to a base risk score 0–1
_VERB_RISK: dict[ActionKind, float] = {
    # Filesystem reads — LOW
    ActionKind.FS_READ:         0.1,
    ActionKind.FS_HASH:         0.1,
    ActionKind.FS_SEARCH:       0.1,
    ActionKind.FS_WATCH:        0.2,
    # Filesystem writes — MEDIUM/HIGH
    ActionKind.FS_WRITE:        0.4,
    ActionKind.FS_APPEND:       0.35,
    ActionKind.FS_COPY:         0.3,
    ActionKind.FS_MKDIR:        0.25,
    ActionKind.FS_MOVE:         0.45,
    ActionKind.FS_DELETE:       0.75,   # HIGH — irreversible without backup
    # Process / Shell
    ActionKind.PROC_SPAWN:      0.65,
    ActionKind.PROC_SIGNAL:     0.7,
    ActionKind.SHELL_EXEC:      0.8,    # HIGH — arbitrary code
    # Python
    ActionKind.PYTHON_EVAL:     0.5,
    ActionKind.PYTHON_EXEC:     0.6,
    # Git
    ActionKind.GIT_STATUS:      0.05,
    ActionKind.GIT_DIFF:        0.05,
    ActionKind.GIT_LOG:         0.05,
    ActionKind.GIT_CLONE:       0.3,
    ActionKind.GIT_BRANCH:      0.2,
    ActionKind.GIT_STASH:       0.2,
    ActionKind.GIT_CHECKOUT:    0.4,
    ActionKind.GIT_COMMIT:      0.45,
    ActionKind.GIT_PULL:        0.4,
    ActionKind.GIT_RESET:       0.7,
    ActionKind.GIT_PUSH:        0.85,   # HIGH — remote side-effects
    # Docker
    ActionKind.DOCKER_LOGS:     0.1,
    ActionKind.DOCKER_STOP:     0.5,
    ActionKind.DOCKER_RUN:      0.65,
    ActionKind.DOCKER_EXEC:     0.7,
    ActionKind.DOCKER_BUILD:    0.5,
    ActionKind.DOCKER_REMOVE:   0.55,
    # Network
    ActionKind.NET_GET:         0.3,
    ActionKind.NET_POST:        0.5,
    ActionKind.NET_PUT:         0.55,
    ActionKind.NET_PATCH:       0.5,
    ActionKind.NET_DELETE:      0.75,
    # Obsidian
    ActionKind.OBSIDIAN_READ:   0.1,
    ActionKind.OBSIDIAN_SEARCH: 0.1,
    ActionKind.OBSIDIAN_CREATE: 0.35,
    ActionKind.OBSIDIAN_UPDATE: 0.4,
    ActionKind.OBSIDIAN_DELETE: 0.65,
    # Browser (future)
    ActionKind.BROWSER_READ:    0.3,
    ActionKind.BROWSER_NAVIGATE: 0.4,
    ActionKind.BROWSER_CLICK:   0.55,
    ActionKind.BROWSER_FILL:    0.65,
    ActionKind.BROWSER_DOWNLOAD: 0.6,
    # Desktop (future)
    ActionKind.DESKTOP_SCREENSHOT: 0.5,
    ActionKind.DESKTOP_MOUSE:   0.7,
    ActionKind.DESKTOP_KEYBOARD: 0.75,
    ActionKind.DESKTOP_WINDOW:  0.6,
    # Memory
    ActionKind.MEMORY_READ:     0.1,
    ActionKind.MEMORY_WRITE:    0.35,
    ActionKind.MEMORY_DELETE:   0.6,
    ActionKind.MEMORY_EXPORT:   0.4,
    # VS Code
    ActionKind.VSCODE_READ:     0.1,
    ActionKind.VSCODE_SEARCH:   0.1,
    ActionKind.VSCODE_DIAGNOSTICS: 0.15,
    ActionKind.VSCODE_TASK:     0.6,
}

# Subject trust levels — lower = more trusted
_SUBJECT_TRUST: dict[str, float] = {
    "system:core":      0.0,   # TCB — fully trusted
    "system:planner":   0.1,
    "system:memory":    0.05,
    "user:primary":     0.15,
    "plugin:":          0.4,   # prefix match for all plugins
    "generated:":       0.7,   # generated / untrusted tools
}

# Resource scope multipliers
_RESOURCE_SCOPE_RISK: dict[str, float] = {
    "fs:~/":        0.0,   # home dir — normal
    "fs:/tmp/":     0.0,
    "fs:/etc/":     0.4,
    "fs:/sys/":     0.5,
    "fs:/proc/":    0.5,
    "net:":         0.2,
    "proc:":        0.3,
    "docker:":      0.3,
}


@dataclass
class RiskAssessmentResult:
    """Output of the RiskAnalyzer."""

    action_id: object
    risk_level: RiskLevel
    score: float                     # 0.0 – 1.0
    factors: list[str] = field(default_factory=list)
    reversible: bool = True
    blast_radius: str = "local"      # "local" | "project" | "system" | "network"

    @property
    def requires_approval(self) -> bool:
        return self.risk_level is RiskLevel.CRITICAL


class RiskAnalyzer:
    """Stage 2 — risk scorer.

    Stateless; all configuration is baked into the class-level tables.

    Usage::

        analyzer = RiskAnalyzer()
        result = analyzer.assess(action)
        if result.risk_level >= RiskLevel.HIGH:
            ...
    """

    def assess(self, action: Action) -> RiskAssessmentResult:
        """Score an Action and return a RiskAssessmentResult."""
        factors: list[str] = []
        score = 0.0

        # --- Factor 1: Verb severity (weight 0.6) ---
        verb_score = _VERB_RISK.get(action.kind, 0.5)
        score += verb_score * 0.6
        factors.append(f"verb={action.kind.value}(raw={verb_score:.2f})")

        # --- Factor 2: Subject trust (weight 0.2) ---
        subject_trust = self._subject_trust(action.actor)
        score += subject_trust * 0.2
        factors.append(f"subject_trust={subject_trust:.2f}")

        # --- Factor 3: Resource scope (weight 0.15) ---
        resource_score = self._resource_scope(action.resource)
        score += resource_score * 0.15
        factors.append(f"resource_scope={resource_score:.2f}")

        # --- Factor 4: Reversibility (weight 0.05) ---
        reversible = self._is_reversible(action.kind)
        if not reversible:
            score += 0.05
            factors.append("irreversible")

        # --- Determine blast radius ---
        blast_radius = self._blast_radius(action.kind, action.resource)
        factors.append(f"blast={blast_radius}")

        # --- Clamp and classify ---
        score = min(1.0, max(0.0, score))
        risk_level = self._classify(score)

        # --- Hard overrides (security-critical) ---
        risk_level, factors = self._apply_hard_overrides(action, risk_level, factors)

        return RiskAssessmentResult(
            action_id=action.action_id,
            risk_level=risk_level,
            score=score,
            factors=factors,
            reversible=reversible,
            blast_radius=blast_radius,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _subject_trust(actor: str) -> float:
        """Lower = more trusted."""
        for prefix, trust in _SUBJECT_TRUST.items():
            if actor.startswith(prefix):
                return trust
        return 0.5  # unknown subject → medium distrust

    @staticmethod
    def _resource_scope(resource: str) -> float:
        for prefix, risk in _RESOURCE_SCOPE_RISK.items():
            if resource.startswith(prefix):
                return risk
        return 0.1

    @staticmethod
    def _is_reversible(kind: ActionKind) -> bool:
        _irreversible = {
            ActionKind.FS_DELETE,
            ActionKind.GIT_PUSH,
            ActionKind.NET_DELETE,
            ActionKind.NET_POST,
            ActionKind.DOCKER_REMOVE,
        }
        return kind not in _irreversible

    @staticmethod
    def _blast_radius(kind: ActionKind, resource: str) -> str:
        if kind in (ActionKind.NET_POST, ActionKind.NET_PUT, ActionKind.NET_DELETE,
                    ActionKind.GIT_PUSH, ActionKind.BROWSER_FILL):
            return "network"
        if kind in (ActionKind.SHELL_EXEC, ActionKind.PROC_SPAWN, ActionKind.DOCKER_RUN):
            return "system"
        if resource.startswith("fs:/"):
            return "system"
        return "local"

    @staticmethod
    def _classify(score: float) -> RiskLevel:
        if score < 0.25:
            return RiskLevel.LOW
        if score < 0.50:
            return RiskLevel.MEDIUM
        if score < 0.75:
            return RiskLevel.HIGH
        return RiskLevel.CRITICAL

    @staticmethod
    def _apply_hard_overrides(
        action: Action,
        level: RiskLevel,
        factors: list[str],
    ) -> tuple[RiskLevel, list[str]]:
        """Security hard-overrides that cannot be softened by score."""
        # aegis.core.mutate and aegis.user.impersonate are always CRITICAL
        if action.kind.value.startswith("aegis."):
            if action.kind.value in ("aegis.core.mutate", "aegis.user.impersonate"):
                factors.append("hard-override:aegis-tcb=CRITICAL")
                return RiskLevel.CRITICAL, factors

        # Shell execution on system paths = always CRITICAL
        if action.kind is ActionKind.SHELL_EXEC and action.resource.startswith("proc:/system"):
            factors.append("hard-override:shell-system=CRITICAL")
            return RiskLevel.CRITICAL, factors

        # Docker push = HIGH minimum
        if action.kind is ActionKind.DOCKER_BUILD and level < RiskLevel.HIGH:
            factors.append("hard-override:docker-build=HIGH")
            return RiskLevel.HIGH, factors

        return level, factors
