"""Capabilities model — CapabilityRecord (P08 semantic capability).

This is the canonical record for a capability in the P08 registry.
It answers: "What can AEGIS do, how is it implemented, who provided it,
is it trusted, and how reliable is it?"

Distinct from the pre-P08 env-probe `Capability` type (which answers
"is git installed?"). Both coexist; this is the semantic layer.

Import safety: stdlib + pydantic + aegis.capabilities.model.* only.
"""

from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from aegis.capabilities.model.composition import (
    BuiltinRef,
    CapabilityComposition,
    ImplementationRef,
    ImplementationType,
)
from aegis.capabilities.model.health import CapabilityHealth, HealthStatus
from aegis.capabilities.model.metrics import CapabilityMetrics

__all__ = [
    "CapabilityCategory",
    "ProvenanceSource",
    "TrustState",
    "CapabilityRecord",
]


class CapabilityCategory(str, Enum):
    """Semantic category of a capability."""
    FILESYSTEM      = "filesystem"
    SHELL           = "shell"
    GIT             = "git"
    DOCKER          = "docker"
    PYTHON_RUNTIME  = "python_runtime"
    NODE_RUNTIME    = "node_runtime"
    RUST_TOOLCHAIN  = "rust_toolchain"
    GO_TOOLCHAIN    = "go_toolchain"
    LOCAL_MODEL     = "local_model"
    CLOUD_MODEL     = "cloud_model"
    BROWSER         = "browser"
    WEB_SEARCH      = "web_search"
    MCP             = "mcp"
    EXTERNAL_AGENT  = "external_agent"
    DATABASE        = "database"
    VOICE           = "voice"
    VISION          = "vision"
    RESEARCH        = "research"
    FINANCE         = "finance"
    CODING          = "coding"
    COMMUNICATION   = "communication"
    MEMORY          = "memory"
    CUSTOM          = "custom"


class ProvenanceSource(str, Enum):
    """How a capability entered the registry."""
    BUILTIN         = "builtin"         # Shipped with AEGIS core
    SYSTEM_DISCOVERY = "system_discovery"  # Found via CLI/env probing
    USER_CONFIG     = "user_config"     # Explicitly configured by user
    PLUGIN          = "plugin"          # Declared by a L2 plugin
    MCP             = "mcp"             # Discovered from an MCP server
    EXTERNAL_AGENT  = "external_agent"  # Provided by an external agent
    CUSTOM          = "custom"          # Other


class TrustState(str, Enum):
    """Trust/authorization state of a capability.

    Discovery answers "does it exist?" — TrustState answers "may we use it?".
    New capabilities from external sources (MCP, plugins, external agents)
    always start as UNVERIFIED.
    """
    UNVERIFIED  = "unverified"   # Newly discovered; must not execute
    VERIFIED    = "verified"     # Metadata confirmed; may execute with policy approval
    TRUSTED     = "trusted"      # Explicit user or policy trust grant
    DISABLED    = "disabled"     # Explicitly disabled; must not execute


