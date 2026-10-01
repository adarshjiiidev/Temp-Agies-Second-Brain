"""L3 AI Kernel request/response contracts (Prompt 03 §6 + §7).

Pydantic v2 models for strongly-typed provider-neutral AI inference. All field
names follow AEGIS conventions per 07_AI_STRATEGY §3 (router inputs/outputs).

These models form the stable cross-module API — callers construct AIRequest,
pass to AIKernel.generate()/stream(), and get AIResponse back. Provider-specific
details must NEVER leak through this boundary.
"""

from __future__ import annotations

from dataclasses import field as _dcfield
from enum import Enum
from typing import Any, Callable, Iterable, Protocol, Type, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from aegis.l1_core.interfaces.llm import ChatMessage, ChatParams
from aegis.l3_intelligence.ai_kernel.types import (
    BudgetScope,
    CostEstimate,
    DeploymentKind,
    FinishReason,
    PrivacyTier,
    QualityTier,
    TaskType,
    TokenUsage,
)


# ---------------------------------------------------------------------------
# Pydantic JSON TypeAdapter shorthand — used by structured output for schema
# extraction on generic Pydantic classes.
# ---------------------------------------------------------------------------

T = TypeVar("T", bound=BaseModel)


# ---------------------------------------------------------------------------
# RoutingRequirements — the router-specific portion of an AIRequest.
# Extracted as a dedicated Pydantic model so registry/router/accounting can reuse.
# ---------------------------------------------------------------------------


class RoutingRequirements(BaseModel):
    """Declarative routing requirements (Prompt 03 §9 + §10 + §16).

    Router uses this as its primary input. Any field = None means "no
    constraint on this dimension" (subject to default policy).
    """

    model_config = ConfigDict(extra="forbid", frozen=False)

    # Required capability flags — all MUST be present in model.capabilities
    required_capabilities: set[str] = Field(default_factory=set)
    # Required input/output modalities — "text" is always implicit.
    required_modalities: set[str] = Field(default_factory=lambda: {"text"})
    # Privacy tier — drives §16 privacy-aware routing. Default: STANDARD (P2).
    privacy_tier: PrivacyTier = Field(default=PrivacyTier.STANDARD)
    # Deployment kind filter: if set, only consider models that run at this kind.
    required_deployment: DeploymentKind | None = None
    # Explicit provider allowlist/denylist. Empty allowlist = all providers OK.
    allowed_providers: list[str] = Field(default_factory=list)
    denied_providers: list[str] = Field(default_factory=list)
    # Explicit model allowlist/denylist (for debugging or forcing a model).
    preferred_model: str | None = None
    denied_models: list[str] = Field(default_factory=list)
    # Local-only convenience shortcut (equivalent to setting privacy_tier=P0).
    local_only: bool = False
    # Minimum context window required (input+output estimate). Router will add
    # default headroom of policy.output_headroom_multiplier automatically.
    min_context_window: int | None = None
    # Latency SLA in milliseconds (None = no SLA). Router Stage 3 enforces.
    latency_sla_ms: int | None = None
    # Cost sensitivity 0..1 (1 = most cost-sensitive; penalizes expensive models more).
    cost_sensitivity: float = 0.5
    # Reliability requirement 0..1 (1 = pick model with lowest failure rate only).
    reliability_requirement: float = 0.0
    # Task type (feeds quality scoring, see 07_AI_STRATEGY §3 Stage 4).
    task_type: TaskType = Field(default=TaskType.REASON)
    # Quality minimum bar (Stage 2 soft filter).
    quality_min: QualityTier = Field(default=QualityTier.STANDARD)
    # Per-request budget override (None → fall back to default session/global budgets).
    request_budget_usd: float | None = None
    # Session/project scoping for budget attribution (str ids or UUIDs OK).
    session_id: str | None = None
    project_id: str | None = None
    user_id: str | None = None


# ---------------------------------------------------------------------------
# StructuredOutputRequirements — §19 typed output contracts.
# ---------------------------------------------------------------------------


