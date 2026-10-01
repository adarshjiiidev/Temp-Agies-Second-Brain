"""Integration tests — CostAccountant and budget enforcement.

Validation battery (07_AI_STRATEGY §7):
  - Pre-call budget check passes within limit
  - Pre-call check fails when estimate exceeds daily limit
  - record_spend deducts from all applicable scopes
  - 10th call fails with BUDGET_EXHAUSTED when $0.01/day budget set
  - Daily reset restores budget
  - Per-call limit enforcement
  - Session budget scope
"""

from __future__ import annotations

import time

import pytest

from aegis.l1_core.errors.base import AIBudgetDailyLimitError, AIBudgetError
from aegis.l3_intelligence.ai_kernel.accounting import Budget, BudgetCheckResult, CostAccountant
from aegis.l3_intelligence.ai_kernel.contracts import BudgetLedgerEntry
from aegis.l3_intelligence.ai_kernel.types import BudgetScope, CostEstimate, PrivacyTier, TaskType, TokenUsage


def _ledger_entry(
    *,
    provider_id: str = "openrouter",
    model_id: str = "gpt-4o-mini",
    cost_usd: float = 0.01,
    session_id: str | None = None,
) -> BudgetLedgerEntry:
    return BudgetLedgerEntry(
        timestamp=time.time(),
        request_id=__import__("uuid").uuid4(),
        provider_id=provider_id,
        model_id=model_id,
        usage=TokenUsage(input_tokens=100, output_tokens=50),
        actual_cost=CostEstimate(cost_usd=cost_usd, is_estimate=False),
        session_id=session_id,
    )


class TestBudgetCheckPrecall:
    def test_check_passes_within_limit(self):
        acct = CostAccountant(global_daily_limit_usd=2.0, per_call_limit_usd=1.0)
        result = acct.check_budgets(0.01)
        assert result.ok is True

    def test_check_fails_exceeds_daily_limit(self):
        acct = CostAccountant(global_daily_limit_usd=0.01, per_call_limit_usd=5.0)
        result = acct.check_budgets(0.05)
        assert result.ok is False
        assert result.failing_scope is BudgetScope.GLOBAL

    def test_check_fails_exceeds_per_call_cap(self):
        acct = CostAccountant(global_daily_limit_usd=100.0, per_call_limit_usd=0.50)
        result = acct.check_budgets(0.75)
        assert result.ok is False

    def test_check_passes_for_free_local_call(self):
        acct = CostAccountant(global_daily_limit_usd=0.001, per_call_limit_usd=0.001)
        result = acct.check_budgets(0.0)
        assert result.ok is True

    def test_check_with_session_budget(self):
        acct = CostAccountant(global_daily_limit_usd=100.0, per_call_limit_usd=10.0)
        acct.set_budget(Budget(
            scope=BudgetScope.SESSION,
            scope_id="sess-123",
            limit_usd=0.05,
            period_seconds=None,
        ))
        result = acct.check_budgets(0.10, session_id="sess-123")
        assert result.ok is False
        assert result.failing_scope is BudgetScope.SESSION


class TestBudgetRecord:
    def test_record_deducts_from_daily(self):
        acct = CostAccountant(global_daily_limit_usd=10.0)
        acct.record_spend(_ledger_entry(cost_usd=1.0))
        remaining = acct.get_global_daily_remaining()
        assert abs(remaining - 9.0) < 0.001

    def test_10th_call_fails_with_tiny_daily_budget(self):
        """Budget=$0.01/day. After 1 call of $0.001, 10 calls should exhaust it."""
        acct = CostAccountant(global_daily_limit_usd=0.01, per_call_limit_usd=1.0)
        successful = 0
        failed = False
        for i in range(20):
            check = acct.check_budgets(0.001)
            if not check.ok:
                failed = True
                break
            try:
                acct.record_spend(_ledger_entry(cost_usd=0.001))
                successful += 1
            except AIBudgetError:
                failed = True
                break
        assert failed, "Budget should exhaust before 20 calls at $0.001 each"
        assert successful <= 10, f"Expected at most 10 successful calls, got {successful}"

    def test_budget_exhausted_raises_daily_error(self):
        acct = CostAccountant(global_daily_limit_usd=0.005)
        # Manually consume most
        acct.record_spend(_ledger_entry(cost_usd=0.004))
        with pytest.raises(AIBudgetError):
            acct.record_spend(_ledger_entry(cost_usd=0.002))

    def test_record_updates_session_spend(self):
        acct = CostAccountant(global_daily_limit_usd=100.0, per_call_limit_usd=10.0)
        acct.set_budget(Budget(
            scope=BudgetScope.SESSION,
            scope_id="sess-abc",
            limit_usd=1.0,
            period_seconds=None,
        ))
        acct.record_spend(_ledger_entry(cost_usd=0.40, session_id="sess-abc"))
        sess_budget = acct.get_budget(BudgetScope.SESSION, "sess-abc")
        assert sess_budget is not None
        assert abs(sess_budget.spent_usd - 0.40) < 0.0001


class TestBudgetLedger:
    def test_ledger_records_all_entries(self):
        acct = CostAccountant(global_daily_limit_usd=100.0)
        for i in range(5):
            acct.record_spend(_ledger_entry(cost_usd=0.001 * (i + 1)))
        entries = acct.ledger()
        assert len(entries) == 5

    def test_total_spent(self):
        acct = CostAccountant(global_daily_limit_usd=100.0)
        acct.record_spend(_ledger_entry(cost_usd=0.10))
        acct.record_spend(_ledger_entry(cost_usd=0.20))
        total = acct.total_spent()
        assert abs(total.cost_usd - 0.30) < 0.0001

    def test_ledger_filter_by_provider(self):
        acct = CostAccountant(global_daily_limit_usd=100.0)
        acct.record_spend(_ledger_entry(provider_id="openrouter"))
        acct.record_spend(_ledger_entry(provider_id="groq"))
        entries = acct.ledger(provider_id="groq")
        assert all(e.provider_id == "groq" for e in entries)
        assert len(entries) == 1


class TestBudgetPeriodReset:
    def test_reset_periodic_budgets(self):
        acct = CostAccountant(global_daily_limit_usd=1.0)
        acct.record_spend(_ledger_entry(cost_usd=0.50))
        assert acct.get_global_daily_remaining() < 0.51

        # Force period expiry by back-dating the start
        daily_budget = acct.get_budget(BudgetScope.GLOBAL, "global_daily")
        daily_budget.period_start_ts -= 90000  # >24h ago
        reset = acct.reset_periodic_budgets()
        assert "global_daily" in reset
        assert acct.get_global_daily_remaining() >= 0.99
