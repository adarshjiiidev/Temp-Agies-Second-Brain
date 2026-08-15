"""Capabilities discovery providers — pluggable discovery backends."""

from aegis.capabilities.discovery_providers.base import CapabilityDiscoveryProvider
from aegis.capabilities.discovery_providers.static_provider import StaticRegistryProvider
from aegis.capabilities.discovery_providers.cli_provider import CLIDiscoveryProvider
from aegis.capabilities.discovery_providers.local_model_provider import LocalModelDiscoveryProvider
from aegis.capabilities.discovery_providers.mcp_provider import MCPDiscoveryProvider
from aegis.capabilities.discovery_providers.plugin_provider import PluginDiscoveryProvider

__all__ = [
    "CapabilityDiscoveryProvider",
    "StaticRegistryProvider",
    "CLIDiscoveryProvider",
    "LocalModelDiscoveryProvider",
    "MCPDiscoveryProvider",
    "PluginDiscoveryProvider",
]
