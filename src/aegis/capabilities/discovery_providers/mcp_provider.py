"""Capabilities discovery — MCPDiscoveryProvider.

Discovers capabilities from registered MCP servers.

IMPORTANT: All MCP-discovered capabilities start as UNVERIFIED.
They cannot be executed until explicitly elevated to VERIFIED or TRUSTED
by the user or a policy rule. This enforces the discovery ≠ authorization
boundary required by the P08 security model.

Import safety: stdlib + aegis.capabilities.model + aegis.capabilities.mcp only.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from aegis.capabilities.discovery_providers.base import CapabilityDiscoveryProvider
from aegis.capabilities.model.capability import (
    CapabilityCategory,
    CapabilityRecord,
    ProvenanceSource,
    TrustState,
)
from aegis.capabilities.model.composition import MCPToolRef, ImplementationType
from aegis.capabilities.model.health import CapabilityHealth, HealthStatus

if TYPE_CHECKING:
    from aegis.capabilities.mcp.server_registry import MCPServerRegistry

logger = logging.getLogger(__name__)

__all__ = ["MCPDiscoveryProvider"]


class MCPDiscoveryProvider(CapabilityDiscoveryProvider):
    """Discovers capabilities from registered MCP servers.

    For each registered server:
    1. Checks server health (is it reachable?)
    2. Fetches the tool list
    3. Converts each tool to a CapabilityRecord with trust_state=UNVERIFIED

    Requires a MCPServerRegistry to be injected (the registry knows which
    servers are configured — this provider does not auto-discover servers
    on the network, which would be a security risk).

    Usage::

        mcp_registry = MCPServerRegistry()
        # ... register servers ...
        provider = MCPDiscoveryProvider(mcp_registry)
        records = provider.safe_discover(deadline=time.monotonic() + 10)
    """

    def __init__(self, server_registry: "MCPServerRegistry | None" = None) -> None:
        self._server_registry = server_registry

    @property
    def name(self) -> str:
        return "mcp_discovery_provider"

    def discover(self, deadline: float) -> list[CapabilityRecord]:
        if self._server_registry is None:
            return []

        records: list[CapabilityRecord] = []
        servers = self._server_registry.list_servers()

        for server in servers:
            if time.monotonic() > deadline:
                logger.warning("MCPDiscoveryProvider: deadline exceeded, stopping early")
                break

            if server.trust_state == TrustState.DISABLED:
                logger.debug(
                    "MCPDiscoveryProvider: skipping disabled server %r", server.server_id
                )
                continue

            # Fetch tools from the server registry (already discovered)
            tools = self._server_registry.list_tools(server_id=server.server_id)

            for tool in tools:
                if time.monotonic() > deadline:
                    break

                cap_id = f"mcp:{server.server_id}:{tool.tool_name}"
                record = CapabilityRecord(
                    capability_id=cap_id,
                    name=f"[MCP] {server.name}/{tool.tool_name}",
                    description=tool.description,
                    category=CapabilityCategory.MCP,
                    version="1.0.0",
                    provider_id=f"mcp:{server.server_id}",
                    provenance=ProvenanceSource.MCP,
                    # KEY SECURITY INVARIANT: MCP tools always start UNVERIFIED
                    trust_state=TrustState.UNVERIFIED,
                    online_required=server.transport in ("http", "sse"),
                    privacy_tier=tool.privacy_tier,
                    required_permissions=list(tool.risk_hints.get("required_permissions", [])),
                    input_schema=tool.input_schema,
                    output_schema=tool.output_schema,
                    implementation=MCPToolRef(
                        server_id=server.server_id,
                        tool_name=tool.tool_name,
                        tool_id=f"{server.server_id}:{tool.tool_name}",
                    ),
                    health=CapabilityHealth(
                        status=(
                            HealthStatus.AVAILABLE
                            if server.health.status == HealthStatus.AVAILABLE
                            else HealthStatus.UNAVAILABLE
                        )
                    ),
                    enabled=True,
                )
                records.append(record)

        logger.debug(
            "MCPDiscoveryProvider: discovered %d capabilities from %d servers",
            len(records), len(servers),
        )
        return records
