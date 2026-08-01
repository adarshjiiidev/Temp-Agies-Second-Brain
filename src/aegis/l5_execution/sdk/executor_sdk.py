"""L5 Execution Engine — Executor SDK.

Provides the public surface for adding custom executors without modifying core.

Usage::

    from aegis.l5_execution.sdk.executor_sdk import ExecutorSDK, BaseExecutor, ExecutorManifest

    class MyExecutor:
        manifest = ExecutorManifest(
            name="my_executor",
            handles=[ActionKind.FS_READ],
            supports_rollback=False,
        )

        async def execute(self, action, sandbox):
            return ActionResult(
                action_id=action.action_id,
                status=ExecutionStatus.SUCCESS,
                output={"result": "hello"},
                executor_name="my_executor",
            )

        async def rollback(self, action, result):
            return {"supported": False}

        async def health(self):
            return ExecutorHealth(name="my_executor", healthy=True)

    sdk = ExecutorSDK(pipeline)
    sdk.register_executor(MyExecutor())
"""

from __future__ import annotations

from aegis.l5_execution.contracts import ExecutorManifest
from aegis.l5_execution.executors.base import BaseExecutor, ExecutorHealth, StubExecutor
from aegis.l5_execution.pipeline import ExecutionPipeline
from aegis.l5_execution.types import (
    Action,
    ActionKind,
    ActionResult,
    ExecutionStatus,
)

__all__ = [
    "ExecutorSDK",
    "BaseExecutor",
    "ExecutorHealth",
    "ExecutorManifest",
    "StubExecutor",
]


class ExecutorSDK:
    """SDK helper for registering custom executors into an ExecutionPipeline.

    Custom executors plugged in through the SDK go through the full 7-stage
    pipeline — the SDK does not bypass any security checks.
    """

    def __init__(self, pipeline: ExecutionPipeline) -> None:
        self._pipeline = pipeline

    def register_executor(self, executor: BaseExecutor) -> None:
        """Register a custom executor into the pipeline's registry.

        The executor must implement the BaseExecutor Protocol:
          - manifest: ExecutorManifest
          - execute(action, sandbox) -> ActionResult
          - rollback(action, result) -> dict
          - health() -> ExecutorHealth
        """
        if not isinstance(executor, BaseExecutor):
            raise TypeError(
                f"Executor {executor!r} does not implement the BaseExecutor Protocol. "
                "Check that it has manifest, execute(), rollback(), and health() methods."
            )
        self._pipeline.registry.register(executor)

    def list_executors(self) -> list[ExecutorManifest]:
        """List all currently registered executors."""
        return self._pipeline.registry.list_executors()

    def has_executor_for(self, kind: ActionKind) -> bool:
        """Return True if an executor handles the given ActionKind."""
        return self._pipeline.registry.has_executor(kind)

    async def health_check(self) -> dict[str, ExecutorHealth]:
        """Run health checks on all registered executors."""
        return await self._pipeline.registry.health_check()
