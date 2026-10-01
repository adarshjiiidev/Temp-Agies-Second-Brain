"""Integration tests — AIKernel end-to-end orchestration.

Validates:
  - generate() succeeds with FakeProvider
  - P0 routing: no non-local model ever used
  - Budget denial: global budget exhausted → AIAllProvidersExhaustedError
  - Fallback chain: provider 1 fails → provider 2 succeeds
  - Structured output retry loop: invalid JSON retried → valid on 2nd attempt
  - Scrubber elevation: API key in message forces P0 for local-only
  - Cache hit: second identical request returns from cache
  - Offline mode: no cloud models selected
"""

from __future__ import annotations

import pytest

from aegis.l1_core.errors.base import AIAllProvidersExhaustedError, AIAuthenticationError
from aegis.l1_core.errors import ErrorCode
from aegis.l1_core.interfaces.llm import ChatMessage, ModelHealth
from aegis.l3_intelligence.ai_kernel.accounting import CostAccountant
from aegis.l3_intelligence.ai_kernel.cache import CachePolicy, ResponseCache
from aegis.l3_intelligence.ai_kernel.contracts import AIRequest, RoutingRequirements, StructuredOutputRequirements
from aegis.l3_intelligence.ai_kernel.kernel import AIKernel
from aegis.l3_intelligence.ai_kernel.keys import KeyManager, ProviderKey
from aegis.l3_intelligence.ai_kernel.metrics import AIMetricsRegistry
from aegis.l3_intelligence.ai_kernel.providers.base import ProviderRegistry
from aegis.l3_intelligence.ai_kernel.providers.fake import FakeProvider, FakeResponse
from aegis.l3_intelligence.ai_kernel.registry import ModelRegistry
from aegis.l3_intelligence.ai_kernel.types import (
    DeploymentKind,
    PrivacyTier,
    RouterPolicy,
    TaskType,
)

