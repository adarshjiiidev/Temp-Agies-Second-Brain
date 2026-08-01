"""L5 Execution Engine — Core Types.

All fundamental enumerations and value types used across the execution engine.
No business logic here; only typed data.

Import safety: stdlib only.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any
from uuid import UUID

__all__ = [
    "ActionKind",
    "ExecutionStatus",
    "PermissionDecision",
    "RiskLevel",
    "SandboxTier",
    "VerificationResult",
    "Action",
    "ActionResult",
    "AuditStage",
]


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class ActionKind(str, Enum):
    """Category of an Action — maps to a verb namespace and executor type."""

    # Filesystem
    FS_READ = "fs.read"
    FS_WRITE = "fs.write"
    FS_APPEND = "fs.append"
    FS_COPY = "fs.copy"
    FS_MOVE = "fs.move"
    FS_DELETE = "fs.delete"
    FS_MKDIR = "fs.mkdir"
    FS_HASH = "fs.hash"
    FS_SEARCH = "fs.search"
    FS_WATCH = "fs.watch"

    # Process / Shell
    PROC_SPAWN = "proc.spawn"
    PROC_SIGNAL = "proc.signal"
    SHELL_EXEC = "shell.exec"

    # Python
    PYTHON_EXEC = "python.exec"
    PYTHON_EVAL = "python.eval"

    # Git
    GIT_CLONE = "git.clone"
    GIT_STATUS = "git.status"
    GIT_COMMIT = "git.commit"
    GIT_BRANCH = "git.branch"
    GIT_CHECKOUT = "git.checkout"
    GIT_PULL = "git.pull"
    GIT_PUSH = "git.push"
    GIT_STASH = "git.stash"
    GIT_DIFF = "git.diff"
    GIT_LOG = "git.log"
    GIT_RESET = "git.reset"

    # Docker
    DOCKER_RUN = "docker.run"
    DOCKER_BUILD = "docker.build"
    DOCKER_EXEC = "docker.exec"
    DOCKER_LOGS = "docker.logs"
    DOCKER_STOP = "docker.stop"
    DOCKER_REMOVE = "docker.remove"

    # Network / HTTP
    NET_GET = "net.get"
    NET_POST = "net.post"
    NET_PUT = "net.put"
    NET_DELETE = "net.delete"
    NET_PATCH = "net.patch"

    # Obsidian
    OBSIDIAN_READ = "obsidian.read"
    OBSIDIAN_CREATE = "obsidian.create"
    OBSIDIAN_UPDATE = "obsidian.update"
    OBSIDIAN_DELETE = "obsidian.delete"
    OBSIDIAN_SEARCH = "obsidian.search"

    # Browser (interface — concrete P10)
    BROWSER_NAVIGATE = "browser.navigate"
    BROWSER_READ = "browser.read"
    BROWSER_FILL = "browser.fill_form"
    BROWSER_CLICK = "browser.click"
    BROWSER_DOWNLOAD = "browser.download"

    # Desktop (interface — concrete P09)
    DESKTOP_SCREENSHOT = "desktop.screenshot"
    DESKTOP_MOUSE = "desktop.mouse"
    DESKTOP_KEYBOARD = "desktop.keyboard"
    DESKTOP_WINDOW = "desktop.window_manage"

    # VS Code (interface — concrete P12)
    VSCODE_READ = "vscode.read"
    VSCODE_SEARCH = "vscode.search"
    VSCODE_DIAGNOSTICS = "vscode.diagnostics"
    VSCODE_TASK = "vscode.task"

    # Memory (bridges to L4)
    MEMORY_WRITE = "memory.write"
    MEMORY_READ = "memory.read"
    MEMORY_DELETE = "memory.delete"
    MEMORY_EXPORT = "memory.export"


class ExecutionStatus(str, Enum):
    """Overall outcome of an execution pipeline run."""

    SUCCESS = "success"
    FAILED = "failed"
    DENIED = "denied"
    APPROVAL_REQUIRED = "approval_required"
    ROLLED_BACK = "rolled_back"
    SANDBOX_ESCAPE = "sandbox_escape"
    VERIFICATION_FAILED = "verification_failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class PermissionDecision(str, Enum):
    """SVRC check outcome."""

    ALLOW = "allow"
    DENY = "deny"
    NEEDS_APPROVAL = "needs_approval"
    SANDBOX_REQUIRED = "sandbox_required"


class RiskLevel(str, Enum):
    """4-tier risk classification for actions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def ordinal(self) -> int:
        return {"low": 0, "medium": 1, "high": 2, "critical": 3}[self.value]

    def __ge__(self, other: "RiskLevel") -> bool:  # type: ignore[override]
        return self.ordinal >= other.ordinal

    def __gt__(self, other: "RiskLevel") -> bool:  # type: ignore[override]
        return self.ordinal > other.ordinal

    def __le__(self, other: "RiskLevel") -> bool:  # type: ignore[override]
        return self.ordinal <= other.ordinal

    def __lt__(self, other: "RiskLevel") -> bool:  # type: ignore[override]
        return self.ordinal < other.ordinal


