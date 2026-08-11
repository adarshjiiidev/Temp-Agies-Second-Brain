"""P07 Scanners — ApplicationDiscoveryProvider abstraction.

Provides a platform-neutral interface for application discovery backends.
The ApplicationScanner uses provider injection so that:
  - Windows uses WindowsRegistryProvider + PathToolProvider
  - Linux/macOS use PathToolProvider (and optionally XdgProvider in future)
  - Tests inject MockProvider with a deterministic fixture

This follows the same pattern as L3 ProviderRegistry — dependency injection,
no platform conditionals scattered through the scanner itself.

Import safety: l4_memory.p07.model.types + stdlib ONLY.
"""

from __future__ import annotations

import os
import shutil
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Protocol, runtime_checkable

from aegis.l4_memory.p07.model.types import EnvNode, EnvNodeKind

__all__ = [
    "ApplicationDiscoveryProvider",
    "PathToolProvider",
    "WindowsRegistryProvider",
    "CompositeProvider",
    "default_providers",
]

# ---------------------------------------------------------------------------
# Common CLI tools probed via shutil.which (cross-platform)
# ---------------------------------------------------------------------------

_COMMON_TOOLS: list[str] = [
    "git", "python", "python3", "pip", "node", "npm", "npx", "yarn",
    "cargo", "rustc", "go", "java", "mvn", "gradle", "docker",
    "kubectl", "terraform", "ansible", "make", "cmake", "gcc", "clang",
    "code", "vim", "nvim", "emacs", "curl", "wget", "jq", "rg", "fd",
    "ffmpeg", "pandoc", "sqlite3", "psql", "mysql",
]


# ---------------------------------------------------------------------------
# Provider protocol
# ---------------------------------------------------------------------------

class ApplicationDiscoveryProvider(ABC):
    """Abstract base for a single application discovery backend.

    Each provider discovers a subset of installed applications on the
    current platform and returns EnvNode records.

    All implementations must:
    - Respect the deadline (time.monotonic() > deadline → stop)
    - Respect max_results
    - Never raise — return an empty list on error
    - Never perform blocking I/O without a time budget

    Import safety: this module and all implementations may only import
    l4_memory.p07.model.types and stdlib.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable identifier for this provider (used in node attributes)."""

    @abstractmethod
    def discover(
        self,
        deadline: float,
        max_results: int,
        privacy_tier: str,
        existing_keys: set[str],
    ) -> list[EnvNode]:
        """Discover applications and return EnvNode records.

        Args:
            deadline:       time.monotonic() value — stop discovery when exceeded.
            max_results:    Maximum number of new nodes to return.
            privacy_tier:   Privacy tier to assign to returned nodes.
            existing_keys:  Keys already discovered (avoid duplicates).

        Returns:
            List of EnvNode records (may be empty). Never raises.
        """


# ---------------------------------------------------------------------------
# PATH-based provider (cross-platform)
# ---------------------------------------------------------------------------

class PathToolProvider(ApplicationDiscoveryProvider):
    """Discover tools available on PATH via shutil.which.

    Cross-platform. Works on Windows, Linux, macOS.
    """

    def __init__(self, tools: list[str] | None = None) -> None:
        """
        Args:
            tools: List of tool names to probe. Defaults to _COMMON_TOOLS.
        """
        self._tools = tools or list(_COMMON_TOOLS)

    @property
    def name(self) -> str:
        return "path_tool_provider"

    def discover(
        self,
        deadline: float,
        max_results: int,
        privacy_tier: str,
        existing_keys: set[str],
    ) -> list[EnvNode]:
        nodes: list[EnvNode] = []
        now = time.time()
        for tool in self._tools:
            if time.monotonic() > deadline or len(nodes) + len(existing_keys) >= max_results:
                break
            key = f"app:{tool}"
            if key in existing_keys:
                continue
            path = shutil.which(tool)
            if path:
                nodes.append(EnvNode(
                    key=key,
                    kind=EnvNodeKind.APPLICATION,
                    label=tool,
                    privacy_tier=privacy_tier,
                    source_path=str(Path(path).parent),
                    attributes={"executable": path, "source": self.name},
                    scanned_at=now,
                ))
        return nodes


# ---------------------------------------------------------------------------
# Windows registry provider
# ---------------------------------------------------------------------------

