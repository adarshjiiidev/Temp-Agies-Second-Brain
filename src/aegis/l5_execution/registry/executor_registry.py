"""L5 Execution Engine — Executor Registry.

Stage 4 routing: maps ActionKind → executor plugin.

Executors are registered at startup.  The registry is immutable after
initialization (adding executors after the pipeline starts is a MEDIUM-risk
operation that requires a health check).

Import safety: stdlib + l5_execution.* ONLY.
"""

from __future__ import annotations

from typing import Any

from aegis.l5_execution.contracts import ExecutorManifest
from aegis.l5_execution.exceptions import ExecutorNotFoundError
from aegis.l5_execution.executors.base import BaseExecutor, ExecutorHealth, StubExecutor
from aegis.l5_execution.types import Action, ActionKind

__all__ = ["ExecutorRegistry"]


class ExecutorRegistry:
    """Stage 4 routing registry.

    Usage::

        registry = ExecutorRegistry()
        registry.register(FilesystemExecutor())
        registry.register(GitExecutor())

        executor = registry.resolve(action)
        result = await executor.execute(action, sandbox)
    """

    def __init__(self) -> None:
        self._executors: dict[ActionKind, BaseExecutor] = {}
        self._by_name: dict[str, BaseExecutor] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, executor: BaseExecutor) -> None:
        """Register an executor.  An executor may handle multiple ActionKinds."""
        name = executor.manifest.name
        self._by_name[name] = executor
        for kind in executor.manifest.handles:
            self._executors[kind] = executor

    def unregister(self, name: str) -> bool:
        """Remove an executor by name.  Returns True if found."""
        if name not in self._by_name:
            return False
        executor = self._by_name.pop(name)
        kinds_to_remove = [k for k, e in self._executors.items() if e is executor]
        for k in kinds_to_remove:
            del self._executors[k]
        return True

    # ------------------------------------------------------------------
    # Routing (Stage 4)
    # ------------------------------------------------------------------

    def resolve(self, action: Action) -> BaseExecutor:
        """Return the executor registered for action.kind.

        Raises:
            ExecutorNotFoundError: if no executor is registered for the kind.
        """
        executor = self._executors.get(action.kind)
        if executor is None:
            raise ExecutorNotFoundError(
                f"No executor registered for ActionKind={action.kind.value!r}. "
                f"Registered kinds: {sorted(k.value for k in self._executors)}",
                action_kind=action.kind.value,
                action_id=action.action_id,
                stage="dispatch",
            )
        return executor

    def has_executor(self, kind: ActionKind) -> bool:
        return kind in self._executors

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def list_executors(self) -> list[ExecutorManifest]:
        """Return manifests for all registered executors."""
        seen: set[str] = set()
        manifests: list[ExecutorManifest] = []
        for e in self._executors.values():
            if e.manifest.name not in seen:
                seen.add(e.manifest.name)
                manifests.append(e.manifest)
        return manifests

    def list_action_kinds(self) -> list[ActionKind]:
        return sorted(self._executors.keys(), key=lambda k: k.value)

    async def health_check(self) -> dict[str, ExecutorHealth]:
        """Run health() on every registered executor."""
        seen: set[str] = set()
        results: dict[str, ExecutorHealth] = {}
        for executor in self._executors.values():
            name = executor.manifest.name
            if name not in seen:
                seen.add(name)
                try:
                    report = await executor.health()
                except Exception as exc:
                    report = ExecutorHealth(
                        name=name, healthy=False, message=str(exc)
                    )
                results[name] = report
        return results

    def __len__(self) -> int:
        return len(self._by_name)

    def __repr__(self) -> str:
        return (
            f"ExecutorRegistry({len(self._by_name)} executors, "
            f"{len(self._executors)} action kinds)"
        )
