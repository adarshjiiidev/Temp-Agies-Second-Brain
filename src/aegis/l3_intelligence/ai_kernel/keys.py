"""Prompt03 §12 API key rotation, multiple keys per provider, cooldown, failure tracking, usage tracking.

Provider-neutral key management abstraction supporting multiple keys per provider
with registration, selection, rotation strategies, failure tracking, cooldowns,
rate-limit awareness, temporary disablement, and usage tracking.

This module MUST NOT import providers, registry, or router modules to avoid
circular import risks. Only types.py + stdlib + L1 errors (AIKeyError / ErrorCode
for the mark_rotation_failure escalation path).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from aegis.l1_core.errors.base import AIKeyError
from aegis.l1_core.errors.codes import ErrorCode
from aegis.l3_intelligence.ai_kernel.types import (
    FailureCategory,
    KeyRotationStrategy,
)


@dataclass(frozen=True, slots=True)
class ProviderKey:
    """Immutable registered provider key metadata.

    IMPORTANT: The literal API secret is NEVER stored here. Only a vault
    reference (vault_ref) is kept — resolve to the real secret via the L2
    crypto/vault module at call time. Use vault_ref patterns like
    "secret://scope/id" or plain env-var names.
    """

    key_id: str
    provider_id: str
    vault_ref: str = ""
    scopes: set[str] = field(default_factory=lambda: {"chat", "embed", "image"})
    priority: int = 0
    enabled: bool = True
    daily_cost_budget_usd: Optional[float] = None
    monthly_cost_budget_usd: Optional[float] = None
    created_at: float = field(default_factory=time.time)


@dataclass(slots=True)
class ProviderKeyState:
    """Mutable internal runtime state for a single registered key.

    Counters, timestamps, and cooldown markers — not part of the frozen
    ProviderKey identity because they change on every select/success/failure.
    """

    consecutive_failures: int = 0
    rate_limited_until: float = 0.0
    disabled_until: float = 0.0
    daily_spend_usd: float = 0.0
    monthly_spend_usd: float = 0.0
    last_used_at: float = 0.0
    last_failed_at: float = 0.0
    last_success_at: float = 0.0


@dataclass(slots=True)
class KeySelectionResult:
    """Returned by KeyManager.select — the chosen key plus a diagnostic reason.

    reason is populated when key is None so callers can distinguish between
    "no keys registered" vs "all currently rate-limited" vs etc.
    """

    key: Optional[ProviderKey] = None
    reason: str = ""


class KeyManager:
    """Multi-key manager with pluggable rotation strategies (§12).

    Tracks per-provider key lists, exposes registration/unregistration,
    strategy-driven selection, success/failure accounting with cooldown
    transitions, and budget-window reset hooks.
    """

    def __init__(
        self,
        rotation: KeyRotationStrategy = KeyRotationStrategy.HEALTH_AWARE,
        *,
        default_cooldown_rate_limit_seconds: float = 30.0,
        default_cooldown_auth_seconds: float = 600.0,
    ) -> None:
        self._rotation: KeyRotationStrategy = rotation
        self._default_cooldown_rate_limit_seconds: float = (
            default_cooldown_rate_limit_seconds
        )
        self._default_cooldown_auth_seconds: float = default_cooldown_auth_seconds
        self._keys: dict[str, ProviderKey] = {}
        self._keys_by_provider: dict[str, list[str]] = {}
        self._state: dict[str, ProviderKeyState] = {}
        self._round_robin_cursor: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, key: ProviderKey) -> None:
        if key.key_id in self._keys:
            raise ValueError("key_id already registered")
        self._keys[key.key_id] = key
        self._state[key.key_id] = ProviderKeyState()
        if key.provider_id not in self._keys_by_provider:
            self._keys_by_provider[key.provider_id] = []
            self._round_robin_cursor[key.provider_id] = 0
        self._keys_by_provider[key.provider_id].append(key.key_id)

    def unregister(self, key_id: str) -> bool:
        if key_id not in self._keys:
            return False
        key = self._keys.pop(key_id)
        self._state.pop(key_id, None)
        key_list = self._keys_by_provider.get(key.provider_id)
        if key_list is not None:
            if key_id in key_list:
                key_list.remove(key_id)
            if not key_list:
                del self._keys_by_provider[key.provider_id]
                self._round_robin_cursor.pop(key.provider_id, None)
        return True

    def list_keys(self, provider_id: Optional[str] = None) -> list[ProviderKey]:
        if provider_id is None:
            return list(self._keys.values())
        key_ids = self._keys_by_provider.get(provider_id, [])
        return [self._keys[kid] for kid in key_ids if kid in self._keys]

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def select(
        self,
        provider_id: str,
        required_scope: str = "chat",
        now: Optional[float] = None,
    ) -> KeySelectionResult:
        ts = now if now is not None else time.time()
        key_ids = self._keys_by_provider.get(provider_id)
        if not key_ids:
            return KeySelectionResult(key=None, reason="no_keys")

        all_keys = [self._keys[kid] for kid in key_ids if kid in self._keys]
        if not all_keys:
            return KeySelectionResult(key=None, reason="no_keys")

        any_scope_match = False
        any_enabled = False
        any_not_rate_limited = False
        any_not_disabled = False
        any_within_budget = False

        candidates: list[tuple[ProviderKey, ProviderKeyState]] = []
        for key in all_keys:
            state = self._state[key.key_id]
            if not key.enabled:
                continue
            any_enabled = True
            if required_scope not in key.scopes:
                continue
            any_scope_match = True
            if ts < state.disabled_until:
                continue
            any_not_disabled = True
            if ts < state.rate_limited_until:
                continue
            any_not_rate_limited = True
            if (
                key.daily_cost_budget_usd is not None
                and state.daily_spend_usd >= key.daily_cost_budget_usd
            ):
                continue
            if (
                key.monthly_cost_budget_usd is not None
                and state.monthly_spend_usd >= key.monthly_cost_budget_usd
            ):
                continue
            any_within_budget = True
            candidates.append((key, state))

        if not candidates:
            if not any_enabled:
                reason = "all_disabled"
            elif not any_scope_match:
                reason = "all_scope_mismatch"
            elif not any_not_disabled:
                reason = "all_disabled"
            elif not any_not_rate_limited:
                reason = "all_rate_limited"
            elif not any_within_budget:
                reason = "all_budget_exhausted"
            else:
                reason = "no_keys"
            return KeySelectionResult(key=None, reason=reason)

        chosen_key: ProviderKey
        if self._rotation == KeyRotationStrategy.ROUND_ROBIN:
            chosen_key = self._select_round_robin(provider_id, candidates, ts)
        elif self._rotation == KeyRotationStrategy.LEAST_RECENTLY_USED:
            chosen_key = self._select_lru(candidates)
        elif self._rotation == KeyRotationStrategy.LEAST_RECENTLY_FAILED:
            chosen_key = self._select_lrf(candidates)
        else:
            chosen_key = self._select_health_aware(candidates)

        chosen_state = self._state[chosen_key.key_id]
        chosen_state.last_used_at = ts
        return KeySelectionResult(key=chosen_key, reason="")

    # ------------------------------------------------ strategy dispatch

    def _select_round_robin(
        self,
        provider_id: str,
        candidates: list[tuple[ProviderKey, ProviderKeyState]],
        _ts: float,
    ) -> ProviderKey:
        cursor = self._round_robin_cursor.get(provider_id, 0)
        sorted_candidates = sorted(candidates, key=lambda pair: pair[0].key_id)
        n = len(sorted_candidates)
        if n == 0:
            return candidates[0][0]
        if cursor >= n:
            cursor = 0
        picked = sorted_candidates[cursor][0]
        self._round_robin_cursor[provider_id] = (cursor + 1) % n
        return picked

    def _select_lru(
        self,
        candidates: list[tuple[ProviderKey, ProviderKeyState]],
    ) -> ProviderKey:
        return min(candidates, key=lambda pair: pair[1].last_used_at)[0]

    def _select_lrf(
        self,
        candidates: list[tuple[ProviderKey, ProviderKeyState]],
    ) -> ProviderKey:
        def _rank(pair: tuple[ProviderKey, ProviderKeyState]) -> tuple[float, int]:
            _key, state = pair
            return (state.last_failed_at, -_key.priority)
        return min(candidates, key=_rank)[0]

    def _select_health_aware(
        self,
        candidates: list[tuple[ProviderKey, ProviderKeyState]],
    ) -> ProviderKey:
        def _rank(pair: tuple[ProviderKey, ProviderKeyState]) -> tuple[int, int, float]:
            _key, state = pair
            return (state.consecutive_failures, _key.priority, state.last_used_at)
        return min(candidates, key=_rank)[0]

    # ------------------------------------------------------------------
    # Outcome recording
    # ------------------------------------------------------------------

    def mark_success(
        self,
        provider_id: str,
        key_id: str,
        spend_usd: float = 0.0,
        now: Optional[float] = None,
    ) -> None:
        state = self._state.get(key_id)
        if state is None:
            return
        ts = now if now is not None else time.time()
        state.consecutive_failures = 0
        state.last_success_at = ts
        state.daily_spend_usd += spend_usd
        state.monthly_spend_usd += spend_usd

    def mark_failure(
        self,
        provider_id: str,
        key_id: str,
        failure_category: FailureCategory,
        now: Optional[float] = None,
    ) -> None:
        state = self._state.get(key_id)
        if state is None:
            return
        ts = now if now is not None else time.time()
        state.consecutive_failures += 1
        state.last_failed_at = ts

        if failure_category == FailureCategory.AUTHENTICATION:
            state.disabled_until = 1e18
        elif failure_category == FailureCategory.RATE_LIMITED:
            state.rate_limited_until = ts + self._default_cooldown_rate_limit_seconds
        elif failure_category == FailureCategory.QUOTA_EXHAUSTED:
            state.disabled_until = ts + 86400.0
        elif failure_category in (
            FailureCategory.PROVIDER_UNAVAILABLE,
            FailureCategory.RETRYABLE,
        ):
            state.rate_limited_until = ts + self._default_cooldown_rate_limit_seconds

    # ------------------------------------------------------------------
    # Budget window resets
    # ------------------------------------------------------------------

    def reset_daily_budgets(self, now: Optional[float] = None) -> None:
        for state in self._state.values():
            state.daily_spend_usd = 0.0

    def reset_monthly_budgets(self, now: Optional[float] = None) -> None:
        for state in self._state.values():
            state.monthly_spend_usd = 0.0

    # ------------------------------------------------------------------
    # Escalation
    # ------------------------------------------------------------------

    def mark_rotation_failure(self, provider_id: str) -> None:
        raise AIKeyError(
            ErrorCode.AI_KEY_ROTATION_EXHAUSTED,
            f"All API keys exhausted for provider {provider_id!r}",
        )


__all__ = [
    "ProviderKey",
    "ProviderKeyState",
    "KeyManager",
    "KeySelectionResult",
    "KeyRotationStrategy",
]
