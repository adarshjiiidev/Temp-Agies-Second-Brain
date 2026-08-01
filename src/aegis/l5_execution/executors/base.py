"""L5 Execution Engine — BaseExecutor Protocol + Health.

All executors must implement the BaseExecutor Protocol.
The Executor Registry uses ExecutorManifest to route actions.

Import safety: stdlib + l5_execution.types/contracts/exceptions ONLY.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from aegis.l5_execution.contracts import ExecutorManifest, SandboxContext
from aegis.l5_execution.types import Action, ActionResult

__all__ = ["BaseExecutor", "ExecutorHealth", "StubExecutor"]


@dataclass
class ExecutorHealth:
    """Health report returned by BaseExecutor.health()."""

    name: str
    healthy: bool
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class BaseExecutor(Protocol):
    """Protocol that every executor plugin must implement.

    Usage::

        class MyExecutor:
            manifest = ExecutorManifest(
                name="my_executor",
                handles=[ActionKind.FS_READ],
                supports_rollback=False,
            )

            async def execute(self, action: Action, sandbox: SandboxContext) -> ActionResult:
                ...

            async def rollback(self, action: Action, result: ActionResult) -> dict:
                return {}

            async def health(self) -> ExecutorHealth:
                return ExecutorHealth(name="my_executor", healthy=True)
    """

    manifest: ExecutorManifest

    async def execute(
        self,
        action: Action,
        sandbox: SandboxContext,
    ) -> ActionResult:
        """Execute the action within the provided sandbox context.

        Args:
            action:  The typed Action to execute.
            sandbox: Sandbox configuration assigned by SandboxManager.

        Returns:
            ActionResult with status, output, and error fields populated.
        """
        ...

    async def rollback(
        self,
        action: Action,
        result: ActionResult,
    ) -> dict[str, Any]:
        """Attempt to undo the effects of a completed execution.

        Should return a dict describing what was rolled back.
        Must be a no-op and return {'supported': False} if the executor
        does not support rollback.
        """
        ...

    async def health(self) -> ExecutorHealth:
        """Return a health report for this executor."""
        ...


class StubExecutor:
    """A stub executor for unimplemented actions (browser, desktop, vscode).

    Always returns a clear error explaining that the feature is not yet
    available in this milestone.
    """

    def __init__(self, name: str, handles: list, milestone: str) -> None:
        from aegis.l5_execution.types import ActionKind
        self.manifest = ExecutorManifest(
            name=name,
            handles=handles,
            is_stub=True,
            supports_rollback=False,
            description=(
                f"Stub executor for {name}. "
                f"Full implementation available in {milestone}."
            ),
        )
        self._milestone = milestone

    async def execute(self, action: Action, sandbox: SandboxContext) -> ActionResult:
        from aegis.l5_execution.types import ActionResult, ExecutionStatus, PermissionDecision
        return ActionResult(
            action_id=action.action_id,
            status=ExecutionStatus.FAILED,
            error=(
                f"Executor {self.manifest.name!r} is a stub — "
                f"full implementation is planned for {self._milestone}."
            ),
            error_code="E_EXE_STUB",
            executor_name=self.manifest.name,
        )

    async def rollback(self, action: Action, result: ActionResult) -> dict[str, Any]:
        return {"supported": False}

    async def health(self) -> ExecutorHealth:
        return ExecutorHealth(
            name=self.manifest.name,
            healthy=True,
            message=f"Stub executor (milestone: {self._milestone})",
        )
