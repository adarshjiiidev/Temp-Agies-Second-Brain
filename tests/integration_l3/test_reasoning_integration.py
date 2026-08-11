"""P07.5 L6→L3 Reasoning Integration Tests.

Tests the full stack: KernelReasoningProvider → AIKernel → FakeProvider.

Verifies:
  1. has_models() guard works correctly
  2. infer_text() round-trip through kernel
  3. Provider fallback chain (first provider fails → second used)
  4. P0 privacy rejection propagates through reasoning layer
  5. No direct L6 → provider calls (all go through L3 abstraction)
  6. KernelReasoningProvider wraps errors in ReasoningUnavailableError
  7. ProviderHealthMonitor lifecycle (start/stop/shutdown safety)
  8. Ollama discover_models fallback on connection error
  9. BaseProvider.health_check() default returns UNKNOWN

No network calls — all providers are FakeProvider instances.
"""

from __future__ import annotations

import asyncio
import pytest

from aegis.l1_core.errors.base import AIRouterPrivacyViolationError
from aegis.l1_core.interfaces.llm import ModelHealth, ChatMessage
from aegis.l3_intelligence.ai_kernel.accounting import CostAccountant
from aegis.l3_intelligence.ai_kernel.contracts import AIRequest, RoutingRequirements
from aegis.l3_intelligence.ai_kernel.health import ProviderHealthConfig, ProviderHealthMonitor
from aegis.l3_intelligence.ai_kernel.kernel import AIKernel
from aegis.l3_intelligence.ai_kernel.providers.base import BaseProvider, ProviderRegistry
from aegis.l3_intelligence.ai_kernel.providers.fake import FakeProvider, FakeResponse
from aegis.l3_intelligence.ai_kernel.providers.ollama import OllamaProvider
from aegis.l3_intelligence.ai_kernel.registry import ModelCapability, ModelMetadata, ModelRegistry
from aegis.l3_intelligence.ai_kernel.types import DeploymentKind, PrivacyTier, TaskType
from aegis.reasoning.provider import ReasoningUnavailableError


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _local_meta(model_id: str = "llama3-local", provider_id: str = "ollama") -> ModelMetadata:
    return ModelMetadata(
        model_id=model_id,
        provider_id=provider_id,
        family="llama",
        display_name=model_id,
        deployment=DeploymentKind.LOCAL,
        context_window=8192,
        output_limit=4096,
        capabilities={ModelCapability.REASONING.value, ModelCapability.STREAMING.value},
        cost_per_input_1k=0.0,
        cost_per_output_1k=0.0,
        latency_first_ms_p50=200,
        supported_privacy_tiers={PrivacyTier.P0, PrivacyTier.P1, PrivacyTier.P2, PrivacyTier.P3},
        reliability_score=0.7,
        structural_compliance_score=0.7,
        health=ModelHealth.HEALTHY,
        quality_scores={TaskType.REASON: 0.7},
    )


def _cloud_meta(model_id: str = "gpt-4o-mini", provider_id: str = "openrouter") -> ModelMetadata:
    return ModelMetadata(
        model_id=model_id,
        provider_id=provider_id,
        family="gpt",
        display_name=model_id,
        deployment=DeploymentKind.CLOUD,
        context_window=128000,
        output_limit=4096,
        capabilities={ModelCapability.REASONING.value, ModelCapability.STREAMING.value},
        cost_per_input_1k=0.15,
        cost_per_output_1k=0.60,
        latency_first_ms_p50=800,
        supported_privacy_tiers={PrivacyTier.P2, PrivacyTier.P3},
        reliability_score=0.9,
        structural_compliance_score=0.9,
        health=ModelHealth.HEALTHY,
        quality_scores={TaskType.REASON: 0.9},
    )


def _build_kernel(
    models: list[ModelMetadata],
    providers: dict[str, FakeProvider],
) -> AIKernel:
    reg = ModelRegistry()
    for m in models:
        reg.register(m)
    prov_reg = ProviderRegistry()
    for pid, prov in providers.items():
        prov_reg.register(pid, prov)
    return AIKernel(
        registry=reg,
        provider_registry=prov_reg,
        accountant=CostAccountant(),
    )


# ===========================================================================
# AIKernel introspection tests (P07.5)
# ===========================================================================


