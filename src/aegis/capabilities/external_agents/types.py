"""Capabilities external agents — metadata types for future agent integration.

P08 establishes the abstraction required for later integration of:
- Codex-style coding agents
- Browser agents (Playwright-backed)
- Research agents
- Prime-style harnesses
- OpenClaw / Hermes / OpenCode wrappers

SCOPE: P08 provides the metadata model ONLY.
Actual agent communication and execution is deferred to P20+.
ExternalAgentCapability records may be registered and queried
but invoking them through CapabilityInvoker returns a clear stub error.

Import safety: stdlib + pydantic only.
"""

from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

__all__ = ["AgentType", "AgentCommunication", "ExternalAgentCapability"]


class AgentType(str, Enum):
    """Type of external agent."""
    CODING    = "coding"     # Code generation, editing, debugging
    BROWSER   = "browser"    # Web browsing, form filling, scraping
    RESEARCH  = "research"   # Information gathering, synthesis
    TERMINAL  = "terminal"   # CLI command execution
    VISION    = "vision"     # Screen capture, OCR, visual analysis
    FINANCE   = "finance"    # Market data, trading, analysis
    CUSTOM    = "custom"     # User-defined agent type


class AgentCommunication(str, Enum):
    """How AEGIS communicates with the external agent."""
    HTTP   = "http"    # REST/JSON over HTTP
    STDIO  = "stdio"   # stdin/stdout subprocess
    GRPC   = "grpc"    # gRPC (future)
    MCP    = "mcp"     # Via MCP protocol (agent exposed as MCP server)


class ExternalAgentCapability(BaseModel):
    """Metadata record for an external agent capability.

    This record describes what an external agent can do, how to communicate
    with it, and what resources/permissions it requires. It does NOT contain
    the actual communication logic (deferred to P20+).

    Registered in the CapabilityRegistry as category=EXTERNAL_AGENT with
    implementation=ExternalAgentRef.
    """

    model_config = {"frozen": True}

    agent_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    agent_type: AgentType

    # Declared capabilities (what this agent can do)
    declared_capabilities: list[str] = Field(
        default_factory=list,
        description="List of capability verbs this agent can perform",
    )

    # Communication
    communication: AgentCommunication = AgentCommunication.HTTP
    endpoint: str = ""
    command: list[str] = Field(default_factory=list)  # For STDIO

    # Schemas
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)

    # Resource requirements
    runtime_requirements: list[str] = Field(
        default_factory=list,
        description="Required binaries or services (e.g. 'node', 'docker')",
    )
    memory_mb: int | None = None
    gpu_required: bool = False

    # Privacy & permissions
    privacy_tier: str = "P2"
    required_permissions: list[str] = Field(default_factory=list)

    # Lifecycle
    supports_persistence: bool = False   # Can state persist between invocations
    supports_streaming: bool = False     # Can results be streamed

    # Provenance
    provenance: str = "user_config"
    version: str = "0.0.0"
    registered_at: float = Field(default_factory=time.time)

    # P08 stub marker
    _p08_stub: bool = True  # Remove when P20+ wires the actual communication

    @property
    def invocation_note(self) -> str:
        """Human-readable note about P08 stub state."""
        return (
            f"ExternalAgentCapability[{self.agent_id!r}] is a P08 metadata stub. "
            f"Full {self.agent_type.value} agent integration is planned for P20+."
        )