class StructuredOutputRequirements(BaseModel):
    """§19 requirements for structured output (JSON schema / Pydantic compliance)."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    # If set, validate the model's response against this Pydantic model schema.
    output_schema: Type[BaseModel] | None = None
    # Raw JSON schema dict (alternative to Pydantic model). Preferred: use output_schema.
    json_schema: dict[str, Any] | None = None
    # If True and provider supports native JSON mode, enable it (default True).
    prefer_native_json_mode: bool = True
    # Max retries on schema parse/validation failure (§19 step 4 retry loop default).
    max_retries: int = 3
    # If True, include the raw LLM text body alongside the parsed structured object.
    include_raw_text: bool = False
    # If True and validation continues to fail, return a best-effort partial object.
    allow_partial: bool = False

    @property
    def has_schema(self) -> bool:
        return self.output_schema is not None or self.json_schema is not None

    def effective_json_schema(self) -> dict[str, Any] | None:
        if self.output_schema is not None:
            return self.output_schema.model_json_schema()
        return self.json_schema


# ---------------------------------------------------------------------------
# AIRequest — §6 strongly-typed contract. All future AEGIS subsystems use this.
# ---------------------------------------------------------------------------


class AIRequest(BaseModel):
    """Strongly-typed AI inference request (§6).

    Examples:
        Simple text:
            req = AIRequest(messages=[ChatMessage(role="user", content="hi")])

        Structured coding task with P2 privacy:
            from pydantic import BaseModel
            class CodePlan(BaseModel):
                steps: list[str]
                risk_level: str
            req = AIRequest(
                messages=[ChatMessage(role="user", content="Plan a refactor")],
                task_type=TaskType.CODE_GEN,
                routing=RoutingRequirements(
                    privacy_tier=PrivacyTier.P2,
                    quality_min=QualityTier.HIGH,
                    required_capabilities={"json_mode", "function_calling"},
                ),
                structured=StructuredOutputRequirements(output_schema=CodePlan),
            )
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    # ------------------------------------------------------------------ IDs
    # Unique request id; auto-generated but can be supplied for replay/idempotency.
    request_id: UUID = Field(default_factory=uuid4)
    # Correlation id — if present here, overrides CorrelationContext for trace id.
    correlation_id: UUID | None = None
    # Conversation id — for grouping a chat thread.
    conversation_id: str | None = None

    # ------------------------------------------------------------- Messages
    # Chat messages — the primary input. Required (unless embedding_request).
    messages: list[ChatMessage] = Field(default_factory=list)
    # Optional system instruction prepended as a system message by the pipeline.
    system_instruction: str | None = None

    # ------------------------------------------------------- Model knobs
    # Temperature / sampling — None means use model/provider defaults.
    temperature: float | None = None
    top_p: float | None = None
    # Max output tokens (None → provider default or Router policy).
    max_output_tokens: int | None = None
    # Stop sequences.
    stop: list[str] | None = None
    # Random seed for reproducibility where supported.
    seed: int | None = None

    # ---------------------------------------------------------- Routing
    routing: RoutingRequirements = Field(default_factory=RoutingRequirements)

    # --------------------------------------------------- Structured output
    structured: StructuredOutputRequirements = Field(default_factory=StructuredOutputRequirements)

    # ----------------------------------------------------- Streaming pref
    # If True, caller intends to use .stream() interface. Used internally for
    # pre-filtering router to streaming-capable models; caller MUST still use
    # stream() — this flag alone does not initiate streaming on generate().
    streaming_preferred: bool = False

    # ------------------------------------------------------ Timeout/Retry
    # Per-call timeout (seconds). None → policy default.
    timeout_seconds: float | None = None
    # Bounded retries. Router/kernel enforces retry classification via §13.
    max_inference_retries: int = 2

    # ----------------------------------------------------- Budget scopes
    # Convenience: explicit budget scopes. Kernel maps to RoutingRequirements.session_id
    # and RoutingRequirements.project_id as well; provided for ergonomics.
    budget_scopes: dict[BudgetScope, str] = Field(default_factory=dict)

    # ---------------------------------------------------------------- Misc
    metadata: dict[str, Any] = Field(default_factory=dict)
    # Task type convenience alias — also set inside routing.task_type; both
    # are kept in sync by validators (routing.task_type wins on conflict).
    task_type: TaskType | None = None

    @field_validator("task_type")
    @classmethod
    def _sync_task_type(cls, v: TaskType | None) -> TaskType | None:
        # No-op here; sync happens in after_validation to access routing.
        return v

    def model_post_init(self, __context: Any) -> None:  # noqa: D401
        # Sync task_type alias to routing.task_type if explicit override provided.
        if self.task_type is not None:
            object.__setattr__(self.routing, "task_type", self.task_type)
        # Local-only convenience shortcut → privacy_tier=P0 (§16 P0 rule).
        if self.routing.local_only:
            object.__setattr__(self.routing, "privacy_tier", PrivacyTier.P0)
        # Default at least one user message required? Intentionally NOT enforced here —
        # empty requests may be used for template-building pipelines.

    # ---------------------------------------------------------------- Helpers
    def to_chat_params(self, *, force_max_tokens: int | None = None) -> ChatParams:
        """Convert request → L1 ChatParams for provider-level inference."""

        schema_hint: dict[str, Any] | None = None
        if self.structured.has_schema and self.structured.prefer_native_json_mode:
            schema = self.structured.effective_json_schema()
            if schema is not None:
                schema_hint = {"type": "json_object", "schema": schema}

        max_tokens = force_max_tokens or self.max_output_tokens
        return ChatParams(
            max_tokens=max_tokens,
            temperature=self.temperature,
            response_format=schema_hint,
            timeout_seconds=self.timeout_seconds,
            extra={
                "top_p": self.top_p,
                "stop": self.stop or [],
                "seed": self.seed,
                "streaming": self.streaming_preferred,
                "aegis_request_id": str(self.request_id),
            },
        )


