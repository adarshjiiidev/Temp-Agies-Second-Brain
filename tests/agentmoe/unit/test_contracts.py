"""Unit tests — AgentMoe core contracts.

Tests verify:
  1. BaseTool contract (name, description, risk_level, dry_run, idempotent)
  2. ToolResult construction (ok, err)
  3. BaseWorker lifecycle (state transitions, cancel, budget)
  4. WorkerBudget (child budget, exhaustion)
  5. ToolFabric (register, invoke, grants enforcement, span emission)
  6. ExecutionSpan / SpanBuilder

These tests have NO external dependencies (no L5, no network, no filesystem).
"""

from __future__ import annotations

import asyncio
import pytest
from typing import Any, Optional
from unittest.mock import AsyncMock

from aegis.agentmoe.core.tool import BaseTool, ToolResult, ToolRiskLevel, ToolInvokeError
from aegis.agentmoe.core.worker import (
    BaseWorker, WorkerBudget, WorkerContext, WorkerResult, WorkerState,
)
from aegis.agentmoe.core.fabric import ToolFabric, ToolNotFoundError, ToolNotGrantedError
from aegis.agentmoe.observability.span import SpanBuilder, SpanKind, SpanStatus


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

class EchoTool(BaseTool):
    """A simple echo tool that returns its parameters."""

    @property
    def name(self) -> str:
        return "test.echo"

    @property
    def description(self) -> str:
        return "Returns input as output."

    @property
    def default_risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.LOW

    @property
    def supports_dry_run(self) -> bool:
        return True

    @property
    def is_idempotent(self) -> bool:
        return True

    async def invoke(self, *, parameters, worker_id, mission_id,
                     parent_span_id=None, dry_run=False, user_confirmed=False) -> ToolResult:
        if dry_run:
            return ToolResult.ok({"dry_run": True, "would_echo": parameters}, dry_run=True)
        return ToolResult.ok({"echo": parameters})


class FailingTool(BaseTool):
    """A tool that always fails."""

    @property
    def name(self) -> str:
        return "test.fail"

    @property
    def description(self) -> str:
        return "Always fails."

    @property
    def default_risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.MEDIUM

    async def invoke(self, *, parameters, worker_id, mission_id,
                     parent_span_id=None, dry_run=False, user_confirmed=False) -> ToolResult:
        return ToolResult.err("AlwaysFails", "This tool always fails")


class StubWorker(BaseWorker):
    """Minimal worker that completes immediately."""

    @property
    def worker_type(self) -> str:
        return "StubWorker"

    async def run(self, context: WorkerContext) -> WorkerResult:
        self._set_state(WorkerState.RUNNING)
        if self._check_cancelled():
            return WorkerResult.failed("Cancelled", "Cancelled", state=WorkerState.CANCELLED)
        self._set_state(WorkerState.COMPLETED)
        return WorkerResult.completed(f"done: {context.task}")


# ---------------------------------------------------------------------------
# ToolResult tests
# ---------------------------------------------------------------------------

class TestToolResult:
    def test_ok_creates_success_result(self):
        r = ToolResult.ok("hello")
        assert r.success is True
        assert r.output == "hello"
        assert r.dry_run is False

    def test_ok_dry_run(self):
        r = ToolResult.ok("preview", dry_run=True)
        assert r.dry_run is True

    def test_err_creates_failure(self):
        r = ToolResult.err("MyError", "something went wrong")
        assert r.success is False
        assert r.error_type == "MyError"
        assert r.error_message == "something went wrong"

    def test_err_truncates_long_message(self):
        long_msg = "x" * 1000
        r = ToolResult.err("Err", long_msg)
        assert len(r.error_message) <= 500

    def test_ok_with_metadata(self):
        r = ToolResult.ok("out", key="val")
        assert r.metadata["key"] == "val"


# ---------------------------------------------------------------------------
# BaseTool tests
# ---------------------------------------------------------------------------

class TestBaseTool:
    def test_echo_tool_properties(self):
        t = EchoTool()
        assert t.name == "test.echo"
        assert t.default_risk_level == ToolRiskLevel.LOW
        assert t.supports_dry_run is True
        assert t.is_idempotent is True
        assert t.requires_network is False

    def test_repr_contains_name_and_risk(self):
        t = EchoTool()
        r = repr(t)
        assert "EchoTool" in r
        assert "test.echo" in r
        assert "LOW" in r

    @pytest.mark.asyncio
    async def test_echo_tool_invoke(self):
        t = EchoTool()
        result = await t.invoke(
            parameters={"msg": "hello"},
            worker_id="w1",
            mission_id="m1",
        )
        assert result.success is True
        assert result.output["echo"]["msg"] == "hello"

    @pytest.mark.asyncio
    async def test_echo_tool_dry_run(self):
        t = EchoTool()
        result = await t.invoke(
            parameters={"msg": "hello"},
            worker_id="w1",
            mission_id="m1",
            dry_run=True,
        )
        assert result.dry_run is True
        assert result.output["dry_run"] is True

    @pytest.mark.asyncio
    async def test_failing_tool_returns_err(self):
        t = FailingTool()
        result = await t.invoke(parameters={}, worker_id="w1", mission_id="m1")
        assert result.success is False
        assert result.error_type == "AlwaysFails"


