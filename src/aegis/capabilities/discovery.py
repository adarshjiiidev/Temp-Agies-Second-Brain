"""Capabilities subsystem — Runtime discovery probes.

Each probe checks for the presence and version of a specific capability.
Probes are fast (< 500ms each), non-destructive, and failure-safe.

Import safety: stdlib + aegis.capabilities.types only.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
import sys
import time

from aegis.capabilities.types import Capability, CapabilityKind, CapabilityStatus

logger = logging.getLogger(__name__)

__all__ = [
    "probe_git",
    "probe_docker",
    "probe_python",
    "probe_node",
    "probe_shell",
    "probe_filesystem",
    "probe_network",
    "probe_ollama",
    "probe_all",
]

_PROBE_TIMEOUT = 3.0  # seconds per probe


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str]) -> tuple[bool, str]:
    """Run a command and return (success, stdout)."""
    try:
        r = subprocess.run(
            cmd,
            capture_output=True, text=True,
            timeout=_PROBE_TIMEOUT,
        )
        return r.returncode == 0, r.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False, ""


def _make(kind: CapabilityKind, *, ok: bool, name: str,
          version: str | None = None, path: str | None = None,
          error: str | None = None) -> Capability:
    return Capability(
        kind=kind,
        name=name,
        status=CapabilityStatus.AVAILABLE if ok else CapabilityStatus.UNAVAILABLE,
        version=version,
        path=path,
        error=error,
        last_probed_at=time.time(),
    )


# ---------------------------------------------------------------------------
# Individual probes
# ---------------------------------------------------------------------------

def probe_git() -> Capability:
    path = shutil.which("git")
    ok, out = _run(["git", "--version"]) if path else (False, "")
    version = out.split()[-1] if ok else None
    return _make(CapabilityKind.GIT, ok=ok, name=f"Git {version or '?'}",
                 version=version, path=path,
                 error=None if ok else "git not found in PATH")


def probe_docker() -> Capability:
    path = shutil.which("docker")
    ok, out = _run(["docker", "--version"]) if path else (False, "")
    version = out.split()[-1].rstrip(",") if ok else None
    return _make(CapabilityKind.DOCKER, ok=ok, name=f"Docker {version or '?'}",
                 version=version, path=path,
                 error=None if ok else "docker not found in PATH")


def probe_python() -> Capability:
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    path = sys.executable
    return _make(CapabilityKind.PYTHON, ok=True,
                 name=f"Python {version}", version=version, path=path)


def probe_node() -> Capability:
    path = shutil.which("node")
    ok, out = _run(["node", "--version"]) if path else (False, "")
    version = out.lstrip("v") if ok else None
    return _make(CapabilityKind.NODE, ok=ok, name=f"Node.js {version or '?'}",
                 version=version, path=path,
                 error=None if ok else "node not found in PATH")


def probe_shell() -> Capability:
    """Detect available shell (bash/sh/powershell)."""
    for shell in ("bash", "sh", "powershell"):
        p = shutil.which(shell)
        if p:
            return _make(CapabilityKind.SHELL, ok=True,
                         name=f"Shell ({shell})", path=p)
    return _make(CapabilityKind.SHELL, ok=False, name="Shell",
                 error="No shell found in PATH")


def probe_filesystem() -> Capability:
    """Filesystem is always available (we're running on one)."""
    import os
    return _make(CapabilityKind.FILESYSTEM, ok=True,
                 name="Filesystem", path=os.getcwd())


def probe_network() -> Capability:
    """Check basic network connectivity."""
    import socket
    try:
        socket.setdefaulttimeout(2)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return _make(CapabilityKind.NETWORK, ok=True, name="Network (internet)")
    except (OSError, socket.timeout):
        return _make(CapabilityKind.NETWORK, ok=False, name="Network (offline)",
                     error="No internet connectivity detected")


def probe_ollama() -> Capability:
    """Check if Ollama is running locally."""
    path = shutil.which("ollama")
    if not path:
        return _make(CapabilityKind.OLLAMA, ok=False, name="Ollama",
                     error="ollama not found in PATH")
    ok, out = _run(["ollama", "list"])
    return _make(CapabilityKind.OLLAMA, ok=ok, name="Ollama (local LLM)",
                 path=path, error=None if ok else "ollama list failed")


async def probe_all() -> list[Capability]:
    """Run all probes concurrently and return results.

    Probes are run in a thread pool to avoid blocking the event loop.
    """
    probes = [
        probe_git, probe_docker, probe_python, probe_node,
        probe_shell, probe_filesystem, probe_network, probe_ollama,
    ]
    loop = asyncio.get_event_loop()
    results = await asyncio.gather(
        *[loop.run_in_executor(None, p) for p in probes],
        return_exceptions=True,
    )
    capabilities = []
    for probe, result in zip(probes, results):
        if isinstance(result, Exception):
            logger.warning("Probe %s failed: %s", probe.__name__, result)
            # Create an UNKNOWN capability for failed probes
            capabilities.append(Capability(
                kind=CapabilityKind.CUSTOM,
                name=probe.__name__,
                status=CapabilityStatus.UNKNOWN,
                error=str(result),
            ))
        else:
            capabilities.append(result)
    return capabilities