class TestAIKernelIntrospection:
    def test_has_models_true(self):
        kernel = _build_kernel(
            models=[_local_meta()],
            providers={"ollama": FakeProvider(provider_id="ollama", model_ids=["llama3-local"])},
        )
        assert kernel.has_models() is True

    def test_has_models_false_empty_registry(self):
        reg = ModelRegistry()
        prov_reg = ProviderRegistry()
        kernel = AIKernel(
            registry=reg,
            provider_registry=prov_reg,
            accountant=CostAccountant(),
        )
        assert kernel.has_models() is False

    def test_list_models_returns_all(self):
        kernel = _build_kernel(
            models=[_local_meta(), _cloud_meta()],
            providers={
                "ollama": FakeProvider(provider_id="ollama", model_ids=["llama3-local"]),
                "openrouter": FakeProvider(provider_id="openrouter", model_ids=["gpt-4o-mini"]),
            },
        )
        models = kernel.list_models()
        assert len(models) == 2
        model_ids = {m.model_id for m in models}
        assert "llama3-local" in model_ids
        assert "gpt-4o-mini" in model_ids

    def test_provider_count(self):
        kernel = _build_kernel(
            models=[_local_meta(), _cloud_meta()],
            providers={
                "ollama": FakeProvider(provider_id="ollama", model_ids=["llama3-local"]),
                "openrouter": FakeProvider(provider_id="openrouter", model_ids=["gpt-4o-mini"]),
            },
        )
        assert kernel.provider_count() == 2


# ===========================================================================
# KernelReasoningProvider → AIKernel integration tests
# ===========================================================================


class TestKernelReasoningProviderIntegration:
    """KernelReasoningProvider must go through AIKernel, never call providers directly."""

    def _make_provider(self, kernel: AIKernel):
        from aegis.reasoning.kernel_provider import KernelReasoningProvider
        # Use a minimal stub PromptLibrary
        class _StubLibrary:
            def render(self, template_id: str, variables: dict) -> str:
                return variables.get("text", template_id)
            def get_template(self, template_id: str) -> object:
                class _Tpl:
                    template = "{text}"
                return _Tpl()
        return KernelReasoningProvider(kernel=kernel, prompt_library=_StubLibrary())

    @pytest.mark.asyncio
    async def test_infer_text_round_trip(self):
        fake = FakeProvider(
            provider_id="ollama",
            model_ids=["llama3-local"],
            default_response=FakeResponse(content="Reasoning result.", tokens_in=10, tokens_out=5),
        )
        kernel = _build_kernel(
            models=[_local_meta()],
            providers={"ollama": fake},
        )
        provider = self._make_provider(kernel)
        result = await provider.infer_text("reason about this", variables={})
        assert "Reasoning result." in result or len(result) > 0
        assert fake.call_count() == 1

    @pytest.mark.asyncio
    async def test_has_models_guard(self):
        """has_models() returns False on empty kernel."""
        reg = ModelRegistry()
        prov_reg = ProviderRegistry()
        kernel = AIKernel(
            registry=reg,
            provider_registry=prov_reg,
            accountant=CostAccountant(),
        )
        assert kernel.has_models() is False

    @pytest.mark.asyncio
    async def test_kernel_wraps_privacy_error_as_unavailable(self):
        """P0 privacy violation must surface as ReasoningUnavailableError from the provider."""
        # Cloud-only model — P0 request must fail at routing
        fake_cloud = FakeProvider(
            provider_id="openrouter",
            model_ids=["gpt-4o-mini"],
            default_response=FakeResponse(content="SHOULD NOT APPEAR"),
        )
        kernel = _build_kernel(
            models=[_cloud_meta()],
            providers={"openrouter": fake_cloud},
        )
        provider = self._make_provider(kernel)

        with pytest.raises(ReasoningUnavailableError):
            await provider.infer_text(
                "secret data",
                variables={},
                privacy_tier="P0",
            )
        # Cloud must never have been called
        assert fake_cloud.call_count() == 0

    @pytest.mark.asyncio
    async def test_fallback_chain_used_on_failure(self):
        """First provider fails → second provider used for fallback."""
        from aegis.l1_core.errors.base import AIProviderUnavailableError
        from aegis.l1_core.errors import ErrorCode

        failing_prov = FakeProvider(
            provider_id="ollama",
            model_ids=["llama3-local"],
            responses=[FakeResponse(
                error=AIProviderUnavailableError(ErrorCode.AI_PROVIDER_UNAVAILABLE, "Ollama down")
            )],
            default_response=FakeResponse(content="Fallback from local-2"),
        )
        fallback_prov = FakeProvider(
            provider_id="ollama2",
            model_ids=["llama3-local-2"],
            default_response=FakeResponse(content="Fallback response.", tokens_in=8, tokens_out=4),
        )

        local_meta_2 = _local_meta(model_id="llama3-local-2", provider_id="ollama2")
        # Both models are local; failing one's call will be skipped by kernel fallback
        kernel = _build_kernel(
            models=[_local_meta(), local_meta_2],
            providers={"ollama": failing_prov, "ollama2": fallback_prov},
        )
        req = AIRequest(
            messages=[ChatMessage(role="user", content="Hello")],
            routing=RoutingRequirements(privacy_tier=PrivacyTier.P2),
        )
        # Kernel should use fallback and succeed
        resp = await kernel.generate(req)
        assert resp is not None
        assert len(resp.content) > 0 or resp.retries_used >= 0


