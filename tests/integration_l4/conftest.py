"""Shared fixtures for L4 Memory Engine integration tests.

All tests use in-memory SQLite (path=None) so no disk I/O or cleanup is needed.
"""

from __future__ import annotations

import time
import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio

from aegis.l4_memory import (
    MemoryManager,
    MemoryPolicy,
    MemoryRecord,
    MemoryTier,
    MemoryKind,
    MemoryStatus,
    Importance,
    ProvenanceChain,
    ProvenanceLink,
    ProvenanceKind,
)


def _make_provenance(kind: ProvenanceKind = ProvenanceKind.USER_PROVIDED) -> ProvenanceChain:
    return ProvenanceChain.single(kind=kind, subject="test_user")


def _make_record(
    *,
    key: str = "test/record/1",
    tier: MemoryTier = MemoryTier.T1_SESSION,
    kind: MemoryKind = MemoryKind.OBSERVATION,
    content: object = "Test content for AEGIS memory.",
    summary: str | None = None,
    privacy_tier: str = "P2",
    importance: Importance = Importance.NORMAL,
    is_draft: bool = True,
    status: MemoryStatus = MemoryStatus.DRAFT,
    confidence: float = 0.6,
    namespace: str = "global",
    session_id: str | None = "session_test_001",
    project_id: str | None = None,
    tags: frozenset[str] | None = None,
    expires_at: float | None = None,
    provenance_kind: ProvenanceKind = ProvenanceKind.USER_PROVIDED,
) -> MemoryRecord:
    auto_summary = summary if summary is not None else (
        str(content)[:60] if isinstance(content, str) else None
    )
    return MemoryRecord(
        id=uuid.uuid4(),
        key=key,
        namespace=namespace,
        tier=tier,
        kind=kind,
        content=content,
        summary=auto_summary,
        privacy_tier=privacy_tier,
        importance=importance,
        is_draft=is_draft,
        status=status,
        confidence=confidence,
        session_id=session_id,
        project_id=project_id,
        tags=tags or frozenset(),
        expires_at=expires_at,
        provenance=_make_provenance(provenance_kind),
        created_at=time.time(),
        updated_at=time.time(),
    )


@pytest_asyncio.fixture
async def manager() -> AsyncGenerator[MemoryManager, None]:
    """In-memory MemoryManager (no disk I/O). Isolated per test."""
    mgr = MemoryManager(db_path=None, policy=MemoryPolicy.default())
    await mgr.initialize()
    yield mgr
    await mgr.close()


@pytest_asyncio.fixture
async def strict_manager() -> AsyncGenerator[MemoryManager, None]:
    """MemoryManager with strict_privacy policy (P0 access only)."""
    mgr = MemoryManager(db_path=None, policy=MemoryPolicy.strict_privacy())
    await mgr.initialize()
    yield mgr
    await mgr.close()


@pytest.fixture
def make_record():
    """Factory fixture for constructing test MemoryRecords."""
    return _make_record
