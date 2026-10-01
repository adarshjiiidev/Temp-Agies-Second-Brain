"""L5 Execution Engine — Rollback Engine.

Orchestrates best-effort rollback after a verification failure.
Calls executor.rollback(), logs the result to the audit chain, and
returns a RollbackRecord.

Import safety: stdlib + l5_execution.* ONLY.
"""

from __future__ import annotations

import time
from typing import Any

from aegis.l5_execution.contracts import RollbackRecord
from aegis.l5_execution.executors.base import BaseExecutor
from aegis.l5_execution.exceptions import RollbackError
from aegis.l5_execution.types import Action, ActionResult

__all__ = ["RollbackEngine"]


class RollbackEngine:
    """Orchestrates rollback after a failed verification.

    Usage::

        engine = RollbackEngine()
        record = await engine.rollback(action, result, executor)
        # record.succeeded tells if rollback worked
    """

    async def rollback(
        self,
        action: Action,
        result: ActionResult,
        executor: BaseExecutor,
    ) -> RollbackRecord:
        """Attempt to roll back the effects of ``result``.

        Returns a RollbackRecord (never raises — failures are recorded in the record).
        """
        executor_name = executor.manifest.name

        if not executor.manifest.supports_rollback:
            return RollbackRecord(
                action_id=action.action_id,
                executor_name=executor_name,
                supported=False,
                succeeded=None,  # not attempted
                error="Executor does not support rollback",
                rolled_back_at=time.time(),
            )

        try:
            rollback_result = await executor.rollback(action, result)
        except Exception as exc:
            return RollbackRecord(
                action_id=action.action_id,
                executor_name=executor_name,
                supported=True,
                succeeded=False,
                steps=[],
                error=str(exc),
                rolled_back_at=time.time(),
            )

        supported = rollback_result.get("supported", True)
        succeeded = rollback_result.get("succeeded", True)
        steps = rollback_result.get("steps", [rollback_result])
        error = rollback_result.get("error")

        return RollbackRecord(
            action_id=action.action_id,
            executor_name=executor_name,
            supported=supported,
            succeeded=succeeded,
            steps=steps if isinstance(steps, list) else [steps],
            error=error,
            rolled_back_at=time.time(),
        )
