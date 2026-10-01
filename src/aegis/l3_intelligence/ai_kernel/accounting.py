"""§14 Cost accounting and budget enforcement — 4-point budget checks (pre-call, mid-stream future hook, post-call deduction, daily rollup). Default daily $2, monthly $40, per-task $0.50 per 07_AI_STRATEGY §7.3."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any

from aegis.l1_core.errors.base import (
    AIBudgetDailyLimitError,
    AIBudgetError,
)
from aegis.l1_core.errors import ErrorCode
from aegis.l3_intelligence.ai_kernel.contracts import BudgetLedgerEntry
from aegis.l3_intelligence.ai_kernel.types import BudgetScope, CostEstimate


GLOBAL_DAILY_ID = "global_daily"
GLOBAL_MONTHLY_ID = "global_monthly"
_UNLIMITED_INTERNAL = 1e18
_DAY_SECONDS = 86400.0
_MONTH_SECONDS = 30 * _DAY_SECONDS


@dataclass
class Budget:
    scope: BudgetScope
    scope_id: str
    limit_usd: float
    spent_usd: float = 0.0
    enabled: bool = True
    period_start_ts: float = 0.0
    period_seconds: float | None = None

    def __post_init__(self) -> None:
        if self.limit_usd == float("inf"):
            self.limit_usd = _UNLIMITED_INTERNAL
        if self.period_start_ts == 0.0:
            self.period_start_ts = time.time()

    @property
    def remaining_usd(self) -> float:
        if not self.enabled:
            return 0.0
        return max(0.0, self.limit_usd - self.spent_usd)

    def is_period_expired(self, now: float | None = None) -> bool:
        if self.period_seconds is None:
            return False
        t = now if now is not None else time.time()
        return (t - self.period_start_ts) > self.period_seconds

    def reset_period(self, now: float | None = None) -> None:
        self.spent_usd = 0.0
        self.period_start_ts = now if now is not None else time.time()


@dataclass
class BudgetCheckResult:
    ok: bool
    remaining_usd: float
    limit_usd: float
    spent_usd: float
    failing_scope: BudgetScope | None = None
    failing_scope_id: str | None = None
    reason: str = ""


class CostAccountant:
    def __init__(
        self,
        global_daily_limit_usd: float = 2.00,
        global_monthly_limit_usd: float = 40.00,
        per_call_limit_usd: float = 0.50,
    ) -> None:
        self._per_call_limit_usd: float = per_call_limit_usd
        self._budgets: dict[tuple[BudgetScope, str], Budget] = {}
        self._ledger: list[BudgetLedgerEntry] = []
        now = time.time()
        self._budgets[(BudgetScope.GLOBAL, GLOBAL_DAILY_ID)] = Budget(
            scope=BudgetScope.GLOBAL,
            scope_id=GLOBAL_DAILY_ID,
            limit_usd=global_daily_limit_usd,
            spent_usd=0.0,
            enabled=True,
            period_start_ts=now,
            period_seconds=_DAY_SECONDS,
        )
        self._budgets[(BudgetScope.GLOBAL, GLOBAL_MONTHLY_ID)] = Budget(
            scope=BudgetScope.GLOBAL,
            scope_id=GLOBAL_MONTHLY_ID,
            limit_usd=global_monthly_limit_usd,
            spent_usd=0.0,
            enabled=True,
            period_start_ts=now,
            period_seconds=_MONTH_SECONDS,
        )

    # ------------------------------------------------------------------ Budget management

    def set_budget(self, budget: Budget) -> None:
        if budget.limit_usd == float("inf"):
            budget.limit_usd = _UNLIMITED_INTERNAL
        if budget.period_start_ts == 0.0:
            budget.period_start_ts = time.time()
        self._budgets[(budget.scope, budget.scope_id)] = budget

    def get_budget(self, scope: BudgetScope, scope_id: str) -> Budget | None:
        return self._budgets.get((scope, scope_id))

    def list_budgets(self) -> list[Budget]:
        return list(self._budgets.values())

    def reset_periodic_budgets(self, now: float | None = None) -> list[str]:
        t = now if now is not None else time.time()
        reset_ids: list[str] = []
        for budget in self._budgets.values():
            if budget.period_seconds is not None and (t - budget.period_start_ts) > budget.period_seconds:
                budget.spent_usd = 0.0
                budget.period_start_ts = t
                reset_ids.append(budget.scope_id)
        return reset_ids

    # ------------------------------------------------------------------ Pre-call check

    def check_budgets(
        self,
        estimated_cost_usd: float,
        *,
        session_id: str | None = None,
        project_id: str | None = None,
        provider_id: str | None = None,
        key_id: str | None = None,
        request_id: str | None = None,
    ) -> BudgetCheckResult:
        req_scope_id = f"req_{request_id or uuid.uuid4().hex}"

        check_order: list[tuple[BudgetScope, str | None]] = [
            (BudgetScope.REQUEST, req_scope_id),
            (BudgetScope.SESSION, session_id),
            (BudgetScope.KEY, key_id),
            (BudgetScope.PROVIDER, provider_id),
            (BudgetScope.PROJECT, project_id),
            (BudgetScope.GLOBAL, GLOBAL_DAILY_ID),
            (BudgetScope.GLOBAL, GLOBAL_MONTHLY_ID),
        ]

        min_remaining = float("inf")
        min_limit = float("inf")
        min_spent = 0.0

        for scope, sid in check_order:
            if sid is None:
                continue
            budget = self.get_budget(scope, sid)
            if budget is None:
                continue
            if not budget.enabled:
                return BudgetCheckResult(
                    ok=False,
                    remaining_usd=0.0,
                    limit_usd=budget.limit_usd,
                    spent_usd=budget.spent_usd,
                    failing_scope=scope,
                    failing_scope_id=sid,
                    reason=f"Budget disabled for {scope.value}:{sid}",
                )
            remaining = budget.limit_usd - budget.spent_usd
            if estimated_cost_usd > remaining:
                return BudgetCheckResult(
                    ok=False,
                    remaining_usd=max(0.0, remaining),
                    limit_usd=budget.limit_usd,
                    spent_usd=budget.spent_usd,
                    failing_scope=scope,
                    failing_scope_id=sid,
                    reason=(
                        f"Estimated cost ${estimated_cost_usd:.4f} exceeds remaining "
                        f"${remaining:.4f} in {scope.value}:{sid} "
                        f"(limit=${budget.limit_usd:.4f}, spent=${budget.spent_usd:.4f})"
                    ),
                )
            if remaining < min_remaining:
                min_remaining = remaining
                min_limit = budget.limit_usd
                min_spent = budget.spent_usd

        if estimated_cost_usd > self._per_call_limit_usd:
            return BudgetCheckResult(
                ok=False,
                remaining_usd=max(0.0, min_remaining if min_remaining != float("inf") else self._per_call_limit_usd),
                limit_usd=self._per_call_limit_usd,
                spent_usd=estimated_cost_usd,
                failing_scope=BudgetScope.REQUEST,
                failing_scope_id=req_scope_id,
                reason=(
                    f"Estimated cost ${estimated_cost_usd:.4f} exceeds per-call cap "
                    f"${self._per_call_limit_usd:.4f}"
                ),
            )

        effective_remaining = min_remaining if min_remaining != float("inf") else (self._per_call_limit_usd - estimated_cost_usd)
        effective_limit = min_limit if min_limit != float("inf") else self._per_call_limit_usd
        effective_spent = min_spent if min_limit != float("inf") else 0.0

        return BudgetCheckResult(
            ok=True,
            remaining_usd=max(0.0, effective_remaining),
            limit_usd=effective_limit,
            spent_usd=effective_spent,
            failing_scope=None,
            failing_scope_id=None,
            reason="",
        )

    # ------------------------------------------------------------------ Post-call deduction

    def record_spend(self, entry: BudgetLedgerEntry) -> list[BudgetScope]:
        reset_scopes: list[BudgetScope] = []
        cost_usd = entry.actual_cost.cost_usd
        now = time.time()

        for budget in list(self._budgets.values()):
            if budget.period_seconds is not None and (now - budget.period_start_ts) > budget.period_seconds:
                budget.spent_usd = 0.0
                budget.period_start_ts = now
                if budget.scope not in reset_scopes:
                    reset_scopes.append(budget.scope)

        scope_ids: list[tuple[BudgetScope, str | None]] = []
        if entry.session_id is not None:
            scope_ids.append((BudgetScope.SESSION, entry.session_id))
        if entry.project_id is not None:
            scope_ids.append((BudgetScope.PROJECT, entry.project_id))
        if entry.provider_id is not None:
            scope_ids.append((BudgetScope.PROVIDER, entry.provider_id))
        if entry.key_id is not None:
            scope_ids.append((BudgetScope.KEY, entry.key_id))
        scope_ids.append((BudgetScope.GLOBAL, GLOBAL_DAILY_ID))
        scope_ids.append((BudgetScope.GLOBAL, GLOBAL_MONTHLY_ID))

        first_exceeded: tuple[BudgetScope, str, Budget] | None = None

        for scope, sid in scope_ids:
            if sid is None:
                continue
            budget = self.get_budget(scope, sid)
            if budget is None or not budget.enabled:
                continue
            budget.spent_usd += cost_usd
            if budget.spent_usd > budget.limit_usd and first_exceeded is None:
                first_exceeded = (scope, sid, budget)

        self._ledger.append(entry)

        if first_exceeded is not None:
            scope, sid, budget = first_exceeded
            if scope is BudgetScope.GLOBAL and sid == GLOBAL_DAILY_ID:
                raise AIBudgetDailyLimitError(
                    ErrorCode.AI_BUDGET_DAILY_LIMIT,
                    (
                        f"Daily global budget exceeded: spent ${budget.spent_usd:.4f} "
                        f"> limit ${budget.limit_usd:.4f}"
                    ),
                )
            raise AIBudgetError(
                ErrorCode.AI_BUDGET_EXHAUSTED,
                (
                    f"Budget exhausted for {scope.value}:{sid} — "
                    f"spent ${budget.spent_usd:.4f} > limit ${budget.limit_usd:.4f}"
                ),
            )

        return reset_scopes

    # ------------------------------------------------------------------ Ledger queries

    def ledger(
        self,
        start_ts: float | None = None,
        end_ts: float | None = None,
        **filters: Any,
    ) -> list[BudgetLedgerEntry]:
        results: list[BudgetLedgerEntry] = []
        for entry in self._ledger:
            if start_ts is not None and entry.timestamp < start_ts:
                continue
            if end_ts is not None and entry.timestamp > end_ts:
                continue
            match = True
            for key, value in filters.items():
                entry_val = getattr(entry, key, None)
                if entry_val != value:
                    match = False
                    break
            if match:
                results.append(entry)
        return results

    def total_spent(
        self,
        start_ts: float | None = None,
        end_ts: float | None = None,
        **filters: Any,
    ) -> CostEstimate:
        entries = self.ledger(start_ts, end_ts, **filters)
        total = sum(e.actual_cost.cost_usd for e in entries)
        return CostEstimate(cost_usd=total, currency="USD", is_estimate=False)

    # ------------------------------------------------------------------ Budget accessors

    def get_global_daily_remaining(self) -> float:
        budget = self.get_budget(BudgetScope.GLOBAL, GLOBAL_DAILY_ID)
        if budget is None:
            return 0.0
        return max(0.0, budget.limit_usd - budget.spent_usd)

    def get_global_monthly_remaining(self) -> float:
        budget = self.get_budget(BudgetScope.GLOBAL, GLOBAL_MONTHLY_ID)
        if budget is None:
            return 0.0
        return max(0.0, budget.limit_usd - budget.spent_usd)


__all__ = [
    "Budget",
    "BudgetCheckResult",
    "CostAccountant",
]
