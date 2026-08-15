"""G4: Groq provider + KeyManager + Credential unit tests.

Verified facts (read from source):
- KeyManager() takes rotation + cooldown params (no provider_id)
- km.select(provider_id) returns KeySelectionResult(key=..., reason=...)
- km.mark_failure(provider_id, key_id, failure_category)
- km._state is keyed by key_id (string, not tuple)
- FailureCategory: AUTHENTICATION, RATE_LIMITED, QUOTA_EXHAUSTED, PROVIDER_UNAVAILABLE, RETRYABLE
- FakeProvider.responses must be list[FakeResponse], not list[str]
- FakeProvider.call_count() is a METHOD, not a property
- GroqProvider._raise_from_http(exc) raises mapped error types

No live network calls.
"""

from __future__ import annotations

import time
import pytest
import httpx

from aegis.l3_intelligence.ai_kernel.credentials import (
    BrowserProvisioner,
    CredentialResolutionError,
    CredentialResolver,
    EnvironmentProvisioner,
    ManualProvisioner,
)
from aegis.l3_intelligence.ai_kernel.keys import (
    KeyManager,
    KeySelectionResult,
    ProviderKey,
    ProviderKeyState,
)
from aegis.l3_intelligence.ai_kernel.providers.groq import GroqProvider
from aegis.l3_intelligence.ai_kernel.types import FailureCategory, KeyRotationStrategy
from aegis.l1_core.errors.base import (
    AIAuthenticationError,
    AIProviderUnavailableError,
    AIRateLimitError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MOCK_KEY_VALUE = "sk-test-mock-sentinel-not-real"


def _make_key(
    key_id: str,
    provider_id: str = "groq",
    vault_ref: str = "env:GROQ_API_KEY",
) -> ProviderKey:
    return ProviderKey(
        key_id=key_id,
        provider_id=provider_id,
        vault_ref=vault_ref,
    )


def _make_km_with_keys(n: int, provider_id: str = "groq") -> KeyManager:
    """Make a KeyManager with n pre-registered keys for provider_id."""
    km = KeyManager()  # no provider_id arg — keys self-classify via ProviderKey.provider_id
    for i in range(n):
        km.register(_make_key(f"key-{i}", provider_id=provider_id))
    return km


def _http_exc(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError(f"HTTP {status}", request=request, response=response)


# ---------------------------------------------------------------------------
# GroqProvider construction
# ---------------------------------------------------------------------------


class TestGroqProviderConstruction:
    def test_provider_id(self):
        p = GroqProvider(api_key=MOCK_KEY_VALUE)
        assert p.provider_id == "groq"

    def test_api_key_not_in_repr(self):
        """Raw key value must never appear in repr."""
        p = GroqProvider(api_key=MOCK_KEY_VALUE)
        assert MOCK_KEY_VALUE not in repr(p)

    def test_available_models_non_empty(self):
        p = GroqProvider(api_key=MOCK_KEY_VALUE)
        models = p.available_models()
        assert len(models) > 0
        assert all(m.provider == "groq" for m in models)

    def test_available_models_custom_list(self):
        p = GroqProvider(
            api_key=MOCK_KEY_VALUE,
            model_ids=["llama3-70b-8192", "mixtral-8x7b-32768"],
        )
        ids = [m.model_id for m in p.available_models()]
        assert "llama3-70b-8192" in ids
        assert "mixtral-8x7b-32768" in ids


# ---------------------------------------------------------------------------
# HTTP error mapping
# ---------------------------------------------------------------------------


class TestGroqHTTPErrorMapping:
    def test_401_raises_auth_error(self):
        p = GroqProvider(api_key=MOCK_KEY_VALUE)
        with pytest.raises(AIAuthenticationError):
            p._raise_from_http(_http_exc(401))

    def test_403_raises_auth_error(self):
        p = GroqProvider(api_key=MOCK_KEY_VALUE)
        with pytest.raises(AIAuthenticationError):
            p._raise_from_http(_http_exc(403))

    def test_429_raises_rate_limit_error(self):
        p = GroqProvider(api_key=MOCK_KEY_VALUE)
        with pytest.raises(AIRateLimitError):
            p._raise_from_http(_http_exc(429))

    def test_500_raises_unavailable_error(self):
        p = GroqProvider(api_key=MOCK_KEY_VALUE)
        with pytest.raises(AIProviderUnavailableError):
            p._raise_from_http(_http_exc(500))

    def test_503_raises_unavailable_error(self):
        p = GroqProvider(api_key=MOCK_KEY_VALUE)
        with pytest.raises(AIProviderUnavailableError):
            p._raise_from_http(_http_exc(503))

    def test_secret_not_in_auth_exception(self):
        """Key value must not leak into exception messages."""
        p = GroqProvider(api_key=MOCK_KEY_VALUE)
        try:
            p._raise_from_http(_http_exc(401))
        except AIAuthenticationError as e:
            assert MOCK_KEY_VALUE not in str(e)
            assert MOCK_KEY_VALUE not in repr(e)

    def test_secret_not_in_rate_limit_exception(self):
        p = GroqProvider(api_key=MOCK_KEY_VALUE)
        try:
            p._raise_from_http(_http_exc(429))
        except AIRateLimitError as e:
            assert MOCK_KEY_VALUE not in str(e)


# ---------------------------------------------------------------------------
# EnvironmentProvisioner
# ---------------------------------------------------------------------------


class TestEnvironmentProvisioner:
    def test_discovers_numbered_keys(self, monkeypatch):
        for i in range(1, 5):
            monkeypatch.setenv(f"GROQ_API_KEY_{i}", f"mock-k{i}")

        provisioner = EnvironmentProvisioner()
        km = KeyManager()
        key_ids = provisioner.provision(km, "groq")

        assert "env-groq-1" in key_ids
        assert "env-groq-2" in key_ids
        assert "env-groq-3" in key_ids
        assert "env-groq-4" in key_ids
        assert len(km.list_keys("groq")) == 4

    def test_discovers_primary_key(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "mock-primary")
        # Remove numbered keys so only primary is seen
        for i in range(1, 5):
            monkeypatch.delenv(f"GROQ_API_KEY_{i}", raising=False)
        provisioner = EnvironmentProvisioner()
        km = KeyManager()
        key_ids = provisioner.provision(km, "groq")
        assert "env-groq-0" in key_ids

    def test_no_env_vars_registers_nothing(self, monkeypatch):
        for var in ["GROQ_API_KEY"] + [f"GROQ_API_KEY_{i}" for i in range(1, 5)]:
            monkeypatch.delenv(var, raising=False)
        provisioner = EnvironmentProvisioner()
        km = KeyManager()
        key_ids = provisioner.provision(km, "groq")
        assert key_ids == []

    def test_idempotent_double_provision(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY_1", "mock-k1")
        for var in ["GROQ_API_KEY"] + [f"GROQ_API_KEY_{i}" for i in range(2, 5)]:
            monkeypatch.delenv(var, raising=False)
        provisioner = EnvironmentProvisioner()
        km = KeyManager()
        provisioner.provision(km, "groq")
        provisioner.provision(km, "groq")  # second call is a no-op
        assert len(km.list_keys("groq")) == 1

    def test_vault_ref_stores_name_not_value(self, monkeypatch):
        """vault_ref must store the env var NAME, not the resolved secret value."""
        monkeypatch.setenv("GROQ_API_KEY_1", "super-secret-value")
        for var in ["GROQ_API_KEY"] + [f"GROQ_API_KEY_{i}" for i in range(2, 5)]:
            monkeypatch.delenv(var, raising=False)
        provisioner = EnvironmentProvisioner()
        km = KeyManager()
        provisioner.provision(km, "groq")
        for k in km.list_keys("groq"):
            assert "super-secret-value" not in k.vault_ref
            assert "GROQ_API_KEY" in k.vault_ref


# ---------------------------------------------------------------------------
# KeyManager rotation
# ---------------------------------------------------------------------------


class TestKeyManagerRotation:
    def test_round_robin_cycles_through_keys(self):
        km = KeyManager(rotation=KeyRotationStrategy.ROUND_ROBIN)
        for i in range(3):
            km.register(_make_key(f"key-{i}"))
        seen = set()
        for _ in range(6):
            result = km.select("groq")
            if result.key:
                seen.add(result.key.key_id)
        assert len(seen) == 3

    def test_failed_key_gets_rate_limit_cooldown(self):
        km = _make_km_with_keys(1)
        result = km.select("groq")
        assert result.key is not None
        km.mark_failure("groq", result.key.key_id, FailureCategory.RATE_LIMITED)
        # State is keyed by key_id
        state = km._state[result.key.key_id]
        assert state.rate_limited_until > time.time()

    def test_rate_limited_key_not_selected(self):
        """A single rate-limited key yields key=None from select."""
        km = _make_km_with_keys(1)
        result = km.select("groq")
        assert result.key is not None
        km.mark_failure("groq", result.key.key_id, FailureCategory.RATE_LIMITED)
        # Only 1 key and it's rate-limited — nothing selectable
        second = km.select("groq")
        assert second.key is None

    def test_auth_failure_disables_key(self):
        """Auth-failed key is disabled; second key is still selectable."""
        km = KeyManager()
        km.register(_make_key("key-0"))
        km.register(_make_key("key-1"))
        keys = km.list_keys("groq")
        first_id = keys[0].key_id
        km.mark_failure("groq", first_id, FailureCategory.AUTHENTICATION)
        # disabled_until = 1e18 (effectively permanent)
        assert km._state[first_id].disabled_until > time.time() + 1e10
        # key-1 should still be selectable
        result = km.select("groq")
        assert result.key is not None
        assert result.key.key_id != first_id

    def test_successful_call_resets_consecutive_failures(self):
        km = _make_km_with_keys(1)
        result = km.select("groq")
        key_id = result.key.key_id
        km.mark_failure("groq", key_id, FailureCategory.RETRYABLE)
        assert km._state[key_id].consecutive_failures == 1
        km.mark_success("groq", key_id)
        assert km._state[key_id].consecutive_failures == 0


# ---------------------------------------------------------------------------
# CredentialResolver
# ---------------------------------------------------------------------------


class TestCredentialResolver:
    def test_env_scheme_resolves(self, monkeypatch):
        monkeypatch.setenv("GROQ_TEST_KEY_RESOLVER", "resolved-value")
        resolver = CredentialResolver()
        result = resolver.resolve("env:GROQ_TEST_KEY_RESOLVER")
        assert result == "resolved-value"

    def test_env_scheme_missing_raises(self, monkeypatch):
        monkeypatch.delenv("GROQ_NONEXISTENT_XYZ_999", raising=False)
        resolver = CredentialResolver()
        with pytest.raises(CredentialResolutionError):
            resolver.resolve("env:GROQ_NONEXISTENT_XYZ_999")

    def test_bare_string_treated_as_env_var(self, monkeypatch):
        monkeypatch.setenv("GROQ_BARE_KEY_TEST", "bare-resolved")
        resolver = CredentialResolver()
        result = resolver.resolve("GROQ_BARE_KEY_TEST")
        assert result == "bare-resolved"

    def test_empty_vault_ref_raises(self):
        resolver = CredentialResolver()
        with pytest.raises(CredentialResolutionError):
            resolver.resolve("")

    def test_resolved_value_not_in_error_message(self, monkeypatch):
        monkeypatch.delenv("GROQ_MISSING_VAR_999", raising=False)
        resolver = CredentialResolver()
        try:
            resolver.resolve("env:GROQ_MISSING_VAR_999")
        except CredentialResolutionError as e:
            # Exception should reference the var name, not reveal secrets
            assert "super-secret" not in str(e)


# ---------------------------------------------------------------------------
# BrowserProvisioner safety
# ---------------------------------------------------------------------------


class TestBrowserProvisionerSafety:
    def test_raises_not_implemented(self):
        """BrowserProvisioner must always raise NotImplementedError — safety contract."""
        provisioner = BrowserProvisioner()
        km = KeyManager()
        with pytest.raises(NotImplementedError) as exc_info:
            provisioner.provision(km, "groq")
        assert "not yet implemented" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# ManualProvisioner
# ---------------------------------------------------------------------------


class TestManualProvisioner:
    def test_noop_returns_existing_key_ids(self):
        km = _make_km_with_keys(2)
        provisioner = ManualProvisioner()
        key_ids = provisioner.provision(km, "groq")
        assert len(key_ids) == 2
        assert "key-0" in key_ids
        assert "key-1" in key_ids

    def test_noop_does_not_add_keys(self):
        km = _make_km_with_keys(1)
        provisioner = ManualProvisioner()
        provisioner.provision(km, "groq")
        provisioner.provision(km, "groq")
        assert len(km.list_keys("groq")) == 1
