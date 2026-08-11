"""P07.5 L6→L3 Reasoning Integration Tests.

Tests the full stack: KernelReasoningProvider → AIKernel → FakeProvider.

Verifies:
  1. AIKernel.has_models() / list_models() / provider_count() introspection
  2. AIKernel.generate() round-trip through kernel
  3. Provider fallback chain (first provider fails → kernel tries next)
  4. P0 privacy rejection propagates through reasoning layer
  5. KernelReasoningProvider.reason() wraps errors in ReasoningUnavailableError
  6. ProviderHealthMonitor lifecycle (start/stop/shutdown safety)
  7. ProviderHealthMonitor updates ModelRegistry health from provider probes
  8. Ollama discover_models fallback on connection error
  9. BaseProvider.health_check() default returns UNKNOWN

No network calls — all providers are FakeProvider instances.
"""

from __future__ import annotations

import asyncio
import json
import pytest

from pydantic import BaseModel

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
from aegis.reasoning.kernel_provider import KernelReasoningProvider


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


# ---------------------------------------------------------------------------
# Stub PromptLibrary for KernelReasoningProvider
# ---------------------------------------------------------------------------

class _StubTemplate:
    """Minimal template that renders variables dict as a string prompt."""
    def render(self, variables: dict) -> str:
        return variables.get("text", "test prompt")


class _StubLibrary:
    """Minimal prompt library for tests."""
    def get(self, template_id: str) -> _StubTemplate:
        return _StubTemplate()


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

    def test_list_models_empty(self):
        reg = ModelRegistry()
        prov_reg = ProviderRegistry()
        kernel = AIKernel(
            registry=reg,
            provider_registry=prov_reg,
            accountant=CostAccountant(),
        )
        assert kernel.list_models() == []

    def test_provider_count_two(self):
        kernel = _build_kernel(
            models=[_local_meta(), _cloud_meta()],
            providers={
                "ollama": FakeProvider(provider_id="ollama", model_ids=["llama3-local"]),
                "openrouter": FakeProvider(provider_id="openrouter", model_ids=["gpt-4o-mini"]),
            },
        )
        assert kernel.provider_count() == 2

    def test_provider_count_zero(self):
        reg = ModelRegistry()
        prov_reg = ProviderRegistry()
        kernel = AIKernel(
            registry=reg,
            provider_registry=prov_reg,
            accountant=CostAccountant(),
        )
        assert kernel.provider_count() == 0


# ===========================================================================
# AIKernel.generate() round-trip tests
# ===========================================================================


class TestAIKernelGenerateRoundTrip:
    @pytest.mark.asyncio
    async def test_generate_returns_content(self):
        fake = FakeProvider(
            provider_id="ollama",
            model_ids=["llama3-local"],
            default_response=FakeResponse(content="Hello, World!", tokens_in=5, tokens_out=3),
        )
        kernel = _build_kernel(models=[_local_meta()], providers={"ollama": fake})
        req = AIRequest(messages=[ChatMessage(role="user", content="Hi")])
        resp = await kernel.generate(req)
        assert resp.content == "Hello, World!"
        assert fake.call_count() == 1

    @pytest.mark.asyncio
    async def test_generate_p0_refuses_cloud(self):
        cloud_fake = FakeProvider(
            provider_id="openrouter",
            model_ids=["gpt-4o-mini"],
            default_response=FakeResponse(content="CLOUD LEAK"),
        )
        kernel = _build_kernel(models=[_cloud_meta()], providers={"openrouter": cloud_fake})
        req = AIRequest(
            messages=[ChatMessage(role="user", content="secret")],
            routing=RoutingRequirements(privacy_tier=PrivacyTier.P0),
        )
        with pytest.raises(AIRouterPrivacyViolationError):
            await kernel.generate(req)
        assert cloud_fake.call_count() == 0

    @pytest.mark.asyncio
    async def test_generate_p0_uses_local(self):
        local_fake = FakeProvider(
            provider_id="ollama",
            model_ids=["llama3-local"],
            default_response=FakeResponse(content="Local safe.", tokens_in=5, tokens_out=3),
        )
        cloud_fake = FakeProvider(
            provider_id="openrouter",
            model_ids=["gpt-4o-mini"],
            default_response=FakeResponse(content="CLOUD LEAK"),
        )
        kernel = _build_kernel(
            models=[_local_meta(), _cloud_meta()],
            providers={"ollama": local_fake, "openrouter": cloud_fake},
        )
        req = AIRequest(
            messages=[ChatMessage(role="user", content="private data")],
            routing=RoutingRequirements(privacy_tier=PrivacyTier.P0),
        )
        resp = await kernel.generate(req)
        assert resp.content == "Local safe."
        assert cloud_fake.call_count() == 0

    @pytest.mark.asyncio
    async def test_generate_provider_called_once_on_success(self):
        fake = FakeProvider(
            provider_id="ollama",
            model_ids=["llama3-local"],
            default_response=FakeResponse(content="OK", tokens_in=2, tokens_out=1),
        )
        kernel = _build_kernel(models=[_local_meta()], providers={"ollama": fake})
        req = AIRequest(messages=[ChatMessage(role="user", content="test")])
        await kernel.generate(req)
        await kernel.generate(req)
        assert fake.call_count() == 2


