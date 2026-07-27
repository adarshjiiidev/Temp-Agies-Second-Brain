"""L3 AI Kernel shared primitive types and enums.

All types here are primitive — they MUST NOT import from higher kernel modules
(contracts, registry, router, providers, kernel). They may import L1 interfaces
and stdlib only. This module is depended on by nearly every other L3 module, so
keep it stable, small, and free of circular-import risks.

Enums follow Prompt 01 §07 AI_STRATEGY taxonomy where explicitly defined.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID


# ---------------------------------------------------------------------------
# Privacy Tier — operationalization of Prompt 01 security architecture.
# P0 requires LOCAL ONLY (never routes to cloud). See 07_AI_STRATEGY §4.
# ---------------------------------------------------------------------------


class PrivacyTier(str, Enum):
    """Prompt 01 privacy tiers (P0 strictest). Router enforces these.

    Rules (from §4 of 07_AI_STRATEGY):
      * P0 — NEVER_CLOUD: if prompt contains P0 data, candidates = local models ONLY.
        No local model eligible → HARD FAIL with E30203/E30205 (never silent leak).
      * P1 — PREFER_LOCAL: pick local if quality is within 85% of best cloud;
        otherwise cloud with audit + zero-retention headers + non-blocking notify.
      * P2 — STANDARD: normal scoring with privacy_cost penalty.
      * P3 — PUBLIC_ALLOWED: no privacy constraint; optimize freely.
    """

    DEVICE_LOCAL_ONLY = "P0"
    E2EE_CLOUD_SYNC = "P1"
    STANDARD = "P2"
    PUBLIC_ALLOWED = "P3"

    # Convenience short aliases (common usage).
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"

    @property
    def is_local_mandatory(self) -> bool:
        return self is PrivacyTier.P0 or self.value == "P0"

    @property
    def numeric_rank(self) -> int:
        _rank: dict[str, int] = {"P0": 4, "P1": 3, "P2": 2, "P3": 1}
        return _rank[self.value]


# PrivacyTier convenience constants (exposed for callers that prefer short names).
LOCAL_ONLY = PrivacyTier.P0
PREFER_LOCAL = PrivacyTier.P1
PRIVACY_STANDARD = PrivacyTier.P2
PUBLIC_ALLOWED = PrivacyTier.P3


# ---------------------------------------------------------------------------
# Deployment Kind — where a provider/model physically runs.
# Drives privacy routing (LOCAL_ONLY tier requires LOCAL deployment kind).
# ---------------------------------------------------------------------------


class DeploymentKind(str, Enum):
    """Physical deployment location for a provider or model."""

    LOCAL = "local"          # Runs on-device: Ollama, vLLM local server, etc.
    GATEWAY = "gateway"      # Aggregator/proxy that routes to multiple backends: OpenRouter.
    CLOUD = "cloud"          # Dedicated single-provider cloud: Groq, OpenAI, Anthropic.


# ---------------------------------------------------------------------------
# Task Type — semantic classification of a request. Feeds into router quality
# scoring (quality scores are task_type × model — see 07_AI_STRATEGY §3 Stage 2).
# ---------------------------------------------------------------------------


class TaskType(str, Enum):
    """Semantic task categories. Router uses task_type in quality scoring.

    NOTE: New task types added here must also have quality_min thresholds defined
    in `RouterPolicy`; otherwise default (STANDARD) is used.
    """

    # General
    REASON = "reason"
    SUMMARIZE = "summarize"
    EXTRACT_STRUCTURED = "extract_structured"
    WRITING = "writing"
    TRANSLATION = "translation"

    # Agents / orchestration
    TOOL_USE_LOOP = "tool_use_loop"
    PLANNING = "planning"
    CODE_GEN = "code_gen"
    CODE_REVIEW = "code_review"

    # Perception (not required in P02 scope; enum for future).
    EMBEDDING = "embedding"
    AUDIO = "audio"
    VISION = "vision"


# ---------------------------------------------------------------------------
# Quality tier — caller-declared minimum quality bar. Router Stage 2 soft filter.
# ---------------------------------------------------------------------------


class QualityTier(str, Enum):
    """Minimum quality bar. Router Stage 2 (soft filter) uses this."""

    DRAFT = "draft"           # Fastest, cheapest: OK for brainstorming, throwaway drafts.
    STANDARD = "standard"     # Default: acceptable for general-purpose internal use.
    HIGH = "high"             # High quality: user-visible outputs, critical code, legal text.
    CRITICAL = "critical"     # Maximum achievable: production releases, irreversible decisions.


# ---------------------------------------------------------------------------
# FailureCategory — Provider error classification for retry/rotation logic.
# See Prompt 03 §13.
# ---------------------------------------------------------------------------


class FailureCategory(str, Enum):
    """Normalized provider failure categories (§13).

    Bounded retry behavior:
      * RETRYABLE → backoff retry on same provider+key+model.
      * NON_RETRYABLE → fail immediately (bad input, not transient).
      * AUTHENTICATION → disable key permanently until user rotates it.
      * RATE_LIMITED → rotate key; short TTL cooldown; mark key as rate-limited.
      * QUOTA_EXHAUSTED → rotate key; mark key's daily/monthly quota as exhausted.
      * PROVIDER_UNAVAILABLE → try different provider / circuit-breaker + backoff.
      * INVALID_REQUEST → non-retryable caller bug.
      * MODEL_UNAVAILABLE → try same provider with different model (fallback).
    """

    RETRYABLE = "retryable"
    NON_RETRYABLE = "non_retryable"
    AUTHENTICATION = "authentication"
    RATE_LIMITED = "rate_limited"
    QUOTA_EXHAUSTED = "quota_exhausted"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    INVALID_REQUEST = "invalid_request"
    MODEL_UNAVAILABLE = "model_unavailable"

    @property
    def is_retryable(self) -> bool:
        return self in {
            FailureCategory.RETRYABLE,
            FailureCategory.RATE_LIMITED,
            FailureCategory.PROVIDER_UNAVAILABLE,
            FailureCategory.MODEL_UNAVAILABLE,
        }

    @property
    def should_rotate_key(self) -> bool:
        return self in {FailureCategory.AUTHENTICATION, FailureCategory.RATE_LIMITED, FailureCategory.QUOTA_EXHAUSTED}

    @property
    def should_rotate_provider(self) -> bool:
        return self in {FailureCategory.PROVIDER_UNAVAILABLE}


# ---------------------------------------------------------------------------
# FinishReason — normalized ChatResult.finish_reason across providers.
# ---------------------------------------------------------------------------


class FinishReason(str, Enum):
    """Normalized finish reasons. Provider-specific strings are mapped here."""

    STOP = "stop"                # Model naturally stopped (EOS, stop-seq hit).
    LENGTH = "length"            # max_tokens cap reached. Output may be truncated.
    TOOL_CALLS = "tool_calls"    # Model emitted function/tool call(s).
    CONTENT_FILTER = "content_filter"  # Provider safety filter truncated output.
    ERROR = "error"              # Provider error (but normalized result still returned).
    CANCELLED = "cancelled"      # Caller cancelled streaming/request mid-flight.
    OTHER = "other"


# ---------------------------------------------------------------------------
# KeyRotationStrategy — §12 rotation algorithm selection.
# ---------------------------------------------------------------------------


class KeyRotationStrategy(str, Enum):
    """§12 Key selection algorithms."""

    ROUND_ROBIN = "round_robin"
    LEAST_RECENTLY_USED = "lru"
    LEAST_RECENTLY_FAILED = "least_recently_failed"
    HEALTH_AWARE = "health_aware"  # Prefer lowest consecutive_failures + highest priority.


# ---------------------------------------------------------------------------
# BudgetScope — §14 Budget granularities.
# ---------------------------------------------------------------------------


class BudgetScope(str, Enum):
    """§14 Budget levels. Each scope has its own ledger of cumulative spend."""

    REQUEST = "request"     # Single AIRequest — zero-retries means 1 inference call.
    SESSION = "session"     # Correlation-scoped; bounded by lifetime of a user session.
    PROVIDER = "provider"   # Per provider.
    PROJECT = "project"     # Per project/project_id metadata (future use, hook now).
    GLOBAL = "global"       # Global daily / monthly system cap.
    KEY = "key"             # Per-provider-api-key (§5.2 key-level budgets).


# ---------------------------------------------------------------------------
# StreamEventType — §20 chunk event discriminator.
# ---------------------------------------------------------------------------


class StreamEventType(str, Enum):
    """§20 Streaming chunk types. Provider adapters normalize to this set."""

    CONTENT_DELTA = "content_delta"
    CONTENT_START = "content_start"
    CONTENT_END = "content_end"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_DELTA = "tool_call_delta"
    TOOL_CALL_END = "tool_call_end"
    USAGE = "usage"              # Mid-stream / final usage snapshot.
    ERROR = "error"              # Recoverable stream error (consumer decides).
    COMPLETION = "completion"    # Final event: stream complete successfully.
    CANCELLED = "cancelled"      # Final event: stream was cancelled.


# ---------------------------------------------------------------------------
# PromptStageKind — §17 stage ids used by PromptPipeline.
# ---------------------------------------------------------------------------


class PromptStageKind(str, Enum):
    """Well-known pipeline stage identifiers (§17 example flow)."""

    INPUT_NORMALIZE = "input_normalize"
    CONTEXT_PREP = "context_prep"
    PROMPT_CONSTRUCT = "prompt_construct"
    VALIDATE = "validate"
    MODEL_ROUTE = "model_route"
    INFERENCE = "inference"
    OUTPUT_VALIDATE = "output_validate"
    POST_PROCESS = "post_process"


# ---------------------------------------------------------------------------
# Simple shared dataclasses (primitive, no pydantic — pure dataclass for speed
# in hot paths; contracts.py builds on top of these with Pydantic validation).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TokenUsage:
    """Normalized usage — returned by every provider call, recorded in ledger."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0  # Convenience sum; can also be derived.
    reasoning_tokens: int = 0  # Some providers expose internal "thinking" tokens.

    def __post_init__(self) -> None:
        if self.total_tokens == 0 and (self.input_tokens or self.output_tokens):
            object.__setattr__(
                self, "total_tokens", self.input_tokens + self.output_tokens
            )