class CapabilityRecord(BaseModel):
    """Full semantic record for a single capability.

    The registry stores one CapabilityRecord per capability.
    Capabilities are uniquely identified by capability_id.
    """

    model_config = {"frozen": False, "validate_assignment": True}

    # --- Identity ---
    capability_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Globally unique identifier (UUID or stable slug)",
    )
    name: str = Field(description="Human-readable name, e.g. 'Git commit'")
    description: str = Field(default="", description="Semantic description for AI reasoning")
    category: CapabilityCategory

    # --- Versioning ---
    version: str = Field(default="0.0.0", description="Semver of this capability definition")
    provider_id: str = Field(
        default="builtin",
        description="Who provides this capability (executor name, MCP server id, agent id)",
    )

    # --- Provenance & Trust ---
    provenance: ProvenanceSource = ProvenanceSource.BUILTIN
    trust_state: TrustState = TrustState.UNVERIFIED
    registered_at: float = Field(default_factory=time.time)

    # --- Schemas ---
    input_schema: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema for capability inputs",
    )
    output_schema: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema for capability outputs",
    )

    # --- Permission & Privacy ---
    required_permissions: list[str] = Field(
        default_factory=list,
        description="SVRC verbs required to invoke (e.g. 'fs.write', 'network.request')",
    )
    required_resources: list[str] = Field(
        default_factory=list,
        description="Runtime binaries/services required (e.g. 'git', 'docker', 'ollama')",
    )
    privacy_tier: str = Field(
        default="P2",
        description="Minimum privacy tier for this capability (P0=most sensitive)",
    )

    # --- Environment ---
    online_required: bool = Field(
        default=False,
        description="True if this capability needs internet access",
    )
    supported_environments: list[str] = Field(
        default_factory=list,
        description="Supported OS/environments (e.g. ['windows', 'linux', 'macos']). Empty = all.",
    )

    # --- Implementation ---
    implementation: ImplementationRef = Field(
        default_factory=lambda: BuiltinRef(
            executor_name="unknown",
            action_kind="unknown",
        )
    )

    # --- Composition ---
    composition: CapabilityComposition = Field(
        default_factory=CapabilityComposition
    )

    # --- State ---
    enabled: bool = True

    # --- Health & Metrics ---
    health: CapabilityHealth = Field(default_factory=CapabilityHealth)
    metrics: CapabilityMetrics = Field(default_factory=CapabilityMetrics)

    # --- Reliability metadata (for ranking) ---
    limitations: list[str] = Field(
        default_factory=list,
        description="Known failure modes and edge cases",
    )

    # ------------------------------------------------------------------ #
    # Convenience properties
    # ------------------------------------------------------------------ #

    @property
    def is_usable(self) -> bool:
        """True if capability can be selected: enabled, not UNVERIFIED, health usable."""
        return (
            self.enabled
            and self.trust_state not in (TrustState.UNVERIFIED, TrustState.DISABLED)
            and self.health.is_usable
        )

    @property
    def is_builtin(self) -> bool:
        return self.implementation.type == ImplementationType.BUILTIN

    @property
    def is_mcp(self) -> bool:
        return self.implementation.type == ImplementationType.MCP_TOOL

    @property
    def is_composite(self) -> bool:
        return self.implementation.type == ImplementationType.COMPOSITE

    # ------------------------------------------------------------------ #
    # Ranking score (used by CapabilitySelector deterministic fallback)
    # ------------------------------------------------------------------ #

    def ranking_score(self) -> float:
        """Compute a composite ranking score 0.0–1.0.

        Higher = prefer this capability.
        Weights: success_rate 0.4, health 0.3, trust 0.2, freshness 0.1
        """
        # Success rate component
        sr = self.metrics.success_rate  # 0.0–1.0

        # Health component
        health_score = {
            HealthStatus.AVAILABLE:   1.0,
            HealthStatus.DEGRADED:    0.5,
            HealthStatus.UNKNOWN:     0.3,
            HealthStatus.UNAVAILABLE: 0.0,
            HealthStatus.DISABLED:    0.0,
        }.get(self.health.status, 0.0)

        # Trust component
        trust_score = {
            TrustState.TRUSTED:     1.0,
            TrustState.VERIFIED:    0.8,
            TrustState.UNVERIFIED:  0.0,
            TrustState.DISABLED:    0.0,
        }.get(self.trust_state, 0.0)

        # Implementation type preference: builtin > composite > mcp > agent
        impl_score = {
            ImplementationType.BUILTIN:        1.0,
            ImplementationType.COMPOSITE:      0.8,
            ImplementationType.MCP_TOOL:       0.6,
            ImplementationType.EXTERNAL_AGENT: 0.4,
        }.get(self.implementation.type, 0.5)

        return (
            sr          * 0.40
            + health_score  * 0.30
            + trust_score   * 0.20
            + impl_score    * 0.10
        )
