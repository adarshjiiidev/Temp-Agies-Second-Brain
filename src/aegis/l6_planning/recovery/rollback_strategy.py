"""L6 Planning Engine — Rollback Strategy generators.

Generates rollback step specifications per task type.
Import safety: stdlib + pydantic + l6_planning internal only.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from aegis.l6_planning.decomposition.task_decomposer import Task

__all__ = ["RollbackStep", "RollbackStrategy", "RollbackStrategyBuilder"]


class RollbackStep(BaseModel):
    task_id: str
    description: str
    action_kind_hint: str | None = None
    reversible: bool = True
    manual_only: bool = False


class RollbackStrategy(BaseModel):
    steps: list[RollbackStep] = Field(default_factory=list)
    fully_reversible: bool = True
    notes: list[str] = Field(default_factory=list)


class RollbackStrategyBuilder:
    """Builds rollback steps for reversible tasks."""

    _ROLLBACK_ACTIONS: dict[str, str] = {
        "fs.write": "fs.delete",
        "fs.mkdir": "fs.delete",
        "fs.copy": "fs.delete",
        "fs.move": "fs.move",       # move back
        "git.commit": "git.reset",
        "git.push": "git.reset",    # requires --force, manual
    }

    def build(self, tasks: list[Task]) -> RollbackStrategy:
        steps: list[RollbackStep] = []
        notes: list[str] = []
        fully_reversible = True

        for task in reversed(tasks):    # rollback in reverse order
            if not task.reversible:
                fully_reversible = False
                notes.append(f"Task '{task.title.split('[')[0].strip()}' is NOT reversible")
                continue

            rollback_hint = self._ROLLBACK_ACTIONS.get(task.action_kind_hint or "", None)
            steps.append(RollbackStep(
                task_id=task.task_id,
                description=f"Undo: {task.title.split('[')[0].strip()}",
                action_kind_hint=rollback_hint,
                reversible=task.reversible,
                manual_only=(rollback_hint is None),
            ))

        return RollbackStrategy(steps=steps, fully_reversible=fully_reversible, notes=notes)