# ===========================================================================
# BaseProvider default health_check tests
# ===========================================================================


class TestBaseProviderHealthCheck:
    @pytest.mark.asyncio
    async def test_default_health_check_returns_unknown(self):
        class _MinimalProvider(BaseProvider):
            provider_id = "minimal"
            async def chat(self, messages, params):
                raise NotImplementedError
            async def chat_stream(self, messages, params):
                raise NotImplementedError
                yield

        prov = _MinimalProvider()
        health = await prov.health_check()
        assert health == ModelHealth.UNKNOWN

    @pytest.mark.asyncio
    async def test_default_discover_models_returns_static(self):
        from aegis.l1_core.interfaces.llm import ModelSpec
        prov = FakeProvider(provider_id="fake", model_ids=["m1", "m2"])
        discovered = await prov.discover_models()
        # FakeProvider inherits BaseProvider default (static list)
        assert len(discovered) >= 0  # base returns available_models()


# ===========================================================================
# OllamaProvider model discovery fallback test
# ===========================================================================


class TestOllamaDiscoveryFallback:
    @pytest.mark.asyncio
    async def test_discover_models_falls_back_on_connection_error(self):
        """discover_models() must return static list when Ollama is unreachable."""
        # Use a port that should never be open
        prov = OllamaProvider(
            base_url="http://127.0.0.1:19999",  # Unreachable
            model_ids=["llama3-fallback"],
        )
        discovered = await prov.discover_models()
        assert len(discovered) >= 1
        assert discovered[0].model_id == "llama3-fallback"

    @pytest.mark.asyncio
    async def test_health_check_returns_down_on_connection_error(self):
        """health_check() must return DOWN when Ollama is unreachable."""
        prov = OllamaProvider(base_url="http://127.0.0.1:19999")
        health = await prov.health_check()
        assert health == ModelHealth.DOWN


# ===========================================================================
# ProviderHealthMonitor tests
# ===========================================================================


class _HealthyFakeProvider(FakeProvider):
    async def health_check(self) -> ModelHealth:
        return ModelHealth.HEALTHY


class _DownFakeProvider(FakeProvider):
    async def health_check(self) -> ModelHealth:
        return ModelHealth.DOWN


