"""Capabilities MCP abstraction layer — P08 provider-neutral MCP boundary."""

from aegis.capabilities.mcp.types import (
    MCPServerRecord,
    MCPToolRecord,
    MCPTransport,
)
from aegis.capabilities.mcp.server_registry import MCPServerRegistry
from aegis.capabilities.mcp.tool_registry import MCPToolRegistry
from aegis.capabilities.mcp.schema_normalizer import MCPSchemaNormalizer
from aegis.capabilities.mcp.health_monitor import MCPHealthMonitor

__all__ = [
    "MCPServerRecord",
    "MCPToolRecord",
    "MCPTransport",
    "MCPServerRegistry",
    "MCPToolRegistry",
    "MCPSchemaNormalizer",
    "MCPHealthMonitor",
]