# ---------------------------------------------------------------------------
# WorkerBudget tests
# ---------------------------------------------------------------------------

class TestWorkerBudget:
    def test_fresh_budget_not_exhausted(self):
        b = WorkerBudget(max_input_tokens=1000, max_wall_seconds=300)
        assert not b.is_exhausted()

    def test_exhausted_on_token_limit(self):
        b = WorkerBudget(max_input_tokens=100)
        b.used_input_tokens = 100
        assert b.is_exhausted()

    def test_exhausted_on_tool_calls(self):
        b = WorkerBudget(max_tool_calls=5)
        b.used_tool_calls = 5
        assert b.is_exhausted()

    def test_child_budget_fraction(self):
        b = WorkerBudget(max_input_tokens=100_000, max_cost_usd=10.0, max_tool_calls=100)
        child = b.child_budget(fraction=0.5)
        assert child.max_input_tokens == 50_000
        assert abs(child.max_cost_usd - 5.0) < 0.001
        assert child.max_tool_calls == 50

    def test_child_budget_respects_remaining(self):
        b = WorkerBudget(max_input_tokens=100_000)
        b.used_input_tokens = 80_000  # 20k remaining
        child = b.child_budget(fraction=0.5)
        assert child.max_input_tokens == 10_000  # 50% of 20k remaining

    def test_summary_returns_dict(self):
        b = WorkerBudget()
        s = b.summary()
        assert "input_tokens" in s
        assert "cost_usd" in s


# ---------------------------------------------------------------------------
# BaseWorker tests
# ---------------------------------------------------------------------------

class TestBaseWorker:
    def _make_worker(self, **kwargs):
        return StubWorker(
            session_id="sess1",
            mission_id="miss1",
            tool_grants=frozenset({"filesystem", "terminal"}),
            **kwargs,
        )

    def test_initial_state_is_created(self):
        w = self._make_worker()
        assert w.state == WorkerState.CREATED

    def test_cancel_sets_event(self):
        w = self._make_worker()
        assert not w.is_cancelled()
        w.cancel()
        assert w.is_cancelled()

    def test_has_tool_with_explicit_grant(self):
        w = self._make_worker()
        assert w._has_tool("filesystem")
        assert not w._has_tool("browser")

    def test_has_tool_with_wildcard(self):
        w = self._make_worker(tool_grants=frozenset({"*"}))
        assert w._has_tool("anything")

    def test_depth_inherited(self):
        w = self._make_worker(depth=3)
        assert w.depth == 3

    @pytest.mark.asyncio
    async def test_run_completes(self):
        w = self._make_worker()
        ctx = WorkerContext(task="do something")
        result = await w.run(ctx)
        assert result.success
        assert w.state == WorkerState.COMPLETED

    @pytest.mark.asyncio
    async def test_cancelled_worker_returns_cancelled_result(self):
        class SlowWorker(BaseWorker):
            @property
            def worker_type(self): return "SlowWorker"
            async def run(self, context):
                self._set_state(WorkerState.RUNNING)
                self.cancel()  # immediately cancel self
                if self._check_cancelled():
                    return WorkerResult.failed("Cancelled", "cancelled", state=WorkerState.CANCELLED)
                return WorkerResult.completed("done")

        w = SlowWorker(session_id="s", mission_id="m", tool_grants=frozenset())
        result = await w.run(WorkerContext(task="slow task"))
        assert not result.success
        assert result.state == WorkerState.CANCELLED


# ---------------------------------------------------------------------------
# ToolFabric tests
# ---------------------------------------------------------------------------

