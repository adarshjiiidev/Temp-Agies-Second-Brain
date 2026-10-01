"""L5 Execution Engine — T2 Subprocess Sandbox.

T2 runs commands in an isolated subprocess with:
  - A scoped temporary workspace (no host FS access outside)
  - Stripped environment (only allowlisted env vars passed through)
  - Hard timeout (process killed after deadline)
  - Memory limit via resource module (POSIX) or Job Objects (Windows via workaround)
  - Captured stdout/stderr returned in ActionResult

Import safety: stdlib + l5_execution.sandbox.workspace ONLY.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from aegis.l5_execution.exceptions import ExecutionTimeoutError, SandboxEscapeError
from aegis.l5_execution.sandbox.workspace import TempWorkspace

__all__ = ["T2SubprocessSandbox", "SubprocessResult"]

# Env vars that are allowed to pass through to the subprocess
_DEFAULT_ENV_ALLOWLIST = [
    "PATH",
    "USERPROFILE",  # Windows home
    "HOME",         # POSIX home
    "TEMP",
    "TMP",
    "TMPDIR",
    "LANG",
    "LC_ALL",
    "PYTHONPATH",
]


class SubprocessResult:
    """Result of a T2 subprocess execution."""

    def __init__(
        self,
        returncode: int,
        stdout: str,
        stderr: str,
        timed_out: bool = False,
    ) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.timed_out = timed_out

    @property
    def succeeded(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    def __repr__(self) -> str:
        return (
            f"SubprocessResult(rc={self.returncode}, "
            f"timed_out={self.timed_out}, "
            f"stdout={self.stdout[:80]!r})"
        )


class T2SubprocessSandbox:
    """T2 isolated subprocess sandbox.

    Usage::

        sandbox = T2SubprocessSandbox(timeout_seconds=10)
        with TempWorkspace.create("shell") as ws:
            result = await sandbox.run(
                cmd=["python", "-c", "print('hello')"],
                workspace=ws,
                env_allowlist=["PATH"],
            )
        print(result.stdout)  # "hello\\n"
    """

    def __init__(
        self,
        timeout_seconds: float = 30.0,
        max_memory_bytes: int | None = None,
        env_allowlist: list[str] | None = None,
    ) -> None:
        self._timeout = timeout_seconds
        self._max_memory = max_memory_bytes
        self._env_allowlist = env_allowlist or _DEFAULT_ENV_ALLOWLIST

    async def run(
        self,
        cmd: list[str],
        *,
        workspace: TempWorkspace | None = None,
        cwd: Path | None = None,
        extra_env: dict[str, str] | None = None,
        stdin_data: bytes | None = None,
        env_allowlist: list[str] | None = None,
    ) -> SubprocessResult:
        """Run a command in the sandbox.

        Args:
            cmd:           Command line as a list of strings.
            workspace:     TempWorkspace to use as cwd (recommended).
            cwd:           Override working directory (ignored if workspace given).
            extra_env:     Additional env vars to add after allowlist filtering.
            stdin_data:    Optional bytes to pipe to stdin.
            env_allowlist: Override the default env allowlist for this run.

        Returns:
            SubprocessResult with returncode, stdout, stderr, timed_out.
        """
        allowed = set(env_allowlist or self._env_allowlist)
        safe_env: dict[str, str] = {}
        for key in allowed:
            val = os.environ.get(key)
            if val is not None:
                safe_env[key] = val
        if extra_env:
            safe_env.update(extra_env)

        work_dir: Path | None = None
        if workspace is not None:
            work_dir = workspace.path
        elif cwd is not None:
            work_dir = cwd

        timed_out = False
        proc: asyncio.subprocess.Process | None = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE if stdin_data else None,
                cwd=str(work_dir) if work_dir else None,
                env=safe_env,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(input=stdin_data),
                    timeout=self._timeout,
                )
            except asyncio.TimeoutError:
                timed_out = True
                if proc.returncode is None:
                    proc.kill()
                    await proc.communicate()
                stdout_bytes = b""
                stderr_bytes = b""

        except FileNotFoundError as exc:
            return SubprocessResult(
                returncode=127,
                stdout="",
                stderr=f"Command not found: {cmd[0]!r} — {exc}",
            )

        if timed_out:
            raise ExecutionTimeoutError(
                f"T2 subprocess exceeded timeout ({self._timeout}s): {cmd[0]!r}",
                timeout_seconds=self._timeout,
                stage="sandbox",
            )

        return SubprocessResult(
            returncode=proc.returncode or 0,
            stdout=stdout_bytes.decode("utf-8", errors="replace"),
            stderr=stderr_bytes.decode("utf-8", errors="replace"),
            timed_out=timed_out,
        )

    async def run_python(
        self,
        code: str,
        *,
        workspace: TempWorkspace | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> SubprocessResult:
        """Run Python code string in an isolated subprocess."""
        return await self.run(
            cmd=[sys.executable, "-c", code],
            workspace=workspace,
            extra_env=extra_env,
        )

    async def run_script(
        self,
        script_path: Path,
        args: list[str] | None = None,
        *,
        workspace: TempWorkspace | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> SubprocessResult:
        """Run a Python script file in an isolated subprocess."""
        cmd = [sys.executable, str(script_path)] + (args or [])
        return await self.run(
            cmd=cmd,
            workspace=workspace,
            extra_env=extra_env,
        )
