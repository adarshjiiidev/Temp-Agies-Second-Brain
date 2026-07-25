"""Prompt 02 tests: Background task manager (startup/cancellation/graceful shutdown/retry)."""
from __future__ import annotations

import asyncio
import uuid

import pytest

import aegis
from aegis import BackgroundTaskManager, RetryPolicy, TaskState, get_logger

log = get_logger(__name__)


@pytest.mark.anyio
async def test_background_task_runs_and_reports_succeeded():
    btm = BackgroundTaskManager()
    btm.start()
    loop = asyncio.get_running_loop()
    called: list[int] = []

    async def work() -> int:
        await asyncio.sleep(0.001)
        called.append(1)
        return 42

    tid = btm.submit(loop, work, name="w1")
    # Give it a moment
    await asyncio.sleep(0.05)
    info = btm.get(tid)
    assert info.state == TaskState.SUCCEEDED
    assert info.result == 42
    assert called == [1]
    await btm.graceful_shutdown(timeout=1.0)


@pytest.mark.anyio
async def test_cancel_stops_running_task():
    btm = BackgroundTaskManager()
    btm.start()
    loop = asyncio.get_running_loop()
    started = asyncio.Event()

    async def long_task() -> None:
        started.set()
        await asyncio.sleep(10)

    tid = btm.submit(loop, long_task, name="long")
    await started.wait()
    assert btm.cancel(tid) is True
    await asyncio.sleep(0.05)
    assert btm.get(tid).state == TaskState.CANCELLED
    await btm.graceful_shutdown(timeout=0.5)


@pytest.mark.anyio
async def test_failed_task_invokes_on_failure_hook():
    btm = BackgroundTaskManager()
    btm.start()
    loop = asyncio.get_running_loop()
    errors: list[str] = []
    btm.on_failure(lambda info: errors.append(str(info.last_error or "")))

    async def boom() -> None:
        raise RuntimeError("oops")

    tid = btm.submit(loop, boom, retry=RetryPolicy(max_attempts=1))
    await asyncio.sleep(0.05)
    assert btm.get(tid).state == TaskState.FAILED
    assert "oops" in errors[0]
    await btm.graceful_shutdown(timeout=0.5)


@pytest.mark.anyio
async def test_retry_policy_backoff_grows():
    policy = RetryPolicy(
        max_attempts=3,
        base_backoff_seconds=0.1,
        max_backoff_seconds=10.0,
        multiplier=2.0,
        jitter=0.0,
    )
    # With jitter = 0, backoff should be exactly 0.1, 0.2, 0.4
    b0 = policy.backoff_seconds(0)
    b1 = policy.backoff_seconds(1)
    b2 = policy.backoff_seconds(2)
    assert b0 == pytest.approx(0.1)
    assert b1 == pytest.approx(0.2)
    assert b2 == pytest.approx(0.4)


@pytest.mark.anyio
async def test_run_with_retry_succeeds_after_retries(monkeypatch):
    policy = RetryPolicy(max_attempts=3, base_backoff_seconds=0.001, jitter=0.0)
    tries: list[int] = []

    async def fn():
        tries.append(1)
        if len(tries) < 3:
            raise RuntimeError("retry me")
        return "done"

    res = await aegis.run_with_retry(fn, policy=policy)
    assert res == "done"
    assert len(tries) == 3
