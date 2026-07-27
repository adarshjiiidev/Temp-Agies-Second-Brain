"""Prompt 02 tests: Watchdog / Recovery primitives (Supervisor, exponential backoff, max attempts)."""

from __future__ import annotations

import asyncio

import pytest

from aegis import CoreRuntime, ServiceInfo, Supervisor
from aegis.l1_core.interfaces.base import ServiceState
from aegis.l1_core.supervisor import RestartPolicy, RestartPolicyKind


class _FlakyService:
    """Service that starts successfully once; restart_fn will re-initialize and re-start."""

    def __init__(self) -> None:
        self.start_count = 0
        self.init_count = 0
        self.stop_count = 0
        self.start_fail_next = False

    async def initialize(self, context=None) -> None:
        self.init_count += 1

    async def start(self) -> None:
        self.start_count += 1
        if self.start_fail_next:
            self.start_fail_next = False
            raise RuntimeError("flaky start")

    async def stop(self, timeout=None) -> None:
        self.stop_count += 1

    def health(self):
        return {"start_count": self.start_count}


@pytest.mark.anyio
async def test_supervisor_recovers_failed_service():
    rt = CoreRuntime()
    svc = _FlakyService()
    sid = rt.register_service(
        svc, depends_on=[], info=ServiceInfo(service_id="flaky", name="flaky", version="0.1.0")
    )
    await rt.start()
    policy = RestartPolicy(
        kind=RestartPolicyKind.ON_FAILURE,
        max_attempts=3,
        base_backoff_seconds=0.001,
        max_backoff_seconds=1.0,
        multiplier=2.0,
        jitter=0.0,
    )
    sup = Supervisor(watchdog_interval=0.005)
    recovery_started = asyncio.Event()
    recoveries: list[int] = []

    async def restart_fn(service_id: str):
        assert service_id == sid
        # Re-initialize and start the flaky service, marking runtime slot as RUNNING.
        await svc.initialize({})
        await svc.start()
        slot = rt.slots.get(service_id)
        if slot is not None:
            slot.state = ServiceState.RUNNING
        recoveries.append(1)
        if len(recoveries) >= 1:
            recovery_started.set()

    # Force the service state into FAILED to trigger recovery
    rt.slots[sid].state = ServiceState.FAILED

    sup.register(
        svc,
        service_id=sid,
        policy=policy,
        get_state_fn=lambda sid=sid: rt.slots[sid].state,
        restart_fn=restart_fn,
    )
    sup_task = asyncio.create_task(sup.start())
    try:
        await asyncio.wait_for(recovery_started.wait(), timeout=2.0)
    finally:
        await sup.stop()
        await rt.stop()
    # After recovery start_count = initial + 1
    assert svc.start_count >= 2
    assert svc.init_count >= 2