class TestToolFabric:
    def setup_method(self):
        self.fabric = ToolFabric()
        self.echo = EchoTool()
        self.fail = FailingTool()

    def test_register_tool(self):
        self.fabric.register(self.echo)
        tools = self.fabric.list_tools()
        names = [t["name"] for t in tools]
        assert "test.echo" in names

    def test_register_non_tool_raises(self):
        with pytest.raises(TypeError):
            self.fabric.register("not a tool")  # type: ignore

    def test_get_registered_tool(self):
        self.fabric.register(self.echo)
        t = self.fabric.get_tool("test.echo")
        assert t is self.echo

    def test_get_unregistered_raises(self):
        with pytest.raises(ToolNotFoundError):
            self.fabric.get_tool("does.not.exist")

    def test_unregister_tool(self):
        self.fabric.register(self.echo)
        self.fabric.unregister("test.echo")
        with pytest.raises(ToolNotFoundError):
            self.fabric.get_tool("test.echo")

    @pytest.mark.asyncio
    async def test_invoke_not_registered_raises(self):
        with pytest.raises(ToolNotFoundError):
            await self.fabric.invoke(
                tool_name="does.not.exist",
                parameters={},
                worker_id="w1",
                mission_id="m1",
                tool_grants=frozenset({"*"}),
            )

    @pytest.mark.asyncio
    async def test_invoke_without_grant_raises(self):
        self.fabric.register(self.echo)
        with pytest.raises(ToolNotGrantedError):
            await self.fabric.invoke(
                tool_name="test.echo",
                parameters={},
                worker_id="w1",
                mission_id="m1",
                tool_grants=frozenset(),  # no grants
            )

    @pytest.mark.asyncio
    async def test_invoke_with_explicit_grant(self):
        self.fabric.register(self.echo)
        result = await self.fabric.invoke(
            tool_name="test.echo",
            parameters={"x": 1},
            worker_id="w1",
            mission_id="m1",
            tool_grants=frozenset({"test.echo"}),
        )
        assert result.success
        assert result.output["echo"]["x"] == 1

    @pytest.mark.asyncio
    async def test_invoke_with_wildcard_grant(self):
        self.fabric.register(self.echo)
        result = await self.fabric.invoke(
            tool_name="test.echo",
            parameters={},
            worker_id="w1",
            mission_id="m1",
            tool_grants=frozenset({"*"}),
        )
        assert result.success

    @pytest.mark.asyncio
    async def test_span_emitted_on_success(self):
        spans = []
        fabric = ToolFabric(span_handler=spans.append)
        fabric.register(self.echo)
        await fabric.invoke(
            tool_name="test.echo",
            parameters={},
            worker_id="w1",
            mission_id="m1",
            tool_grants=frozenset({"*"}),
        )
        assert len(spans) == 1
        assert spans[0].status == SpanStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_span_emitted_on_failure(self):
        spans = []
        fabric = ToolFabric(span_handler=spans.append)
        fabric.register(self.fail)
        result = await fabric.invoke(
            tool_name="test.fail",
            parameters={},
            worker_id="w1",
            mission_id="m1",
            tool_grants=frozenset({"*"}),
        )
        assert not result.success
        assert len(spans) == 1
        assert spans[0].status == SpanStatus.FAILED

    @pytest.mark.asyncio
    async def test_get_spans_filtered_by_mission(self):
        fabric = ToolFabric()
        fabric.register(self.echo)
        await fabric.invoke(tool_name="test.echo", parameters={},
                             worker_id="w1", mission_id="m1", tool_grants=frozenset({"*"}))
        await fabric.invoke(tool_name="test.echo", parameters={},
                             worker_id="w2", mission_id="m2", tool_grants=frozenset({"*"}))
        m1_spans = fabric.get_spans(mission_id="m1")
        assert len(m1_spans) == 1

    @pytest.mark.asyncio
    async def test_dry_run_propagated(self):
        self.fabric.register(self.echo)
        result = await self.fabric.invoke(
            tool_name="test.echo",
            parameters={"x": 1},
            worker_id="w1",
            mission_id="m1",
            tool_grants=frozenset({"*"}),
            dry_run=True,
        )
        assert result.success
        assert result.dry_run is True


# ---------------------------------------------------------------------------
# SpanBuilder tests
# ---------------------------------------------------------------------------

class TestSpanBuilder:
    def _builder(self, name="test"):
        return SpanBuilder(
            kind=SpanKind.TOOL,
            name=name,
            worker_id="w1",
            mission_id="m1",
        )

    def test_success_span(self):
        b = self._builder()
        b.success(audit_ref="audit-123", risk_level="LOW")
        span = b.build()
        assert span.status == SpanStatus.SUCCESS
        assert span.audit_ref == "audit-123"
        assert span.risk_level == "LOW"
        assert span.latency_ms is not None
        assert span.latency_ms >= 0

    def test_failed_span(self):
        b = self._builder()
        b.failed(ValueError("bad input"))
        span = b.build()
        assert span.status == SpanStatus.FAILED
        assert span.error_type == "ValueError"
        assert "bad input" in span.error_summary

    def test_denied_span(self):
        b = self._builder()
        b.denied("path escape")
        span = b.build()
        assert span.status == SpanStatus.DENIED

    def test_cancelled_span(self):
        b = self._builder()
        b.cancelled()
        span = b.build()
        assert span.status == SpanStatus.CANCELLED

    def test_span_has_unique_id(self):
        b1 = self._builder()
        b2 = self._builder()
        assert b1.build().span_id != b2.build().span_id

    def test_span_as_dict(self):
        b = self._builder("myop")
        b.success()
        d = b.build().as_dict()
        assert d["name"] == "myop"
        assert d["kind"] == "tool"
        assert "latency_ms" in d

    def test_metadata_added(self):
        b = self._builder()
        b.add_metadata(file_count=42, workspace="/ws")
        span = b.build()
        assert span.metadata["file_count"] == 42
