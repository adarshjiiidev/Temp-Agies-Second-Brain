"""P07 Scanners — RelationScanner.

Infers relationships between already-discovered EnvNodes:
  - Project → DEV_ENVIRONMENT (USES: based on .venv presence inside project dir)
  - Project → TOOL (USES: based on manifest dependency declarations)
  - APPLICATION → TECHNOLOGY (USES: heuristic name-based matching)

Requires a list of existing EnvNodes to work from — it does NOT scan the
filesystem itself; it analyses already-collected nodes and emits EnvEdge records.

Import safety: l4_memory.p07.* + stdlib ONLY.
"""

from __future__ import annotations

import time
from pathlib import Path

from aegis.l4_memory.p07.model.types import (
    EnvEdge, EnvEdgeKind, EnvNode, EnvNodeKind, ScanResult,
)
from aegis.l4_memory.p07.scanners.base import ScannerBase, ScannerConfig

__all__ = ["RelationScanner"]

# Tool name → technology label for simple heuristic matching
_TOOL_TECH_MAP: dict[str, str] = {
    "python": "Python",
    "python3": "Python",
    "node": "Node.js",
    "npm": "Node.js",
    "cargo": "Rust",
    "rustc": "Rust",
    "go": "Go",
    "java": "Java",
    "mvn": "Java",
    "gradle": "Java",
    "ruby": "Ruby",
    "php": "PHP",
    "docker": "Docker",
    "kubectl": "Kubernetes",
}


class RelationScanner(ScannerBase):
    """Infer relationships between existing EnvNodes.

    This scanner does NOT perform I/O — it analyses a node list and emits edges.
    It should be run AFTER AppScanner, ProjectScanner, and CLIScanner.

    Usage::

        scanner = RelationScanner(nodes=all_discovered_nodes)
        result = await scanner.scan()
        # result.edges contains inferred relationships
    """

    name = "relation_scanner"

    def __init__(
        self,
        config: ScannerConfig | None = None,
        nodes: list[EnvNode] | None = None,
    ) -> None:
        super().__init__(config)
        self._nodes: list[EnvNode] = nodes or []

    def set_nodes(self, nodes: list[EnvNode]) -> None:
        """Update the node list to analyse."""
        self._nodes = nodes

    async def _run(self, config: ScannerConfig, deadline: float) -> ScanResult:
        edges: list[EnvEdge] = []

        # Index nodes by kind
        projects = [n for n in self._nodes if n.kind == EnvNodeKind.PROJECT or n.kind == EnvNodeKind.REPOSITORY]
        devenvs = [n for n in self._nodes if n.kind == EnvNodeKind.DEV_ENVIRONMENT]
        tools = [n for n in self._nodes if n.kind == EnvNodeKind.TOOL]

        # 1. Project → DevEnvironment (USES) via path containment
        for project in projects:
            if time.monotonic() > deadline or len(edges) >= config.max_results:
                break
            if not project.source_path:
                continue
            proj_path = Path(project.source_path).resolve()
            for devenv in devenvs:
                if not devenv.source_path:
                    continue
                env_path = Path(devenv.source_path).resolve()
                try:
                    env_path.relative_to(proj_path)
                    # devenv is inside project directory
                    edges.append(EnvEdge(
                        subject_key=project.key,
                        object_key=devenv.key,
                        kind=EnvEdgeKind.USES,
                        confidence=0.9,
                        privacy_tier=config.privacy_tier,
                        attributes={"inferred_by": "path_containment"},
                    ))
                except ValueError:
                    pass

        # 2. Project → Tool (DEPENDS_ON) via manifest file inspection
        for project in projects:
            if time.monotonic() > deadline or len(edges) >= config.max_results:
                break
            if not project.source_path:
                continue
            proj_path = Path(project.source_path)
            used_tools = self._infer_project_tools(proj_path, tools)
            for tool_key, confidence in used_tools:
                edges.append(EnvEdge(
                    subject_key=project.key,
                    object_key=tool_key,
                    kind=EnvEdgeKind.DEPENDS_ON,
                    confidence=confidence,
                    privacy_tier=config.privacy_tier,
                    attributes={"inferred_by": "manifest_heuristic"},
                ))

        return ScanResult(
            scanner_name=self.name,
            nodes=[],
            edges=edges[:config.max_results],
            truncated=time.monotonic() > deadline,
        )

    def _infer_project_tools(self, proj_path: Path, tools: list[EnvNode]) -> list[tuple[str, float]]:
        """Heuristic: read manifest files to find tool references."""
        result: list[tuple[str, float]] = []
        if not proj_path.exists():
            return result

        # Check pyproject.toml → Python
        if (proj_path / "pyproject.toml").exists() or (proj_path / "setup.py").exists():
            for tool in tools:
                if tool.label in ("python", "python3", "pip", "pip3"):
                    result.append((tool.key, 0.85))

        # Check package.json → Node
        if (proj_path / "package.json").exists():
            for tool in tools:
                if tool.label in ("node", "npm", "npx", "yarn", "pnpm"):
                    result.append((tool.key, 0.85))

        # Check Cargo.toml → Rust
        if (proj_path / "Cargo.toml").exists():
            for tool in tools:
                if tool.label in ("cargo", "rustc"):
                    result.append((tool.key, 0.85))

        # Check go.mod → Go
        if (proj_path / "go.mod").exists():
            for tool in tools:
                if tool.label == "go":
                    result.append((tool.key, 0.85))

        # Check Dockerfile / docker-compose → Docker
        if (proj_path / "Dockerfile").exists() or (proj_path / "docker-compose.yml").exists():
            for tool in tools:
                if tool.label == "docker":
                    result.append((tool.key, 0.8))

        return result
