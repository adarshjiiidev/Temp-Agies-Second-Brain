"""Integration tests — Audit Chain (Stage 7).

Tests:
  - Append entries and read back
  - Hash chain integrity intact
  - Verifier detects tampering (hash modification)
  - Verifier detects truncation (gap in sequence)
"""

from __future__ import annotations

import json

import pytest
import pytest_asyncio

from aegis.l5_execution.audit.chain import AuditChain, _GENESIS_HASH
from aegis.l5_execution.audit.verifier import AuditVerifier
from aegis.l5_execution.exceptions import AuditIntegrityError
from aegis.l5_execution.types import AuditStage


@pytest_asyncio.fixture
async def chain():
    c = AuditChain(db_path=None)  # in-memory
    await c.initialize()
    yield c
    await c.close()


@pytest.mark.asyncio
async def test_append_and_count(chain):
    assert await chain.count() == 0
    await chain.append(
        stage=AuditStage.PERMISSION,
        action_id="action-001",
        actor="system:planner",
        verb="fs.read",
        resource="fs:~/test.txt",
        decision="ALLOW",
        result="SUCCESS",
    )
    assert await chain.count() == 1


@pytest.mark.asyncio
async def test_entries_for_action(chain):
    await chain.append(
        stage=AuditStage.PERMISSION,
        action_id="action-001",
        actor="system:planner",
        verb="fs.read",
        resource="fs:~/a.txt",
        decision="ALLOW",
        result="SUCCESS",
    )
    await chain.append(
        stage=AuditStage.EXECUTE,
        action_id="action-001",
        actor="system:planner",
        verb="fs.read",
        resource="fs:~/a.txt",
        decision="EXECUTED",
        result="SUCCESS",
    )
    await chain.append(
        stage=AuditStage.PERMISSION,
        action_id="action-002",
        actor="system:planner",
        verb="fs.write",
        resource="fs:~/b.txt",
        decision="DENY",
        result="DENIED",
    )
    entries = await chain.get_entries_for_action("action-001")
    assert len(entries) == 2
    stages = [e.stage for e in entries]
    assert AuditStage.PERMISSION in stages
    assert AuditStage.EXECUTE in stages


@pytest.mark.asyncio
async def test_hash_chain_intact_after_multiple_appends(chain):
    for i in range(10):
        await chain.append(
            stage=AuditStage.EXECUTE,
            action_id=f"action-{i:03d}",
            actor="system:planner",
            verb="fs.read",
            resource="fs:~/test.txt",
            decision="ALLOW",
            result="SUCCESS",
        )
    # Verify last 10
    intact = await chain.verify_last_n(10)
    assert intact is True


@pytest.mark.asyncio
async def test_verifier_detects_hash_tampering(chain, tmp_path):
    """Verifier detects a tampered entry_hash in a file-backed chain."""
    import aiosqlite

    db_path = tmp_path / "audit_tamper.db"
    file_chain = AuditChain(db_path=db_path)
    await file_chain.initialize()

    for i in range(5):
        await file_chain.append(
            stage=AuditStage.PERMISSION,
            action_id=f"act-{i}",
            actor="system:planner",
            verb="fs.read",
            resource="fs:~/t.txt",
            decision="ALLOW",
            result="SUCCESS",
        )
    await file_chain.close()

    # Tamper: corrupt entry_hash of sequence 3
    async with aiosqlite.connect(str(db_path)) as conn:
        await conn.execute(
            "UPDATE audit_entries SET entry_hash='deadbeef' * 8 WHERE sequence=3"
        )
        await conn.commit()

    verifier = AuditVerifier(db_path=db_path)
    report = await verifier.verify()
    assert report.is_intact is False
    assert len(report.violations) > 0


@pytest.mark.asyncio
async def test_verifier_detects_sequence_gap(chain, tmp_path):
    """Verifier detects a deleted entry (gap in sequence)."""
    import aiosqlite

    db_path = tmp_path / "audit_gap.db"
    file_chain = AuditChain(db_path=db_path)
    await file_chain.initialize()

    for i in range(6):
        await file_chain.append(
            stage=AuditStage.EXECUTE,
            action_id=f"act-{i}",
            actor="system:planner",
            verb="fs.read",
            resource="fs:~/t.txt",
            decision="ALLOW",
            result="SUCCESS",
        )
    await file_chain.close()

    # Delete entry 3 — creates a gap
    async with aiosqlite.connect(str(db_path)) as conn:
        await conn.execute("DELETE FROM audit_entries WHERE sequence=3")
        await conn.commit()

    verifier = AuditVerifier(db_path=db_path)
    report = await verifier.verify()
    assert report.is_intact is False


@pytest.mark.asyncio
async def test_get_recent(chain):
    for i in range(15):
        await chain.append(
            stage=AuditStage.RISK,
            action_id=f"act-{i}",
            actor="system:planner",
            verb="fs.read",
            resource="fs:~/t.txt",
            decision="LOW",
            result="ASSESSED",
        )
    recent = await chain.get_recent(limit=5)
    assert len(recent) == 5


@pytest.mark.asyncio
async def test_escape_attempt_result_recorded(chain):
    """An ESCAPE_ATTEMPT result must be recordable."""
    entry_id = await chain.append(
        stage=AuditStage.EXECUTE,
        action_id="escape-001",
        actor="generated:evil_tool",
        verb="python.eval",
        resource="proc:python",
        decision="ESCAPE_ATTEMPT",
        result="SANDBOX_ESCAPE",
        details={"escape_pattern": "import os"},
    )
    assert entry_id is not None
    entries = await chain.get_entries_for_action("escape-001")
    assert entries[0].result == "SANDBOX_ESCAPE"