@dataclass(frozen=True)
class CostEstimate:
    """Cost in a specific currency (USD default, from Prompt 01 strategy doc)."""

    cost_usd: float = 0.0
    currency: str = "USD"
    billing_currency: str | None = None  # If provider billed in different currency.
    is_estimate: bool = True             # False means post-hoc actual cost.


@dataclass
class RoutingWeights:
    """Stage 4 scoring weights (07_AI_STRATEGY §3 Stage 4 defaults).

    Weights are normalized internally; caller can supply unnormalized values.
    See 07_AI_STRATEGY §3 Stage 4 for reference defaults (0.40/0.25/0.20/0.05/0.10).
    """

    quality: float = 0.40
    cost: float = 0.25
    latency: float = 0.20
    health_penalty: float = 0.05
    historical_success: float = 0.10


@dataclass
class RouterPolicy:
    """All knobs for router (Stage 1-5, fallback, privacy).

    Reasonable defaults derived from Prompt 01 07_AI_STRATEGY.md. Applications with
    different risk profiles can construct custom RouterPolicy instances.
    """

    # Stage 4 scoring weights (quality·cost·latency·health·success).
    weights: RoutingWeights = field(default_factory=RoutingWeights)
    # Stage 2 (soft filter). QualityTier → minimum model_quality_score threshold (0..1).
    quality_min_thresholds: dict[QualityTier, float] = field(
        default_factory=lambda: {
            QualityTier.DRAFT: 0.30,
            QualityTier.STANDARD: 0.55,
            QualityTier.HIGH: 0.80,
            QualityTier.CRITICAL: 0.95,
        }
    )
    # P1 local preference multiplier (§4 RULE P1). If local quality >= best_cloud * this
    # multiplier → choose local even if cloud scores higher.
    p1_local_quality_floor_ratio: float = 0.85
    # Output headroom added to context requirement (Stage 1b). Ensures model room for
    # max_tokens without exceeding context window. Default 1.2x = +20%.
    output_headroom_multiplier: float = 1.2
    # Whether offline state restricts to local models. Kernel orchestrator
    # is responsible for detecting offline state and setting this flag.
    offline: bool = False
    # Task-type → recommended baseline model_family_quality_score overrides (optional).
    task_quality_bias: dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Request status (for metrics / event payloads).
