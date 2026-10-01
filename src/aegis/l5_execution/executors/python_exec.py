"""L5 Execution Engine — Python Executor.

Handles python.exec and python.eval actions.
  - python.eval: T1 AST jail (safe, in-process, no I/O)
  - python.exec: T2 subprocess (isolated process with workspace)

Import safety: stdlib + l5_execution.* ONLY.
"""

from __future__ import annotations

import sys
import time
from typing import Any

from aegis.l5_execution.contracts import ExecutorManifest, SandboxContext
from aegis.l5_execution.exceptions import ExecutorError, SandboxEscapeError
from aegis.l5_execution.executors.base import ExecutorHealth
from aegis.l5_execution.sandbox.t1_ast import T1ASTJail
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

__all__ = ["PythonExecutor"]


class PythonExecutor:
    """Concrete executor for python.exec and python.eval."""

    manifest = ExecutorManifest(
        name="python",
        version="0.1.0",
        description="Executes Python code using T1 AST jail (eval) or T2 subprocess (exec).",
        handles=[ActionKind.PYTHON_EXEC, ActionKind.PYTHON_EVAL],
        min_sandbox_tier=SandboxTier.T1_AST,
        supports_rollback=False,
        default_timeout_seconds=30.0,
    )

    def __init__(self) -> None:
        self._t1 = T1ASTJail(timeout_seconds=5.0)
        self._t2 = T2SubprocessSandbox(timeout_seconds=30.0)

    async def execute(self, action: Action, sandbox: SandboxContext) -> ActionResult:
        started = time.time()
        p = action.parameters
        code = p.get("code", "")

        if not code.strip():
            return ActionResult(
                action_id=action.action_id,
                status=ExecutionStatus.FAILED,
                error="No code provided in parameters['code']",
                error_code="E_EXE_EXECUTOR_FAILED",
                executor_name="python",
            )

        if sandbox.dry_run:
            violations = self._t1.analyze(code)
            return ActionResult(
                action_id=action.action_id,
                status=ExecutionStatus.SUCCESS,
                output={"dry_run": True, "violations": violations, "safe": not violations},
                sandbox_tier=sandbox.tier,
                permission_decision=PermissionDecision.ALLOW,
                executor_name="python",
            )

        try:
            if action.kind == ActionKind.PYTHON_EVAL or sandbox.tier == SandboxTier.T1_AST:
                output = await self._run_t1(code, p.get("namespace", {}))
            else:
                output = await self._run_t2(code, sandbox)

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
                executor_name="python",
            )
        except SandboxEscapeError:
            raise
        except Exception as exc:
            return ActionResult(
                action_id=action.action_id,
                status=ExecutionStatus.FAILED,
                error=str(exc),
                error_code="E_EXE_EXECUTOR_FAILED",
                sandbox_tier=sandbox.tier,
                started_at=started,
                executor_name="python",
            )

    async def rollback(self, action: Action, result: ActionResult) -> dict[str, Any]:
        return {"supported": False}

    async def health(self) -> ExecutorHealth:
        try:
            self._t1.run("x = 1 + 1")
            return ExecutorHealth(
                name="python",
                healthy=True,
                message=f"Python executor operational (Python {sys.version.split()[0]})",
            )
        except Exception as exc:
            return ExecutorHealth(name="python", healthy=False, message=str(exc))

    # ------------------------------------------------------------------

    async def _run_t1(self, code: str, namespace: dict) -> dict:
        ns = self._t1.run(code, namespace)
        # Filter out built-ins from result namespace
        return {
            k: v for k, v in ns.items()
            if not k.startswith("__") and not callable(v)
        }

    async def _run_t2(self, code: str, sandbox: SandboxContext) -> dict:
        ws: TempWorkspace | None = None
        if sandbox.workspace_path:
            from pathlib import Path
            ws = TempWorkspace(Path(sandbox.workspace_path))
        else:
            ws = TempWorkspace.create("python-exec")

        try:
            result = await self._t2.run_python(code, workspace=ws)
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "succeeded": result.succeeded,
            }
        finally:
            if sandbox.workspace_path is None and ws:
                ws.cleanup()
