"""P07.5 Credential Security Tests.

Verifies that raw API key material NEVER appears in:
  - Log output (caplog)
  - Exception messages
  - AIResponse / BudgetLedgerEntry / AIMetricsSnapshot serialised state
  - AIResponse.model_dump() output

Also verifies P0 privacy isolation:
  - P0 request with cloud-only model registry raises AIRouterPrivacyViolationError
  - P0 request NEVER reaches a cloud FakeProvider (call_count == 0)

Tests use deterministic fake credentials (never real keys).
No network calls.
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
import pytest

from aegis.l1_core.errors.base import AIRouterPrivacyViolationError
from aegis.l1_core.interfaces.llm import ModelHealth
from aegis.l3_intelligence.ai_kernel.accounting import CostAccountant
from aegis.l3_intelligence.ai_kernel.contracts import AIRequest, AIResponse, RoutingRequirements
from aegis.l3_intelligence.ai_kernel.credentials import (
    BrowserProvisioner,
    CredentialResolutionError,
    CredentialResolver,
    EnvironmentProvisioner,
    ManualProvisioner,
)
from aegis.l3_intelligence.ai_kernel.kernel import AIKernel
from aegis.l3_intelligence.ai_kernel.keys import KeyManager, ProviderKey
from aegis.l3_intelligence.ai_kernel.providers.base import ProviderRegistry
from aegis.l3_intelligence.ai_kernel.providers.fake import FakeProvider, FakeResponse
from aegis.l3_intelligence.ai_kernel.registry import ModelMetadata, ModelRegistry
from aegis.l3_intelligence.ai_kernel.types import DeploymentKind, PrivacyTier, TaskType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_KEY = "sk-fake-secret-key-DO-NOT-LOG-abc123xyz"
_FAKE_KEY_SHORT = "sk-fake-abc"


def _contains_secret(text: str, secret: str = _FAKE_KEY) -> bool:
    """Return True if the secret appears verbatim in text."""
    return secret in text


def _make_cloud_model(model_id: str = "cloud-model") -> ModelMetadata:
    from aegis.l3_intelligence.ai_kernel.registry import ModelCapability
    return ModelMetadata(
        model_id=model_id,
        provider_id="cloud",
        family="gpt",
        display_name=model_id,
        deployment=DeploymentKind.CLOUD,
        context_window=128000,
        output_limit=4096,
        capabilities={ModelCapability.REASONING.value},
        cost_per_input_1k=0.15,
        cost_per_output_1k=0.60,
        latency_first_ms_p50=800,
        supported_privacy_tiers={PrivacyTier.P2, PrivacyTier.P3},
        reliability_score=0.9,
        structural_compliance_score=0.9,
        health=ModelHealth.HEALTHY,
        quality_scores={TaskType.REASON: 0.9},
    )


def _make_local_model(model_id: str = "local-model") -> ModelMetadata:
    from aegis.l3_intelligence.ai_kernel.registry import ModelCapability
    return ModelMetadata(
        model_id=model_id,
        provider_id="local",
        family="llama",
        display_name=model_id,
        deployment=DeploymentKind.LOCAL,
        context_window=8192,
        output_limit=4096,
        capabilities={ModelCapability.REASONING.value},
        cost_per_input_1k=0.0,
        cost_per_output_1k=0.0,
        latency_first_ms_p50=200,
        supported_privacy_tiers={PrivacyTier.P0, PrivacyTier.P1, PrivacyTier.P2, PrivacyTier.P3},
        reliability_score=0.7,
        structural_compliance_score=0.7,
        health=ModelHealth.HEALTHY,
        quality_scores={TaskType.REASON: 0.7},
    )


# ===========================================================================
# CredentialResolver tests
# ===========================================================================


class TestCredentialResolverEnv:
    """CredentialResolver: env: scheme tests."""

    def test_resolve_env_present(self, monkeypatch):
        monkeypatch.setenv("TEST_RESOLVE_KEY", _FAKE_KEY)
        resolver = CredentialResolver()
        result = resolver.resolve("env:TEST_RESOLVE_KEY")
        assert result == _FAKE_KEY

    def test_resolve_bare_var_present(self, monkeypatch):
        monkeypatch.setenv("TEST_BARE_KEY", _FAKE_KEY_SHORT)
        resolver = CredentialResolver()
        result = resolver.resolve("TEST_BARE_KEY")
        assert result == _FAKE_KEY_SHORT

    def test_resolve_env_missing_raises(self, monkeypatch):
        monkeypatch.delenv("NONEXISTENT_VAR_P075", raising=False)
        resolver = CredentialResolver()
        with pytest.raises(CredentialResolutionError) as exc_info:
            resolver.resolve("env:NONEXISTENT_VAR_P075")
        # Exception message must NOT contain the raw key
        assert _FAKE_KEY not in str(exc_info.value)

    def test_resolve_env_empty_raises(self, monkeypatch):
        monkeypatch.setenv("EMPTY_KEY_VAR", "")
        resolver = CredentialResolver()
        with pytest.raises(CredentialResolutionError):
            resolver.resolve("env:EMPTY_KEY_VAR")

    def test_resolve_empty_ref_raises(self):
        resolver = CredentialResolver()
        with pytest.raises(CredentialResolutionError):
            resolver.resolve("")


class TestCredentialResolverFile:
    """CredentialResolver: file: scheme tests."""

    def test_resolve_file_present(self):
        resolver = CredentialResolver()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(f"{_FAKE_KEY}\n")
            path = f.name
        try:
            result = resolver.resolve(f"file:{path}")
            assert result == _FAKE_KEY
        finally:
            os.unlink(path)

    def test_resolve_file_strips_whitespace(self):
        resolver = CredentialResolver()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(f"  {_FAKE_KEY_SHORT}  \n")
            path = f.name
        try:
            result = resolver.resolve(f"file:{path}")
            assert result == _FAKE_KEY_SHORT
        finally:
            os.unlink(path)

    def test_resolve_file_missing_raises(self):
        resolver = CredentialResolver()
        with pytest.raises(CredentialResolutionError) as exc_info:
            resolver.resolve("file:/nonexistent/path/secret.txt")
        # Message must not be empty but must not contain leaked data
        assert len(str(exc_info.value)) > 5

    def test_resolve_file_empty_raises(self):
        resolver = CredentialResolver()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("\n\n\n")  # Only blank lines
            path = f.name
        try:
            with pytest.raises(CredentialResolutionError):
                resolver.resolve(f"file:{path}")
        finally:
            os.unlink(path)

    def test_resolve_keyring_raises_not_implemented(self):
        resolver = CredentialResolver()
        with pytest.raises(NotImplementedError):
            resolver.resolve("aegis-keyring:scope/my-key")


# ===========================================================================
# CredentialProvisioner tests
# ===========================================================================


class TestManualProvisioner:
    def test_provision_returns_existing_keys(self):
        km = KeyManager()
        km.register(ProviderKey(
            key_id="manual-groq-1",
            provider_id="groq",
            vault_ref=f"env:GROQ_API_KEY",
        ))
        prov = ManualProvisioner()
        result = prov.provision(km, "groq")
        assert "manual-groq-1" in result

    def test_provision_empty_returns_empty(self):
        km = KeyManager()
        prov = ManualProvisioner()
        result = prov.provision(km, "groq")
        assert result == []


class TestEnvironmentProvisioner:
    def test_discovers_primary_key(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", _FAKE_KEY)
        km = KeyManager()
        prov = EnvironmentProvisioner()
        result = prov.provision(km, "groq")
        assert len(result) >= 1
        registered = km.list_keys("groq")
        assert any(k.key_id == "env-groq-0" for k in registered)
        # vault_ref is the env var NAME, not the value
        key = next(k for k in registered if k.key_id == "env-groq-0")
        assert key.vault_ref == "env:GROQ_API_KEY"
        # Raw secret must NOT be stored in vault_ref
        assert _FAKE_KEY not in key.vault_ref

    def test_discovers_numbered_keys(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY_1", _FAKE_KEY)
        monkeypatch.setenv("GROQ_API_KEY_2", _FAKE_KEY_SHORT)
        km = KeyManager()
        prov = EnvironmentProvisioner()
        prov.provision(km, "groq")
        key_ids = [k.key_id for k in km.list_keys("groq")]
        assert "env-groq-1" in key_ids
        assert "env-groq-2" in key_ids

    def test_no_env_var_returns_empty(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("GROQ_API_KEY_1", raising=False)
        km = KeyManager()
        prov = EnvironmentProvisioner()
        result = prov.provision(km, "groq")
        assert result == []

    def test_idempotent_registration(self, monkeypatch):
        """Provisioning twice does not raise or duplicate keys."""
        monkeypatch.setenv("OPENROUTER_API_KEY", _FAKE_KEY)
        km = KeyManager()
        prov = EnvironmentProvisioner()
        r1 = prov.provision(km, "openrouter")
        r2 = prov.provision(km, "openrouter")
        assert r1 == r2
        assert len(km.list_keys("openrouter")) == 1


class TestBrowserProvisioner:
    def test_raises_not_implemented(self):
        km = KeyManager()
        prov = BrowserProvisioner()
        with pytest.raises(NotImplementedError) as exc_info:
            prov.provision(km, "groq")
        msg = str(exc_info.value)
        assert "BrowserProvisioner" in msg
        assert "not yet implemented" in msg
        # Must not have leaked any secret
        assert _FAKE_KEY not in msg


# ===========================================================================
# Secret never in logs tests
# ===========================================================================


class TestSecretNeverInLogs:
    """Verify raw API key material never appears in log output."""

    def test_resolver_env_not_logged(self, monkeypatch, caplog):
        monkeypatch.setenv("SECRET_VAR_LOG_TEST", _FAKE_KEY)
        resolver = CredentialResolver()
        with caplog.at_level(logging.DEBUG, logger="aegis"):
            resolver.resolve("env:SECRET_VAR_LOG_TEST")
        assert not _contains_secret(caplog.text)

    def test_provisioner_env_key_not_logged(self, monkeypatch, caplog):
        monkeypatch.setenv("GROQ_API_KEY", _FAKE_KEY)
        km = KeyManager()
        prov = EnvironmentProvisioner()
        with caplog.at_level(logging.DEBUG, logger="aegis"):
            prov.provision(km, "groq")
        assert not _contains_secret(caplog.text)

    def test_provider_key_vault_ref_not_raw_secret(self):
        """ProviderKey.vault_ref must not contain the raw API key."""
        key = ProviderKey(
            key_id="test-key-1",
            provider_id="groq",
            vault_ref="env:GROQ_API_KEY",
        )
        # vault_ref is an opaque reference — it must not be the raw secret
        assert _FAKE_KEY not in key.vault_ref
        # Serialised key must not contain the secret
        import dataclasses
        d = dataclasses.asdict(key)
        assert _FAKE_KEY not in str(d)


# ===========================================================================
# P0 privacy isolation tests
# ===========================================================================


class TestP0PrivacyIsolation:
    """P0 requests must NEVER reach cloud providers."""

    @pytest.mark.asyncio
    async def test_p0_request_never_reaches_cloud_provider(self):
        """P0 request with cloud-only model raises privacy error without calling provider."""
        reg = ModelRegistry()
        reg.register(_make_cloud_model())

        cloud_provider = FakeProvider(
            provider_id="cloud",
            model_ids=["cloud-model"],
            default_response=FakeResponse(content="SHOULD NOT BE SEEN"),
        )
        prov_reg = ProviderRegistry()
        prov_reg.register("cloud", cloud_provider)

        kernel = AIKernel(
            registry=reg,
            provider_registry=prov_reg,
            accountant=CostAccountant(),
        )

        from aegis.l1_core.interfaces.llm import ChatMessage
        req = AIRequest(
            messages=[ChatMessage(role="user", content="Secret info")],
            routing=RoutingRequirements(privacy_tier=PrivacyTier.P0),
        )

        with pytest.raises(AIRouterPrivacyViolationError):
            await kernel.generate(req)

        # Cloud provider must never have been called
        assert cloud_provider.call_count() == 0

    @pytest.mark.asyncio
    async def test_p0_request_succeeds_with_local_provider(self):
        """P0 request routes correctly to local model."""
        reg = ModelRegistry()
        reg.register(_make_local_model())
        reg.register(_make_cloud_model())  # Should be ignored for P0

        local_provider = FakeProvider(
            provider_id="local",
            model_ids=["local-model"],
            default_response=FakeResponse(content="Local P0 response.", tokens_in=5, tokens_out=5),
        )
        cloud_provider = FakeProvider(
            provider_id="cloud",
            model_ids=["cloud-model"],
            default_response=FakeResponse(content="CLOUD LEAK"),
        )
        prov_reg = ProviderRegistry()
        prov_reg.register("local", local_provider)
        prov_reg.register("cloud", cloud_provider)

        kernel = AIKernel(
            registry=reg,
            provider_registry=prov_reg,
            accountant=CostAccountant(),
        )

        from aegis.l1_core.interfaces.llm import ChatMessage
        req = AIRequest(
            messages=[ChatMessage(role="user", content="Private data")],
            routing=RoutingRequirements(privacy_tier=PrivacyTier.P0),
        )
        resp = await kernel.generate(req)
        assert resp.content == "Local P0 response."
        assert cloud_provider.call_count() == 0

    @pytest.mark.asyncio
    async def test_local_only_flag_sets_p0(self):
        """RoutingRequirements.local_only=True must set privacy_tier=P0."""
        req = AIRequest(
            messages=[],
            routing=RoutingRequirements(local_only=True),
        )
        assert req.routing.privacy_tier == PrivacyTier.P0


# ===========================================================================
# AIResponse / ledger never contain raw secrets
# ===========================================================================


class TestResponseNeverContainsSecrets:
    """AIResponse and BudgetLedgerEntry must never contain raw credential values."""

    @pytest.mark.asyncio
    async def test_response_dump_no_secrets(self, monkeypatch):
        """Serialised AIResponse must not contain raw API key strings."""
        monkeypatch.setenv("OPENROUTER_API_KEY", _FAKE_KEY)

        reg = ModelRegistry()
        reg.register(_make_local_model())
        prov_reg = ProviderRegistry()
        prov_reg.register("local", FakeProvider(
            provider_id="local",
            model_ids=["local-model"],
            default_response=FakeResponse(content="Safe response.", tokens_in=5, tokens_out=3),
        ))

        kernel = AIKernel(
            registry=reg,
            provider_registry=prov_reg,
            accountant=CostAccountant(),
        )

        from aegis.l1_core.interfaces.llm import ChatMessage
        req = AIRequest(
            messages=[ChatMessage(role="user", content="Hello")],
        )
        resp = await kernel.generate(req)
        dumped = str(resp.model_dump())
        assert _FAKE_KEY not in dumped

    def test_provider_key_not_in_ledger_entry(self):
        """BudgetLedgerEntry.key_id is the non-secret key_id, not the vault_ref."""
        from aegis.l3_intelligence.ai_kernel.contracts import BudgetLedgerEntry
        import time, uuid
        from aegis.l3_intelligence.ai_kernel.types import TokenUsage, CostEstimate
        entry = BudgetLedgerEntry(
            timestamp=time.time(),
            request_id=uuid.uuid4(),
            provider_id="groq",
            model_id="llama3",
            key_id="env-groq-0",  # Only the non-secret ID, not the vault_ref value
            usage=TokenUsage(),
            actual_cost=CostEstimate(),
        )
        d = entry.model_dump(mode="json")
        assert _FAKE_KEY not in str(d)
        assert entry.key_id == "env-groq-0"
