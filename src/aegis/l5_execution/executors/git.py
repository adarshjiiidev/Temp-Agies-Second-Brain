"""L5 Execution Engine — Git Executor.

Handles all git.* ActionKinds.

Invariant: git.push ALWAYS requires action.user_confirmed=True.
           If not confirmed, raises PermissionDeniedError before any
           network contact is made.

All git operations run via the git CLI using T2SubprocessSandbox.

Import safety: stdlib + l5_execution.* ONLY.
"""

from __future__ import annotations

import asyncio
import shutil
import time
from pathlib import Path
from typing import Any

from aegis.l5_execution.contracts import ExecutorManifest, SandboxContext
from aegis.l5_execution.exceptions import ExecutorError, PermissionDeniedError
from aegis.l5_execution.executors.base import ExecutorHealth
from aegis.l5_execution.sandbox.t2_subprocess import T2SubprocessSandbox
from aegis.l5_execution.sandbox.workspace import TempWorkspace
from aegis.l5_execution.types import (
    Action,
    ActionKind,
    ActionResult,
    ExecutionStatus,
    PermissionDecision,
    RiskLevel,
    SandboxTier,
    VerificationResult,
)

__all__ = ["GitExecutor"]


class GitExecutor:
    """Concrete executor for all git.* actions."""

    manifest = ExecutorManifest(
        name="git",
        version="0.1.0",
        description="Handles git operations: clone, status, commit, branch, checkout, pull, push, stash, diff, log, reset.",
        handles=[
            ActionKind.GIT_CLONE,
            ActionKind.GIT_STATUS,
            ActionKind.GIT_COMMIT,
            ActionKind.GIT_BRANCH,
            ActionKind.GIT_CHECKOUT,
            ActionKind.GIT_PULL,
            ActionKind.GIT_PUSH,
            ActionKind.GIT_STASH,
            ActionKind.GIT_DIFF,
            ActionKind.GIT_LOG,
            ActionKind.GIT_RESET,
        ],
        min_sandbox_tier=SandboxTier.T2_SUBPROCESS,
        supports_rollback=True,
        default_timeout_seconds=120.0,
    )

    def __init__(self) -> None:
        self._sandbox = T2SubprocessSandbox(timeout_seconds=120.0)

    async def execute(self, action: Action, sandbox: SandboxContext) -> ActionResult:
        started = time.time()
        try:
            output = await self._dispatch(action, sandbox)
            return ActionResult(
                action_id=action.action_id,
                status=ExecutionStatus.SUCCESS,
                output=output,
                sandbox_tier=sandbox.tier,
                permission_decision=PermissionDecision.ALLOW,
                verification_result=VerificationResult.PASSED,
                started_at=started,
                completed_at=time.time(),
                duration_ms=(time.time() - started) * 1000,
                executor_name="git",
            )
        except (PermissionDeniedError,):
            raise
        except Exception as exc:
            return ActionResult(
                action_id=action.action_id,
                status=ExecutionStatus.FAILED,
                error=str(exc),
                error_code="E_EXE_EXECUTOR_FAILED",
                sandbox_tier=sandbox.tier,
                started_at=started,
                completed_at=time.time(),
                executor_name="git",
            )

    async def rollback(self, action: Action, result: ActionResult) -> dict[str, Any]:
        """Git operations: rollback by git reset --hard HEAD~1 for commit."""
        if action.kind == ActionKind.GIT_COMMIT:
            p = action.parameters
            repo = p.get("repo", ".")
            ws = TempWorkspace.create("git-rollback")
            try:
                res = await self._sandbox.run(
                    ["git", "reset", "--hard", "HEAD~1"],
                    workspace=None,
                    cwd=Path(repo),
                )
                return {"supported": True, "succeeded": res.succeeded, "output": res.stdout}
            finally:
                ws.cleanup()
        return {"supported": False}

    async def health(self) -> ExecutorHealth:
        if not shutil.which("git"):
            return ExecutorHealth(name="git", healthy=False, message="git not found on PATH")
        return ExecutorHealth(name="git", healthy=True, message="git CLI available")

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def _dispatch(self, action: Action, sandbox: SandboxContext) -> Any:
        kind = action.kind
        p = action.parameters

        if kind == ActionKind.GIT_PUSH and not action.user_confirmed:
            raise PermissionDeniedError(
                "git.push requires user_confirmed=True — pushing has irreversible "
                "remote side effects and must be explicitly approved.",
                verb="git.push",
                resource=p.get("remote", "origin"),
                stage="execute",
            )

        if sandbox.dry_run:
            return {"dry_run": True, "kind": kind.value, "params": p}

        repo = Path(p.get("repo", ".")).expanduser().resolve()
        ws = TempWorkspace.create("git-exec") if sandbox.workspace_path is None else None
        workspace = ws or TempWorkspace(Path(sandbox.workspace_path))
        try:
            return await self._run_git_cmd(kind, p, repo, workspace, sandbox)
        finally:
            if ws:
                ws.cleanup()

    async def _run_git_cmd(
        self,
        kind: ActionKind,
        p: dict,
        repo: Path,
        ws: TempWorkspace,
        sandbox: SandboxContext,
    ) -> Any:
        cmd: list[str] = []

        if kind == ActionKind.GIT_STATUS:
            cmd = ["git", "status", "--porcelain"]
        elif kind == ActionKind.GIT_DIFF:
            args = p.get("args", [])
            cmd = ["git", "diff"] + args
        elif kind == ActionKind.GIT_LOG:
            n = p.get("n", 10)
            cmd = ["git", "log", f"--oneline", f"-{n}"]
        elif kind == ActionKind.GIT_CLONE:
            url = p["url"]
            dest = p.get("dest", ws.path.name)
            cmd = ["git", "clone", url, dest]
            repo = ws.path
        elif kind == ActionKind.GIT_COMMIT:
            msg = p.get("message", "AEGIS auto-commit")
            add_all = p.get("add_all", True)
            if add_all:
                await self._sandbox.run(["git", "add", "-A"], cwd=repo)
            cmd = ["git", "commit", "-m", msg]
        elif kind == ActionKind.GIT_BRANCH:
            name = p.get("name")
            if name:
                cmd = ["git", "branch", name]
            else:
                cmd = ["git", "branch", "--list"]
        elif kind == ActionKind.GIT_CHECKOUT:
            branch = p["branch"]
            create = p.get("create", False)
            cmd = ["git", "checkout", "-b", branch] if create else ["git", "checkout", branch]
        elif kind == ActionKind.GIT_PULL:
            remote = p.get("remote", "origin")
            branch = p.get("branch", "")
            cmd = ["git", "pull", remote] + ([branch] if branch else [])
        elif kind == ActionKind.GIT_PUSH:
            remote = p.get("remote", "origin")
            branch = p.get("branch", "")
            cmd = ["git", "push", remote] + ([branch] if branch else [])
        elif kind == ActionKind.GIT_STASH:
            subcmd = p.get("subcmd", "push")
            cmd = ["git", "stash", subcmd]
        elif kind == ActionKind.GIT_RESET:
            mode = p.get("mode", "--hard")
            ref = p.get("ref", "HEAD")
            cmd = ["git", "reset", mode, ref]
        else:
            raise ExecutorError(f"Unsupported git ActionKind: {kind.value!r}")

        result = await self._sandbox.run(cmd, cwd=repo)
        if not result.succeeded and kind not in (ActionKind.GIT_STATUS,):
            raise ExecutorError(
                f"git command failed (rc={result.returncode}): {result.stderr[:500]}"
            )
        return {
            "command": cmd,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
