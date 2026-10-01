"""Integration tests — ModelRegistry filter_candidates 10-stage filter.

Validates all 10 filter stages from 07_AI_STRATEGY §9.1:
  Stage 1: offline → LOCAL only
  Stage 2: required_deployment
  Stage 3/4: P0 privacy → LOCAL + P0-in-supported-tiers
  Stage 5: required_capabilities ⊆ model.capabilities
  Stage 6: required_modalities ⊆ model.modalities
  Stage 7: min_context window
  Stage 8: denied providers/models
  Stage 9: allowed providers (whitelist)
  Stage 10: preferred_model prepend
"""

from __future__ import annotations

import pytest

from aegis.l1_core.interfaces.llm import ModelHealth
from aegis.l3_intelligence.ai_kernel.registry import ModelCapability, ModelMetadata, ModelRegistry
from aegis.l3_intelligence.ai_kernel.types import DeploymentKind, PrivacyTier, TaskType

from tests.integration_l3.conftest import make_cloud_model, make_local_model


@pytest.fixture
def reg_multi():
    """Registry with 3 models: 2 local, 1 cloud."""
    reg = ModelRegistry()
    reg.register(make_local_model("local-a", provider_id="ollama", quality=0.70))
    reg.register(make_local_model("local-b", provider_id="vllm", quality=0.75))
    reg.register(make_cloud_model("cloud-a", provider_id="openrouter", quality=0.95))
    return reg


class TestFilterCandidatesStages:
    """Test each stage of the 10-stage filter in isolation."""

    def test_stage1_offline_returns_only_local(self, reg_multi):
        results = reg_multi.filter_candidates(offline=True)
        assert results, "Should have local candidates"
        assert all(m.deployment is DeploymentKind.LOCAL for m in results)

    def test_stage2_required_deployment_cloud(self, reg_multi):
        results = reg_multi.filter_candidates(required_deployment=DeploymentKind.CLOUD)
        assert all(m.deployment is DeploymentKind.CLOUD for m in results)
        assert len(results) == 1

    def test_stage2_required_deployment_local(self, reg_multi):
        results = reg_multi.filter_candidates(required_deployment=DeploymentKind.LOCAL)
        assert all(m.deployment is DeploymentKind.LOCAL for m in results)
        assert len(results) == 2

    def test_stage3_p0_forces_local_only(self, reg_multi):
        results = reg_multi.filter_candidates(privacy_tier=PrivacyTier.P0)
        assert results, "Should have P0-eligible local models"
        assert all(m.deployment is DeploymentKind.LOCAL for m in results)

    def test_stage3_p0_excludes_cloud(self, reg_multi):
        results = reg_multi.filter_candidates(privacy_tier=PrivacyTier.P0)
        provider_ids = {m.provider_id for m in results}
        assert "openrouter" not in provider_ids

    def test_stage4_p2_allows_cloud(self, reg_multi):
        results = reg_multi.filter_candidates(privacy_tier=PrivacyTier.P2)
        provider_ids = {m.provider_id for m in results}
        # Cloud model only has P2/P3 — should still appear
        assert "openrouter" in provider_ids

    def test_stage5_capabilities_filter(self):
        reg = ModelRegistry()
        m_with = make_local_model(
            "m-with", capabilities={ModelCapability.VISION.value, ModelCapability.REASONING.value}
        )
        m_without = make_local_model("m-without", capabilities={ModelCapability.REASONING.value})
        reg.register(m_with)
        reg.register(m_without)
        results = reg.filter_candidates(required_capabilities={ModelCapability.VISION.value})
        ids = {m.model_id for m in results}
        assert "m-with" in ids
        assert "m-without" not in ids

    def test_stage6_modalities_filter(self):
        reg = ModelRegistry()
        m_text = make_local_model("m-text")
        m_text_image = make_local_model("m-text-image")
        object.__setattr__(m_text_image, "modalities", {"text", "image"})
        reg.register(m_text)
        reg.register(m_text_image)
        results = reg.filter_candidates(required_modalities={"text", "image"})
        ids = {m.model_id for m in results}
        assert "m-text-image" in ids
        assert "m-text" not in ids

    def test_stage7_min_context_window(self, reg_multi):
        results = reg_multi.filter_candidates(min_context=200000)
        # Local models have 8192, cloud has 128000 — none exceed 200k
        assert len(results) == 0

    def test_stage7_min_context_window_hit(self, reg_multi):
        results = reg_multi.filter_candidates(min_context=8000)
        assert len(results) >= 1

    def test_stage8_denied_providers(self, reg_multi):
        results = reg_multi.filter_candidates(denied_providers=["ollama"])
        ids = {m.provider_id for m in results}
        assert "ollama" not in ids

    def test_stage8_denied_models(self, reg_multi):
        results = reg_multi.filter_candidates(denied_models=["local-a"])
        ids = {m.model_id for m in results}
        assert "local-a" not in ids

    def test_stage9_allowed_providers_whitelist(self, reg_multi):
        results = reg_multi.filter_candidates(allowed_providers=["openrouter"])
        assert all(m.provider_id == "openrouter" for m in results)

    def test_stage10_preferred_model_prepend(self, reg_multi):
        results = reg_multi.filter_candidates(preferred_model="cloud-a")
        assert results[0].model_id == "cloud-a"

    def test_empty_registry_returns_empty(self):
        reg = ModelRegistry()
        assert reg.filter_candidates() == []


class TestModelRegistryCRUD:
    """Test register/unregister/get/list_all."""

    def test_register_and_get(self):
        reg = ModelRegistry()
        m = make_local_model("m1", provider_id="p1")
        reg.register(m)
        found = reg.get("m1", provider_id="p1")
        assert found is m

    def test_duplicate_registration_raises(self):
        reg = ModelRegistry()
        m = make_local_model("dup")
        reg.register(m)
        with pytest.raises(ValueError, match="Duplicate"):
            reg.register(m)

    def test_unregister(self):
        reg = ModelRegistry()
        m = make_local_model("gone")
        reg.register(m)
        removed = reg.unregister("gone", "ollama")
        assert removed is True
        assert reg.get("gone", "ollama") is None

    def test_list_for_provider(self):
        reg = ModelRegistry()
        reg.register(make_local_model("m1", provider_id="pA"))
        reg.register(make_local_model("m2", provider_id="pA"))
        reg.register(make_local_model("m3", provider_id="pB"))
        assert len(reg.list_for_provider("pA")) == 2
        assert len(reg.list_for_provider("pB")) == 1

    def test_quality_score_fallback(self):
        reg = ModelRegistry()
        m = make_local_model("m1")
        reg.register(m)
        # quality_scores is populated via fixture — check fallback when task not found
        score = reg.quality_score_for(m, TaskType.WRITING)
        assert 0.0 <= score <= 1.0

    def test_record_outcome_and_state(self):
        reg = ModelRegistry()
        m = make_local_model("m1", provider_id="p1")
        reg.register(m)
        reg.record_outcome("m1", "p1", success=True)
        reg.record_outcome("m1", "p1", success=True)
        reg.record_outcome("m1", "p1", success=False)
        state = reg._model_state[("p1", "m1")]
        assert state.total_successes == 2
        assert state.total_failures == 1
        assert state.consecutive_failures == 1

    def test_update_health(self):
        from aegis.l1_core.interfaces.llm import ModelHealth
        reg = ModelRegistry()
        m = make_local_model("m1", provider_id="p1")
        reg.register(m)
        ok = reg.update_health("m1", "p1", ModelHealth.DEGRADED)
        assert ok is True
        assert reg.get("m1", "p1").health is ModelHealth.DEGRADED
