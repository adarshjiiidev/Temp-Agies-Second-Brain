"""AgentMoe — BaseWorker ABC.

Defines the contract for every AgentMoe worker.

Workers differ from tools in that they:
  1. Have a full lifecycle (created → running → completed/failed/cancelled).
  2. Can spawn child workers (delegation), subject to depth/privilege limits.
  3. Carry a budget (tokens, cost, time) that propagates to all children.
  4. Maintain a context window of task state (backed by L4 memory).
  5. Produce structured WorkerResult objects, not raw outputs.

Security invariants:
  - A child worker's tool_grants must be a STRICT SUBSET of its parent's.
  - A child's autonomy_level cannot exceed its parent's.
  - Children inherit the parent's budget and deduct from it.
  - Maximum delegation depth is enforced by WorkerRuntime (not here).

Import safety: stdlib + agentmoe.core.tool + agentmoe.config (no L5 imports).
"""

from __future__ import annotations

import abc
import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, FrozenSet, Optional


__all__ = [
    "WorkerState",
    "WorkerBudget",
    "WorkerContext",
    "WorkerResult",
    "BaseWorker",
]


# ---------------------------------------------------------------------------
# Worker lifecycle states
# ---------------------------------------------------------------------------

class WorkerState(str, Enum):
    """Lifecycle state of a worker."""
    CREATED    = "created"
    RUNNING    = "running"
    COMPLETED  = "completed"
    FAILED     = "failed"
    CANCELLED  = "cancelled"
    TIMEOUT    = "timeout"


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------

@dataclass
class WorkerBudget:
    """Resource budget for a worker and all its descendants.

    Budget is shared: the parent and all descendants draw from the same
    counters. WorkerRuntime enforces this via atomic operations.

    Attributes:
        max_input_tokens:   Hard cap on input tokens across all LLM calls.
        max_output_tokens:  Hard cap on output tokens.
        max_cost_usd:       Hard cap on estimated spend.
        max_tool_calls:     Hard cap on tool invocations.
        max_wall_seconds:   Hard cap on elapsed wall time.
        used_input_tokens:  Running total.
        used_output_tokens: Running total.
        used_cost_usd:      Running total.
        used_tool_calls:    Running total.
        started_at:         Wall time when budget was created.
    """
    max_input_tokens:  int   = 100_000
    max_output_tokens: int   = 50_000
    max_cost_usd:      float = 5.0
    max_tool_calls:    int   = 200
    max_wall_seconds:  float = 300.0

    used_input_tokens:  int   = 0
    used_output_tokens: int   = 0
    used_cost_usd:      float = 0.0
    used_tool_calls:    int   = 0
    started_at:         float = field(default_factory=time.monotonic)

    def is_exhausted(self) -> bool:
        """Return True if any budget dimension is exhausted."""
        elapsed = time.monotonic() - self.started_at
        return (
            self.used_input_tokens  >= self.max_input_tokens
            or self.used_output_tokens >= self.max_output_tokens
            or self.used_cost_usd      >= self.max_cost_usd
            or self.used_tool_calls    >= self.max_tool_calls
            or elapsed                 >= self.max_wall_seconds
        )

    def summary(self) -> dict[str, Any]:
        return {
            "input_tokens":  f"{self.used_input_tokens}/{self.max_input_tokens}",
            "output_tokens": f"{self.used_output_tokens}/{self.max_output_tokens}",
            "cost_usd":      f"{self.used_cost_usd:.4f}/{self.max_cost_usd:.4f}",
            "tool_calls":    f"{self.used_tool_calls}/{self.max_tool_calls}",
            "elapsed_s":     f"{time.monotonic() - self.started_at:.1f}/{self.max_wall_seconds}",
        }

    def child_budget(
        self,
        *,
        fraction: float = 0.5,
    ) -> "WorkerBudget":
        """Create a child budget as a fraction of remaining budget.

        Children can never exceed the remaining parent budget.
        """
        remaining_tokens_in  = self.max_input_tokens  - self.used_input_tokens
        remaining_tokens_out = self.max_output_tokens - self.used_output_tokens
        remaining_cost       = self.max_cost_usd      - self.used_cost_usd
        remaining_calls      = self.max_tool_calls    - self.used_tool_calls
        remaining_time       = self.max_wall_seconds  - (time.monotonic() - self.started_at)
        return WorkerBudget(
            max_input_tokens  = max(0, int(remaining_tokens_in  * fraction)),
            max_output_tokens = max(0, int(remaining_tokens_out * fraction)),
            max_cost_usd      = max(0.0, remaining_cost         * fraction),
            max_tool_calls    = max(0, int(remaining_calls      * fraction)),
            max_wall_seconds  = max(0.0, remaining_time         * fraction),
        )


# ---------------------------------------------------------------------------
# Worker context
# ---------------------------------------------------------------------------

@dataclass
class WorkerContext:
    """Scoped context for a worker's execution.

    Attributes:
        task:         Plain-text description of what this worker must do.
        artifacts:    Key→value dict of artifacts accumulated so far.
        history:      List of prior step summaries (for context window).
        metadata:     Arbitrary safe extras (no secrets).
    """
    task:      str
    artifacts: dict[str, Any]    = field(default_factory=dict)
    history:   list[str]         = field(default_factory=list)
    metadata:  dict[str, Any]    = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Worker result
