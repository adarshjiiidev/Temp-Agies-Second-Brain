"""AgentMoe — GitTool.

Git operations tool for AgentMoe workers.

Routes to L5 GitExecutor via CapabilityInvoker. Adds:
  - Explicit safety gates for destructive git operations
  - Structured output parsing
  - Dry-run support for all mutating operations

Supported operations:
  status, diff, log, branch, checkout, commit, fetch, pull, push,
  clone, stash, tag, show, reset (soft only)

SECURITY:
  - git push, clone, fetch always require user_confirmed=True.
  - git reset --hard and git clean -fd require user_confirmed=True.
  - All operations use T2SubprocessSandbox (via L5).
  - Repository path is validated by PathGuard.

Import safety: agentmoe.core + agentmoe.security (no L5 direct imports).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from aegis.agentmoe.core.tool import BaseTool, ToolResult, ToolRiskLevel
from aegis.agentmoe.security.path_guard import PathGuard, PathGuardError
from aegis.agentmoe.observability.span import SpanBuilder, SpanKind

logger = logging.getLogger(__name__)

__all__ = ["GitTool"]

# Git operations and their risk classification
_OP_RISK: dict[str, ToolRiskLevel] = {
    "status":   ToolRiskLevel.LOW,
    "diff":     ToolRiskLevel.LOW,
    "log":      ToolRiskLevel.LOW,
    "show":     ToolRiskLevel.LOW,
    "branch":   ToolRiskLevel.LOW,
    "stash":    ToolRiskLevel.MEDIUM,
    "tag":      ToolRiskLevel.MEDIUM,
    "checkout": ToolRiskLevel.MEDIUM,
    "commit":   ToolRiskLevel.MEDIUM,
    "reset":    ToolRiskLevel.HIGH,
    "fetch":    ToolRiskLevel.HIGH,
    "pull":     ToolRiskLevel.HIGH,
    "push":     ToolRiskLevel.HIGH,
    "clone":    ToolRiskLevel.HIGH,
}

# Operations requiring user_confirmed=True (SAFETY boundary, not config)
_REQUIRES_CONFIRMATION: frozenset[str] = frozenset({
    "push", "clone", "fetch", "pull",   # network ops
    "reset",                              # potentially destructive
})

# L5 ActionKind mapping
_OP_ACTION: dict[str, str] = {
    "status":   "GIT_STATUS",
    "diff":     "GIT_DIFF",
    "log":      "GIT_LOG",
    "show":     "GIT_LOG",      # reuse log kind
    "branch":   "GIT_BRANCH",
    "checkout": "GIT_CHECKOUT",
    "commit":   "GIT_COMMIT",
    "fetch":    "GIT_FETCH",
    "pull":     "GIT_PULL",
    "push":     "GIT_PUSH",
    "clone":    "GIT_CLONE",
    "stash":    "GIT_STATUS",   # stash via shell args in params
    "tag":      "GIT_BRANCH",   # tag via shell args in params
    "reset":    "GIT_CHECKOUT", # soft reset via shell args
}


class GitTool(BaseTool):
    """AgentMoe git tool.

    Usage::

        tool = GitTool(invoker=capability_invoker, workspace_root=Path("/workspace"))
        # Read operation (no confirmation needed):
        result = await tool.invoke(
            parameters={"op": "status", "repo": "/workspace/myproject"},
            worker_id="...", mission_id="...",
        )
        # Write operation (requires user_confirmed):
        result = await tool.invoke(
            parameters={"op": "push", "repo": "/workspace/myproject", "remote": "origin"},
            worker_id="...", mission_id="...",
            user_confirmed=True,
        )
    """

    @property
    def name(self) -> str:
        return "git"

    @property
    def description(self) -> str:
        return (
            "Git version control operations: status, diff, log, branch, checkout, "
            "commit, fetch, pull, push, clone. "
            "Network operations and destructive ops require user_confirmed=True."
        )

    @property
    def default_risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.MEDIUM

    @property
    def supports_dry_run(self) -> bool:
        return True

    def __init__(
        self,
        *,
        invoker: Any,
        workspace_root: Optional[Path] = None,
    ) -> None:
        self._invoker = invoker
        self._guard = PathGuard(
            workspace_root=workspace_root or Path.home() / "workspace",
        )

    async def invoke(
        self,
        *,
        parameters: dict[str, Any],
        worker_id: str,
        mission_id: str,
        parent_span_id: Optional[str] = None,
        dry_run: bool = False,
        user_confirmed: bool = False,
    ) -> ToolResult:
        op = parameters.get("op", "status")
        span = SpanBuilder(
            kind=SpanKind.TOOL,
            name=f"git.{op}",
            worker_id=worker_id,
            mission_id=mission_id,
            parent_id=parent_span_id,
            tool=self.name,
        )

        # 1. Validate operation
        if op not in _OP_ACTION:
            return ToolResult.err(
                "InvalidOperation",
                f"Unknown git operation: {op!r}. Valid: {sorted(_OP_ACTION.keys())}",
            )

        # 2. Validate repo path
        repo_str = parameters.get("repo") or parameters.get("path") or "."
        try:
            repo_path = self._guard.validate(repo_str)
        except PathGuardError as exc:
            span.denied(str(exc))
            return ToolResult.err("PathGuardError", str(exc))

        # 3. Confirmation gate for dangerous ops
        if op in _REQUIRES_CONFIRMATION and not user_confirmed:
            span.denied(f"git {op} requires user_confirmed=True", risk_level="HIGH")
            return ToolResult.err(
                "ApprovalRequired",
                f"git {op!r} requires explicit user approval (user_confirmed=True). "
                "This operation accesses network or modifies repository history.",
            )

        # 4. Dry-run
        if dry_run:
            args_preview = self._describe_dry_run(op, repo_path, parameters)
            return ToolResult.ok({"dry_run_description": args_preview}, dry_run=True)

        # 5. Route to L5
        l5_params = dict(parameters)
        l5_params["repo"] = str(repo_path)
        action_kind = _OP_ACTION[op]

        try:
            result = await self._invoker.invoke_action(
                action_kind=action_kind,
                parameters=l5_params,
                worker_id=worker_id,
                mission_id=mission_id,
                user_confirmed=user_confirmed,
            )
        except Exception as exc:
            logger.exception("GitTool: L5 invocation failed for op=%s", op)
            span.failed(exc, risk_level=_OP_RISK[op].value)
            return ToolResult.err(type(exc).__name__, str(exc)[:300])

        span.success(
            audit_ref=getattr(result, "audit_id", None),
            risk_level=_OP_RISK[op].value,
        )
        return ToolResult.ok(
            output=getattr(result, "output", None),
            audit_ref=getattr(result, "audit_id", None),
        )

    def _describe_dry_run(self, op: str, repo: Path, params: dict[str, Any]) -> str:
        if op == "push":
            remote = params.get("remote", "origin")
            branch = params.get("branch", "HEAD")
            return f"Would push {branch!r} to remote {remote!r} in {repo}"
        if op == "commit":
            msg = params.get("message", "")[:50]
            return f"Would commit with message: {msg!r} in {repo}"
        if op == "clone":
            url = params.get("url", "")
            return f"Would clone {url!r} into {repo}"
        if op == "reset":
            return f"Would reset repository in {repo} (type: {params.get('type', 'soft')})"
        return f"Would run git {op} in {repo}"
