"""Capabilities MCP abstraction — types.

MCPServerRecord and MCPToolRecord are the internal AEGIS representation
of MCP servers and their tools. These are normalized from whatever the
MCP server reports.

SECURITY NOTE: An MCPServerRecord entry does NOT mean the server is trusted.
Trust elevation (UNVERIFIED → VERIFIED → TRUSTED) is a separate step
that must happen explicitly through MCPServerRegistry.set_trust().

Import safety: stdlib + pydantic + aegis.capabilities.model.health only.
"""

from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from aegis.capabilities.model.health import CapabilityHealth, HealthStatus
from aegis.capabilities.model.capability import TrustState

__all__ = ["MCPTransport", "MCPServerRecord", "MCPToolRecord"]


class MCPTransport(str, Enum):
    """MCP transport mechanism."""
    STDIO = "stdio"   # subprocess stdin/stdout (local)
    HTTP  = "http"    # HTTP + SSE (remote or local)
    SSE   = "sse"     # Server-Sent Events (subset of HTTP)


class MCPServerRecord(BaseModel):
    """Registry entry for a configured MCP server."""

    model_config = {"frozen": False}

    server_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    transport: MCPTransport = MCPTransport.HTTP
    endpoint: str = ""          # URL for HTTP/SSE, command for STDIO
    command: list[str] = Field(default_factory=list)  # For STDIO transport
    env: dict[str, str] = Field(default_factory=dict)  # Env vars for STDIO

    # Trust & provenance
    trust_state: TrustState = TrustState.UNVERIFIED  # Always starts unverified
    provenance: str = "user_config"  # How the server was registered
    registered_at: float = Field(default_factory=time.time)
    registered_by: str = "system"

    # Health
    health: CapabilityHealth = Field(
        default_factory=lambda: CapabilityHealth(status=HealthStatus.UNKNOWN)
    )

    # Metadata
    server_version: str | None = None
    protocol_version: str = "2024-11-05"   # MCP spec version

    @property
    def is_local(self) -> bool:
        """True if this server runs locally (STDIO or localhost HTTP)."""
        if self.transport == MCPTransport.STDIO:
            return True
        endpoint = self.endpoint.lower()
        return "localhost" in endpoint or "127.0.0.1" in endpoint or "::1" in endpoint


class MCPToolRecord(BaseModel):
    """Registry entry for a tool exposed by an MCP server."""

    model_config = {"frozen": False}

    tool_id: str = ""             # Composite: f"{server_id}:{tool_name}"
    server_id: str
    tool_name: str
    description: str = ""

    # Normalized schemas
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)

    # Risk and privacy (inferred or declared by server)
    risk_hints: dict[str, Any] = Field(default_factory=dict)
    privacy_tier: str = "P2"

    # State
    enabled: bool = True
    discovered_at: float = Field(default_factory=time.time)

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        if not self.tool_id and self.server_id and self.tool_name:
            object.__setattr__(self, "tool_id", f"{self.server_id}:{self.tool_name}")