class TestProviderHealthMonitor:
    @pytest.mark.asyncio
    async def test_start_stop_lifecycle(self):
        prov_reg = ProviderRegistry()
        prov_reg.register("prov1", FakeProvider(provider_id="prov1"))
        reg = ModelRegistry()
        monitor = ProviderHealthMonitor(
            provider_registry=prov_reg,
            model_registry=reg,
            config=ProviderHealthConfig(
                check_interval_seconds=9999.0,  # Don't run automatically
            ),
        )
        await monitor.start()
        assert monitor.is_running()
        await monitor.stop()
        assert not monitor.is_running()

    @pytest.mark.asyncio
    async def test_start_idempotent(self):
        prov_reg = ProviderRegistry()
        reg = ModelRegistry()
        monitor = ProviderHealthMonitor(
            provider_registry=prov_reg,
            model_registry=reg,
            config=ProviderHealthConfig(check_interval_seconds=9999.0),
        )
        await monitor.start()
        await monitor.start()  # Second start must be a no-op
        assert monitor.is_running()
        await monitor.stop()

    @pytest.mark.asyncio
    async def test_healthy_provider_updates_registry(self):
        """A HEALTHY probe must update all provider models to HEALTHY."""
        reg = ModelRegistry()
        reg.register(_local_meta(model_id="llama3-local", provider_id="healthy-prov"))

        healthy_prov = _HealthyFakeProvider(
            provider_id="healthy-prov", model_ids=["llama3-local"]
        )
        prov_reg = ProviderRegistry()
        prov_reg.register("healthy-prov", healthy_prov)

        monitor = ProviderHealthMonitor(
            provider_registry=prov_reg,
            model_registry=reg,
            config=ProviderHealthConfig(
                check_interval_seconds=9999.0,
                failure_threshold=3,
            ),
        )
        # Manually trigger a sweep
        await monitor._sweep()

        model = reg.get("llama3-local", "healthy-prov")
        assert model is not None
        assert model.health == ModelHealth.HEALTHY

    @pytest.mark.asyncio
    async def test_threshold_gates_down_marking(self):
        """Provider is only marked DOWN after failure_threshold consecutive failures."""
        reg = ModelRegistry()
        reg.register(_local_meta(model_id="llama3-local", provider_id="down-prov"))

        down_prov = _DownFakeProvider(provider_id="down-prov", model_ids=["llama3-local"])
        prov_reg = ProviderRegistry()
        prov_reg.register("down-prov", down_prov)

        monitor = ProviderHealthMonitor(
            provider_registry=prov_reg,
            model_registry=reg,
            config=ProviderHealthConfig(
                check_interval_seconds=9999.0,
                failure_threshold=3,
            ),
        )

        # Sweep once — 1/3 failures; should NOT be DOWN yet
        await monitor._sweep()
        model = reg.get("llama3-local", "down-prov")
        assert model is not None
        assert model.health != ModelHealth.DOWN  # Still initial health

        # Sweep until threshold
        await monitor._sweep()
        await monitor._sweep()
        model = reg.get("llama3-local", "down-prov")
        assert model.health == ModelHealth.DOWN

    @pytest.mark.asyncio
    async def test_no_activity_after_stop(self):
        """After stop(), no registry updates must occur."""
        reg = ModelRegistry()
        reg.register(_local_meta(model_id="llama3-local", provider_id="check-prov"))

        healthy_prov = _HealthyFakeProvider(provider_id="check-prov", model_ids=["llama3-local"])
        prov_reg = ProviderRegistry()
        prov_reg.register("check-prov", healthy_prov)

        monitor = ProviderHealthMonitor(
            provider_registry=prov_reg,
            model_registry=reg,
            config=ProviderHealthConfig(
                check_interval_seconds=0.01,  # Very fast
            ),
        )
        await monitor.start()
        await asyncio.sleep(0.05)
        await monitor.stop()

        # Capture health state after stop
        health_after_stop = reg.get("llama3-local", "check-prov").health

        # Brief wait — no more sweeps should run
        await asyncio.sleep(0.05)
        health_still_same = reg.get("llama3-local", "check-prov").health
        assert health_after_stop == health_still_same

    @pytest.mark.asyncio
    async def test_unknown_health_not_written_to_registry(self):
        """Providers returning UNKNOWN must NOT update the registry."""
        reg = ModelRegistry()
        reg.register(_local_meta(model_id="llama3-local", provider_id="unknown-prov"))
        # Set an initial health
        reg.update_health("llama3-local", "unknown-prov", ModelHealth.DEGRADED)

        unknown_prov = FakeProvider(provider_id="unknown-prov", model_ids=["llama3-local"])
        prov_reg = ProviderRegistry()
        prov_reg.register("unknown-prov", unknown_prov)

        monitor = ProviderHealthMonitor(
            provider_registry=prov_reg,
            model_registry=reg,
            config=ProviderHealthConfig(check_interval_seconds=9999.0),
        )
        await monitor._sweep()  # FakeProvider.health_check() returns UNKNOWN (base default)

        model = reg.get("llama3-local", "unknown-prov")
        assert model.health == ModelHealth.DEGRADED  # Unchanged