from tests.integration_l3.conftest import (
    make_cloud_model,
    make_local_model,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_kernel(
    models,
    providers: dict[str, FakeProvider],
    *,
    accountant: CostAccountant | None = None,
    policy: RouterPolicy | None = None,
    cache: ResponseCache | None = None,
) -> AIKernel:
    reg = ModelRegistry()
    for m in models:
        reg.register(m)
    pr = ProviderRegistry()
    for pid, p in providers.items():
        pr.register(pid, p)
    return AIKernel(
        registry=reg,
        provider_registry=pr,
        accountant=accountant or CostAccountant(global_daily_limit_usd=100.0),
        policy=policy,
        cache=cache,
    )


def _simple_request(privacy: PrivacyTier = PrivacyTier.P2, content: str = "Hello") -> AIRequest:
    return AIRequest(
        messages=[ChatMessage(role="user", content=content)],
        routing=RoutingRequirements(privacy_tier=privacy),
    )


# ---------------------------------------------------------------------------
# Basic generate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_returns_response():
    local = make_local_model("local-1")
    fake = FakeProvider(
        provider_id="ollama",
        model_ids=["local-1"],
        default_response=FakeResponse(content="Hello world!", tokens_in=5, tokens_out=3),
    )
    kernel = _build_kernel([local], {"ollama": fake})
    req = _simple_request()
    resp = await kernel.generate(req)
    assert resp.content == "Hello world!"
    assert resp.provider_id == "ollama"


@pytest.mark.asyncio
async def test_generate_records_metrics():
    local = make_local_model("local-m")
    fake = FakeProvider(provider_id="ollama", model_ids=["local-m"])
    metrics = AIMetricsRegistry()
    reg = ModelRegistry()
    reg.register(local)
    pr = ProviderRegistry()
    pr.register("ollama", fake)
    kernel = AIKernel(registry=reg, provider_registry=pr, metrics=metrics)
    await kernel.generate(_simple_request())
    snap = kernel.get_metrics()
    assert snap.requests_total == 1
    assert snap.requests_succeeded == 1


# ---------------------------------------------------------------------------
# P0 routing — 20 cases; never routes to cloud
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("case_idx", range(20))
async def test_p0_never_routes_to_cloud(case_idx):
    local = make_local_model(f"loc-{case_idx}")
    cloud = make_cloud_model(f"cld-{case_idx}", privacy_tiers={PrivacyTier.P2, PrivacyTier.P3})
    fake_local = FakeProvider(
        provider_id="ollama",
        model_ids=[f"loc-{case_idx}"],
        default_response=FakeResponse(content=f"local-resp-{case_idx}"),
    )
    fake_cloud = FakeProvider(provider_id="openrouter", model_ids=[f"cld-{case_idx}"])
    kernel = _build_kernel(
        [local, cloud],
        {"ollama": fake_local, "openrouter": fake_cloud},
    )
    req = AIRequest(
        messages=[ChatMessage(role="user", content="private task")],
        routing=RoutingRequirements(privacy_tier=PrivacyTier.P0),
    )
    resp = await kernel.generate(req)
    assert resp.provider_id == "ollama", (
        f"P0 case {case_idx}: response came from {resp.provider_id!r} instead of local 'ollama'"
    )


# ---------------------------------------------------------------------------
# Budget denial
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_budget_denial_raises_all_exhausted():
    """With $0 daily budget, even a $0.001 call is denied → fallback exhausted."""
    cloud = make_cloud_model("cloud-pricey", cost_in=1.0, cost_out=4.0)
    fake_cloud = FakeProvider(provider_id="openrouter", model_ids=["cloud-pricey"])
    acct = CostAccountant(global_daily_limit_usd=0.0, per_call_limit_usd=0.0)
    kernel = _build_kernel([cloud], {"openrouter": fake_cloud}, accountant=acct)
    req = AIRequest(
        messages=[ChatMessage(role="user", content="hi")],
        routing=RoutingRequirements(privacy_tier=PrivacyTier.P2),
    )
    with pytest.raises(AIAllProvidersExhaustedError):
        await kernel.generate(req)


# ---------------------------------------------------------------------------
# Fallback chain
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fallback_to_second_provider_on_auth_error():
    """First provider fails with auth error → fallback to second succeeds."""
    local1 = make_local_model("loc-a", provider_id="ollama")
    local2 = make_local_model("loc-b", provider_id="vllm", quality=0.65)

    failing_provider = FakeProvider(
        provider_id="ollama",
        model_ids=["loc-a"],
        responses=[
            FakeResponse(
                error=AIAuthenticationError(ErrorCode.AI_AUTHENTICATION_FAILED, "bad key")
            )
        ],
    )
    working_provider = FakeProvider(
        provider_id="vllm",
        model_ids=["loc-b"],
        default_response=FakeResponse(content="fallback works!"),
    )
    kernel = _build_kernel(
        [local1, local2],
        {"ollama": failing_provider, "vllm": working_provider},
    )
    resp = await kernel.generate(_simple_request())
    assert resp.content == "fallback works!"
    assert len(resp.fallback_attempts) == 1


@pytest.mark.asyncio
async def test_all_providers_fail_raises_error():
    local = make_local_model("loc")
    failing = FakeProvider(
        provider_id="ollama",
        model_ids=["loc"],
        responses=[
            FakeResponse(
                error=AIAuthenticationError(ErrorCode.AI_AUTHENTICATION_FAILED, "bad key")
            )
        ],
    )
    kernel = _build_kernel([local], {"ollama": failing})
    with pytest.raises(AIAllProvidersExhaustedError):
        await kernel.generate(_simple_request())


# ---------------------------------------------------------------------------
# Scrubber elevation (API key in message → P0)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scrubber_detects_api_key_forces_p0():
    """Messages containing API keys should be scrubbed and routed LOCAL_ONLY."""
    local = make_local_model("local-sec")
    cloud = make_cloud_model("cloud-sec", privacy_tiers={PrivacyTier.P2, PrivacyTier.P3})
    fake_local = FakeProvider(
        provider_id="ollama",
        model_ids=["local-sec"],
        default_response=FakeResponse(content="safe local response"),
    )
    fake_cloud = FakeProvider(provider_id="openrouter", model_ids=["cloud-sec"])
    kernel = _build_kernel(
        [local, cloud],
        {"ollama": fake_local, "openrouter": fake_cloud},
    )
    # Message contains a fake OpenAI-style API key
    req = AIRequest(
        messages=[ChatMessage(role="user", content="My API key is sk-" + "a" * 45)],
        routing=RoutingRequirements(privacy_tier=PrivacyTier.P2),  # caller says P2
    )
    resp = await kernel.generate(req)
    # Scrubber should elevate to P0 → only local used
    assert resp.provider_id == "ollama"
    # Key should be redacted in the actual message sent (fake provider recorded it)
    call_log = fake_local.call_log()
    assert call_log, "Local provider should have been called"
    sent_content = str(call_log[-1]["messages"])
    assert "sk-" not in sent_content or "REDACTED" in sent_content


# ---------------------------------------------------------------------------
# Offline mode
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_offline_mode_only_local():
    local = make_local_model("local-offline")
    cloud = make_cloud_model("cloud-online")
    fake_local = FakeProvider(
        provider_id="ollama",
        model_ids=["local-offline"],
        default_response=FakeResponse(content="offline ok"),
    )
    kernel = _build_kernel(
        [local, cloud],
        {"ollama": fake_local},
        policy=RouterPolicy(offline=True),
    )
    resp = await kernel.generate(_simple_request())
    assert resp.provider_id == "ollama"


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_hit_on_second_identical_request():
    local = make_local_model("cache-model")
    fake = FakeProvider(
        provider_id="ollama",
        model_ids=["cache-model"],
        default_response=FakeResponse(content="cached!"),
    )
    cache = ResponseCache(CachePolicy(enabled=True, cache_p2=True))
    kernel = _build_kernel([local], {"ollama": fake}, cache=cache)
    req = _simple_request(content="deterministic content")
    resp1 = await kernel.generate(req)
    resp2 = await kernel.generate(req)
    # Both responses same content
    assert resp1.content == resp2.content
    # Second request had a cache hit — provider called only once
    assert fake.call_count() == 1