# ---------------------------------------------------------------------------
# AIResponse — §7 Normalized provider-neutral response.
# ---------------------------------------------------------------------------


class AIResponse(BaseModel):
    """§7 Normalized response — provider-specific internals never leak here."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    # Ids
    request_id: UUID
    response_id: UUID = Field(default_factory=uuid4)
    provider_id: str
    model_id: str
    deployment: DeploymentKind

    # Content
    content: str = ""
    # If structured output succeeded, this holds the typed Pydantic object.
    structured_output: BaseModel | None = None
    # If include_raw_text=True, raw LLM response is preserved (never logged/redacted).
    raw_text: str | None = None

    # Meta
    finish_reason: FinishReason = FinishReason.STOP
    usage: TokenUsage = Field(default_factory=TokenUsage)
    estimated_cost: CostEstimate = Field(default_factory=CostEstimate)
    latency_ms: int = 0  # End-to-end latency (kernel measures, not provider).

    # Tool calls (normalized). Structured as list of (name, arguments_json) dicts.
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)

    # Fallback info (non-empty only if fallback/orchestration happened):
    # Records (provider_id, model_id, error_summary) for each attempt that failed
    # before the successful attempt.
    fallback_attempts: list[dict[str, Any]] = Field(default_factory=list)
    retries_used: int = 0

    # Correlation/misc
    correlation_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_serializer("structured_output")
    def _serialize_structured(self, v: BaseModel | None) -> dict[str, Any] | None:
        return v.model_dump(mode="json") if v is not None else None


# ---------------------------------------------------------------------------
# BudgetLedgerEntry — §14 accounting entries.
# ---------------------------------------------------------------------------


class BudgetLedgerEntry(BaseModel):
    """Immutable §14 ledger row. Written once per inference by CostAccountant."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    call_id: UUID = Field(default_factory=uuid4)
    timestamp: float  # POSIX seconds (UTC)
    request_id: UUID
    correlation_id: UUID | None = None
    provider_id: str
    model_id: str
    task_type: TaskType = TaskType.REASON
    privacy_tier: PrivacyTier = PrivacyTier.STANDARD
    usage: TokenUsage = Field(default_factory=TokenUsage)
    actual_cost: CostEstimate = Field(default_factory=CostEstimate)
    latency_ms: int = 0
    success: bool = True
    error_code: str | None = None
    # Scope attribution
    session_id: str | None = None
    project_id: str | None = None
    user_id: str | None = None
    key_id: str | None = None
    # Fingerprint for cache linking (optional)
    request_fingerprint: str | None = None


# ---------------------------------------------------------------------------
# Prompt Scrubber output (§4.1 of 07_AI_STRATEGY) — returned by pipeline
# InputNormalize stage. Kernel/routers use the computed `max_privacy_tier`.
# ---------------------------------------------------------------------------


class ScrubResult(BaseModel):
    """§4.1 Prompt Scrubber result."""

    model_config = ConfigDict(extra="forbid")

    messages: list[ChatMessage]  # Potentially scrubbed messages.
    max_privacy_tier: PrivacyTier = PrivacyTier.STANDARD
    detected_secrets: int = 0
    redacted_segments: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


__all__ = [
    "AIRequest",
    "AIResponse",
    "BudgetLedgerEntry",
    "RoutingRequirements",
    "ScrubResult",
    "StructuredOutputRequirements",
    "TokenUsage",
]
