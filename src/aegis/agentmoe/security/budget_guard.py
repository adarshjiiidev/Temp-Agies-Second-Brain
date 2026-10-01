"""AgentMoe — BudgetGuard (Phase 2 security).

Shared budget tracking across all workers in a mission.

The BudgetGuard prevents budget bypass attacks where parallel workers
each believe they have the full budget. It implements a shared atomic
counter (using asyncio.Lock) so the total spend across all workers
is accurate.

Workers deduct from the shared budget via BudgetGuard.deduct().
If a deduction would exceed the budget, BudgetExceededError is raised
BEFORE the operation is executed.

Import safety: stdlib + asyncio only.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional


__all__ = ["BudgetExceededError", "BudgetSnapshot", "BudgetGuard"]


class BudgetExceededError(Exception):
    """Raised when a deduction would exceed the mission budget."""
    def __init__(self, message: str, dimension: str = "") -> None:
        super().__init__(message)
        self.dimension = dimension


@dataclass
class BudgetSnapshot:
    """Point-in-time snapshot of mission budget usage."""
    max_input_tokens:  int
    max_output_tokens: int
    max_cost_usd:      float
    max_tool_calls:    int
    max_wall_seconds:  float
    used_input_tokens:  int
    used_output_tokens: int
    used_cost_usd:      float
    used_tool_calls:    int
    elapsed_seconds:    float

    def is_exhausted(self) -> bool:
        return (
            self.used_input_tokens  >= self.max_input_tokens
            or self.used_output_tokens >= self.max_output_tokens
            or self.used_cost_usd      >= self.max_cost_usd
            or self.used_tool_calls    >= self.max_tool_calls
            or self.elapsed_seconds    >= self.max_wall_seconds
        )

    def remaining_fraction(self) -> float:
        """Fraction of budget remaining (min across all dimensions)."""
        fracs = []
        if self.max_input_tokens  > 0: fracs.append(1.0 - self.used_input_tokens  / self.max_input_tokens)
        if self.max_output_tokens > 0: fracs.append(1.0 - self.used_output_tokens / self.max_output_tokens)
        if self.max_cost_usd      > 0: fracs.append(1.0 - self.used_cost_usd      / self.max_cost_usd)
        if self.max_tool_calls    > 0: fracs.append(1.0 - self.used_tool_calls    / self.max_tool_calls)
        if self.max_wall_seconds  > 0: fracs.append(1.0 - self.elapsed_seconds    / self.max_wall_seconds)
        return min(fracs) if fracs else 1.0

    def __str__(self) -> str:
        return (
            f"BudgetSnapshot("
            f"in={self.used_input_tokens}/{self.max_input_tokens}, "
            f"out={self.used_output_tokens}/{self.max_output_tokens}, "
            f"cost=${self.used_cost_usd:.4f}/{self.max_cost_usd:.4f}, "
            f"calls={self.used_tool_calls}/{self.max_tool_calls}, "
            f"time={self.elapsed_seconds:.1f}s/{self.max_wall_seconds:.1f}s"
            f")"
        )


class BudgetGuard:
    """Thread-safe shared budget for a mission (all workers draw from one pool).

    Usage::

        guard = BudgetGuard(
            max_input_tokens=100_000,
            max_cost_usd=5.0,
            max_tool_calls=200,
        )
        # Before LLM call:
        async with guard.deduct_context(input_tokens=1000, output_tokens=500):
            result = await llm.generate(...)
        # Before tool call:
        await guard.deduct_tool_call()
    """

    def __init__(
        self,
        *,
        max_input_tokens:  int   = 100_000,
        max_output_tokens: int   = 50_000,
        max_cost_usd:      float = 5.0,
        max_tool_calls:    int   = 200,
        max_wall_seconds:  float = 300.0,
    ) -> None:
        self._max_input  = max_input_tokens
        self._max_output = max_output_tokens
        self._max_cost   = max_cost_usd
        self._max_calls  = max_tool_calls
        self._max_wall   = max_wall_seconds

        self._used_input:  int   = 0
        self._used_output: int   = 0
        self._used_cost:   float = 0.0
        self._used_calls:  int   = 0
        self._started:     float = time.monotonic()

        self._lock = asyncio.Lock()

    # -- deductions --------------------------------------------------------

    async def deduct_tokens(
        self,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
    ) -> None:
        """Deduct token usage from shared budget.

        Raises:
            BudgetExceededError: If deduction would exceed any budget dimension.
        """
        async with self._lock:
            new_in   = self._used_input  + input_tokens
            new_out  = self._used_output + output_tokens
            new_cost = self._used_cost   + cost_usd

            if new_in > self._max_input:
                raise BudgetExceededError(
                    f"Input token budget exceeded: {new_in} > {self._max_input}",
                    dimension="input_tokens",
                )
            if new_out > self._max_output:
                raise BudgetExceededError(
                    f"Output token budget exceeded: {new_out} > {self._max_output}",
                    dimension="output_tokens",
                )
            if new_cost > self._max_cost:
                raise BudgetExceededError(
                    f"Cost budget exceeded: ${new_cost:.4f} > ${self._max_cost:.4f}",
                    dimension="cost_usd",
                )

            self._used_input  = new_in
            self._used_output = new_out
            self._used_cost   = new_cost

    async def deduct_tool_call(self) -> None:
        """Deduct one tool call from the shared budget.

        Raises:
            BudgetExceededError: If tool call budget is exhausted.
        """
        async with self._lock:
            new_calls = self._used_calls + 1
            if new_calls > self._max_calls:
                raise BudgetExceededError(
                    f"Tool call budget exceeded: {new_calls} > {self._max_calls}",
                    dimension="tool_calls",
                )
            self._used_calls = new_calls

    def check_wall_time(self) -> None:
        """Raise BudgetExceededError if wall time is exhausted.

        Non-async (safe to call from anywhere).
        """
        elapsed = time.monotonic() - self._started
        if elapsed >= self._max_wall:
            raise BudgetExceededError(
                f"Wall time budget exceeded: {elapsed:.1f}s > {self._max_wall:.1f}s",
                dimension="wall_seconds",
            )

    # -- snapshot ----------------------------------------------------------

    def snapshot(self) -> BudgetSnapshot:
        """Return a point-in-time snapshot (no lock — may be slightly stale)."""
        return BudgetSnapshot(
            max_input_tokens  = self._max_input,
            max_output_tokens = self._max_output,
            max_cost_usd      = self._max_cost,
            max_tool_calls    = self._max_calls,
            max_wall_seconds  = self._max_wall,
            used_input_tokens = self._used_input,
            used_output_tokens= self._used_output,
            used_cost_usd     = self._used_cost,
            used_tool_calls   = self._used_calls,
            elapsed_seconds   = time.monotonic() - self._started,
        )

    def is_exhausted(self) -> bool:
        """Non-async check if any budget dimension is exhausted."""
        snap = self.snapshot()
        return snap.is_exhausted()
