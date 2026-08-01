"""L5 Execution Engine — Execution Queue.

Priority async queue for action execution jobs.
Supports: priority ordering, serial/parallel execution, dependency chains,
pause/resume/cancel, timeout enforcement, dead-letter queue, retry with jitter.

Import safety: stdlib (asyncio, heapq) + l5_execution.types ONLY.
"""

from __future__ import annotations

import asyncio
import heapq
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine

from aegis.l5_execution.types import Action, ActionResult

__all__ = ["ExecutionQueue", "JobState", "QueuedJob"]


class JobState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DEAD_LETTER = "dead_letter"


@dataclass(order=True)
class QueuedJob:
    """A job waiting in the execution queue."""

    priority: int                                  # lower = higher priority
    enqueued_at: float = field(compare=True)
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()), compare=False)
    action: Action = field(compare=False, default=None)  # type: ignore[assignment]
    max_retries: int = field(default=3, compare=False)
    retry_count: int = field(default=0, compare=False)
    depends_on: list[str] = field(default_factory=list, compare=False)
    state: JobState = field(default=JobState.PENDING, compare=False)
    result: ActionResult | None = field(default=None, compare=False)
    error: str | None = field(default=None, compare=False)
    deadline: float | None = field(default=None, compare=False)  # Unix ts
    metadata: dict[str, Any] = field(default_factory=dict, compare=False)


class ExecutionQueue:
    """Async priority execution queue.

    Usage::

        queue = ExecutionQueue(max_parallel=3)
        queue.start(pipeline_fn)  # pipeline_fn: async (Action) -> ActionResult

        job = await queue.enqueue(action, priority=0)
        result = await queue.wait_for(job.job_id, timeout=30)

        await queue.stop()
    """

    def __init__(self, max_parallel: int = 1) -> None:
        self._max_parallel = max_parallel
        self._heap: list[QueuedJob] = []
        self._jobs: dict[str, QueuedJob] = {}
        self._dead_letter: list[QueuedJob] = []
        self._paused = False
        self._running = False
        self._semaphore: asyncio.Semaphore | None = None
        self._worker_task: asyncio.Task | None = None
        self._pipeline_fn: Callable[[Action], Coroutine[Any, Any, ActionResult]] | None = None
        self._lock = asyncio.Lock()
        self._completions: dict[str, asyncio.Event] = {}

    def start(
        self,
        pipeline_fn: Callable[[Action], Coroutine[Any, Any, ActionResult]],
    ) -> None:
        """Start the queue worker."""
        self._pipeline_fn = pipeline_fn
        self._semaphore = asyncio.Semaphore(self._max_parallel)
        self._running = True
        self._worker_task = asyncio.ensure_future(self._worker_loop())

    async def stop(self) -> None:
        """Drain the queue and stop the worker."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    async def enqueue(
        self,
        action: Action,
        *,
        priority: int = 50,
        max_retries: int = 3,
        depends_on: list[str] | None = None,
        deadline_seconds: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> QueuedJob:
        """Enqueue an action for execution.

        Args:
            action:           The Action to execute.
            priority:         0 = highest, 100 = lowest.
            max_retries:      Maximum retry attempts on failure.
            depends_on:       List of job_ids that must complete before this one runs.
            deadline_seconds: Max seconds before job is dead-lettered.
            metadata:         Extra data attached to the job.

        Returns:
            QueuedJob with job_id.
        """
        job = QueuedJob(
            priority=priority,
            enqueued_at=time.time(),
            action=action,
            max_retries=max_retries,
            depends_on=depends_on or [],
            deadline=time.time() + deadline_seconds if deadline_seconds else None,
            metadata=metadata or {},
        )
        completion = asyncio.Event()
        async with self._lock:
            self._jobs[job.job_id] = job
            self._completions[job.job_id] = completion
            heapq.heappush(self._heap, job)
        return job

    async def cancel(self, job_id: str) -> bool:
        """Cancel a PENDING job.  Running jobs cannot be cancelled via queue."""
        async with self._lock:
            job = self._jobs.get(job_id)
            if job and job.state == JobState.PENDING:
                job.state = JobState.CANCELLED
                if job_id in self._completions:
                    self._completions[job_id].set()
                return True
        return False

    async def wait_for(self, job_id: str, *, timeout: float | None = None) -> QueuedJob | None:
        """Wait for a job to complete and return it."""
        event = self._completions.get(job_id)
        if event is None:
            return None
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            pass
        return self._jobs.get(job_id)

    def pause(self) -> None:
        """Pause queue processing (in-flight jobs finish)."""
        self._paused = True

    def resume(self) -> None:
        """Resume queue processing."""
        self._paused = False

    def dead_letter_jobs(self) -> list[QueuedJob]:
        return list(self._dead_letter)

    def stats(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for j in self._jobs.values():
            counts[j.state.value] = counts.get(j.state.value, 0) + 1
        counts["dead_letter"] = len(self._dead_letter)
        return counts

    # ------------------------------------------------------------------
    # Internal worker loop
    # ------------------------------------------------------------------

    async def _worker_loop(self) -> None:
        assert self._semaphore is not None
        while self._running:
            if self._paused:
                await asyncio.sleep(0.05)
                continue

            job = await self._next_ready_job()
            if job is None:
                await asyncio.sleep(0.01)
                continue

            # Check deadline
            if job.deadline and time.time() > job.deadline:
                job.state = JobState.DEAD_LETTER
                self._dead_letter.append(job)
                self._completions[job.job_id].set()
                continue

            asyncio.ensure_future(self._run_job(job))

    async def _next_ready_job(self) -> QueuedJob | None:
        async with self._lock:
            if not self._heap:
                return None
            # Peek at the top-priority job
            job = self._heap[0]
            if job.state != JobState.PENDING:
                heapq.heappop(self._heap)
                return None
            # Check dependencies
            if job.depends_on:
                all_done = all(
                    self._jobs.get(dep_id, QueuedJob(99, 0.0)).state == JobState.DONE
                    for dep_id in job.depends_on
                )
                if not all_done:
                    return None
            heapq.heappop(self._heap)
            job.state = JobState.RUNNING
            return job
        return None

    async def _run_job(self, job: QueuedJob) -> None:
        assert self._semaphore is not None
        assert self._pipeline_fn is not None

        async with self._semaphore:
            try:
                result = await self._pipeline_fn(job.action)
                job.result = result
                if result.succeeded:
                    job.state = JobState.DONE
                else:
                    await self._handle_failure(job, result.error or "unknown error")
            except Exception as exc:
                await self._handle_failure(job, str(exc))
            finally:
                if event := self._completions.get(job.job_id):
                    event.set()

    async def _handle_failure(self, job: QueuedJob, error: str) -> None:
        job.error = error
        if job.retry_count < job.max_retries:
            job.retry_count += 1
            job.state = JobState.PENDING
            # Jitter retry delay
            delay = 0.1 * (2 ** job.retry_count)
            await asyncio.sleep(delay)
            async with self._lock:
                heapq.heappush(self._heap, job)
        else:
            job.state = JobState.FAILED
            self._dead_letter.append(job)
