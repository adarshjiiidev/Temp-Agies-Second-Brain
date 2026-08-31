"""AgentMoe — WorkerRuntime.

Manages the lifecycle of all AgentMoe workers within a session.

Responsibilities:
  - Spawn workers with validated privilege inheritance
  - Track all active workers
  - Enforce concurrency limits and depth limits
  - Propagate cancellation
  - Guarantee shutdown (no leaked background tasks)
  - Emit observability events

Security invariants (non-negotiable):
  1. Child tool_grants ⊆ Parent tool_grants (strict subset enforced)
  2. Child autonomy_level ≤ Parent autonomy_level
  3. Child depth = Parent depth + 1 (enforced)
  4. Max depth from config is enforced before spawning
  5. Max concurrent workers from config is enforced
  6. Shutdown waits for all workers with grace period then cancels

Import safety: stdlib + asyncio + agentmoe.core.worker + agentmoe.config.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, FrozenSet, Optional, Type

from aegis.agentmoe.core.worker import (
    BaseWorker,
    WorkerBudget,
    WorkerContext,
    WorkerResult,
    WorkerState,
)
from aegis.agentmoe.config.settings import AgentMoeConfig

logger = logging.getLogger(__name__)

__all__ = [
    "WorkerSpawnError",
    "WorkerRuntime",
]


class WorkerSpawnError(Exception):
    """Raised when a worker cannot be spawned due to policy/limit violation."""


class WorkerRuntime:
    """Manages worker lifecycle within an AgentMoe session.

    Usage::

        runtime = WorkerRuntime(config=AgentMoeConfig(), session_id=session.id)
        result = await runtime.spawn_and_run(
            worker_class=CodingWorker,
            context=WorkerContext(task="Fix failing tests"),
            tool_grants=frozenset({"filesystem", "terminal", "git"}),
            parent_worker=None,  # top-level
        )
        await runtime.shutdown()
    """

    def __init__(
        self,
        *,
        config: Optional[AgentMoeConfig] = None,
        session_id: Optional[str] = None,
        mission_id: Optional[str] = None,
    ) -> None:
        self._config     = config or AgentMoeConfig()
        self._session_id = session_id or str(uuid.uuid4())
        self._mission_id = mission_id or str(uuid.uuid4())
        self._workers:   dict[str, BaseWorker]    = {}
        self._tasks:     dict[str, asyncio.Task]  = {}
        self._lock       = asyncio.Lock()
        self._shutdown   = False
        self._started_at = time.monotonic()

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def mission_id(self) -> str:
        return self._mission_id

    # -- spawn ----------------------------------------------------------------

    async def spawn_and_run(
        self,
        worker_class: Type[BaseWorker],
        context: WorkerContext,
        *,
        tool_grants: FrozenSet[str] = frozenset(),
        budget: Optional[WorkerBudget] = None,
        parent_worker: Optional[BaseWorker] = None,
        autonomy_level: Optional[int] = None,
        worker_kwargs: Optional[dict[str, Any]] = None,
    ) -> WorkerResult:
        """Spawn a worker, run it, and return its result.

        Args:
            worker_class:   The BaseWorker subclass to instantiate.
            context:        The task context for the worker.
            tool_grants:    Tool names this worker may use.
            budget:         Budget for this worker (defaults to session budget).
            parent_worker:  Parent worker if this is a delegation (None = top-level).
            autonomy_level: Override autonomy level (cannot exceed parent's).
            worker_kwargs:  Additional kwargs passed to worker_class.__init__.

        Returns:
            WorkerResult.

        Raises:
            WorkerSpawnError: If limits or privilege constraints prevent spawning.
        """
        if self._shutdown:
            raise WorkerSpawnError("WorkerRuntime is shut down; cannot spawn new workers")

        # 1. Depth check
        parent_depth = parent_worker.depth if parent_worker else -1
        new_depth    = parent_depth + 1
        if new_depth > self._config.workers.max_depth:
            raise WorkerSpawnError(
                f"Maximum worker depth ({self._config.workers.max_depth}) exceeded. "
                f"Worker at depth {parent_depth} tried to spawn a child at depth {new_depth}."
            )

        # 2. Concurrency check
        async with self._lock:
            active = sum(1 for w in self._workers.values() if w.state == WorkerState.RUNNING)
            if active >= self._config.workers.max_concurrent_workers:
                raise WorkerSpawnError(
                    f"Maximum concurrent workers ({self._config.workers.max_concurrent_workers}) reached. "
                    "Wait for a worker to complete before spawning more."
                )

        # 3. Privilege inheritance check (SECURITY INVARIANT)
        if parent_worker is not None:
            self._check_privilege_inheritance(
                parent_grants=parent_worker.tool_grants,
                child_grants=tool_grants,
                parent_autonomy=parent_worker.autonomy_level,
                child_autonomy=autonomy_level or parent_worker.autonomy_level,
            )

        # 4. Resolve autonomy level
        resolved_autonomy = autonomy_level if autonomy_level is not None else self._config.autonomy_level
        if parent_worker is not None:
            resolved_autonomy = min(resolved_autonomy, parent_worker.autonomy_level)

        # 5. Resolve budget
        if budget is None:
            budget = WorkerBudget(
                max_wall_seconds=self._config.workers.default_worker_timeout_seconds,
            )
        if parent_worker is not None:
            budget = parent_worker.budget.child_budget(fraction=0.5)

        # 6. Instantiate worker
        kwargs: dict[str, Any] = {
            "session_id":    self._session_id,
            "mission_id":    self._mission_id,
            "parent_id":     parent_worker.worker_id if parent_worker else None,
            "tool_grants":   tool_grants,
            "budget":        budget,
            "autonomy_level":resolved_autonomy,
            "depth":         new_depth,
        }
        if worker_kwargs:
            kwargs.update(worker_kwargs)

        worker = worker_class(**kwargs)

        # 7. Register and run
        async with self._lock:
            self._workers[worker.worker_id] = worker

        logger.info(
            "WorkerRuntime: spawning %s id=%s depth=%d grants=%s",
            worker.worker_type, worker.worker_id[:8], new_depth, sorted(tool_grants),
        )

        try:
            task = asyncio.create_task(
                self._run_with_timeout(worker, context),
                name=f"agentmoe-{worker.worker_type}-{worker.worker_id[:8]}",
            )
            async with self._lock:
                self._tasks[worker.worker_id] = task
            return await task
        finally:
            async with self._lock:
                self._tasks.pop(worker.worker_id, None)

    # -- shutdown -------------------------------------------------------------

    async def shutdown(self, grace_seconds: Optional[float] = None) -> None:
        """Cancel all workers and wait for them to stop.

        After shutdown, no new workers may be spawned.
        """
        self._shutdown = True
        grace = grace_seconds or self._config.workers.shutdown_grace_seconds
        logger.info("WorkerRuntime: shutting down (grace=%.1fs)", grace)

        # Signal all workers to cancel
        for worker in list(self._workers.values()):
            if worker.state == WorkerState.RUNNING:
                worker.cancel()

        if self._tasks:
            done, pending = await asyncio.wait(
                list(self._tasks.values()),
                timeout=grace,
            )
            if pending:
                logger.warning(
                    "WorkerRuntime: %d workers did not stop within grace period; cancelling",
                    len(pending),
                )
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)

        logger.info("WorkerRuntime: shutdown complete (%d workers processed)", len(self._workers))

    # -- status ---------------------------------------------------------------

    def active_count(self) -> int:
        return sum(1 for w in self._workers.values() if w.state == WorkerState.RUNNING)

    def all_workers(self) -> list[BaseWorker]:
        return list(self._workers.values())

    # -- internals ------------------------------------------------------------

    async def _run_with_timeout(
        self,
        worker: BaseWorker,
        context: WorkerContext,
    ) -> WorkerResult:
        timeout = self._config.workers.default_worker_timeout_seconds
        try:
            return await asyncio.wait_for(worker.run(context), timeout=timeout)
        except asyncio.TimeoutError:
            worker._set_state(WorkerState.TIMEOUT)
            logger.warning("WorkerRuntime: worker %s timed out after %.0fs", worker.worker_id[:8], timeout)
            return WorkerResult.failed(
                "WorkerTimeout",
                f"Worker exceeded time limit of {timeout:.0f}s",
                state=WorkerState.TIMEOUT,
                budget=worker.budget,
            )
        except asyncio.CancelledError:
            worker._set_state(WorkerState.CANCELLED)
            return WorkerResult.failed(
                "WorkerCancelled",
                "Worker was cancelled",
                state=WorkerState.CANCELLED,
            )
        except Exception as exc:
            worker._set_state(WorkerState.FAILED)
            logger.exception("WorkerRuntime: worker %s raised unexpected error", worker.worker_id[:8])
            return WorkerResult.failed(
                type(exc).__name__,
                str(exc)[:300],
                state=WorkerState.FAILED,
            )

    @staticmethod
    def _check_privilege_inheritance(
        parent_grants: FrozenSet[str],
        child_grants: FrozenSet[str],
        parent_autonomy: int,
        child_autonomy: int,
    ) -> None:
        """Enforce that child cannot exceed parent privileges. (SECURITY INVARIANT)"""
        # Tool grants: child must be subset of parent (unless parent has "*")
        if "*" not in parent_grants:
            illegal = child_grants - parent_grants
            if illegal:
                raise WorkerSpawnError(
                    f"Child worker requested tool grants not held by parent: {sorted(illegal)}. "
                    "A child worker can never exceed its parent's tool grants. "
                    "This is a security invariant."
                )
        # Autonomy: child ≤ parent
        if child_autonomy > parent_autonomy:
            raise WorkerSpawnError(
                f"Child worker requested autonomy_level={child_autonomy} "
                f"but parent only has level={parent_autonomy}. "
                "Children cannot have higher autonomy than their parents."
            )
