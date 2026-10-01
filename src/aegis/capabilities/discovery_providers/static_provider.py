"""Capabilities discovery — StaticRegistryProvider.

Returns a fixed set of builtin AEGIS capabilities that are always available
regardless of environment. These represent core L5 executor capabilities.

These are TRUSTED by default (builtin, shipped with AEGIS).

Import safety: stdlib + aegis.capabilities.model only.
"""

from __future__ import annotations

import sys

from aegis.capabilities.discovery_providers.base import CapabilityDiscoveryProvider
from aegis.capabilities.model.capability import (
    CapabilityCategory,
    CapabilityRecord,
    ProvenanceSource,
    TrustState,
)
from aegis.capabilities.model.composition import BuiltinRef, ImplementationType
from aegis.capabilities.model.health import CapabilityHealth, HealthStatus

__all__ = ["StaticRegistryProvider"]


def _builtin(
    cap_id: str,
    name: str,
    description: str,
    category: CapabilityCategory,
    executor_name: str,
    action_kind: str,
    required_permissions: list[str] | None = None,
    online_required: bool = False,
    privacy_tier: str = "P2",
) -> CapabilityRecord:
    return CapabilityRecord(
        capability_id=cap_id,
        name=name,
        description=description,
        category=category,
        version="1.0.0",
        provider_id="builtin",
        provenance=ProvenanceSource.BUILTIN,
        trust_state=TrustState.TRUSTED,
        required_permissions=required_permissions or [],
        online_required=online_required,
        privacy_tier=privacy_tier,
        implementation=BuiltinRef(
            executor_name=executor_name,
            action_kind=action_kind,
            module_path=f"aegis.l5_execution.executors.{executor_name.replace('_executor', '')}",
        ),
        health=CapabilityHealth(status=HealthStatus.AVAILABLE),
        enabled=True,
    )


# ---------------------------------------------------------------------------
# Builtin capability catalog
# ---------------------------------------------------------------------------

_BUILTIN_CAPABILITIES: list[CapabilityRecord] = [
    # Filesystem
    _builtin(
        "builtin:fs.read",
        "Filesystem Read",
        "Read files and directories from the local filesystem",
        CapabilityCategory.FILESYSTEM,
        "filesystem_executor", "fs.read",
        required_permissions=["fs.read"],
    ),
    _builtin(
        "builtin:fs.write",
        "Filesystem Write",
        "Write, create, or modify files on the local filesystem",
        CapabilityCategory.FILESYSTEM,
        "filesystem_executor", "fs.write",
        required_permissions=["fs.write"],
        privacy_tier="P1",
    ),
    _builtin(
        "builtin:fs.delete",
        "Filesystem Delete",
        "Delete files or directories from the local filesystem",
        CapabilityCategory.FILESYSTEM,
        "filesystem_executor", "fs.delete",
        required_permissions=["fs.delete"],
        privacy_tier="P1",
    ),
    _builtin(
        "builtin:fs.search",
        "Filesystem Search",
        "Search for files matching patterns in the local filesystem",
        CapabilityCategory.FILESYSTEM,
        "filesystem_executor", "fs.search",
        required_permissions=["fs.read"],
    ),
    # Shell
    _builtin(
        "builtin:shell.exec",
        "Shell Execute",
        "Execute shell commands in a sandboxed environment",
        CapabilityCategory.SHELL,
        "shell_executor", "shell.exec",
        required_permissions=["shell.exec"],
        privacy_tier="P1",
    ),
    # Python execution
    _builtin(
        "builtin:python.exec",
        "Python Execute",
        "Execute Python code in an isolated sandbox",
        CapabilityCategory.PYTHON_RUNTIME,
        "python_exec_executor", "python.exec",
        required_permissions=["python.exec"],
        privacy_tier="P1",
    ),
    # HTTP
    _builtin(
        "builtin:http.get",
        "HTTP GET",
        "Make HTTP GET requests to external URLs",
        CapabilityCategory.WEB_SEARCH,
        "http_executor", "http.get",
        required_permissions=["network.request"],
        online_required=True,
        privacy_tier="P2",
    ),
    _builtin(
        "builtin:http.post",
        "HTTP POST",
        "Make HTTP POST requests to external APIs",
        CapabilityCategory.WEB_SEARCH,
        "http_executor", "http.post",
        required_permissions=["network.request"],
        online_required=True,
        privacy_tier="P2",
    ),
    # Memory (via L4 — described at L5 invocation boundary)
    _builtin(
        "builtin:memory.store",
        "Memory Store",
        "Store information in the AEGIS memory engine",
        CapabilityCategory.MEMORY,
        "memory_executor", "memory.store",
        required_permissions=["memory.write"],
        privacy_tier="P0",
    ),
    _builtin(
        "builtin:memory.recall",
        "Memory Recall",
        "Retrieve information from the AEGIS memory engine",
        CapabilityCategory.MEMORY,
        "memory_executor", "memory.recall",
        required_permissions=["memory.read"],
        privacy_tier="P0",
    ),
]


class StaticRegistryProvider(CapabilityDiscoveryProvider):
    """Returns the fixed builtin AEGIS capability catalog.

    Always runs offline. Capabilities are TRUSTED by default.
    Used as the baseline registry that guarantees core L5 capabilities
    are always present in the CapabilityRegistry.
    """

    @property
    def name(self) -> str:
        return "static_registry_provider"

    def discover(self, deadline: float) -> list[CapabilityRecord]:
        """Return all builtin capabilities (no I/O, instant)."""
        # Add Python runtime version to the python.exec capability
        py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        result = []
        for cap in _BUILTIN_CAPABILITIES:
            if cap.capability_id == "builtin:python.exec":
                cap = cap.model_copy(update={"version": py_version})
            result.append(cap)
        return result