class WindowsRegistryProvider(ApplicationDiscoveryProvider):
    """Discover installed software via Windows Uninstall registry keys.

    Only active on Windows (os.name == 'nt'). On other platforms, discover()
    returns an empty list immediately without any I/O.

    Registry locations scanned:
      - HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall
      - HKLM\\SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall
      - HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall
    """

    @property
    def name(self) -> str:
        return "windows_registry_provider"

    def discover(
        self,
        deadline: float,
        max_results: int,
        privacy_tier: str,
        existing_keys: set[str],
    ) -> list[EnvNode]:
        if os.name != "nt":
            return []
        try:
            import winreg  # type: ignore[import]
        except ImportError:
            return []
        return self._scan_registry(winreg, deadline, max_results, privacy_tier, existing_keys)

    def _scan_registry(
        self,
        winreg,
        deadline: float,
        max_results: int,
        privacy_tier: str,
        existing_keys: set[str],
    ) -> list[EnvNode]:
        nodes: list[EnvNode] = []
        now = time.time()
        reg_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]

        for hive, path in reg_paths:
            if time.monotonic() > deadline or len(nodes) + len(existing_keys) >= max_results:
                break
            try:
                with winreg.OpenKey(hive, path) as key:
                    idx = 0
                    while True:
                        if time.monotonic() > deadline or len(nodes) + len(existing_keys) >= max_results:
                            break
                        try:
                            sub_name = winreg.EnumKey(key, idx)
                            idx += 1
                        except OSError:
                            break
                        try:
                            with winreg.OpenKey(key, sub_name) as sub:
                                def _qv(n: str, default: str = "") -> str:
                                    try:
                                        v, _ = winreg.QueryValueEx(sub, n)
                                        return str(v) if v else default
                                    except OSError:
                                        return default

                                display_name = _qv("DisplayName")
                                if not display_name:
                                    continue
                                node_key = f"app:{display_name.lower().replace(' ', '_')}"
                                if node_key in existing_keys:
                                    continue

                                version = _qv("DisplayVersion")
                                install_loc = _qv("InstallLocation")
                                publisher = _qv("Publisher")

                                nodes.append(EnvNode(
                                    key=node_key,
                                    kind=EnvNodeKind.APPLICATION,
                                    label=display_name,
                                    privacy_tier=privacy_tier,
                                    version=version or None,
                                    source_path=install_loc or None,
                                    attributes={
                                        "publisher": publisher,
                                        "install_location": install_loc,
                                        "source": self.name,
                                    },
                                    scanned_at=now,
                                ))
                        except OSError:
                            pass
            except OSError:
                pass

        return nodes


# ---------------------------------------------------------------------------
# Composite provider
# ---------------------------------------------------------------------------

class CompositeProvider(ApplicationDiscoveryProvider):
    """Aggregates multiple providers into a single discovery run.

    Providers are executed in order. Nodes from earlier providers take
    precedence (keys already discovered are skipped by later providers).
    """

    def __init__(self, providers: list[ApplicationDiscoveryProvider]) -> None:
        self._providers = list(providers)

    @property
    def name(self) -> str:
        return "composite_provider"

    def discover(
        self,
        deadline: float,
        max_results: int,
        privacy_tier: str,
        existing_keys: set[str],
    ) -> list[EnvNode]:
        all_nodes: list[EnvNode] = []
        seen: set[str] = set(existing_keys)
        for provider in self._providers:
            if time.monotonic() > deadline or len(all_nodes) + len(existing_keys) >= max_results:
                break
            remaining = max_results - len(all_nodes) - len(existing_keys)
            new_nodes = provider.discover(deadline, remaining, privacy_tier, seen)
            for node in new_nodes:
                seen.add(node.key)
            all_nodes.extend(new_nodes)
        return all_nodes


# ---------------------------------------------------------------------------
# Factory: default providers for current platform
# ---------------------------------------------------------------------------

def default_providers() -> list[ApplicationDiscoveryProvider]:
    """Return the default provider stack for the current platform.

    Windows: [WindowsRegistryProvider, PathToolProvider]
    Other:   [PathToolProvider]
    """
    providers: list[ApplicationDiscoveryProvider] = []
    if os.name == "nt":
        providers.append(WindowsRegistryProvider())
    providers.append(PathToolProvider())
    return providers
