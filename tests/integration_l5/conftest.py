"""Integration tests for L5 Execution Engine — shared fixtures."""

from __future__ import annotations

import pytest
import pytest_asyncio

from aegis.l5_execution.pipeline import ExecutionPipeline
from aegis.l5_execution.types import Action, ActionKind


@pytest_asyncio.fixture
async def pipeline():
    """A fresh ExecutionPipeline with in-memory stores and default executor set."""
    p = ExecutionPipeline(audit_db_path=None, permission_db_path=None)
    await p.initialize()
    yield p
    await p.close()


@pytest_asyncio.fixture
async def pipeline_with_grant():
    """Pipeline with a broad fs.* grant for system:planner — for happy-path tests."""
    p = ExecutionPipeline(audit_db_path=None, permission_db_path=None)
    await p.initialize()
    await p.permission_engine.grant(
        subject="system:planner",
        verbs=["fs"],
        resources=["fs:*"],
        granted_by="user:primary",
        reason="test fixture broad grant",
    )
    yield p
    await p.close()


def make_action(
    kind: ActionKind,
    resource: str = "fs:~/test",
    actor: str = "system:planner",
    parameters: dict | None = None,
    context: dict | None = None,
    user_confirmed: bool = False,
    dry_run: bool = False,
) -> Action:
    """Helper to build Action instances in tests."""
    return Action(
        actor=actor,
        kind=kind,
        resource=resource,
        parameters=parameters or {},
        context=context or {"reason": "test"},
        user_confirmed=user_confirmed,
        dry_run=dry_run,
    )
