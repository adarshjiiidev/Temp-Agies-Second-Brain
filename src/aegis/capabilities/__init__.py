"""Capabilities subsystem — public API.

Pre-P08 (env-probe layer): CapabilityRegistry, Capability, CapabilityKind, etc.
P08+ (semantic layer): CapabilityRecord, SemanticCapabilityRegistry, MCP types, etc.

Both APIs coexist. The env-probe layer answers "is tool X installed?".
The semantic layer answers "what can AEGIS do and how?"
"""

# ---------------------------------------------------------------------------
# Pre-P08 env-probe layer (preserved for backward compatibility)
# ---------------------------------------------------------------------------
from aegis.capabilities.types import (
    Capability,
    CapabilityKind,
    CapabilityStatus,
    CapabilitySet,
)
from aegis.capabilities.registry import CapabilityRegistry

# ---------------------------------------------------------------------------
# P08 semantic model layer
# ---------------------------------------------------------------------------
from aegis.capabilities.model.capability import (
    CapabilityCategory,
    CapabilityRecord,
    ProvenanceSource,
    TrustState,
)
from aegis.capabilities.model.health import CapabilityHealth, HealthStatus
from aegis.capabilities.model.metrics import CapabilityMetrics
from aegis.capabilities.model.composition import (
    BuiltinRef,
    CapabilityComposition,
    ExternalAgentRef,
    ImplementationRef,
    ImplementationType,
    MCPToolRef,
    CompositeRef,
)

# P08 store
from aegis.capabilities.store.capability_store import CapabilityStore

# P08 semantic registry
from aegis.capabilities.registry_v2.capability_registry import CapabilityRegistry as SemanticCapabilityRegistry

# P08 discovery providers
from aegis.capabilities.discovery_providers.base import CapabilityDiscoveryProvider
from aegis.capabilities.discovery_providers.static_provider import StaticRegistryProvider
from aegis.capabilities.discovery_providers.cli_provider import CLIDiscoveryProvider
from aegis.capabilities.discovery_providers.local_model_provider import LocalModelDiscoveryProvider
from aegis.capabilities.discovery_providers.mcp_provider import MCPDiscoveryProvider
from aegis.capabilities.discovery_providers.plugin_provider import PluginDiscoveryProvider

# P08 MCP abstraction
from aegis.capabilities.mcp.types import MCPServerRecord, MCPToolRecord, MCPTransport
from aegis.capabilities.mcp.server_registry import MCPServerRegistry
from aegis.capabilities.mcp.tool_registry import MCPToolRegistry
from aegis.capabilities.mcp.schema_normalizer import MCPSchemaNormalizer
from aegis.capabilities.mcp.health_monitor import MCPHealthMonitor

# P08 selection
from aegis.capabilities.selection.schemas import (
    CapabilityConstraints,
    CapabilitySelectionInput,
    CapabilitySelectionOutput,
)
from aegis.capabilities.selection.selector import CapabilitySelector

# P08 invocation
from aegis.capabilities.invocation.invoker import CapabilityInvoker

# P08 external agents
from aegis.capabilities.external_agents.types import (
    AgentCommunication,
    AgentType,
    ExternalAgentCapability,
)

__all__ = [
    # --- Pre-P08 env-probe layer ---
    "Capability",
    "CapabilityKind",
    "CapabilityStatus",
    "CapabilitySet",
    "CapabilityRegistry",           # env-probe registry (pre-P08)
    # --- P08 model ---
    "CapabilityCategory",
    "CapabilityRecord",
    "ProvenanceSource",
    "TrustState",
    "CapabilityHealth",
    "HealthStatus",
    "CapabilityMetrics",
    "BuiltinRef",
    "CapabilityComposition",
    "ExternalAgentRef",
    "ImplementationRef",
    "ImplementationType",
    "MCPToolRef",
    "CompositeRef",
    # --- P08 store ---
    "CapabilityStore",
    # --- P08 semantic registry ---
    "SemanticCapabilityRegistry",   # P08 semantic registry (use this going forward)
    # --- P08 discovery providers ---
    "CapabilityDiscoveryProvider",
    "StaticRegistryProvider",
    "CLIDiscoveryProvider",
    "LocalModelDiscoveryProvider",
    "MCPDiscoveryProvider",
    "PluginDiscoveryProvider",
    # --- P08 MCP ---
    "MCPServerRecord",
    "MCPToolRecord",
    "MCPTransport",
    "MCPServerRegistry",
    "MCPToolRegistry",
    "MCPSchemaNormalizer",
    "MCPHealthMonitor",
    # --- P08 selection ---
    "CapabilityConstraints",
    "CapabilitySelectionInput",
    "CapabilitySelectionOutput",
    "CapabilitySelector",
    # --- P08 invocation ---
    "CapabilityInvoker",
    # --- P08 external agents ---
    "AgentCommunication",
    "AgentType",
    "ExternalAgentCapability",
]
