"""Integration tests — KeyManager rotation strategies, failure tracking, cooldown."""

from __future__ import annotations

import time

import pytest

from aegis.l3_intelligence.ai_kernel.keys import (
    KeyManager,
    KeyRotationStrategy,
    ProviderKey,
)
from aegis.l3_intelligence.ai_kernel.types import FailureCategory


def _key(key_id: str, provider_id: str = "openrouter", priority: int = 0, enabled: bool = True) -> ProviderKey:
    return ProviderKey(
        key_id=key_id,
        provider_id=provider_id,
        vault_ref=f"env:{key_id.upper()}",
        scopes={"chat"},
        priority=priority,
        enabled=enabled,
    )


class TestKeyRegistration:
    def test_register_and_list(self):
        km = KeyManager()
        km.register(_key("k1"))
        km.register(_key("k2"))
        keys = km.list_keys("openrouter")
        assert len(keys) == 2

    def test_duplicate_key_id_raises(self):
        km = KeyManager()
        km.register(_key("k1"))
        with pytest.raises(ValueError, match="already registered"):
            km.register(_key("k1"))

    def test_unregister(self):
        km = KeyManager()
        km.register(_key("k1"))
        removed = km.unregister("k1")
        assert removed is True
        assert km.list_keys("openrouter") == []


class TestKeySelection:
    def test_select_returns_key(self):
        km = KeyManager()
        km.register(_key("k1"))
        result = km.select("openrouter", required_scope="chat")
        assert result.key is not None
        assert result.key.key_id == "k1"

    def test_select_no_keys_returns_none(self):
        km = KeyManager()
        result = km.select("openrouter")
        assert result.key is None
        assert result.reason == "no_keys"

    def test_select_disabled_key_skipped(self):
        km = KeyManager()
        km.register(_key("k-disabled", enabled=False))
        result = km.select("openrouter")
        assert result.key is None
        assert result.reason == "all_disabled"

    def test_select_scope_mismatch_skipped(self):
        km = KeyManager()
        k = ProviderKey(
            key_id="k-embed-only",
            provider_id="openrouter",
            vault_ref="env:K",
            scopes={"embed"},
            priority=0,
            enabled=True,
        )
        km.register(k)
        result = km.select("openrouter", required_scope="chat")
        assert result.key is None
        assert result.reason == "all_scope_mismatch"


class TestKeyRotation:
    def test_round_robin_cycles(self):
        km = KeyManager(rotation=KeyRotationStrategy.ROUND_ROBIN)
        km.register(_key("k1", priority=0))
        km.register(_key("k2", priority=1))
        km.register(_key("k3", priority=2))
        seen = set()
        for _ in range(9):
            result = km.select("openrouter")
            assert result.key is not None
            seen.add(result.key.key_id)
        assert seen == {"k1", "k2", "k3"}

    def test_health_aware_prefers_no_failures(self):
        km = KeyManager(rotation=KeyRotationStrategy.HEALTH_AWARE)
        km.register(_key("good-key", priority=0))
        km.register(_key("bad-key", priority=0))
        # Mark bad-key with failures
        km.mark_failure("openrouter", "bad-key", FailureCategory.RETRYABLE)
        km.mark_failure("openrouter", "bad-key", FailureCategory.RETRYABLE)
        result = km.select("openrouter")
        assert result.key is not None
        assert result.key.key_id == "good-key"


class TestKeyFailureHandling:
    def test_auth_failure_disables_key(self):
        km = KeyManager()
        km.register(_key("k1"))
        km.mark_failure("openrouter", "k1", FailureCategory.AUTHENTICATION)
        result = km.select("openrouter")
        assert result.key is None
        assert result.reason in ("all_disabled", "all_rate_limited")

    def test_rate_limit_with_cooldown(self):
        km = KeyManager(default_cooldown_rate_limit_seconds=3600.0)
        km.register(_key("k1"))
        km.mark_failure("openrouter", "k1", FailureCategory.RATE_LIMITED)
        result = km.select("openrouter")
        assert result.key is None
        assert result.reason == "all_rate_limited"

    def test_cooldown_expires_and_key_reselected(self):
        km = KeyManager(default_cooldown_rate_limit_seconds=0.0)
        km.register(_key("k1"))
        km.mark_failure("openrouter", "k1", FailureCategory.RATE_LIMITED)
        # Cooldown = 0 → immediately available again
        result = km.select("openrouter", now=time.time() + 1)
        assert result.key is not None

    def test_mark_success_resets_failures(self):
        km = KeyManager()
        km.register(_key("k1"))
        km.mark_failure("openrouter", "k1", FailureCategory.RETRYABLE)
        km.mark_success("openrouter", "k1", spend_usd=0.01)
        state = km._state["k1"]
        assert state.consecutive_failures == 0

    def test_mark_rotation_failure_raises(self):
        from aegis.l1_core.errors.base import AIKeyError
        km = KeyManager()
        with pytest.raises(AIKeyError):
            km.mark_rotation_failure("openrouter")


class TestKeyBudgets:
    def test_key_daily_budget_exhausted(self):
        km = KeyManager()
        k = ProviderKey(
            key_id="k-budget",
            provider_id="openrouter",
            vault_ref="env:K",
            scopes={"chat"},
            priority=0,
            enabled=True,
            daily_cost_budget_usd=0.01,
        )
        km.register(k)
        km.mark_success("openrouter", "k-budget", spend_usd=0.02)
        result = km.select("openrouter")
        assert result.key is None
        assert result.reason == "all_budget_exhausted"

    def test_daily_budget_reset(self):
        km = KeyManager()
        k = ProviderKey(
            key_id="k-budget",
            provider_id="openrouter",
            vault_ref="env:K",
            scopes={"chat"},
            priority=0,
            enabled=True,
            daily_cost_budget_usd=0.01,
        )
        km.register(k)
        km.mark_success("openrouter", "k-budget", spend_usd=0.02)
        km.reset_daily_budgets()
        result = km.select("openrouter")
        assert result.key is not None
