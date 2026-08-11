"""L3 AI Kernel public package — Prompt 03.

This is the stable public API for all AEGIS AI inference. Import from here
rather than from submodules directly.

Quick-start::

    from aegis.l3_intelligence.ai_kernel import (
        AIKernel,
        AIRequest,
        AIResponse,
        RoutingRequirements,
        PrivacyTier,
        ModelRegistry,
        ModelMetadata,
    )
"""

from __future__ import annotations

# Core contracts
from aegis.l3_intelligence.ai_kernel.contracts import (
    AIRequest,
    AIResponse,
    BudgetLedgerEntry,
    RoutingRequirements,
    ScrubResult,
    StructuredOutputRequirements,
    TokenUsage,
)

# Kernel orchestrator
from aegis.l3_intelligence.ai_kernel.kernel import AIKernel

# Registry + model metadata
from aegis.l3_intelligence.ai_kernel.registry import (
    ModelCapability,
    ModelMetadata,
    ModelRegistry,
)

# Router + decision type
from aegis.l3_intelligence.ai_kernel.router import RouteDecision, Router

# Key management
from aegis.l3_intelligence.ai_kernel.keys import (
    KeyManager,
    KeyRotationStrategy,
    KeySelectionResult,
    ProviderKey,
    ProviderKeyState,
)

# Accounting
from aegis.l3_intelligence.ai_kernel.accounting import (
    Budget,
    BudgetCheckResult,
    CostAccountant,
)

# Providers
from aegis.l3_intelligence.ai_kernel.providers.base import BaseProvider, ProviderRegistry
from aegis.l3_intelligence.ai_kernel.providers.fake import FakeProvider, FakeResponse

# Pipeline
from aegis.l3_intelligence.ai_kernel.pipeline import PromptPipeline

# Cache
from aegis.l3_intelligence.ai_kernel.cache import (
    CachePolicy,
    ResponseCache,
    fingerprint_request,
)

# Types / enums
from aegis.l3_intelligence.ai_kernel.types import (
    AIMetricsSnapshot,
    AIRequestStatus,
    BudgetScope,
    CostEstimate,
    DeploymentKind,
    FailureCategory,
    FinishReason,
    KeyRotationStrategy,
    PrivacyTier,
    PromptStageKind,
    QualityTier,
    RouterPolicy,
    RoutingWeights,
    StreamEventType,
    TaskType,
    TokenUsage,
)

# Metrics
from aegis.l3_intelligence.ai_kernel.metrics import AIMetricsRegistry

# Streaming
from aegis.l3_intelligence.ai_kernel.streaming import StreamEvent, StreamEventEmitter

# Conversation
from aegis.l3_intelligence.ai_kernel.conversation import Conversation, ConversationMessage

# Structured output
from aegis.l3_intelligence.ai_kernel.structured import (
    StructuredOutputProcessor,
    ParsedStructuredResult,
    extract_json_block,
)

# Scrubber
from aegis.l3_intelligence.ai_kernel.scrubber import scrub_messages

# P07.5: Provider health monitor
from aegis.l3_intelligence.ai_kernel.health import (
    ProviderHealthConfig,
    ProviderHealthMonitor,
)

# P07.5: Credential resolution + provisioners
from aegis.l3_intelligence.ai_kernel.credentials import (
    CredentialResolver,
    CredentialResolutionError,
    CredentialProvisioner,
    ManualProvisioner,
    EnvironmentProvisioner,
    BrowserProvisioner,
)

__all__ = [
    # Kernel
    "AIKernel",
    # Contracts
    "AIRequest",
    "AIResponse",
    "BudgetLedgerEntry",
    "RoutingRequirements",
    "ScrubResult",
    "StructuredOutputRequirements",
    "TokenUsage",
    # Registry
    "ModelCapability",
    "ModelMetadata",
    "ModelRegistry",
    # Router
    "RouteDecision",
    "Router",
    # Keys
    "KeyManager",
    "KeyRotationStrategy",
    "KeySelectionResult",
    "ProviderKey",
    "ProviderKeyState",
    # Accounting
    "Budget",
    "BudgetCheckResult",
    "CostAccountant",
    # Providers
    "BaseProvider",
    "ProviderRegistry",
    "FakeProvider",
    "FakeResponse",
    # Pipeline
    "PromptPipeline",
    # Cache
    "CachePolicy",
    "ResponseCache",
    "fingerprint_request",
    # Types
    "AIMetricsSnapshot",
    "AIRequestStatus",
    "BudgetScope",
    "CostEstimate",
    "DeploymentKind",
    "FailureCategory",
    "FinishReason",
    "PrivacyTier",
    "PromptStageKind",
    "QualityTier",
    "RouterPolicy",
    "RoutingWeights",
    "StreamEventType",
    "TaskType",
    # Metrics
    "AIMetricsRegistry",
    # Streaming
    "StreamEvent",
    "StreamEventEmitter",
    # Conversation
    "Conversation",
    "ConversationMessage",
    # Structured
    "StructuredOutputProcessor",
    "ParsedStructuredResult",
    "extract_json_block",
    # Scrubber
    "scrub_messages",
    # P07.5: Health monitor
    "ProviderHealthConfig",
    "ProviderHealthMonitor",
    # P07.5: Credentials
    "CredentialResolver",
    "CredentialResolutionError",
    "CredentialProvisioner",
    "ManualProvisioner",
    "EnvironmentProvisioner",
    "BrowserProvisioner",
]
