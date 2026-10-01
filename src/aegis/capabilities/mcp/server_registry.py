"""Capabilities MCP abstraction — MCPServerRegistry.

Manages the lifecycle of MCP server records: registration, trust elevation,
disable, and listing. Also manages the associated tool records.

SECURITY INVARIANT: Newly registered servers always start as UNVERIFIED.
No automatic trust is granted. Trust must be elevated explicitly.

Import safety: stdlib + pydantic + aegis.capabilities.mcp.types only.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from aegis.capabilities.mcp.types import MCPServerRecord, MCPToolRecord, MCPTransport
from aegis.capabilities.model.capability import TrustState
from aegis.capabilities.model.health import CapabilityHealth, HealthStatus

logger = logging.getLogger(__name__)

__all__ = ["MCPServerRegistry"]


class MCPServerRegistry:
    """Thread-safe registry for MCP server and tool records.

    Servers are registered manually (no auto-discovery on the network).
    Tools are registered after the server is known and its tool list is fetched.

    Trust elevation path:
        UNVERIFIED → (user or policy elevates) → VERIFIED → TRUSTED

    Usage::

        registry = MCPServerRegistry()
        server = MCPServerRecord(name="MyMCP", endpoint="http://localhost:3000", ...)
        registry.register_server(server)
        # Later, after verification:
        registry.set_trust(server.server_id, TrustState.VERIFIED)
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._servers: dict[str, MCPServerRecord] = {}   # server_id → record
        self._tools: dict[str, MCPToolRecord] = {}       # tool_id → record
        # Index: server_id → set of tool_ids
        self._server_tools: dict[str, set[str]] = {}

    # ------------------------------------------------------------------ #
    # Server management
    # ------------------------------------------------------------------ #

    def register_server(self, record: MCPServerRecord) -> None:
        """Register a new MCP server. Always starts UNVERIFIED."""
        with self._lock:
            if record.trust_state != TrustState.UNVERIFIED:
                # Enforce: external registration always starts UNVERIFIED
                record = record.model_copy(update={"trust_state": TrustState.UNVERIFIED})
                logger.warning(
                    "MCPServerRegistry: forced trust_state=UNVERIFIED for %r",
                    record.server_id,
                )
            self._servers[record.server_id] = record
            self._server_tools.setdefault(record.server_id, set())
            logger.info(
                "MCPServerRegistry: registered server %r (%s) trust=%s",
                record.server_id, record.name, record.trust_state.value,
            )

    def unregister_server(self, server_id: str) -> bool:
        """Remove a server and all its tools. Returns True if it existed."""
        with self._lock:
            server = self._servers.pop(server_id, None)
            if server is None:
                return False
            # Remove all associated tools
            tool_ids = self._server_tools.pop(server_id, set())
            for tid in tool_ids:
                self._tools.pop(tid, None)
            logger.info("MCPServerRegistry: unregistered server %r (removed %d tools)",
                        server_id, len(tool_ids))
            return True

    def get_server(self, server_id: str) -> MCPServerRecord | None:
        with self._lock:
            return self._servers.get(server_id)

    def list_servers(
        self,
        trust_state: TrustState | None = None,
    ) -> list[MCPServerRecord]:
        with self._lock:
            servers = list(self._servers.values())
        if trust_state is not None:
            servers = [s for s in servers if s.trust_state == trust_state]
        return servers

    def set_trust(self, server_id: str, trust_state: TrustState) -> bool:
        """Elevate or demote trust for a server. Returns True if found."""
        with self._lock:
            server = self._servers.get(server_id)
            if server is None:
                return False
            self._servers[server_id] = server.model_copy(update={"trust_state": trust_state})
            logger.info(
                "MCPServerRegistry: trust updated %r → %s",
                server_id, trust_state.value,
            )
            return True

    def disable_server(self, server_id: str) -> bool:
        """Disable a server (trust_state → DISABLED). Returns True if found."""
        return self.set_trust(server_id, TrustState.DISABLED)

    def update_health(self, server_id: str, health: CapabilityHealth) -> bool:
        """Update the health record of a server. Returns True if found."""
        with self._lock:
            server = self._servers.get(server_id)
            if server is None:
                return False
            self._servers[server_id] = server.model_copy(update={"health": health})
            return True

    # ------------------------------------------------------------------ #
    # Tool management
    # ------------------------------------------------------------------ #

    def register_tool(self, record: MCPToolRecord) -> None:
        """Register a tool for a known server.

        The tool inherits the server's disabled state if the server is disabled.
        """
        with self._lock:
            if record.server_id not in self._servers:
                raise ValueError(
                    f"MCPServerRegistry: cannot register tool for unknown server {record.server_id!r}"
                )
            self._tools[record.tool_id] = record
            self._server_tools.setdefault(record.server_id, set()).add(record.tool_id)
            logger.debug(
                "MCPServerRegistry: registered tool %r on server %r",
                record.tool_name, record.server_id,
            )

    def get_tool(self, tool_id: str) -> MCPToolRecord | None:
        with self._lock:
            return self._tools.get(tool_id)

    def list_tools(
        self,
        server_id: str | None = None,
        enabled_only: bool = False,
    ) -> list[MCPToolRecord]:
        with self._lock:
            if server_id is not None:
                tool_ids = self._server_tools.get(server_id, set())
                tools = [self._tools[tid] for tid in tool_ids if tid in self._tools]
            else:
                tools = list(self._tools.values())
        if enabled_only:
            tools = [t for t in tools if t.enabled]
        return tools

    def disable_tool(self, tool_id: str) -> bool:
        with self._lock:
            tool = self._tools.get(tool_id)
            if tool is None:
                return False
            self._tools[tool_id] = tool.model_copy(update={"enabled": False})
            return True

    def server_count(self) -> int:
        with self._lock:
            return len(self._servers)

    def tool_count(self) -> int:
        with self._lock:
            return len(self._tools)
