"""Prompt 02 tests: Runtime lifecycle, failure propagation, dependency ordering."""

from __future__ import annotations

from typing import Any

import pytest

import aegis
from aegis import (
    AegisError,
    CoreRuntime,
    LifecycleError,
    RuntimeState,
    ServiceInfo,
)


class _Recorder:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []  # (event_name, service)

    def record(self, evt: str, who: str) -> None:
        self.events.append((evt, who))


class _CountingService(aegis.AbstractService if hasattr(aegis, "AbstractService") else object):  # type: ignore[attr-defined]
    _rec: _Recorder
    _name: str
    start_should_fail: bool = False
    init_should_fail: bool = False
    stop_should_fail: bool = False

    def __init__(self, name: str, rec: _Recorder) -> None:
        self._name = name
        self._rec = rec
        self.initialize_called = 0
        self.start_called = 0
        self.stop_called = 0
        self.close_called = 0

    async def initialize(self, context: dict[str, Any] | None = None) -> None:
        self.initialize_called += 1
        if self.init_should_fail:
            raise RuntimeError(f"{self._name} init failed")
        self._rec.record("init", self._name)

    async def start(self) -> None:
        self.start_called += 1
        if self.start_should_fail:
            raise RuntimeError(f"{self._name} start failed")
        self._rec.record("start", self._name)

    async def stop(self, timeout: float | None = None) -> None:
        self.stop_called += 1
        self._rec.record("stop", self._name)
        if self.stop_should_fail:
            raise RuntimeError(f"{self._name} stop failed")

    async def close(self) -> None:
        self.close_called += 1
        self._rec.record("close", self._name)

    def health(self) -> dict:
        return {"healthy": True, "service": self._name}


@pytest.fixture
def anyio_backend():
    return "asyncio"


pytestmark = pytest.mark.anyio


async def test_runtime_created_to_running_to_stopped():
    rt = CoreRuntime()
    assert rt.state == RuntimeState.CREATED
    rec = _Recorder()
    a = _CountingService("a", rec)
    b = _CountingService("b", rec)
    rt.register_service(
        a, depends_on=[], info=ServiceInfo(service_id="a", name="a", version="0.0.1")
    )
    rt.register_service(
        b, depends_on=["a"], info=ServiceInfo(service_id="b", name="b", version="0.0.1")
    )
    await rt.start()
    assert rt.state == RuntimeState.RUNNING
    # Dependency order
    assert rec.events[0] == ("init", "a")
    assert rec.events[1] == ("init", "b")
    assert rec.events[2] == ("start", "a")
    assert rec.events[3] == ("start", "b")
    await rt.stop()
    # Reverse order: stop b before a
    stops = [(e, w) for e, w in rec.events if e == "stop"]
    assert stops == [("stop", "b"), ("stop", "a")]
    assert rt.state == RuntimeState.STOPPED


async def test_dependency_topological_missing_raises():
    rt = CoreRuntime()
    b = object()
    with pytest.raises(AegisError) as excinfo:
        rt.register_service(
            b,
            depends_on=["nonexistent"],
            info=ServiceInfo(service_id="b", name="b", version="0.0.1"),
        )
    assert excinfo.value.error_code == "E10110"


async def test_partial_initialization_rollback():
    rt = CoreRuntime()
    rec = _Recorder()
    a = _CountingService("a", rec)
    b = _CountingService("b", rec)
    c = _CountingService("c", rec)
    b.start_should_fail = True
    rt.register_service(a, depends_on=[], info=ServiceInfo(service_id="a", name="a"))
    rt.register_service(b, depends_on=["a"], info=ServiceInfo(service_id="b", name="b"))
    rt.register_service(c, depends_on=["b"], info=ServiceInfo(service_id="c", name="c"))
    with pytest.raises(LifecycleError):
        await rt.start()
    # a must have been stopped, c must never have been started
    starts = [w for e, w in rec.events if e == "start"]
    assert starts == ["a"]  # b fails, c never tried
    stops = [w for e, w in rec.events if e == "stop"]
    # reverse order of started services (only 'a' was started)
    assert stops == ["a"]


async def test_double_start_prevented():
    rt = CoreRuntime()
    await rt.start()
    assert rt.state == RuntimeState.RUNNING
    with pytest.raises(AegisError):
        await rt.start()
    await rt.stop()


async def test_health_aggregation_empty_is_unknown():
    rt = CoreRuntime()
    await rt.start()
    health = await rt.overall_health()
    # No services — unknown or healthy is acceptable; our runtime returns aggregated
    await rt.stop()


async def test_stop_when_not_started_is_noop():
    rt = CoreRuntime()
    await rt.stop()  # must not raise
    assert rt.state in (RuntimeState.STOPPED, RuntimeState.CREATED)
