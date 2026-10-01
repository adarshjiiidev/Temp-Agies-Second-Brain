"""AgentMoe — typed configuration.

Every tunable value in the AgentMoe fabric lives here.
No hardcoding in tool/worker/security implementations.

Constants classification (per AGENTS.md hardcoding audit):
  - Timeout values          → configuration
  - Depth/concurrency limits → configuration
  - Security invariants      → safety boundaries (not config, marked SAFETY)
  - Retry counts             → configuration
  - Autonomy default         → configuration
"""

from __future__ import annotations

from pathlib import Path
from typing import FrozenSet, Optional

from pydantic import BaseModel, Field


class FilesystemConfig(BaseModel):
    """Filesystem tool configuration."""

    workspace_root: Path = Field(
        default=Path.home() / "workspace",
        description="Default workspace root. Tools enforce that operations stay inside.",
    )
    max_read_bytes: int = Field(
        default=10 * 1024 * 1024,  # 10 MB
        description="Maximum bytes returned by a single FS_READ call.",
    )
    max_search_results: int = Field(
        default=500,
        description="Maximum results returned by a single FS_SEARCH call.",
    )
    search_timeout_seconds: float = Field(
        default=10.0,
        description="Wall-clock budget for FS_SEARCH traversal.",
    )
    # SAFETY — never allow operations outside workspace without explicit grant
    allow_outside_workspace: bool = Field(
        default=False,
        description="If False (SAFETY default), all FS ops are restricted to workspace_root.",
    )


class TerminalConfig(BaseModel):
    """Terminal tool configuration."""

    default_timeout_seconds: float = Field(
        default=60.0,
        description="Default command timeout.",
    )
    max_timeout_seconds: float = Field(
        default=600.0,
        description="Maximum allowed timeout any caller may request.",
    )
    max_output_bytes: int = Field(
        default=1 * 1024 * 1024,  # 1 MB
        description="Maximum output captured per command invocation.",
    )
    # SAFETY — shell=True is always prohibited; this flag is informational only
    allow_shell_string: bool = Field(
        default=False,
        description="SAFETY — always False. Shell string execution is prohibited.",
    )
    env_passthrough_allowlist: FrozenSet[str] = Field(
        default=frozenset({"PATH", "HOME", "USER", "LANG", "TERM"}),
        description="Environment variables passed through to subprocess.",
    )


class BrowserConfig(BaseModel):
    """Browser tool configuration."""

    headless: bool = Field(default=True, description="Run browser headless.")
    default_timeout_seconds: float = Field(default=30.0)
    max_download_bytes: int = Field(
        default=50 * 1024 * 1024,  # 50 MB
        description="Maximum download size.",
    )
    download_dir: Optional[Path] = Field(
        default=None,
        description="Where downloads land. None = temp dir under workspace.",
    )
    allowed_domains: FrozenSet[str] = Field(
        default=frozenset(),
        description="If non-empty, only these domains are reachable. Empty = all (subject to SSRF guard).",
    )
    blocked_domains: FrozenSet[str] = Field(
        default=frozenset(),
        description="Domains always blocked regardless of other config.",
    )


class WorkerConfig(BaseModel):
    """Worker runtime configuration."""

    max_depth: int = Field(
        default=4,
        description="Maximum worker delegation depth (parent→child→grandchild...).",
    )
    max_concurrent_workers: int = Field(
        default=8,
        description="Maximum simultaneously active workers per session.",
    )
    default_worker_timeout_seconds: float = Field(
        default=300.0,
        description="Default timeout for a worker task.",
    )
    max_worker_timeout_seconds: float = Field(
        default=3600.0,
        description="Maximum allowed worker timeout.",
    )
    shutdown_grace_seconds: float = Field(
        default=10.0,
        description="How long to wait for workers to stop cleanly on shutdown.",
    )


class ModelConfig(BaseModel):
    """Model fabric configuration."""

    default_task_timeout_seconds: float = Field(default=60.0)
    max_retries: int = Field(default=3)
    retry_base_delay_seconds: float = Field(default=1.0)
    retry_max_delay_seconds: float = Field(default=30.0)
    credential_pool_rotation: str = Field(
        default="health_weighted",
        description="Key rotation strategy: 'round_robin' | 'health_weighted' | 'least_used'.",
    )


class SwarmConfig(BaseModel):
    """Swarm coordination configuration."""

    max_workers: int = Field(default=16)
    max_depth: int = Field(default=3)
    max_total_budget_tokens: int = Field(
        default=500_000,
        description="Hard token budget across all workers in a swarm.",
    )
    max_runtime_seconds: float = Field(default=1800.0)


class AgentMoeConfig(BaseModel):
    """Root configuration for the AgentMoe fabric.

    Instantiate once and pass to AgentMoeSession or ToolFabric.

    Usage::

        from aegis.agentmoe.config.settings import AgentMoeConfig
        cfg = AgentMoeConfig()               # all defaults
        cfg = AgentMoeConfig(
            autonomy_level=2,
            filesystem=FilesystemConfig(workspace_root=Path("/workspace")),
        )
    """

    autonomy_level: int = Field(
        default=2,
        ge=0,
        le=5,
        description=(
            "L0=observe-only, L1=suggest, L2=execute-low-risk (default), "
            "L3=approved-workflows, L4=autonomous-bounded, L5=system-level (disabled by default)."
        ),
    )
    # SAFETY — L5 disabled by default; must be set explicitly
    allow_autonomy_level_5: bool = Field(
        default=False,
        description="SAFETY gate for autonomy L5. Must be explicitly True to use L5.",
    )

    session_timeout_seconds: float = Field(
        default=3600.0,
        description="Maximum lifetime of an AgentMoe session.",
    )

    filesystem: FilesystemConfig = Field(default_factory=FilesystemConfig)
    terminal: TerminalConfig = Field(default_factory=TerminalConfig)
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    workers: WorkerConfig = Field(default_factory=WorkerConfig)
    models: ModelConfig = Field(default_factory=ModelConfig)
    swarm: SwarmConfig = Field(default_factory=SwarmConfig)

    class Config:
        frozen = True  # config is immutable at runtime
