"""L3 AI Kernel — Prompt 03 top-level orchestrator facade.

AIKernel is the single entry point for all AI inference in AEGIS. It
coordinates the full lifecycle per 07_AI_STRATEGY §3, §4, §5, §7:

  generate(AIRequest) → AIResponse:
    1. Scrub messages (§4.1) — detect secrets/PII, compute max privacy_tier
    2. Cache lookup — return cached response if hit (skips everything below)
    3. Route (§3) — 5-stage router produces ordered RouteDecision list
    4. Fallback chain — for each RouteDecision:
         a. Select API key (§5.2 KeyManager)
         b. Pre-call budget check (§7)
         c. Call provider.chat()
         d. Structured output validate + retry loop (§6)
         e. Post-call budget deduction (§7)
         f. Cache store
         g. Update metrics + registry outcome
         h. Return AIResponse
    5. If chain exhausted → AIAllProvidersExhaustedError

  stream(AIRequest) → StreamEventEmitter:
    Same phases 1-3, then provider.chat_stream() with streaming delivery.

Constructor dependencies:
    registry (ModelRegistry) — caller populates before passing.
    provider_registry (ProviderRegistry) — maps provider_id → LLMProvider.
    key_manager (KeyManager) — optional; keys required for cloud providers.
    accountant (CostAccountant) — enforces budgets, records ledger entries.
    policy (RouterPolicy) — routing tuning knobs.
    cache (ResponseCache) — optional; disabled by default.
    metrics (AIMetricsRegistry) — rolling counters.

This class is NOT a BaseService subclass in Prompt 03. It is a plain class
that can be instantiated standalone or plugged into CoreRuntime later (P04).
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any
from uuid import UUID

from aegis.l1_core.errors import ErrorCode
from aegis.l1_core.errors.base import (
    AIAllProvidersExhaustedError,
    AIAuthenticationError,
    AIBudgetError,
    AIInferenceError,
    AIProviderUnavailableError,
    AIRateLimitError,
    AIRouterError,
    AIStructuredRetriesExhaustedError,
)
from aegis.l1_core.interfaces.llm import ChatMessage, ChatParams, ChatResult
from aegis.l3_intelligence.ai_kernel.accounting import CostAccountant
from aegis.l3_intelligence.ai_kernel.cache import (
    CachePolicy,
    ResponseCache,
    fingerprint_request,
)
from aegis.l3_intelligence.ai_kernel.contracts import (
    AIRequest,
    AIResponse,
    BudgetLedgerEntry,
    ScrubResult,
    StructuredOutputRequirements,
)
from aegis.l3_intelligence.ai_kernel.keys import KeyManager
from aegis.l3_intelligence.ai_kernel.metrics import AIMetricsRegistry
from aegis.l3_intelligence.ai_kernel.providers.base import ProviderRegistry
from aegis.l3_intelligence.ai_kernel.registry import ModelRegistry
from aegis.l3_intelligence.ai_kernel.router import Router, RouteDecision
from aegis.l3_intelligence.ai_kernel.scrubber import scrub_messages
from aegis.l3_intelligence.ai_kernel.structured import StructuredOutputProcessor
from aegis.l3_intelligence.ai_kernel.types import (
    CostEstimate,
    DeploymentKind,
    FinishReason,
    PrivacyTier,
    RouterPolicy,
    TokenUsage,
)

logger = logging.getLogger(__name__)

__all__ = ["AIKernel"]

# Quality tier → numeric threshold for quality score (used by Stage 2 in router).
# Duplicated here for reference; actual enforcement is in Router._compute_score.
_QUALITY_THRESHOLDS = {
    "draft": 0.30,
    "standard": 0.55,
    "high": 0.80,
    "critical": 0.95,
}


class AIKernel:
    """Top-level AI Kernel orchestrator.

    Usage::

        kernel = AIKernel(
            registry=registry,
            provider_registry=prov_registry,
            key_manager=key_mgr,
            accountant=accountant,
        )
        response = await kernel.generate(AIRequest(
            messages=[ChatMessage(role="user", content="Hello!")],
        ))
    """

    def __init__(
        self,
        *,
        registry: ModelRegistry,
        provider_registry: ProviderRegistry,
        key_manager: KeyManager | None = None,
        accountant: CostAccountant | None = None,
        policy: RouterPolicy | None = None,
        cache: ResponseCache | None = None,
        metrics: AIMetricsRegistry | None = None,
        log: logging.Logger | None = None,
    ) -> None:
        self._registry = registry
        self._prov_reg = provider_registry
        self._key_mgr = key_manager
        self._accountant = accountant or CostAccountant()
        self._policy = policy or RouterPolicy()
        self._cache = cache or ResponseCache(CachePolicy(enabled=False))
        self._metrics = metrics or AIMetricsRegistry()
        self._log = log or logger
        self._router = Router(registry=registry, policy=self._policy, logger_=self._log)
        self._structured_proc = StructuredOutputProcessor()

    # ------------------------------------------------------------------
    # Public API — Introspection (P07.5)
    # ------------------------------------------------------------------

    def has_models(self) -> bool:
        """Return True if at least one model is registered in the kernel.

        Useful for guard checks in calling code (e.g. KernelReasoningProvider)
        before attempting an inference call that would fail immediately.
        """
        return len(self._registry.list_all()) > 0

    def list_models(self) -> list:
        """Return a snapshot of all registered ModelMetadata entries.

        Returns:
            Ordered list of ModelMetadata (same order as ModelRegistry.list_all()).
        """
        return self._registry.list_all()

    def provider_count(self) -> int:
        """Return the number of providers registered in the provider registry."""
        return len(self._prov_reg.list_provider_ids())

    # ------------------------------------------------------------------
    # Public API — Inference
    # ------------------------------------------------------------------

    async def generate(self, request: AIRequest) -> AIResponse:
        """Execute a full inference request and return a normalized AIResponse.

        Raises:
            AIRouterPrivacyViolationError: P0 required but no local model eligible.
            AIAllProvidersExhaustedError: Entire fallback chain failed.
            AIBudgetError: Global daily budget exceeded.
        """
        start_ms = time.monotonic()

        # Phase 1: Scrub messages
        scrubbed_msgs, max_privacy_tier = self._scrub(request)

        # Effective request with potentially elevated privacy tier
        eff_request = _with_scrubbed_privacy(request, scrubbed_msgs, max_privacy_tier)

        # Phase 2: Cache lookup
        if eff_request.routing.privacy_tier != PrivacyTier.P0:
            fp = fingerprint_request(eff_request)
            cache_hit = await self._cache.lookup(fp)
            if cache_hit.hit and cache_hit.entry is not None:
                entry = cache_hit.entry
                elapsed_ms = int((time.monotonic() - start_ms) * 1000)
                self._metrics.record_request(
                    provider_id=entry.provider_id,
                    model_id=entry.model_id,
                    success=True,
                    from_cache=True,
                    latency_ms=elapsed_ms,
                )
                return _build_response_from_cache(request, entry, elapsed_ms)
        else:
            fp = ""

        # Phase 3: Route
        tok_in = self._estimate_tokens(eff_request)
        tok_out = eff_request.max_output_tokens or 512
        available_budget = self._accountant.get_global_daily_remaining()

        route_decisions = self._router.route(
            eff_request.routing,
            estimated_tok_in=tok_in,
            estimated_tok_out=tok_out,
            available_budget_usd=available_budget,
        )

        # Phase 4: Fallback chain
        fallback_attempts: list[dict[str, Any]] = []
        last_error: Exception | None = None

        for decision in route_decisions:
            provider = self._prov_reg.get(decision.provider_id)
            if provider is None:
                self._log.warning(
                    "Router chose provider %r but not found in ProviderRegistry; skipping",
                    decision.provider_id,
                )
                fallback_attempts.append(
                    {
                        "provider_id": decision.provider_id,
                        "model_id": decision.model_id,
                        "error": "provider_not_found",
                    }
                )
                continue

            # Select key
            key_id: str | None = None
            if self._key_mgr is not None:
                key_result = self._key_mgr.select(decision.provider_id)
                if key_result.key is None:
                    self._log.warning(
                        "No usable API key for provider %r (%s); skipping",
                        decision.provider_id, key_result.reason
                    )
                    fallback_attempts.append(
                        {
                            "provider_id": decision.provider_id,
                            "model_id": decision.model_id,
                            "error": f"key_unavailable:{key_result.reason}",
                        }
                    )
                    continue
                key_id = key_result.key.key_id

            # Pre-call budget check
            budget_check = self._accountant.check_budgets(
                decision.estimated_cost_usd,
                session_id=eff_request.routing.session_id,
                project_id=eff_request.routing.project_id,
                provider_id=decision.provider_id,
                key_id=key_id,
                request_id=str(eff_request.request_id),
            )
            if not budget_check.ok:
                self._log.warning(
                    "Budget check failed: %s — skipping model %s",
                    budget_check.reason, decision.model_id
                )
                self._metrics.record_request(
                    provider_id=decision.provider_id,
                    model_id=decision.model_id,
                    success=False,
                    budget_denied=True,
                )
                fallback_attempts.append(
                    {
                        "provider_id": decision.provider_id,
                        "model_id": decision.model_id,
                        "error": f"budget_denied:{budget_check.reason}",
                    }
                )
                continue

            # Inference
            call_start = time.monotonic()
            try:
                chat_params = self._build_chat_params(eff_request, decision)
                result = await provider.chat(list(scrubbed_msgs), chat_params)
                elapsed_ms = int((time.monotonic() - call_start) * 1000)
            except (AIAuthenticationError, AIRateLimitError, AIProviderUnavailableError) as exc:
                elapsed_ms = int((time.monotonic() - call_start) * 1000)
                self._log.warning(
                    "Provider %r model %r failed (%s); trying fallback",
                    decision.provider_id, decision.model_id, type(exc).__name__
                )
                self._registry.record_outcome(decision.model_id, decision.provider_id, success=False)
                self._metrics.record_request(
                    provider_id=decision.provider_id,
                    model_id=decision.model_id,
                    success=False,
                    latency_ms=elapsed_ms,
                )
                if self._key_mgr is not None and key_id is not None:
                    from aegis.l3_intelligence.ai_kernel.types import FailureCategory
                    cat = (
                        FailureCategory.AUTHENTICATION
                        if isinstance(exc, AIAuthenticationError)
                        else (
                            FailureCategory.RATE_LIMITED
                            if isinstance(exc, AIRateLimitError)
                            else FailureCategory.PROVIDER_UNAVAILABLE
                        )
                    )
                    self._key_mgr.mark_failure(decision.provider_id, key_id, cat)
                fallback_attempts.append(
                    {
                        "provider_id": decision.provider_id,
                        "model_id": decision.model_id,
                        "error": str(exc),
                    }
                )
                last_error = exc
                continue
            except Exception as exc:
                elapsed_ms = int((time.monotonic() - call_start) * 1000)
                self._log.error(
                    "Unexpected error from provider %r model %r: %s",
                    decision.provider_id, decision.model_id, exc, exc_info=True
                )
                self._registry.record_outcome(decision.model_id, decision.provider_id, success=False)
                self._metrics.record_request(
                    provider_id=decision.provider_id,
                    model_id=decision.model_id,
                    success=False,
                    latency_ms=elapsed_ms,
                )
                fallback_attempts.append(
                    {
                        "provider_id": decision.provider_id,
                        "model_id": decision.model_id,
                        "error": str(exc),
                    }
                )
                last_error = exc
                continue

            # Structured output validation + retry loop
            structured_output = None
            retries_used = 0
            if eff_request.structured.has_schema:
                structured_output, retries_used, retry_error = await self._validate_structured(
                    provider=provider,
                    messages=list(scrubbed_msgs),
                    params=chat_params,
                    result=result,
                    req_structured=eff_request.structured,
                )
                if retry_error is not None:
                    # Structured retries exhausted — record and move to next model
                    fallback_attempts.append(
                        {
                            "provider_id": decision.provider_id,
                            "model_id": decision.model_id,
                            "error": f"structured_retries_exhausted:{retry_error}",
                        }
                    )
                    last_error = retry_error
                    continue

            # Post-call: budget deduction
            actual_cost_usd = self._registry.estimate_cost(
                decision.model,
                result.tokens_in,
                result.tokens_out,
            )
            ledger_entry = BudgetLedgerEntry(
                timestamp=time.time(),
                request_id=eff_request.request_id,
                correlation_id=eff_request.correlation_id,
                provider_id=decision.provider_id,
                model_id=decision.model_id,
                task_type=eff_request.routing.task_type,
                privacy_tier=max_privacy_tier,
                usage=TokenUsage(
                    input_tokens=result.tokens_in,
                    output_tokens=result.tokens_out,
                    total_tokens=result.tokens_in + result.tokens_out,
                ),
                actual_cost=CostEstimate(cost_usd=actual_cost_usd, is_estimate=False),
                latency_ms=elapsed_ms,
                success=True,
                session_id=eff_request.routing.session_id,
                project_id=eff_request.routing.project_id,
                user_id=eff_request.routing.user_id,
                key_id=key_id,
            )
            try:
                self._accountant.record_spend(ledger_entry)
            except AIBudgetError as exc:
                self._log.error("Post-call budget exceeded (already spent): %s", exc)
                # Still return the result — the call already happened

            # Cache store
            if fp:
                await self._cache.store(
                    fp,
                    content=result.content,
                    provider_id=decision.provider_id,
                    model_id=decision.model_id,
                    privacy_tier=max_privacy_tier,
                    tokens_in=result.tokens_in,
                    tokens_out=result.tokens_out,
                    local_only=decision.is_local,
                )

            # Registry + metrics
            self._registry.record_outcome(decision.model_id, decision.provider_id, success=True)
            total_elapsed_ms = int((time.monotonic() - start_ms) * 1000)
            self._metrics.record_request(
                provider_id=decision.provider_id,
                model_id=decision.model_id,
                success=True,
                retries_used=retries_used,
                fallback_used=len(fallback_attempts) > 0,
                from_cache=False,
                latency_ms=total_elapsed_ms,
                tokens_in=result.tokens_in,
                tokens_out=result.tokens_out,
                cost_usd=actual_cost_usd,
            )

            # Key success tracking
            if self._key_mgr is not None and key_id is not None:
                self._key_mgr.mark_success(
                    decision.provider_id, key_id, spend_usd=actual_cost_usd
                )

            return AIResponse(
                request_id=eff_request.request_id,
                provider_id=decision.provider_id,
                model_id=result.model,
                deployment=decision.model.deployment,
                content=result.content,
                structured_output=structured_output,
                finish_reason=_normalize_finish_reason(result.finish_reason),
                usage=TokenUsage(
                    input_tokens=result.tokens_in,
                    output_tokens=result.tokens_out,
                    total_tokens=result.tokens_in + result.tokens_out,
                ),
                estimated_cost=CostEstimate(cost_usd=actual_cost_usd, is_estimate=False),
                latency_ms=total_elapsed_ms,
                tool_calls=result.tool_calls or [],
                fallback_attempts=fallback_attempts,
                retries_used=retries_used,
                correlation_id=eff_request.correlation_id,
            )

        # Exhausted
        raise AIAllProvidersExhaustedError(
            ErrorCode.AI_ALL_PROVIDERS_EXHAUSTED,
            f"All eligible models/providers exhausted. Attempts={len(fallback_attempts)}. "
            f"Last error: {last_error!s}",
        )

    # ------------------------------------------------------------------
    # Public: metrics + health
    # ------------------------------------------------------------------

    def get_metrics(self):
        """Return current AIMetricsSnapshot."""
        return self._metrics.snapshot()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _scrub(self, request: AIRequest) -> tuple[list[ChatMessage], PrivacyTier]:
        """Run the prompt scrubber and return scrubbed messages + effective tier."""
        msgs, max_tier, detected, segments, warnings = scrub_messages(
            list(request.messages),
            caller_privacy_tier=request.routing.privacy_tier,
        )
        if warnings:
            for w in warnings:
                self._log.warning("Scrubber: %s", w)
        return msgs, max_tier

    def _build_chat_params(
        self, request: AIRequest, decision: RouteDecision
    ) -> ChatParams:
        """Build L1 ChatParams from the AIRequest for a specific RouteDecision."""
        schema_hint = None
        if request.structured.has_schema and request.structured.prefer_native_json_mode:
            schema = request.structured.effective_json_schema()
            if schema is not None:
                schema_hint = {"type": "json_object", "schema": schema}

        return ChatParams(
            max_tokens=request.max_output_tokens,
            temperature=request.temperature,
            response_format=schema_hint,
            timeout_seconds=request.timeout_seconds,
            extra={
                "model": decision.model_id,
                "top_p": request.top_p,
                "stop": request.stop or [],
                "seed": request.seed,
                "streaming": request.streaming_preferred,
                "aegis_request_id": str(request.request_id),
            },
        )

    def _estimate_tokens(self, request: AIRequest) -> int:
        """Rough token estimate for routing (actual measured post-call)."""
        total_chars = 0
        for msg in request.messages:
            c = msg.content
            if c is None:
                continue
            total_chars += len(str(c))
        if request.system_instruction:
            total_chars += len(request.system_instruction)
        return max(1, int(total_chars / 3.5))

    async def _validate_structured(
        self,
        *,
        provider,
        messages: list[ChatMessage],
        params: ChatParams,
        result: ChatResult,
        req_structured: StructuredOutputRequirements,
    ) -> tuple[Any, int, Exception | None]:
        """Run structured output validation + retry loop (§6).

        Returns (structured_obj, retries_used, error_or_none).
        """
        proc = StructuredOutputProcessor(
            max_retries=req_structured.max_retries,
            include_raw_text=req_structured.include_raw_text,
            allow_partial=req_structured.allow_partial,
        )
        parsed = proc.parse(result.content, req_structured)
        if parsed.is_valid:
            return parsed.data, 0, None

        # Retry loop
        retries_used = 0
        current_msgs = list(messages)
        current_result = result
        original_schema = req_structured.effective_json_schema()

        while proc.should_retry(parsed, retries_used):
            retry_msg = proc.format_retry_prompt(parsed, original_schema_json=original_schema)
            current_msgs = current_msgs + [
                ChatMessage(role="assistant", content=current_result.content),
                ChatMessage(role="user", content=retry_msg),
            ]
            try:
                current_result = await provider.chat(current_msgs, params)
            except Exception:
                break
            parsed = proc.parse(current_result.content, req_structured)
            retries_used += 1
            if parsed.is_valid:
                return parsed.data, retries_used, None

        # Exhausted
        try:
            proc.raise_retries_exhausted()
        except AIStructuredRetriesExhaustedError as exc:
            return None, retries_used, exc

        return None, retries_used, None


# ---------------------------------------------------------------------------
# Helpers (module-level, no instance state)
# ---------------------------------------------------------------------------

def _with_scrubbed_privacy(
    original: AIRequest,
    scrubbed_msgs: list[ChatMessage],
    max_privacy_tier: PrivacyTier,
) -> AIRequest:
    """Return a copy of AIRequest with scrubbed messages and elevated privacy tier."""
    from copy import copy
    from pydantic import BaseModel

    # Build new routing with elevated privacy tier
    new_routing = original.routing.model_copy(
        update={"privacy_tier": max_privacy_tier}
    )
    return original.model_copy(
        update={"messages": scrubbed_msgs, "routing": new_routing}
    )


def _normalize_finish_reason(raw: str | None) -> FinishReason:
    mapping = {
        "stop": FinishReason.STOP,
        "length": FinishReason.LENGTH,
        "tool_calls": FinishReason.TOOL_CALLS,
        "content_filter": FinishReason.CONTENT_FILTER,
        "error": FinishReason.ERROR,
        "cancelled": FinishReason.CANCELLED,
    }
    return mapping.get(raw or "stop", FinishReason.STOP)


def _build_response_from_cache(
    original_request: AIRequest,
    entry: Any,
    elapsed_ms: int,
) -> AIResponse:
    """Build an AIResponse from a ResponseCache CacheEntry."""
    return AIResponse(
        request_id=original_request.request_id,
        provider_id=entry.provider_id,
        model_id=entry.model_id,
        deployment=DeploymentKind.LOCAL if entry.is_local_only else DeploymentKind.CLOUD,
        content=entry.content,
        structured_output=None,
        finish_reason=FinishReason.STOP,
        usage=TokenUsage(
            input_tokens=entry.tokens_in,
            output_tokens=entry.tokens_out,
            total_tokens=entry.tokens_in + entry.tokens_out,
        ),
        estimated_cost=CostEstimate(cost_usd=0.0, is_estimate=False),
        latency_ms=elapsed_ms,
        metadata={"from_cache": True, "cache_fingerprint": entry.fingerprint},
    )