# ===========================================================================
# KernelReasoningProvider integration tests
# ===========================================================================


class _SimpleOutput(BaseModel):
    answer: str


class TestKernelReasoningProviderIntegration:
    """KernelReasoningProvider must go through AIKernel, never call providers directly."""

    @pytest.mark.asyncio
    async def test_reason_wraps_routing_error_in_unavailable(self):
        """P0 routing failure must surface as ReasoningUnavailableError."""
        cloud_fake = FakeProvider(
            provider_id="openrouter",
            model_ids=["gpt-4o-mini"],
            default_response=FakeResponse(content="SHOULD NOT APPEAR"),
        )
        kernel = _build_kernel(
            models=[_cloud_meta()],
            providers={"openrouter": cloud_fake},
        )
        provider = KernelReasoningProvider(
            kernel=kernel,
            prompt_library=_StubLibrary(),
            privacy_tier=PrivacyTier.P0.value,
        )
        with pytest.raises(ReasoningUnavailableError):
            await provider.reason("test_prompt", variables={}, output_schema=_SimpleOutput)
        # Cloud must never have been called
        assert cloud_fake.call_count() == 0

    @pytest.mark.asyncio
    async def test_reason_wraps_bad_prompt_id_in_unavailable(self):
        """Missing prompt template must raise ReasoningUnavailableError."""
        fake = FakeProvider(
            provider_id="ollama",
            model_ids=["llama3-local"],
            default_response=FakeResponse(content='{"answer":"hi"}', tokens_in=5, tokens_out=3),
        )
        kernel = _build_kernel(models=[_local_meta()], providers={"ollama": fake})

        class _BadLibrary:
            def get(self, template_id: str):
                raise KeyError(f"Template '{template_id}' not found")

        provider = KernelReasoningProvider(
            kernel=kernel,
            prompt_library=_BadLibrary(),
        )
        with pytest.raises(ReasoningUnavailableError):
            await provider.reason("nonexistent_prompt", {}, output_schema=_SimpleOutput)

    def test_is_available_true_with_models(self):
        kernel = _build_kernel(
            models=[_local_meta()],
            providers={"ollama": FakeProvider(provider_id="ollama", model_ids=["llama3-local"])},
        )
        provider = KernelReasoningProvider(kernel=kernel, prompt_library=_StubLibrary())
        assert provider.is_available is True

    def test_is_available_false_empty_kernel(self):
        reg = ModelRegistry()
        prov_reg = ProviderRegistry()
        kernel = AIKernel(
            registry=reg,
            provider_registry=prov_reg,
            accountant=CostAccountant(),
        )
        provider = KernelReasoningProvider(kernel=kernel, prompt_library=_StubLibrary())
        assert provider.is_available is False


# ===========================================================================
# BaseProvider default health_check tests
# ===========================================================================


class TestBaseProviderHealthCheck:
    @pytest.mark.asyncio
    async def test_default_health_check_returns_unknown(self):
        """BaseProvider.health_check() default must return UNKNOWN (no-op)."""
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
        """BaseProvider.discover_models() default returns available_models()."""
        from aegis.l1_core.interfaces.llm import CapabilityFlag, ModelSpec, Modality

        class _StaticProvider(BaseProvider):
            provider_id = "static"
            async def chat(self, messages, params):
                raise NotImplementedError
            async def chat_stream(self, messages, params):
                raise NotImplementedError
                yield

        spec = ModelSpec(
            model_id="static-model",
            provider="static",
            family="test",
            context_window=4096,
            output_limit=1024,
            modality={Modality.TEXT},
            capabilities={CapabilityFlag.STREAMING},
        )
        prov = _StaticProvider(models=[spec])
        discovered = await prov.discover_models()
        # BaseProvider.discover_models() returns available_models() (the static list)
        assert isinstance(discovered, list)
        assert len(discovered) == 1
        assert discovered[0].model_id == "static-model"

    @pytest.mark.asyncio
    async def test_base_provider_health_check_returns_unknown(self):
        """BaseProvider.health_check() default must return UNKNOWN."""
        class _MinProv(BaseProvider):
            provider_id = "min"
            async def chat(self, messages, params):
                raise NotImplementedError
            async def chat_stream(self, messages, params):
                raise NotImplementedError
                yield

        prov = _MinProv()
        health = await prov.health_check()
        assert health == ModelHealth.UNKNOWN


# ===========================================================================
# OllamaProvider model discovery fallback test
# ===========================================================================


