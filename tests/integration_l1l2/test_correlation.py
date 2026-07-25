"""Prompt 02 tests: Correlation context propagation (sync + async-safe)."""
from __future__ import annotations

import asyncio
import uuid

import pytest

import aegis
from aegis import CorrelationContext, new_correlation


def test_fork_inherits_correlation_id_by_default():
    parent = CorrelationContext.new()
    child = parent.fork(new_task_id=True)
    assert child.correlation_id == parent.correlation_id
    assert child.task_id != parent.task_id
    assert child.parent_op_id == parent.task_id  # task_id inherited becomes parent_op_id for child


def test_enter_restores_previous():
    a = CorrelationContext.new()
    b = CorrelationContext.new()
    with a.enter():
        assert CorrelationContext.current().correlation_id == a.correlation_id
        with b.enter():
            assert CorrelationContext.current().correlation_id == b.correlation_id
        assert CorrelationContext.current().correlation_id == a.correlation_id


def test_new_correlation_no_inherit_creates_fresh():
    with new_correlation() as outer:
        outer_cid = outer.correlation_id
        with new_correlation(inherit=True) as inner_inherit:
            assert inner_inherit.correlation_id == outer_cid
        with new_correlation(inherit=False) as inner_fresh:
            assert inner_fresh.correlation_id != outer_cid


@pytest.mark.anyio
async def test_propagation_through_asyncio_gather():
    results: list[uuid.UUID] = []

    async def worker(idx: int) -> None:
        results.append(CorrelationContext.current().correlation_id)

    ctx = CorrelationContext.new()
    with ctx.enter():
        await asyncio.gather(worker(1), worker(2), worker(3))
    # every task inherited the correlation context
    assert results == [ctx.correlation_id] * 3


def test_as_dict_roundtrip():
    c = CorrelationContext.new(
        request_id=uuid.uuid4(), task_id=uuid.uuid4(), metadata={"x": 1}
    )
    d = c.as_dict(stringify=True)
    assert d["correlation_id"] == str(c.correlation_id)
    assert d["request_id"] == str(c.request_id)
    assert d["meta"] == {"x": 1}
