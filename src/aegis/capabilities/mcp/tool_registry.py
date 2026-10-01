"""Capabilities MCP abstraction — MCPToolRegistry.

Thin convenience layer over MCPServerRegistry.list_tools() that provides
tool-centric lookup. In P08 the tool registry IS the server registry for
tool storage — this class provides a focused interface.

Import safety: stdlib + aegis.capabilities.mcp.server_registry only.
"""

from __future__ import annotations

from aegis.capabilities.mcp.server_registry import MCPServerRegistry
from aegis.capabilities.mcp.types import MCPToolRecord

__all__ = ["MCPToolRegistry"]


class MCPToolRegistry:
    """Tool-centric view over the MCPServerRegistry.

    Delegates to MCPServerRegistry for storage; provides tool-focused API.
    """

    def __init__(self, server_registry: MCPServerRegistry) -> None:
        self._registry = server_registry

    def get_tool(self, tool_id: str) -> MCPToolRecord | None:
        return self._registry.get_tool(tool_id)

    def list_tools(
        self,
        server_id: str | None = None,
        enabled_only: bool = False,
    ) -> list[MCPToolRecord]:
        return self._registry.list_tools(server_id=server_id, enabled_only=enabled_only)

    def register_tool(self, record: MCPToolRecord) -> None:
        self._registry.register_tool(record)

    def disable_tool(self, tool_id: str) -> bool:
        return self._registry.disable_tool(tool_id)
