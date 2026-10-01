"""Capabilities discovery — CLIDiscoveryProvider.

Wraps the existing env-probe layer (aegis.capabilities.discovery) to convert
raw CLI probe results into CapabilityRecord objects.

Capabilities found via CLI probing start as VERIFIED (the tool exists and
responds to --version) but require explicit user trust elevation to TRUSTED
before they can be used for privacy-sensitive operations.

Import safety: stdlib + aegis.capabilities.model + aegis.capabilities.discovery
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import time

from aegis.capabilities.discovery_providers.base import CapabilityDiscoveryProvider
from aegis.capabilities.model.capability import (
    CapabilityCategory,
    CapabilityRecord,
    ProvenanceSource,
    TrustState,
)
from aegis.capabilities.model.composition import BuiltinRef
from aegis.capabilities.model.health import CapabilityHealth, HealthStatus

logger = logging.getLogger(__name__)

__all__ = ["CLIDiscoveryProvider"]

_PROBE_TIMEOUT = 3.0


def _run_version(cmd: list[str]) -> str | None:
    """Run a version command and return stdout, or None on failure."""
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=_PROBE_TIMEOUT,
        )
        if r.returncode == 0:
            return r.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None


def _make_cli_record(
    cap_id: str,
    name: str,
    description: str,
    category: CapabilityCategory,
    action_kind: str,
    path: str,
    version: str | None,
    required_permissions: list[str] | None = None,
    privacy_tier: str = "P2",
) -> CapabilityRecord:
    return CapabilityRecord(
        capability_id=cap_id,
        name=f"{name}{' ' + version if version else ''}",
        description=description,
        category=category,
        version=version or "unknown",
        provider_id="cli_discovery",
        provenance=ProvenanceSource.SYSTEM_DISCOVERY,
        trust_state=TrustState.VERIFIED,   # Found on system — not yet user-trusted
        required_permissions=required_permissions or [],
        privacy_tier=privacy_tier,
        implementation=BuiltinRef(
            executor_name=action_kind.split(".")[0] + "_executor",
            action_kind=action_kind,
            module_path=path,
        ),
        health=CapabilityHealth(
            status=HealthStatus.AVAILABLE,
            path_detected=path,
            version_detected=version,
        ),
        enabled=True,
    )


# ---------------------------------------------------------------------------
# CLI tool probe definitions
# ---------------------------------------------------------------------------

_CLI_TOOLS: list[dict] = [
    {
        "id": "cli:git",
        "name": "Git",
        "desc": "Version control operations: commit, push, pull, branch, merge",
        "category": CapabilityCategory.GIT,
        "cmd": "git",
        "version_cmd": ["git", "--version"],
        "version_extract": lambda o: o.split()[-1] if o else None,
        "action_kind": "git.exec",
        "permissions": ["git.read", "git.write"],
        "privacy_tier": "P1",
    },
    {
        "id": "cli:docker",
        "name": "Docker",
        "desc": "Container lifecycle: build, run, stop, remove containers and images",
        "category": CapabilityCategory.DOCKER,
        "cmd": "docker",
        "version_cmd": ["docker", "--version"],
        "version_extract": lambda o: o.split()[-1].rstrip(",") if o else None,
        "action_kind": "docker.exec",
        "permissions": ["docker.exec"],
        "privacy_tier": "P1",
    },
    {
        "id": "cli:node",
        "name": "Node.js",
        "desc": "Run JavaScript/TypeScript applications and Node.js scripts",
        "category": CapabilityCategory.NODE_RUNTIME,
        "cmd": "node",
        "version_cmd": ["node", "--version"],
        "version_extract": lambda o: o.lstrip("v") if o else None,
        "action_kind": "shell.exec",
        "permissions": ["shell.exec"],
        "privacy_tier": "P1",
    },
    {
        "id": "cli:cargo",
        "name": "Cargo (Rust)",
        "desc": "Build, test, and manage Rust projects",
        "category": CapabilityCategory.RUST_TOOLCHAIN,
        "cmd": "cargo",
        "version_cmd": ["cargo", "--version"],
        "version_extract": lambda o: o.split()[1] if o and len(o.split()) > 1 else None,
        "action_kind": "shell.exec",
        "permissions": ["shell.exec"],
        "privacy_tier": "P2",
    },
    {
        "id": "cli:go",
        "name": "Go",
        "desc": "Build and run Go programs",
        "category": CapabilityCategory.GO_TOOLCHAIN,
        "cmd": "go",
        "version_cmd": ["go", "version"],
        "version_extract": lambda o: o.split()[2].lstrip("go") if o and len(o.split()) > 2 else None,
        "action_kind": "shell.exec",
        "permissions": ["shell.exec"],
        "privacy_tier": "P2",
    },
    {
        "id": "cli:make",
        "name": "Make",
        "desc": "Run Makefile build targets",
        "category": CapabilityCategory.CODING,
        "cmd": "make",
        "version_cmd": ["make", "--version"],
        "version_extract": lambda o: o.split("\n")[0].split()[-1] if o else None,
        "action_kind": "shell.exec",
        "permissions": ["shell.exec"],
        "privacy_tier": "P2",
    },
    {
        "id": "cli:ollama",
        "name": "Ollama",
        "desc": "Run local LLM inference via Ollama",
        "category": CapabilityCategory.LOCAL_MODEL,
        "cmd": "ollama",
        "version_cmd": ["ollama", "--version"],
        "version_extract": lambda o: o.strip().split()[-1] if o else None,
        "action_kind": "shell.exec",
        "permissions": ["network.local"],
        "privacy_tier": "P0",
    },
]


class CLIDiscoveryProvider(CapabilityDiscoveryProvider):
    """Discovers CLI tools available on PATH and converts them to CapabilityRecords.

    Each found tool produces one or more VERIFIED capability records.
    Capabilities start as VERIFIED (exists on this system) — not TRUSTED
    (explicit user authorization not yet granted).
    """

    def __init__(self, tools: list[dict] | None = None) -> None:
        """
        Args:
            tools: Override the default tool probe list (for testing).
        """
        self._tools = tools if tools is not None else _CLI_TOOLS

    @property
    def name(self) -> str:
        return "cli_discovery_provider"

    def discover(self, deadline: float) -> list[CapabilityRecord]:
        """Probe each tool and return CapabilityRecord for found ones."""
        records: list[CapabilityRecord] = []
        for tool_def in self._tools:
            if time.monotonic() > deadline:
                logger.warning("CLIDiscoveryProvider: deadline exceeded, stopping early")
                break
            cmd = tool_def["cmd"]
            path = shutil.which(cmd)
            if not path:
                continue
            out = _run_version(tool_def["version_cmd"])
            version: str | None = None
            try:
                version = tool_def["version_extract"](out)
            except Exception:  # noqa: BLE001
                pass
            record = _make_cli_record(
                cap_id=tool_def["id"],
                name=tool_def["name"],
                description=tool_def["desc"],
                category=tool_def["category"],
                action_kind=tool_def["action_kind"],
                path=path,
                version=version,
                required_permissions=tool_def.get("permissions", []),
                privacy_tier=tool_def.get("privacy_tier", "P2"),
            )
            records.append(record)
            logger.debug(
                "CLIDiscoveryProvider: found %r at %s v%s",
                tool_def["id"], path, version or "?",
            )
        return records