# ---------------------------------------------------------------------------

@dataclass
class WorkerResult:
    """Structured result produced by a worker when it completes."""

    success:       bool
    state:         WorkerState
    output:        Any                  = None
    artifacts:     dict[str, Any]       = field(default_factory=dict)
    span_ids:      list[str]            = field(default_factory=list)
    budget_used:   Optional[dict]       = None
    error_type:    Optional[str]        = None
    error_message: Optional[str]        = None
    child_results: list["WorkerResult"] = field(default_factory=list)

    @classmethod
    def completed(
        cls,
        output: Any,
        *,
        artifacts: Optional[dict] = None,
        span_ids: Optional[list[str]] = None,
        budget: Optional[WorkerBudget] = None,
    ) -> "WorkerResult":
        return cls(
            success=True,
            state=WorkerState.COMPLETED,
            output=output,
            artifacts=artifacts or {},
            span_ids=span_ids or [],
            budget_used=budget.summary() if budget else None,
        )

    @classmethod
    def failed(
        cls,
        error_type: str,
        error_message: str,
        *,
        state: WorkerState = WorkerState.FAILED,
        budget: Optional[WorkerBudget] = None,
    ) -> "WorkerResult":
        return cls(
            success=False,
            state=state,
            error_type=error_type,
            error_message=error_message[:500],
            budget_used=budget.summary() if budget else None,
        )


# ---------------------------------------------------------------------------
# BaseWorker ABC
# ---------------------------------------------------------------------------

class BaseWorker(abc.ABC):
    """Abstract base class for every AgentMoe worker.

    Lifecycle::

        worker = MyWorker(session_id=..., parent_id=..., tool_grants=..., budget=...)
        result = await worker.run(context)
        # worker.state is now COMPLETED/FAILED/CANCELLED

    Subclasses must implement:
        - worker_type (property): human name like "CodingWorker"
        - run()                 : the actual worker logic

    Subclasses MUST NOT:
        - Grant themselves more tools than those in tool_grants.
        - Spawn children with more privileges than themselves.
        - Continue running after cancel() is called.
        - Access L5 directly — use tool.invoke() → CapabilityInvoker.
    """

    def __init__(
        self,
        *,
        session_id: str,
        mission_id: str,
        parent_id: Optional[str] = None,
        tool_grants: FrozenSet[str] = frozenset(),
        budget: Optional[WorkerBudget] = None,
        autonomy_level: int = 2,
        depth: int = 0,
    ) -> None:
        self._worker_id      = str(uuid.uuid4())
        self._session_id     = session_id
        self._mission_id     = mission_id
        self._parent_id      = parent_id
        self._tool_grants    = frozenset(tool_grants)
        self._budget         = budget or WorkerBudget()
        self._autonomy_level = autonomy_level
        self._depth          = depth
        self._state          = WorkerState.CREATED
        self._cancel_event   = asyncio.Event()
        self._span_ids:  list[str] = []

    # --- identity ---------------------------------------------------------

    @property
    def worker_id(self) -> str:
        return self._worker_id

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def mission_id(self) -> str:
        return self._mission_id

    @property
    def parent_id(self) -> Optional[str]:
        return self._parent_id

    @property
    def depth(self) -> int:
        return self._depth

    @property
    def state(self) -> WorkerState:
        return self._state

    @property
    def budget(self) -> WorkerBudget:
        return self._budget

    @property
    def tool_grants(self) -> FrozenSet[str]:
        return self._tool_grants

    @property
    def autonomy_level(self) -> int:
        return self._autonomy_level

    # --- subclass must implement ------------------------------------------

    @property
    @abc.abstractmethod
    def worker_type(self) -> str:
        """Human-readable worker type, e.g. 'CodingWorker'."""

    @abc.abstractmethod
    async def run(self, context: WorkerContext) -> WorkerResult:
        """Execute the worker's task.

        This method MUST:
          - Periodically check self._cancel_event.is_set() and cancel cleanly.
          - Check self._budget.is_exhausted() and return WorkerResult.failed() if so.
          - Set self._state at start (RUNNING) and on exit (COMPLETED/FAILED/CANCELLED).
          - Never continue execution after returning.
        """

    # --- lifecycle helpers -----------------------------------------------

    def cancel(self) -> None:
        """Signal this worker to stop. Non-blocking."""
        self._cancel_event.set()

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def _set_state(self, state: WorkerState) -> None:
        self._state = state

    def _check_cancelled(self) -> bool:
        """Return True (and mark state) if cancellation was requested."""
        if self._cancel_event.is_set():
            self._state = WorkerState.CANCELLED
            return True
        return False

    def _check_budget(self) -> bool:
        """Return True (and mark state) if budget is exhausted."""
        if self._budget.is_exhausted():
            self._state = WorkerState.FAILED
            return True
        return False

    def _record_span(self, span_id: str) -> None:
        self._span_ids.append(span_id)

    def _has_tool(self, tool_name: str) -> bool:
        """Check if this worker has been granted access to a named tool."""
        return tool_name in self._tool_grants or "*" in self._tool_grants

    def __repr__(self) -> str:
        return (
            f"<{self.worker_type} id={self._worker_id[:8]} "
            f"state={self._state.value} depth={self._depth}>"
        )