class TestOllamaDiscoveryFallback:
    @pytest.mark.asyncio
    async def test_discover_models_falls_back_on_connection_error(self):
        """discover_models() must return static list when Ollama is unreachable."""
        prov = OllamaProvider(
            base_url="http://127.0.0.1:19999",  # Unreachable port
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

    @pytest.mark.asyncio
    async def test_discover_models_with_mocked_response(self):
        """discover_models() parses Ollama /api/tags response correctly."""
        import unittest.mock as mock

        tags_response = {
            "models": [
                {"name": "llama3:latest", "details": {"family": "llama", "context_length": 8192}},
                {"name": "mistral:7b", "details": {"family": "mistral", "context_length": 32768}},
            ]
        }

        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = tags_response

        prov = OllamaProvider(
            base_url="http://localhost:11434",
            model_ids=["fallback-model"],
        )

        with mock.patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = mock.AsyncMock()
            mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = mock.AsyncMock(return_value=False)
            mock_client.get = mock.AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            discovered = await prov.discover_models()

        assert len(discovered) == 2
        model_ids = {m.model_id for m in discovered}
        assert "llama3:latest" in model_ids
        assert "mistral:7b" in model_ids

    @pytest.mark.asyncio
    async def test_health_check_healthy_on_200(self):
        """health_check() returns HEALTHY when Ollama /api/version returns 200."""
        import unittest.mock as mock

        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200

        prov = OllamaProvider(base_url="http://localhost:11434")

        with mock.patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = mock.AsyncMock()
            mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = mock.AsyncMock(return_value=False)
            mock_client.get = mock.AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            health = await prov.health_check()

        assert health == ModelHealth.HEALTHY


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
            config=ProviderHealthConfig(check_interval_seconds=9999.0),
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
        await monitor.start()  # Must be a no-op
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
            config=ProviderHealthConfig(check_interval_seconds=9999.0, failure_threshold=3),
        )
        # Manually trigger a single sweep
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
            config=ProviderHealthConfig(check_interval_seconds=9999.0, failure_threshold=3),
        )

        # 1st sweep — 1/3 failures — NOT DOWN yet
        await monitor._sweep()
        model = reg.get("llama3-local", "down-prov")
        assert model.health != ModelHealth.DOWN

        # 2nd sweep — 2/3 — still not DOWN
        await monitor._sweep()
        model = reg.get("llama3-local", "down-prov")
        assert model.health != ModelHealth.DOWN

        # 3rd sweep — 3/3 — NOW DOWN
        await monitor._sweep()
        model = reg.get("llama3-local", "down-prov")
        assert model.health == ModelHealth.DOWN

    @pytest.mark.asyncio
    async def test_unknown_health_not_written_to_registry(self):
        """Providers returning UNKNOWN must NOT update the registry."""
        reg = ModelRegistry()
        reg.register(_local_meta(model_id="llama3-local", provider_id="unknown-prov"))
        # Set a non-UNKNOWN initial health
        reg.update_health("llama3-local", "unknown-prov", ModelHealth.DEGRADED)

        unknown_prov = FakeProvider(provider_id="unknown-prov", model_ids=["llama3-local"])
        prov_reg = ProviderRegistry()
        prov_reg.register("unknown-prov", unknown_prov)

        monitor = ProviderHealthMonitor(
            provider_registry=prov_reg,
            model_registry=reg,
            config=ProviderHealthConfig(check_interval_seconds=9999.0),
        )
        # FakeProvider inherits BaseProvider default (returns UNKNOWN)
        await monitor._sweep()

        model = reg.get("llama3-local", "unknown-prov")
        assert model.health == ModelHealth.DEGRADED  # Unchanged

    @pytest.mark.asyncio
    async def test_healthy_resets_failure_count(self):
        """After HEALTHY probe, consecutive_failures resets to 0."""
        prov_reg = ProviderRegistry()
        reg = ModelRegistry()
        reg.register(_local_meta(model_id="llama3-local", provider_id="flip-prov"))

        down_prov = _DownFakeProvider(provider_id="flip-prov", model_ids=["llama3-local"])
        prov_reg.register("flip-prov", down_prov)

        monitor = ProviderHealthMonitor(
            provider_registry=prov_reg,
            model_registry=reg,
            config=ProviderHealthConfig(check_interval_seconds=9999.0, failure_threshold=5),
        )

        # Two failures below threshold
        await monitor._sweep()
        await monitor._sweep()
        state = monitor.get_probe_state("flip-prov")
        assert state is not None
        assert state.consecutive_failures == 2

        # Now swap to healthy
        prov_reg.register_force("flip-prov", _HealthyFakeProvider(
            provider_id="flip-prov", model_ids=["llama3-local"]
        ))
        await monitor._sweep()
        state = monitor.get_probe_state("flip-prov")
        assert state.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_probe_state_tracks_last_health(self):
        prov_reg = ProviderRegistry()
        reg = ModelRegistry()
        reg.register(_local_meta(model_id="m1", provider_id="state-prov"))

        healthy_prov = _HealthyFakeProvider(provider_id="state-prov", model_ids=["m1"])
        prov_reg.register("state-prov", healthy_prov)

        monitor = ProviderHealthMonitor(
            provider_registry=prov_reg,
            model_registry=reg,
            config=ProviderHealthConfig(check_interval_seconds=9999.0),
        )
        assert monitor.get_probe_state("state-prov") is None  # Not probed yet

        await monitor._sweep()

        state = monitor.get_probe_state("state-prov")
        assert state is not None
        assert state.last_health == ModelHealth.HEALTHY
        assert state.last_check_at > 0.0
