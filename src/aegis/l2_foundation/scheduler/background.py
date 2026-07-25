"""L2 Background Task Management (scheduler).

Prompt 02 scope: local asyncio-based task manager with:
  - Background task registration / startup
  - Cancellation (individual / all)
  - Graceful shutdown with timeout
  - Failure reporting via on_failure callbacks + EventBus (runtime.task.failed)
  - Task identification, lifecycle state tracking
  - Per-task retry via optional RetryPolicy

Not implemented: Celery, Temporal, Taskiq, Kafka, RabbitMQ, distributed queues.
"""
from __future__ import annotations

import asyncio
import enum
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from aegis.l1_core.errors import ErrorCode, ExecutionError, TimeoutError as AegisTimeoutError
from aegis.l1_core.interfaces.events import NORMAL, EventEnvelope
from aegis.l2_foundation.event_bus.core import CoreEventBus
from aegis.l2_foundation.telemetry.context import CorrelationContext
from aegis.l2_foundation.telemetry.logger import get_logger
from aegis.l2_foundation.telemetry.metrics import get_metrics_registry

log = get_logger(__name__)


class TaskState(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class RetryPolicy:
    """Used both by background tasks AND (via supervisor) service recovery."""

    max_attempts: int = 3
    base_backoff_seconds: float = 0.25
    max_backoff_seconds: float = 10.0
    multiplier: float = 2.0
    jitter: float = 0.1
    reset_after_success_seconds: float = 60.0

    def backoff_seconds(self, attempt: int) -> float:
        """Exponential backoff with full jitter, bounded."""
        attempt = max(0, int(attempt))
        base = min(self.max_backoff_seconds, self.base_backoff_seconds * (self.multiplier ** attempt))
        # full jitter in range [base*(1-jitter), base*(1+jitter)]
        jitter_span = base * self.jitter
        lo = max(0.0, base - jitter_span)
        hi = base + jitter_span
        import random  # local import to allow seed-free deterministic tests that mock random

        rng = random.random()
        return lo + (hi - lo) * rng


@dataclass
class TaskInfo:
    task_id: uuid.UUID
    name: str
    state: TaskState = TaskState.PENDING
    started_at: float | None = None
    finished_at: float | None = None
    last_error: str | None = None
    attempts: int = 0
    result: Any = None
    error: BaseException | None = field(default=None, repr=False)
    correlation: CorrelationContext | None = field(default=None, repr=False)


# Coro-returning callable
AsyncTaskFn = Callable[..., Awaitable[Any]]


class BackgroundTaskManager:
    """Thread-safe manager around asyncio.Task group.

    Usage pattern for Prompt 02:
        rt = CoreRuntime(...)
        rt.register_task_manager(btm)
        task_id = btm.submit(loop, my_coro, name="sync.heartbeat")
        await btm.graceful_shutdown(timeout=5.0)
    """

    def __init__(
        self,
        *,
        max_workers: int = 8,  # informational cap — asyncio has its own scheduling
        event_bus: CoreEventBus | None = None,
        default_retry: RetryPolicy | None = None,
    ) -> None:
        self._max_workers = max_workers
        self._eb = event_bus
        self._default_retry = default_retry
        self._tasks: dict[uuid.UUID, tuple[TaskInfo, asyncio.Task[Any]]] = {}
        self._lock = threading.RLock()
        self._on_failure: list[Callable[[TaskInfo], None]] = []
        self._on_success: list[Callable[[TaskInfo], None]] = []
        self._started = False
        self._stopped = False
        metrics = get_metrics_registry()
        self._m_submitted = metrics.counter("aegis.tasks.submitted")
        self._m_succeeded = metrics.counter("aegis.tasks.succeeded")
        self._m_failed = metrics.counter("aegis.tasks.failed")
        self._m_cancelled = metrics.counter("aegis.tasks.cancelled")

    # -------- lifecycle --------

    def start(self) -> None:
        with self._lock:
            self._started = True

    async def graceful_shutdown(self, timeout: float = 10.0) -> list[uuid.UUID]:
        """Cancel pending/running tasks. Returns list of task_ids that refused to stop in time."""
        with self._lock:
            self._stopped = True
            tasks = [(tid, info, async_task) for tid, (info, async_task) in self._tasks.items()]
        to_cancel: list[tuple[uuid.UUID, asyncio.Task[Any]]] = []
        for tid, info, atask in tasks:
            if not atask.done():
                atask.cancel()
                to_cancel.append((tid, atask))
                info.state = TaskState.CANCELLED
        leftover: list[uuid.UUID] = []
        if to_cancel:
            done, pending = await asyncio.wait(
                [asyncio.shield(atask) for _tid, atask in to_cancel],
                timeout=timeout,
                return_when=asyncio.ALL_COMPLETED,
            )
            # Map pending back to tids (positional)
            for idx, (tid, _atask) in enumerate(to_cancel):
                if idx >= len(done) and len(pending) > 0:
                    # Heuristic: any pending shielded task is timed out; wait() returns remainder
                    if idx in [p.get_name() for p in pending]:  # type: ignore[comparison-overlap]
                        leftover.append(tid)
                    else:
                        leftover.append(tid)
        return leftover

    # -------- hooks --------

    def on_failure(self, fn: Callable[[TaskInfo], None]) -> None:
        with self._lock:
            self._on_failure.append(fn)

    def on_success(self, fn: Callable[[TaskInfo], None]) -> None:
        with self._lock:
            self._on_success.append(fn)

    # -------- submission --------

    def submit(
        self,
        loop: asyncio.AbstractEventLoop,
        coro_fn: AsyncTaskFn,
        *args: Any,
        name: str | None = None,
        retry: RetryPolicy | None = None,
        correlation: CorrelationContext | None = None,
        **kwargs: Any,
    ) -> uuid.UUID:
        if not self._started:
            raise ExecutionError(
                ErrorCode.E20301,
                "BackgroundTaskManager.start() must be called before submit()",
            )
        if self._stopped:
            raise ExecutionError(ErrorCode.E20303, "BackgroundTaskManager is stopped")
        policy = retry or self._default_retry
        tid = uuid.uuid4()
        info = TaskInfo(
            task_id=tid,
            name=name or f"task-{tid.hex[:8]}",
            correlation=correlation or CorrelationContext.get_current_or_none(),
        )
        wrapped = self._wrap(info, coro_fn, args, kwargs, policy)
        with self._lock:
            atask = loop.create_task(wrapped, name=f"aegis:{info.name}:{tid.hex[:8]}")
            self._tasks[tid] = (info, atask)
        self._m_submitted.inc()
        return tid

    # -------- introspection --------

    def list(self) -> list[TaskInfo]:
        with self._lock:
            return [TaskInfo(**info.__dict__) for info, _at in self._tasks.values()]

    def get(self, task_id: uuid.UUID) -> TaskInfo:
        with self._lock:
            try:
                info, _ = self._tasks[task_id]
            except KeyError as exc:
                raise ExecutionError(
                    ErrorCode.E20302,
                    f"No task with id={task_id}",
                ) from exc
            return TaskInfo(**info.__dict__)

    def cancel(self, task_id: uuid.UUID) -> bool:
        with self._lock:
            entry = self._tasks.get(task_id)
        if entry is None:
            return False
        info, atask = entry
        if not atask.done():
            atask.cancel(msg=f"cancelled by user via task_id={task_id}")
            info.state = TaskState.CANCELLED
            self._m_cancelled.inc()
            return True
        return False

    def running_count(self) -> int:
        with self._lock:
            return sum(
                1
                for info, at in self._tasks.values()
                if info.state == TaskState.RUNNING and not at.done()
            )

    # -------- private helpers --------

    async def _wrap(
        self,
        info: TaskInfo,
        coro_fn: AsyncTaskFn,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        policy: RetryPolicy | None,
    ) -> Any:  # noqa: ANN401
        info.state = TaskState.RUNNING
        info.started_at = time.time()
        info.attempts = 0
        max_attempts = max(1, policy.max_attempts) if policy else 1
        last_error: BaseException | None = None
        correlation = info.correlation
        while info.attempts < max_attempts:
            info.attempts += 1
            ctx = correlation or CorrelationContext.get_current_or_none()
            enter = ctx.enter() if ctx else None
            try:
                if enter is not None:
                    with enter:
                        result = await coro_fn(*args, **kwargs)
                else:
                    result = await coro_fn(*args, **kwargs)
                info.state = TaskState.SUCCEEDED
                info.result = result
                info.finished_at = time.time()
                self._m_succeeded.inc()
                self._run_success_hooks(info)
                self._emit_event(info, "runtime.task.succeeded")
                return result
            except asyncio.CancelledError:
                info.state = TaskState.CANCELLED
                info.finished_at = time.time()
                self._m_cancelled.inc()
                self._emit_event(info, "runtime.task.cancelled")
                raise
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                info.last_error = f"{type(exc).__name__}: {exc}"
                info.error = exc
                log.warning(
                    "Task attempt failed",
                    task_id=str(info.task_id)[:8],
                    name=info.name,
                    attempt=info.attempts,
                    error=info.last_error,
                )
                self._m_failed.inc()
                if policy is None or info.attempts >= max_attempts:
                    break
                backoff = policy.backoff_seconds(info.attempts - 1)
                await asyncio.sleep(backoff)
        info.state = TaskState.FAILED
        info.finished_at = time.time()
        self._run_failure_hooks(info)
        self._emit_event(info, "runtime.task.failed")
        if last_error is not None:
            raise ExecutionError(
                ErrorCode.E20303,
                f"Task {info.name!r} failed after {info.attempts} attempts: {info.last_error}",
            ) from last_error
        raise ExecutionError(ErrorCode.E20303, f"Task {info.name!r} failed")

    def _run_success_hooks(self, info: TaskInfo) -> None:
        with self._lock:
            hooks = list(self._on_success)
        for hook in hooks:
            try:
                hook(info)
            except Exception as exc:  # noqa: BLE001
                log.error("task success hook raised", exc=exc)

    def _run_failure_hooks(self, info: TaskInfo) -> None:
        with self._lock:
            hooks = list(self._on_failure)
        for hook in hooks:
            try:
                hook(info)
            except Exception as exc:  # noqa: BLE001
                log.error("task failure hook raised", exc=exc)

    def _emit_event(self, info: TaskInfo, event_type: str) -> None:
        if self._eb is None:
            return
        try:
            payload = {
                "task_id": str(info.task_id),
                "name": info.name,
                "state": info.state.value,
                "attempts": info.attempts,
                "last_error": info.last_error,
            }
            self._eb.publish(
                event_type,
                payload,
                priority=NORMAL,
                source="aegis.tasks",
                metadata={"correlation_id": str(info.correlation.correlation_id) if info.correlation else None},
            )
        except Exception as exc:  # noqa: BLE001
            log.debug("emit_event failed", exc=exc)


# Retry helper without a background task manager: just run a coro with retry logic.
async def run_with_retry(
    coro_fn: AsyncTaskFn,
    *args: Any,
    policy: RetryPolicy | None = None,
    timeout_per_attempt: float | None = None,
    **kwargs: Any,
) -> Any:  # noqa: ANN401
    """Independent helper: useful for synchronous-ish callers wanting retry.
    Does not register anywhere; aegis.tasks BackgroundTaskManager provides registration/shutdown/cancellation.
    """
    pol = policy or RetryPolicy()
    attempt = 0
    last_exc: BaseException | None = None
    while True:
        try:
            if timeout_per_attempt is not None:
                return await asyncio.wait_for(coro_fn(*args, **kwargs), timeout=timeout_per_attempt)
            return await coro_fn(*args, **kwargs)
        except asyncio.CancelledError:
            raise
        except AegisTimeoutError as e:  # our own TimeoutError, distinct from asyncio
            last_exc = e
            if attempt + 1 >= pol.max_attempts:
                raise
        except asyncio.TimeoutError as e:
            last_exc = e
            if attempt + 1 >= pol.max_attempts:
                raise AegisTimeoutError(
                    ErrorCode.E10103,
                    f"Operation timed out after {attempt + 1} attempts",
                ) from e
        except Exception as e:  # noqa: BLE001
            last_exc = e
            if attempt + 1 >= pol.max_attempts:
                raise ExecutionError(
                    ErrorCode.E20303,
                    f"Operation failed after {attempt + 1} attempts: {type(e).__name__}: {e}",
                ) from e
        attempt += 1
        await asyncio.sleep(pol.backoff_seconds(attempt))
