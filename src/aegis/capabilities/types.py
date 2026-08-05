"""Capabilities subsystem — shared types.

Defines the data model for discovered runtime capabilities.
Capabilities are runtime facts: "what can AEGIS do right now?"

Import safety: stdlib + pydantic only.
"""

from __future__ import annotations

import time
from enum import Enum
from pydantic import BaseModel, Field

__all__ = [
    "CapabilityKind",
    "CapabilityStatus",
    "Capability",
    "CapabilitySet",
]


class CapabilityKind(str, Enum):
    """The category of a capability."""
    # Development tools
    GIT         = "git"
    DOCKER      = "docker"
    PYTHON      = "python"
    NODE        = "node"
    RUST        = "rust"
    GO          = "go"

    # System tools
    SHELL       = "shell"
    FILESYSTEM  = "filesystem"
    NETWORK     = "network"

    # AI/ML tools
    OLLAMA      = "ollama"
    LM_STUDIO   = "lm_studio"
    CUDA        = "cuda"

    # Application tools
    BROWSER     = "browser"
    VISION      = "vision"
    VOICE       = "voice"
    CAMERA      = "camera"

    # Integration
    MCP         = "mcp"
    VSCODE      = "vscode"

    # Other
    CUSTOM      = "custom"


class CapabilityStatus(str, Enum):
    """Runtime availability status of a capability."""
    AVAILABLE    = "available"      # Probed and confirmed present
    UNAVAILABLE  = "unavailable"    # Probed and confirmed absent
    DEGRADED     = "degraded"       # Present but not fully functional
    UNKNOWN      = "unknown"        # Not yet probed


class Capability(BaseModel):
    """A single runtime capability with status and metadata."""

    model_config = {"frozen": True}

    kind: CapabilityKind
    name: str                                   # Human-readable (e.g. "Git 2.43.0")
    status: CapabilityStatus = CapabilityStatus.UNKNOWN
    version: str | None = None                  # Version string if discoverable
    path: str | None = None                     # Executable path if applicable
    metadata: dict = Field(default_factory=dict)  # Extra probe data
    last_probed_at: float = Field(default_factory=time.time)
    error: str | None = None                    # Error message if probe failed

    @property
    def is_available(self) -> bool:
        return self.status == CapabilityStatus.AVAILABLE

    def __str__(self) -> str:
        v = f" {self.version}" if self.version else ""
        return f"{self.kind.value}{v} [{self.status.value}]"


class CapabilitySet(BaseModel):
    """Immutable snapshot of all discovered capabilities."""

    model_config = {"frozen": True}

    capabilities: list[Capability] = Field(default_factory=list)
    discovered_at: float = Field(default_factory=time.time)

    def get(self, kind: CapabilityKind) -> Capability | None:
        """Return the first capability of the given kind."""
        for cap in self.capabilities:
            if cap.kind == kind:
                return cap
        return None

    def is_available(self, kind: CapabilityKind) -> bool:
        """True if this capability kind is available."""
        cap = self.get(kind)
        return cap is not None and cap.is_available

    def available_kinds(self) -> list[CapabilityKind]:
        """List all kinds with AVAILABLE status."""
        return [c.kind for c in self.capabilities if c.is_available]

    def to_summary_dict(self) -> dict:
        """Compact summary for prompt injection."""
        return {
            c.kind.value: {
                "available": c.is_available,
                "version": c.version,
            }
            for c in self.capabilities
        }