# ---------------------------------------------------------------------------


class AIRequestStatus(str, Enum):
    """Lifecycle status for a single AIRequest orchestration pass."""

    QUEUED = "queued"
    ROUTING = "routing"
    EXECUTING = "executing"
    STREAMING = "streaming"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRYING = "retrying"
    FALLBACK = "fallback"       # Switched provider/model in fallback chain.
    BUDGET_DENIED = "budget_denied"
    CANCELLED = "cancelled"


@dataclass
class AIMetricsSnapshot:
    """Rolling counters snapshot — emitted by AIMetricsRegistry when queried for health."""

    requests_total: int = 0
    requests_succeeded: int = 0
    requests_failed: int = 0
    retries_total: int = 0
    fallbacks_total: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    rate_limit_events: int = 0
    budget_denials: int = 0
    input_tokens_total: int = 0
    output_tokens_total: int = 0
    estimated_cost_usd_total: float = 0.0
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    per_provider: dict[str, dict[str, Any]] = field(default_factory=dict)
    per_model: dict[str, dict[str, Any]] = field(default_factory=dict)
    updated_at: float = 0.0


# ---------------------------------------------------------------------------
# Small utility: uuid-safe identifiers (not strictly required, but consistent
# with other L1/L2 usages — here for type hints).
# ---------------------------------------------------------------------------

RequestId = UUID
ResponseId = UUID
ConversationId = str
ModelId = str
ProviderId = str
KeyId = str
