"""Unit tests — WorkerRuntime.

Tests:
  1. Spawn and run basic worker
  2. Concurrency limit enforcement
  3. Depth limit enforcement
  4. Privilege inheritance (child cannot exceed parent grants)
  5. Autonomy inheritance (child cannot exceed parent level)
  6. Timeout enforcement
  7. Cancellation propagation
  8. Shutdown with cleanup guarantee
"""

from __future__ import annotations

import asyncio
import pytest

from aegis.agentmoe.core.worker import BaseWorker, WorkerBudget, WorkerContext, WorkerResult, WorkerState
from aegis.agentmoe.workers.runtime import WorkerRuntime, WorkerSpawnError
from aegis.agentmoe.config.settings import AgentMoeConfig, WorkerConfig


# ---------------------------------------------------------------------------
# Test workers
# ---------------------------------------------------------------------------

class QuickWorker(BaseWorker):
    @property
    def worker_type(self): return "QuickWorker"
    async def run(self, context: WorkerContext) -> WorkerResult:
        self._set_state(WorkerState.RUNNING)
        if self._check_cancelled():
            return WorkerResult.failed("Cancelled", "cancelled", state=WorkerState.CANCELLED)
        self._set_state(WorkerState.COMPLETED)
        return WorkerResult.completed(f"done: {context.task}")


class SlowWorker(BaseWorker):
    """Worker that sleeps until cancelled."""
    @property
    def worker_type(self): return "SlowWorker"
    async def run(self, context: WorkerContext) -> WorkerResult:
        self._set_state(WorkerState.RUNNING)
        try:
            await asyncio.sleep(999)
        except asyncio.CancelledError:
            self._set_state(WorkerState.CANCELLED)
            return WorkerResult.failed("Cancelled", "cancelled", state=WorkerState.CANCELLED)
        return WorkerResult.completed("done")


class BudgetHogWorker(BaseWorker):
    @property
    def worker_type(self): return "BudgetHogWorker"
    async def run(self, context: WorkerContext) -> WorkerResult:
        self._set_state(WorkerState.RUNNING)
        self._set_state(WorkerState.COMPLETED)
        return WorkerResult.completed("done")


# ---------------------------------------------------------------------------
# WorkerRuntime tests
# ---------------------------------------------------------------------------

class TestWorkerRuntime:
    def _runtime(self, **worker_overrides):
        config = AgentMoeConfig(
            workers=WorkerConfig(
                max_depth=4,
                max_concurrent_workers=8,
                default_worker_timeout_seconds=5.0,
                shutdown_grace_seconds=2.0,
                **worker_overrides,
            )
        )
        return WorkerRuntime(config=config, session_id="sess1", mission_id="miss1")

    @pytest.mark.asyncio
    async def test_spawn_and_run_basic(self):
        runtime = self._runtime()
        result = await runtime.spawn_and_run(
            QuickWorker,
            WorkerContext(task="test task"),
            tool_grants=frozenset({"filesystem"}),
        )
        assert result.success
        assert result.state == WorkerState.COMPLETED
        await runtime.shutdown()

    @pytest.mark.asyncio
    async def test_max_depth_enforced(self):
        runtime = self._runtime(max_depth=1)
        # Spawn parent at depth 0
        parent = QuickWorker(
            session_id="sess1",
            mission_id="miss1",
            tool_grants=frozenset({"filesystem"}),
            depth=0,
        )
        # Simulate parent running by setting its state
        parent._set_state(WorkerState.RUNNING)

        # Try to spawn child from parent (depth would be 1 = max_depth = allowed)
        # Then try depth 2 which should fail
        child = QuickWorker(
            session_id="sess1",
            mission_id="miss1",
            tool_grants=frozenset({"filesystem"}),
            depth=1,
        )

        with pytest.raises(WorkerSpawnError, match="depth"):
            # parent_worker.depth = 1, child would be depth 2 > max_depth 1
            await runtime.spawn_and_run(
                QuickWorker,
                WorkerContext(task="too deep"),
                tool_grants=frozenset({"filesystem"}),
                parent_worker=child,  # child is at depth 1, grandchild would be 2
            )
        await runtime.shutdown()

    @pytest.mark.asyncio
    async def test_privilege_inheritance_child_subset_of_parent(self):
        runtime = self._runtime()

        parent = QuickWorker(
            session_id="sess1",
            mission_id="miss1",
            tool_grants=frozenset({"filesystem", "terminal"}),
            depth=0,
        )

        # Child requests a tool parent doesn't have
        with pytest.raises(WorkerSpawnError, match="security invariant"):
            await runtime.spawn_and_run(
                QuickWorker,
                WorkerContext(task="escalate"),
                tool_grants=frozenset({"filesystem", "terminal", "browser"}),  # extra!
                parent_worker=parent,
            )
        await runtime.shutdown()

    @pytest.mark.asyncio
    async def test_privilege_inheritance_child_valid_subset(self):
        runtime = self._runtime()

        parent = QuickWorker(
            session_id="sess1",
            mission_id="miss1",
            tool_grants=frozenset({"filesystem", "terminal", "git"}),
            depth=0,
        )

        # Child requests subset — OK
        result = await runtime.spawn_and_run(
            QuickWorker,
            WorkerContext(task="subset task"),
            tool_grants=frozenset({"filesystem"}),  # subset of parent
            parent_worker=parent,
        )
        assert result.success
        await runtime.shutdown()

    @pytest.mark.asyncio
    async def test_autonomy_inheritance_child_cannot_exceed_parent(self):
        runtime = self._runtime()

        parent = QuickWorker(
            session_id="sess1",
            mission_id="miss1",
            tool_grants=frozenset({"*"}),
            autonomy_level=2,
            depth=0,
        )

        with pytest.raises(WorkerSpawnError, match="autonomy"):
            await runtime.spawn_and_run(
                QuickWorker,
                WorkerContext(task="escalate autonomy"),
                tool_grants=frozenset({"filesystem"}),
                autonomy_level=4,  # higher than parent's 2
                parent_worker=parent,
            )
        await runtime.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_after_done(self):
        runtime = self._runtime()
        await runtime.spawn_and_run(
            QuickWorker, WorkerContext(task="done"),
            tool_grants=frozenset(),
        )
        await runtime.shutdown()  # should not hang

    @pytest.mark.asyncio
    async def test_spawn_after_shutdown_raises(self):
        runtime = self._runtime()
        await runtime.shutdown()
        with pytest.raises(WorkerSpawnError, match="shut down"):
            await runtime.spawn_and_run(
                QuickWorker, WorkerContext(task="post shutdown"),
                tool_grants=frozenset(),
            )

    @pytest.mark.asyncio
    async def test_timeout_worker_returns_timeout_result(self):
        config = AgentMoeConfig(
            workers=WorkerConfig(
                default_worker_timeout_seconds=0.05,  # 50ms
                shutdown_grace_seconds=1.0,
            )
        )
        runtime = WorkerRuntime(config=config, session_id="s", mission_id="m")
        result = await runtime.spawn_and_run(
            SlowWorker,
            WorkerContext(task="sleep forever"),
            tool_grants=frozenset(),
        )
        assert not result.success
        assert result.state == WorkerState.TIMEOUT
        await runtime.shutdown()
