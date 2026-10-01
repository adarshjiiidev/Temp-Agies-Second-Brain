"""Prompt 02 tests: Health monitoring."""

from __future__ import annotations

import asyncio

import pytest

from aegis import (
    ComponentHealth,
    HealthAggregator,
    HealthReport,
    HealthState,
)


def test_four_states_exist():
    # Exactly four states per Prompt 01
    states = {s.value for s in HealthState}
    assert states == {"healthy", "degraded", "unhealthy", "unknown"}


@pytest.mark.anyio
async def test_aggregator_collects_component_healths():
    agg = HealthAggregator()

    async def ok_check() -> ComponentHealth:
        return ComponentHealth(
            component="green", state=HealthState.HEALTHY, latency_ms=1.0, details={"x": 1}
        )

    async def bad_check() -> ComponentHealth:
        raise RuntimeError("disconnected")

    agg.register_check("green", ok_check, timeout_seconds=1.0)
    agg.register_check("bad", bad_check, timeout_seconds=1.0)
    report = await agg.check_all(aggregate_timeout=2.0)
    assert isinstance(report, HealthReport)
    assert report.overall in (HealthState.UNHEALTHY, HealthState.DEGRADED)
    component_names = {c.component for c in report.components}
    assert component_names == {"green", "bad"}


@pytest.mark.anyio
async def test_timeout_turns_into_unhealthy_or_degraded():
    agg = HealthAggregator()

    async def slow() -> ComponentHealth:
        await asyncio.sleep(10.0)
        return ComponentHealth(component="s", state=HealthState.HEALTHY, latency_ms=0.0)

    agg.register_check("slow", slow, timeout_seconds=0.001)
    report = await agg.check_all(aggregate_timeout=2.0)
    comps = {c.component: c for c in report.components}
    assert comps["slow"].state in (HealthState.DEGRADED, HealthState.UNHEALTHY)
    assert comps["slow"].error is not None
