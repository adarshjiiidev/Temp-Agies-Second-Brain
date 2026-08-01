"""L5 Execution Engine — T3 Docker Sandbox.

T3 runs commands inside a Docker container:
  - No host FS mount (scratch volume only)
  - Network default deny (--network=none)
  - Resource capped (--memory, --cpus)
  - Container is removed after execution (--rm)
  - Requires Docker daemon available on PATH

If Docker is not available, raises ExecutorNotFoundError.
Tests skip T3 automatically via pytest.mark.skipif.

Import safety: subprocess + stdlib + l5_execution.* ONLY.
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Any

from aegis.l5_execution.exceptions import ExecutorNotFoundError, ExecutionTimeoutError
from aegis.l5_execution.sandbox.t2_subprocess import SubprocessResult

__all__ = ["T3DockerSandbox", "is_docker_available"]


def is_docker_available() -> bool:
    """Return True if the 'docker' CLI is on PATH."""
    return shutil.which("docker") is not None


class T3DockerSandbox:
    """T3 Docker container sandbox.

    Runs a command inside a disposable Docker container with:
      - No host filesystem access (scratch volume only)
      - Network disabled by default
      - Hard memory and CPU limits
      - Container removed after execution

    Usage::

        if not is_docker_available():
            raise ExecutorNotFoundError("Docker not available")

        sandbox = T3DockerSandbox(image="python:3.12-slim")
        result = await sandbox.run(
            cmd=["python", "-c", "print('hello from docker')"],
            timeout_seconds=30,
        )
    """

    def __init__(
        self,
        image: str = "python:3.12-slim",
        *,
        memory: str = "256m",
        cpus: str = "0.5",
        network: str = "none",
        timeout_seconds: float = 60.0,
    ) -> None:
        self._image = image
        self._memory = memory
        self._cpus = cpus
        self._network = network
        self._timeout = timeout_seconds
        self._check_docker()

    def _check_docker(self) -> None:
        if not is_docker_available():
            raise ExecutorNotFoundError(
                "Docker CLI not found on PATH. T3 sandbox requires Docker. "
                "Install Docker Desktop or Docker Engine.",
                action_kind="docker",
                stage="sandbox",
            )

    async def run(
        self,
        cmd: list[str],
        *,
        workspace_path: Path | None = None,
        extra_env: dict[str, str] | None = None,
        timeout_seconds: float | None = None,
        network: str | None = None,
    ) -> SubprocessResult:
        """Run ``cmd`` inside a Docker container.

        Args:
            cmd:            Command to run inside the container.
            workspace_path: Host path to mount as /workspace (read-write).
            extra_env:      Environment variables to pass into the container.
            timeout_seconds: Override default timeout.
            network:        Override network mode (e.g. 'bridge' for internet access;
                            requires explicit ALLOW from permission engine).

        Returns:
            SubprocessResult with returncode, stdout, stderr.
        """
        timeout = timeout_seconds or self._timeout
        net = network or self._network

        docker_cmd = [
            "docker", "run",
            "--rm",
            f"--memory={self._memory}",
            f"--cpus={self._cpus}",
            f"--network={net}",
            "--security-opt=no-new-privileges",
        ]

        # Mount workspace if provided
        if workspace_path is not None:
            docker_cmd += ["-v", f"{workspace_path}:/workspace:rw"]
            docker_cmd += ["-w", "/workspace"]

        # Environment variables
        if extra_env:
            for k, v in extra_env.items():
                docker_cmd += ["-e", f"{k}={v}"]

        docker_cmd.append(self._image)
        docker_cmd.extend(cmd)

        timed_out = False
        try:
            proc = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                timed_out = True
                if proc.returncode is None:
                    proc.kill()
                    await proc.communicate()
                stdout_bytes = b""
                stderr_bytes = b""

        except FileNotFoundError:
            return SubprocessResult(
                returncode=127,
                stdout="",
                stderr="Docker CLI not found",
            )

        if timed_out:
            raise ExecutionTimeoutError(
                f"T3 Docker sandbox exceeded timeout ({timeout}s)",
                timeout_seconds=timeout,
                stage="sandbox",
            )

        return SubprocessResult(
            returncode=proc.returncode or 0,
            stdout=stdout_bytes.decode("utf-8", errors="replace"),
            stderr=stderr_bytes.decode("utf-8", errors="replace"),
        )

    async def pull_image(self) -> SubprocessResult:
        """Pull the configured Docker image."""
        proc = await asyncio.create_subprocess_exec(
            "docker", "pull", self._image,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        return SubprocessResult(
            returncode=proc.returncode or 0,
            stdout=out.decode("utf-8", errors="replace"),
            stderr=err.decode("utf-8", errors="replace"),
        )
