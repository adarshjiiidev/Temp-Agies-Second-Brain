"""L5 Execution Engine — Docker Executor (interface + basic ops).

Handles docker.run / docker.logs / docker.stop / docker.remove / docker.exec.

Requires Docker daemon. Skipped automatically in tests when Docker unavailable.

Import safety: subprocess + stdlib + l5_execution.* ONLY.
"""

from __future__ import annotations

import asyncio
import shutil
import time
from typing import Any

from aegis.l5_execution.contracts import ExecutorManifest, SandboxContext
from aegis.l5_execution.exceptions import ExecutorError, ExecutorNotFoundError
from aegis.l5_execution.executors.base import ExecutorHealth
from aegis.l5_execution.sandbox.t3_docker import is_docker_available
from aegis.l5_execution.types import (
    Action,
    ActionKind,
    ActionResult,
    ExecutionStatus,
    PermissionDecision,
    SandboxTier,
    VerificationResult,
)

__all__ = ["DockerExecutor"]


class DockerExecutor:
    """Docker executor — basic container operations."""

    manifest = ExecutorManifest(
        name="docker",
        version="0.1.0",
        description="Docker container operations: run, exec, logs, stop, remove. Requires Docker daemon.",
        handles=[
            ActionKind.DOCKER_RUN,
            ActionKind.DOCKER_EXEC,
            ActionKind.DOCKER_LOGS,
            ActionKind.DOCKER_STOP,
            ActionKind.DOCKER_REMOVE,
            ActionKind.DOCKER_BUILD,
        ],
        min_sandbox_tier=SandboxTier.T3_DOCKER,
        supports_rollback=False,
        default_timeout_seconds=120.0,
    )

    async def execute(self, action: Action, sandbox: SandboxContext) -> ActionResult:
        if not is_docker_available():
            return ActionResult(
                action_id=action.action_id,
                status=ExecutionStatus.FAILED,
                error="Docker CLI not available. Install Docker Desktop or Docker Engine.",
                error_code="E_EXE_NO_EXECUTOR",
                executor_name="docker",
            )

        started = time.time()
        p = action.parameters
        kind = action.kind

        if sandbox.dry_run:
            return ActionResult(
                action_id=action.action_id,
                status=ExecutionStatus.SUCCESS,
                output={"dry_run": True, "kind": kind.value},
                executor_name="docker",
            )

        try:
            output = await self._dispatch(kind, p, sandbox)
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
                executor_name="docker",
            )
        except Exception as exc:
            return ActionResult(
                action_id=action.action_id,
                status=ExecutionStatus.FAILED,
                error=str(exc),
                error_code="E_EXE_EXECUTOR_FAILED",
                executor_name="docker",
            )

    async def rollback(self, action: Action, result: ActionResult) -> dict[str, Any]:
        return {"supported": False}

    async def health(self) -> ExecutorHealth:
        if not is_docker_available():
            return ExecutorHealth(name="docker", healthy=False, message="docker not found on PATH")
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "info", "--format", "json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, err = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            healthy = proc.returncode == 0
        except Exception as exc:
            return ExecutorHealth(name="docker", healthy=False, message=str(exc))
        return ExecutorHealth(
            name="docker",
            healthy=healthy,
            message="Docker daemon reachable" if healthy else "Docker daemon not reachable",
        )

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def _dispatch(self, kind: ActionKind, p: dict, sandbox: SandboxContext) -> Any:
        timeout = sandbox.timeout_seconds or 120.0

        if kind == ActionKind.DOCKER_RUN:
            return await self._run(p, timeout)
        if kind == ActionKind.DOCKER_EXEC:
            return await self._exec(p, timeout)
        if kind == ActionKind.DOCKER_LOGS:
            return await self._logs(p)
        if kind == ActionKind.DOCKER_STOP:
            return await self._stop(p)
        if kind == ActionKind.DOCKER_REMOVE:
            return await self._remove(p)
        if kind == ActionKind.DOCKER_BUILD:
            return await self._build(p, timeout)
        raise ExecutorError(f"Unsupported Docker ActionKind: {kind.value!r}")

    async def _run(self, p: dict, timeout: float) -> dict:
        image = p.get("image", "python:3.12-slim")
        cmd = p.get("cmd", [])
        memory = p.get("memory", "256m")
        cpus = str(p.get("cpus", "0.5"))
        network = p.get("network", "none")

        docker_cmd = [
            "docker", "run", "--rm",
            f"--memory={memory}",
            f"--cpus={cpus}",
            f"--network={network}",
            "--security-opt=no-new-privileges",
            image,
        ] + (cmd if isinstance(cmd, list) else [])

        proc = await asyncio.create_subprocess_exec(
            *docker_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return {
            "returncode": proc.returncode,
            "stdout": out.decode("utf-8", errors="replace"),
            "stderr": err.decode("utf-8", errors="replace"),
        }

    async def _exec(self, p: dict, timeout: float) -> dict:
        container = p["container"]
        cmd = p.get("cmd", [])
        proc = await asyncio.create_subprocess_exec(
            "docker", "exec", container, *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return {
            "container": container,
            "returncode": proc.returncode,
            "stdout": out.decode("utf-8", errors="replace"),
            "stderr": err.decode("utf-8", errors="replace"),
        }

    async def _logs(self, p: dict) -> dict:
        container = p["container"]
        tail = p.get("tail", "100")
        proc = await asyncio.create_subprocess_exec(
            "docker", "logs", "--tail", str(tail), container,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=10.0)
        return {
            "container": container,
            "logs": out.decode("utf-8", errors="replace"),
            "stderr": err.decode("utf-8", errors="replace"),
        }

    async def _stop(self, p: dict) -> dict:
        container = p["container"]
        proc = await asyncio.create_subprocess_exec(
            "docker", "stop", container,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=30.0)
        return {"container": container, "stopped": proc.returncode == 0}

    async def _remove(self, p: dict) -> dict:
        container = p["container"]
        force = p.get("force", False)
        cmd = ["docker", "rm", container]
        if force:
            cmd.insert(2, "-f")
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=30.0)
        return {"container": container, "removed": proc.returncode == 0}

    async def _build(self, p: dict, timeout: float) -> dict:
        context = p.get("context", ".")
        tag = p.get("tag", "aegis-build:latest")
        dockerfile = p.get("dockerfile", "Dockerfile")
        proc = await asyncio.create_subprocess_exec(
            "docker", "build", "-t", tag, "-f", dockerfile, context,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return {
            "tag": tag,
            "returncode": proc.returncode,
            "stdout": out.decode("utf-8", errors="replace"),
            "stderr": err.decode("utf-8", errors="replace"),
        }