class SandboxTier(str, Enum):
    """4-tier sandbox isolation.

    T0 = no sandbox (trusted reads only, e.g. FS_READ on home dir)
    T1 = Python AST jail (RestrictedPython; pure computation, no I/O)
    T2 = subprocess + temp workspace + env isolation (medium risk)
    T3 = Docker container (high risk; network deny by default)
    T4 = Firecracker VM (critical; interface stub — concrete in P08+)
    """

    T0_NONE = "T0_none"
    T1_AST = "T1_ast"
    T2_SUBPROCESS = "T2_subprocess"
    T3_DOCKER = "T3_docker"
    T4_FIRECRACKER = "T4_firecracker"

    @property
    def ordinal(self) -> int:
        return {
            "T0_none": 0,
            "T1_ast": 1,
            "T2_subprocess": 2,
            "T3_docker": 3,
            "T4_firecracker": 4,
        }[self.value]


class VerificationResult(str, Enum):
    """Post-execution assertion outcome."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ROLLED_BACK = "rolled_back"


class AuditStage(str, Enum):
    """Which pipeline stage generated an audit entry."""

    PERMISSION = "permission"
    RISK = "risk"
    POLICY = "policy"
    DISPATCH = "dispatch"
    SANDBOX = "sandbox"
    EXECUTE = "execute"
    VERIFY = "verify"
    ROLLBACK = "rollback"
    PIPELINE = "pipeline"


# ---------------------------------------------------------------------------
# Core data structures
# ---------------------------------------------------------------------------


@dataclass
class Action:
    """A typed, auditable unit of work submitted to the Execution Engine.

    Every field here maps exactly to an SVRC component:
      - actor      → Subject (who)
      - kind       → Verb    (what)
      - resource   → Resource (on what)
      - context    → Context  (why / under what policy)

    Usage::

        action = Action(
            actor="system:planner",
            kind=ActionKind.FS_WRITE,
            resource="fs:~/Projects/AGIES/notes.md",
            parameters={"content": "# Notes"},
            context={"reason": "write plan output", "plan_id": "plan_001"},
        )
        result = await pipeline.execute(action)
    """

    actor: str
    """SVRC Subject: who is requesting this action (e.g. 'system:planner')."""

    kind: ActionKind
    """SVRC Verb: what kind of action (e.g. ActionKind.FS_WRITE)."""

    resource: str
    """SVRC Resource: what the verb targets (e.g. 'fs:~/Projects/**')."""

    parameters: dict[str, Any] = field(default_factory=dict)
    """Executor-specific parameters (path, content, url, command, etc.)."""

    context: dict[str, Any] = field(default_factory=dict)
    """SVRC Context: reason, plan_id, approval, session_id, correlation_id."""

    action_id: UUID = field(default_factory=uuid.uuid4)
    """Unique ID for this action instance — appears in every audit entry."""

    created_at: float = field(default_factory=time.time)
    """Unix timestamp when this action was created."""

    parent_action_id: UUID | None = None
    """For nested actions (e.g. a plan step spawning sub-actions)."""

    user_confirmed: bool = False
    """Explicit user confirmation — required for CRITICAL risk and T5 Personal."""

    dry_run: bool = False
    """If True, run through all stages but skip actual executor side effects."""

    def svrc_verb(self) -> str:
        """Return the SVRC verb string for permission checks."""
        return self.kind.value

    def __repr__(self) -> str:
        return (
            f"Action(id={self.action_id!s:.8}, actor={self.actor!r}, "
            f"kind={self.kind.value!r}, resource={self.resource!r})"
        )


@dataclass
class ActionResult:
    """The typed outcome returned by the Execution Engine after all 7 stages.

    Consumers should check ``status`` first:
      - SUCCESS            → inspect ``output``
      - DENIED / FAILED    → inspect ``error``
      - APPROVAL_REQUIRED  → inspect ``approval_request_id``
      - ROLLED_BACK        → inspect ``rollback_info``
    """

    action_id: UUID
    """Matches Action.action_id."""

    status: ExecutionStatus
    """Overall outcome of the pipeline."""

    output: Any = None
    """Executor output (may be None on failure)."""

    error: str | None = None
    """Human-readable error description."""

    error_code: str | None = None
    """Machine-readable error code (e.g. 'E_PERM_DENIED')."""

    risk_level: RiskLevel = RiskLevel.LOW
    """Risk level assigned by the Risk Analyzer."""

    sandbox_tier: SandboxTier = SandboxTier.T0_NONE
    """Sandbox tier used during execution."""

    permission_decision: PermissionDecision = PermissionDecision.DENY
    """SVRC decision from the Permission Engine."""

    verification_result: VerificationResult = VerificationResult.SKIPPED
    """Post-execution assertion result."""

    audit_entry_ids: list[str] = field(default_factory=list)
    """IDs of all AuditEntry records created for this action."""

    approval_request_id: str | None = None
    """Set when status == APPROVAL_REQUIRED."""

    rollback_info: dict[str, Any] | None = None
    """Set when status == ROLLED_BACK; describes what was undone."""

    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    duration_ms: float | None = None

    executor_name: str | None = None
    """Which executor plugin handled the action."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Stage-specific diagnostic data."""

    @property
    def succeeded(self) -> bool:
        return self.status is ExecutionStatus.SUCCESS

    @property
    def was_denied(self) -> bool:
        return self.status is ExecutionStatus.DENIED

    @property
    def needs_approval(self) -> bool:
        return self.status is ExecutionStatus.APPROVAL_REQUIRED

    def __repr__(self) -> str:
        return (
            f"ActionResult(action_id={self.action_id!s:.8}, "
            f"status={self.status.value!r}, "
            f"executor={self.executor_name!r})"
        )
