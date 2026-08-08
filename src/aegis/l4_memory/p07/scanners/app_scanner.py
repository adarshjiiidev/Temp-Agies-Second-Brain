"""P07 Scanners — ApplicationScanner.

Discovers installed applications via:
  1. Windows registry (winreg) — HKLM/HKCU Uninstall keys.
  2. PATH executables (shutil.which over common tool names).
  3. Common install directories (lazy rglob, STAB-01 pattern).

All operations are bounded by max_seconds + max_results.
Privacy zone checks must be performed by the caller (coordinator).

Import safety: l4_memory.p07.* + stdlib ONLY. No L5/L6/L3.
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

from aegis.l4_memory.p07.model.types import EnvNode, EnvNodeKind, ScanResult
from aegis.l4_memory.p07.scanners.base import ScannerBase, ScannerConfig

__all__ = ["ApplicationScanner"]

# Common CLI tools to probe via shutil.which
_COMMON_TOOLS = [
    "git", "python", "python3", "pip", "node", "npm", "npx", "yarn",
    "cargo", "rustc", "go", "java", "mvn", "gradle", "docker",
    "kubectl", "terraform", "ansible", "make", "cmake", "gcc", "clang",
    "code", "vim", "nvim", "emacs", "curl", "wget", "jq", "rg", "fd",
    "ffmpeg", "pandoc", "sqlite3", "psql", "mysql",
]


class ApplicationScanner(ScannerBase):
    """Discover installed applications (Windows + cross-platform PATH scan).

    Produces EnvNode records of kind APPLICATION.
    """

    name = "app_scanner"

    async def _run(self, config: ScannerConfig, deadline: float) -> ScanResult:
        nodes: list[EnvNode] = []
        now = time.time()

        # 1. Windows registry scan
        if os.name == "nt":
            nodes.extend(self._scan_registry(config, deadline, now))

        if time.monotonic() > deadline or len(nodes) >= config.max_results:
            return ScanResult(scanner_name=self.name, nodes=nodes, truncated=True)

        # 2. PATH / shutil.which scan (cross-platform)
        nodes.extend(self._scan_path(config, deadline, now, existing_keys={n.key for n in nodes}))

        truncated = time.monotonic() > deadline or len(nodes) >= config.max_results
        return ScanResult(scanner_name=self.name, nodes=nodes[:config.max_results], truncated=truncated)

    def _scan_registry(self, config: ScannerConfig, deadline: float, now: float) -> list[EnvNode]:
        """Scan Windows Uninstall registry keys for installed software."""
        nodes: list[EnvNode] = []
        try:
            import winreg  # type: ignore[import]
        except ImportError:
            return nodes  # Not on Windows or winreg unavailable

        reg_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]

        for hive, path in reg_paths:
            if time.monotonic() > deadline or len(nodes) >= config.max_results:
                break
            try:
                with winreg.OpenKey(hive, path) as key:
                    idx = 0
                    while True:
                        if time.monotonic() > deadline or len(nodes) >= config.max_results:
                            break
                        try:
                            sub_name = winreg.EnumKey(key, idx)
                            idx += 1
                        except OSError:
                            break
                        try:
                            with winreg.OpenKey(key, sub_name) as sub:
                                def _qv(name: str, default: str = "") -> str:
                                    try:
                                        v, _ = winreg.QueryValueEx(sub, name)
                                        return str(v) if v else default
                                    except OSError:
                                        return default

                                display_name = _qv("DisplayName")
                                if not display_name:
                                    continue
                                version = _qv("DisplayVersion")
                                install_loc = _qv("InstallLocation")
                                publisher = _qv("Publisher")

                                node = EnvNode(
                                    key=f"app:{display_name.lower().replace(' ', '_')}",
                                    kind=EnvNodeKind.APPLICATION,
                                    label=display_name,
                                    privacy_tier=config.privacy_tier,
                                    version=version or None,
                                    source_path=install_loc or None,
                                    attributes={
                                        "publisher": publisher,
                                        "install_location": install_loc,
                                        "source": "winreg",
                                    },
                                    scanned_at=now,
                                )
                                nodes.append(node)
                        except OSError:
                            pass
            except OSError:
                pass

        return nodes

    def _scan_path(
        self,
        config: ScannerConfig,
        deadline: float,
        now: float,
        existing_keys: set[str],
    ) -> list[EnvNode]:
        """Probe common tool names via shutil.which."""
        nodes: list[EnvNode] = []
        for tool in _COMMON_TOOLS:
            if time.monotonic() > deadline or len(nodes) + len(existing_keys) >= config.max_results:
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
                    privacy_tier=config.privacy_tier,
                    source_path=str(Path(path).parent),
                    attributes={"executable": path, "source": "PATH"},
                    scanned_at=now,
                ))
        return nodes
