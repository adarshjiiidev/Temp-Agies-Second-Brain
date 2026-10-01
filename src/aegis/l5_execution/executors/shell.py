"""L5 Execution Engine — Shell Executor (T2 only).

Handles shell.exec ActionKind.
Always runs in T2 subprocess sandbox — never T0 or T1.
Command is passed as a list (no shell=True — prevents injection).

Import safety: stdlib + l5_execution.* ONLY.
"""

from __future__ import annotations

import shutil
import sys
import time
from typing import Any

from aegis.l5_execution.contracts import ExecutorManifest, SandboxContext
from aegis.l5_execution.executors.base import ExecutorHealth
from aegis.l5_execution.sandbox.t2_subprocess import T2SubprocessSandbox
from aegis.l5_execution.sandbox.workspace import TempWorkspace
from aegis.l5_execution.types import (
    Action,
    ActionKind,
    ActionResult,
    ExecutionStatus,
    PermissionDecision,
    SandboxTier,
    VerificationResult,
)

__all__ = ["ShellExecutor"]


class ShellExecutor:
    """Shell executor — T2 only.

    Parameters expected in action.parameters:
      - cmd (list[str]): command and arguments (no shell string)
      - env (dict, optional): additional environment variables
      - stdin (str, optional): data to pipe to stdin
    """

    manifest = ExecutorManifest(
        name="shell",
        version="0.1.0",
        description="Executes shell commands in a T2 subprocess sandbox. cmd must be a list (no shell=True).",
        handles=[ActionKind.SHELL_EXEC],
        min_sandbox_tier=SandboxTier.T2_SUBPROCESS,
        supports_rollback=False,
        default_timeout_seconds=60.0,
    )

    def __init__(self) -> None:
        self._t2 = T2SubprocessSandbox(timeout_seconds=60.0)

    async def execute(self, action: Action, sandbox: SandboxContext) -> ActionResult:
        started = time.time()
        p = action.parameters
        cmd = p.get("cmd", [])

        if not cmd:
            return ActionResult(
                action_id=action.action_id,
                status=ExecutionStatus.FAILED,
                error="No cmd provided in parameters['cmd']",
                error_code="E_EXE_EXECUTOR_FAILED",
                executor_name="shell",
            )

        if isinstance(cmd, str):
            # Safety: split string cmd into list to avoid shell injection
            import shlex
            cmd = shlex.split(cmd)

        if sandbox.dry_run:
            return ActionResult(
                action_id=action.action_id,
                status=ExecutionStatus.SUCCESS,
                output={"dry_run": True, "cmd": cmd},
                sandbox_tier=sandbox.tier,
                permission_decision=PermissionDecision.ALLOW,
                executor_name="shell",
            )

        ws: TempWorkspace | None = None
        if sandbox.workspace_path:
            from pathlib import Path
            ws = TempWorkspace(Path(sandbox.workspace_path))
        else:
            ws = TempWorkspace.create("shell-exec")

        try:
            stdin_data = p.get("stdin", "")
            result = await self._t2.run(
                cmd,
                workspace=ws,
                extra_env=p.get("env"),
                stdin_data=stdin_data.encode() if stdin_data else None,
            )

            return ActionResult(
                action_id=action.action_id,
                status=ExecutionStatus.SUCCESS if result.succeeded else ExecutionStatus.FAILED,
                output={
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode,
                },
                error=result.stderr if not result.succeeded else None,
                sandbox_tier=sandbox.tier,
                permission_decision=PermissionDecision.ALLOW,
                verification_result=VerificationResult.PASSED,
                started_at=started,
                completed_at=time.time(),
                duration_ms=(time.time() - started) * 1000,
                executor_name="shell",
            )
        finally:
            if sandbox.workspace_path is None and ws:
                ws.cleanup()

    async def rollback(self, action: Action, result: ActionResult) -> dict[str, Any]:
        return {"supported": False}

    async def health(self) -> ExecutorHealth:
        platform_shell = "powershell.exe" if sys.platform == "win32" else "bash"
        available = shutil.which(platform_shell) is not None
        return ExecutorHealth(
            name="shell",
            healthy=True,
            message=f"Shell executor operational ({platform_shell}: {'found' if available else 'not found'})",
        )
