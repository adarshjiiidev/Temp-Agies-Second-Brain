"""P07 Scanners — CLIScanner.

Discovers CLI tools and dev environments via:
  1. shutil.which over an extended tool list.
  2. Virtual environment detection (common venv dirs in project roots).
  3. Shell rc files for PATH additions (read-only, bounded).

Import safety: l4_memory.p07.* + stdlib ONLY.
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

from aegis.l4_memory.p07.model.types import EnvNode, EnvNodeKind, ScanResult
from aegis.l4_memory.p07.scanners.base import ScannerBase, ScannerConfig

__all__ = ["CLIScanner"]

_EXTENDED_TOOLS = [
    # Version managers
    "nvm", "pyenv", "rbenv", "asdf", "volta", "fnm",
    # Build / CI
    "make", "cmake", "ninja", "bazel", "buck",
    "gh", "glab", "act",
    # Containers / cloud
    "docker", "podman", "kubectl", "helm", "minikube",
    "aws", "gcloud", "az", "terraform", "pulumi",
    # Databases
    "psql", "mysql", "redis-cli", "mongosh",
    # Languages
    "python", "python3", "pip", "pip3",
    "node", "npm", "npx", "yarn", "pnpm", "bun",
    "ruby", "gem", "bundle",
    "go", "cargo", "rustc",
    "java", "javac", "mvn", "gradle",
    "php", "composer",
    # Editors / IDEs
    "code", "cursor", "vim", "nvim", "nano", "emacs",
    # Utilities
    "git", "curl", "wget", "jq", "yq", "fzf", "rg",
    "fd", "bat", "exa", "lsd", "zoxide",
    "ffmpeg", "imagemagick", "pandoc",
    # Testing
    "pytest", "jest", "mocha", "rspec",
]

# Common venv directory names inside project roots
_VENV_NAMES = {".venv", "venv", "env", ".env", "virtualenv"}


class CLIScanner(ScannerBase):
    """Discover installed CLI tools and dev environments."""

    name = "cli_scanner"

    def __init__(
        self,
        config: ScannerConfig | None = None,
        project_roots: list[str] | None = None,
    ) -> None:
        super().__init__(config)
        self._project_roots = project_roots or []

    async def _run(self, config: ScannerConfig, deadline: float) -> ScanResult:
        nodes: list[EnvNode] = []
        now = time.time()

        # 1. Tool discovery via shutil.which
        for tool in _EXTENDED_TOOLS:
            if time.monotonic() > deadline or len(nodes) >= config.max_results:
                break
            path = shutil.which(tool)
            if path:
                nodes.append(EnvNode(
                    key=f"tool:{tool}",
                    kind=EnvNodeKind.TOOL,
                    label=tool,
                    privacy_tier=config.privacy_tier,
                    source_path=str(Path(path).parent),
                    attributes={"executable": path, "source": "PATH"},
                    scanned_at=now,
                ))

        # 2. Virtual environment detection in project roots
        for root_str in self._project_roots:
            if time.monotonic() > deadline or len(nodes) >= config.max_results:
                break
            root = Path(root_str).expanduser().resolve()
            if not root.exists():
                continue
            try:
                for child in root.iterdir():
                    if time.monotonic() > deadline:
                        break
                    if child.is_dir() and child.name in _VENV_NAMES:
                        python_path = child / "bin" / "python"
                        if not python_path.exists():
                            python_path = child / "Scripts" / "python.exe"
                        key = f"devenv:{str(child).lower().replace(chr(92), '/').replace(' ', '_')}"
                        nodes.append(EnvNode(
                            key=key,
                            kind=EnvNodeKind.DEV_ENVIRONMENT,
                            label=f"{root.name}/{child.name}",
                            privacy_tier=config.privacy_tier,
                            source_path=str(child),
                            attributes={
                                "type": "python_venv",
                                "python": str(python_path) if python_path.exists() else None,
                                "project": str(root),
                                "source": "venv_scan",
                            },
                            scanned_at=now,
                        ))
            except PermissionError:
                pass

        truncated = time.monotonic() > deadline or len(nodes) >= config.max_results
        return ScanResult(
            scanner_name=self.name,
            nodes=nodes[:config.max_results],
            truncated=truncated,
        )
