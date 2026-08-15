"""Capabilities model — CapabilityComposition + ImplementationRef.

Describes how a capability is implemented and how it relates to
other capabilities (dependencies and composition groups).

Import safety: stdlib + pydantic only.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

__all__ = [
    "ImplementationType",
    "BuiltinRef",
    "MCPToolRef",
    "CompositeRef",
    "ExternalAgentRef",
    "ImplementationRef",
    "CapabilityComposition",
]


class ImplementationType(str, Enum):
    """How a capability is implemented."""
    BUILTIN        = "builtin"         # Native Python code within AEGIS L5 executors
    MCP_TOOL       = "mcp_tool"        # Wrapped MCP server tool
    COMPOSITE      = "composite"       # Composed from other capabilities
    EXTERNAL_AGENT = "external_agent"  # Delegated to an external agent (P20+)


class BuiltinRef(BaseModel):
    """Reference to a builtin L5 executor action."""
    type: Literal[ImplementationType.BUILTIN] = ImplementationType.BUILTIN
    executor_name: str        # e.g. "filesystem_executor"
    action_kind: str          # e.g. "fs.read"
    module_path: str = ""     # e.g. "aegis.l5_execution.executors.filesystem"


class MCPToolRef(BaseModel):
    """Reference to an MCP server tool."""
    type: Literal[ImplementationType.MCP_TOOL] = ImplementationType.MCP_TOOL
    server_id: str            # Registered MCPServerRecord.server_id
    tool_name: str            # Tool name as reported by the MCP server
    tool_id: str = ""         # Composite key: f"{server_id}:{tool_name}"


class CompositeRef(BaseModel):
    """Reference to a composite capability (ordered sequence of sub-capabilities)."""
    type: Literal[ImplementationType.COMPOSITE] = ImplementationType.COMPOSITE
    step_capability_ids: list[str] = Field(default_factory=list)
    parallel_groups: list[list[str]] = Field(default_factory=list)  # Optional parallel steps


class ExternalAgentRef(BaseModel):
    """Reference to an external agent (P20+ — stub in P08)."""
    type: Literal[ImplementationType.EXTERNAL_AGENT] = ImplementationType.EXTERNAL_AGENT
    agent_id: str
    agent_type: str = "unknown"     # e.g. "codex", "browser", "research"
    communication: str = "http"     # "http" | "stdio" | "grpc"
    endpoint: str = ""


# Discriminated union for type-safe polymorphism
ImplementationRef = Annotated[
    Union[BuiltinRef, MCPToolRef, CompositeRef, ExternalAgentRef],
    Field(discriminator="type"),
]


class CapabilityComposition(BaseModel):
    """Describes capability dependencies and composition relationships."""

    model_config = {"frozen": True}

    depends_on: list[str] = Field(
        default_factory=list,
        description="capability_ids this capability requires to function",
    )
    composes_with: list[str] = Field(
        default_factory=list,
        description="capability_ids that can be combined with this one",
    )
