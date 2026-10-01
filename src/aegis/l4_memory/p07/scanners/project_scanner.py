"""P07 Scanners — ProjectScanner.

Discovers project roots by scanning configured directories for VCS and
manifest markers (.git, .hg, pyproject.toml, package.json, Cargo.toml, etc.).

Bounded by max_seconds + max_results (STAB-01 pattern: lazy iteration).

Import safety: l4_memory.p07.* + stdlib ONLY.
"""

from __future__ import annotations

import time
from pathlib import Path

from aegis.l4_memory.p07.model.types import EnvEdge, EnvEdgeKind, EnvNode, EnvNodeKind, ScanResult
from aegis.l4_memory.p07.scanners.base import ScannerBase, ScannerConfig

__all__ = ["ProjectScanner"]

# Markers whose presence indicates a project root
_VCS_MARKERS = {".git", ".hg", ".svn"}
_MANIFEST_MARKERS = {
    "pyproject.toml", "setup.py", "setup.cfg",
    "package.json", "Cargo.toml", "go.mod",
    "pom.xml", "build.gradle", "CMakeLists.txt",
    "Makefile", "composer.json",
}

# Default roots to scan if not configured
_DEFAULT_ROOTS = [
    "~/Projects",
    "~/Documents",
    "~/Developer",
    "~/dev",
    "~/src",
    "~/code",
    "~/repos",
    "~/workspace",
]


class ProjectScanner(ScannerBase):
    """Scan configured roots for project directories.

    Produces EnvNode records of kind PROJECT or REPOSITORY.
    """

    name = "project_scanner"

    def __init__(
        self,
        config: ScannerConfig | None = None,
        roots: list[str] | None = None,
    ) -> None:
        super().__init__(config)
        self._roots = roots or _DEFAULT_ROOTS

    async def _run(self, config: ScannerConfig, deadline: float) -> ScanResult:
        nodes: list[EnvNode] = []
        now = time.time()

        for root_str in self._roots:
            if time.monotonic() > deadline or len(nodes) >= config.max_results:
                break
            root = Path(root_str).expanduser().resolve()
            if not root.exists() or not root.is_dir():
                continue
            self._scan_root(root, nodes, config, deadline, now)

        truncated = time.monotonic() > deadline or len(nodes) >= config.max_results
        return ScanResult(
            scanner_name=self.name,
            nodes=nodes[:config.max_results],
            truncated=truncated,
        )

    def _scan_root(
        self,
        root: Path,
        nodes: list[EnvNode],
        config: ScannerConfig,
        deadline: float,
        now: float,
        depth: int = 0,
        max_depth: int = 3,
    ) -> None:
        """Recursively scan root up to max_depth for project markers."""
        if depth > max_depth:
            return
        if time.monotonic() > deadline or len(nodes) >= config.max_results:
            return

        try:
            children = list(root.iterdir())
        except PermissionError:
            return

        has_vcs = any(c.name in _VCS_MARKERS for c in children)
        has_manifest = any(c.name in _MANIFEST_MARKERS for c in children)

        if has_vcs or has_manifest:
            kind = EnvNodeKind.REPOSITORY if has_vcs else EnvNodeKind.PROJECT
            key = f"project:{str(root).lower().replace(chr(92), '/').replace(' ', '_')}"
            nodes.append(EnvNode(
                key=key,
                kind=kind,
                label=root.name,
                privacy_tier=config.privacy_tier,
                source_path=str(root),
                attributes={
                    "path": str(root),
                    "has_vcs": has_vcs,
                    "has_manifest": has_manifest,
                    "markers": [
                        c.name for c in children
                        if c.name in _VCS_MARKERS | _MANIFEST_MARKERS
                    ],
                    "source": "project_scanner",
                },
                scanned_at=now,
            ))
            # Don't recurse into project roots (avoid nested repos)
            return

        # Recurse into non-project subdirectories
        for child in children:
            if time.monotonic() > deadline or len(nodes) >= config.max_results:
                break
            if child.is_dir() and not child.name.startswith("."):
                self._scan_root(child, nodes, config, deadline, now, depth + 1, max_depth)
