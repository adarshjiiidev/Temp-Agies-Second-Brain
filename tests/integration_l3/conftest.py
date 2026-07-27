"""Shared fixtures for L3 AI Kernel integration tests.

All tests use FakeProvider — no network calls. Fixtures build minimal
but realistic registry + kernel setups.
"""

from __future__ import annotations

import pytest

from aegis.l1_core.interfaces.llm import ModelHealth
from aegis.l3_intelligence.ai_kernel.accounting import CostAccountant
from aegis.l3_intelligence.ai_kernel.cache import CachePolicy, ResponseCache
from aegis.l3_intelligence.ai_kernel.kernel import AIKernel
from aegis.l3_intelligence.ai_kernel.keys import KeyManager, ProviderKey
from aegis.l3_intelligence.ai_kernel.metrics import AIMetricsRegistry
from aegis.l3_intelligence.ai_kernel.providers.base import ProviderRegistry
from aegis.l3_intelligence.ai_kernel.providers.fake import FakeProvider, FakeResponse
from aegis.l3_intelligence.ai_kernel.registry import ModelCapability, ModelMetadata, ModelRegistry
from aegis.l3_intelligence.ai_kernel.types import (
    DeploymentKind,
    PrivacyTier,
    QualityTier,
    RouterPolicy,
    RoutingWeights,
    TaskType,
)


# ---------------------------------------------------------------------------
# ModelMetadata helpers
# ---------------------------------------------------------------------------

def make_local_model(
    model_id: str = "llama3-local",
    provider_id: str = "ollama",
    quality: float = 0.70,
    cost_in: float = 0.0,
    cost_out: float = 0.0,
    latency_ms: int = 500,
    health: ModelHealth = ModelHealth.HEALTHY,
    context_window: int = 8192,
    capabilities: set[str] | None = None,
) -> ModelMetadata:
    return ModelMetadata(
        model_id=model_id,
        provider_id=provider_id,
        family="llama",
        display_name=model_id,
        deployment=DeploymentKind.LOCAL,
        context_window=context_window,
        output_limit=4096,
        capabilities=capabilities or {
            ModelCapability.REASONING.value,
            ModelCapability.STREAMING.value,
        },
        cost_per_input_1k=cost_in,
        cost_per_output_1k=cost_out,
        latency_first_ms_p50=latency_ms,
        supported_privacy_tiers={PrivacyTier.P0, PrivacyTier.P1, PrivacyTier.P2, PrivacyTier.P3},
        reliability_score=quality,
        structural_compliance_score=quality,
        health=health,
        quality_scores={TaskType.REASON: quality},
    )


def make_cloud_model(
    model_id: str = "gpt-4o-mini",
    provider_id: str = "openrouter",
    quality: float = 0.90,
    cost_in: float = 0.15,
    cost_out: float = 0.60,
    latency_ms: int = 800,
    health: ModelHealth = ModelHealth.HEALTHY,
    privacy_tiers: set[PrivacyTier] | None = None,
    context_window: int = 128000,
    capabilities: set[str] | None = None,
) -> ModelMetadata:
    return ModelMetadata(
        model_id=model_id,
        provider_id=provider_id,
        family="gpt",
        display_name=model_id,
        deployment=DeploymentKind.CLOUD,
        context_window=context_window,
        output_limit=4096,
        capabilities=capabilities or {
            ModelCapability.REASONING.value,
            ModelCapability.STRUCTURED_OUTPUT_JSON.value,
            ModelCapability.STREAMING.value,
        },
        cost_per_input_1k=cost_in,
        cost_per_output_1k=cost_out,
        latency_first_ms_p50=latency_ms,
        supported_privacy_tiers=privacy_tiers or {PrivacyTier.P2, PrivacyTier.P3},
        reliability_score=quality,
        structural_compliance_score=quality,
        health=health,
        quality_scores={TaskType.REASON: quality},
    )


# ---------------------------------------------------------------------------
# Registry fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def local_model() -> ModelMetadata:
    return make_local_model()


@pytest.fixture
def cloud_model() -> ModelMetadata:
    return make_cloud_model()


@pytest.fixture
def registry_local_only(local_model) -> ModelRegistry:
    reg = ModelRegistry()
    reg.register(local_model)
    return reg


@pytest.fixture
def registry_mixed(local_model, cloud_model) -> ModelRegistry:
    """Registry with one local + one cloud model."""
    reg = ModelRegistry()
    reg.register(local_model)
    reg.register(cloud_model)
    return reg


# ---------------------------------------------------------------------------
# Provider registry fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_local_provider() -> FakeProvider:
    return FakeProvider(
        provider_id="ollama",
        model_ids=["llama3-local"],
        default_response=FakeResponse(content="Local response.", tokens_in=10, tokens_out=5),
    )


@pytest.fixture
def fake_cloud_provider() -> FakeProvider:
    return FakeProvider(
        provider_id="openrouter",
        model_ids=["gpt-4o-mini"],
        default_response=FakeResponse(content="Cloud response.", tokens_in=15, tokens_out=20),
    )


@pytest.fixture
def provider_registry_local(fake_local_provider) -> ProviderRegistry:
    pr = ProviderRegistry()
    pr.register("ollama", fake_local_provider)
    return pr


@pytest.fixture
def provider_registry_mixed(fake_local_provider, fake_cloud_provider) -> ProviderRegistry:
    pr = ProviderRegistry()
    pr.register("ollama", fake_local_provider)
    pr.register("openrouter", fake_cloud_provider)
    return pr


# ---------------------------------------------------------------------------
# Accounting + key manager fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def accountant() -> CostAccountant:
    return CostAccountant(
        global_daily_limit_usd=10.0,
        global_monthly_limit_usd=200.0,
        per_call_limit_usd=5.0,
    )


@pytest.fixture
def tight_accountant() -> CostAccountant:
    """Budget so tight only local ($0) calls pass."""
    return CostAccountant(
        global_daily_limit_usd=0.001,
        global_monthly_limit_usd=0.005,
        per_call_limit_usd=0.001,
    )


@pytest.fixture
def key_manager() -> KeyManager:
    km = KeyManager()
    km.register(
        ProviderKey(
            key_id="key-openrouter-1",
            provider_id="openrouter",
            vault_ref="env:OPENROUTER_API_KEY",
            scopes={"chat"},
            priority=0,
            enabled=True,
        )
    )
    return km


# ---------------------------------------------------------------------------
# Kernel fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def kernel_local(
    registry_local_only, provider_registry_local, accountant
) -> AIKernel:
    return AIKernel(
        registry=registry_local_only,
        provider_registry=provider_registry_local,
        accountant=accountant,
    )


@pytest.fixture
def kernel_mixed(
    registry_mixed, provider_registry_mixed, accountant
) -> AIKernel:
    return AIKernel(
        registry=registry_mixed,
        provider_registry=provider_registry_mixed,
        accountant=accountant,
    )
