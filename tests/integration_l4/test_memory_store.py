"""Tests for SQLiteMemoryStore — CRUD, FTS5 search, version history, expiration."""

from __future__ import annotations

import time
import uuid

import pytest
import pytest_asyncio

from aegis.l4_memory.store import SQLiteMemoryStore
from aegis.l4_memory.models import MemoryRecord, ProvenanceChain, ProvenanceLink
from aegis.l4_memory.types import (
    Importance,
    MemoryKind,
    MemoryStatus,
    MemoryTier,
    ProvenanceKind,
)
from aegis.l4_memory.exceptions import MemoryNotFoundError, MemoryStorageError


def _prov() -> ProvenanceChain:
    return ProvenanceChain.single(kind=ProvenanceKind.USER_PROVIDED, subject="test")


def _rec(key: str = "k/1", tier: MemoryTier = MemoryTier.T1_SESSION, content: object = "hello") -> MemoryRecord:
    now = time.time()
    return MemoryRecord(
        id=uuid.uuid4(),
        key=key,
        namespace="global",
        tier=tier,
        kind=MemoryKind.OBSERVATION,
        content=content,
        summary="test summary",
        privacy_tier="P2",
        importance=Importance.NORMAL,
        is_draft=True,
        status=MemoryStatus.ACTIVE,
        confidence=0.7,
        provenance=_prov(),
        created_at=now,
        updated_at=now,
    )


@pytest_asyncio.fixture
async def store():
    s = SQLiteMemoryStore(path=None)
    await s.initialize()
    yield s
    await s.close()


@pytest.mark.asyncio
async def test_store_and_get_by_id(store: SQLiteMemoryStore):
    rec = _rec()
    await store.upsert(rec)
    fetched = await store.get(rec.id)
    assert fetched.id == rec.id
    assert fetched.key == rec.key
    assert fetched.tier == rec.tier


@pytest.mark.asyncio
async def test_get_by_key(store: SQLiteMemoryStore):
    rec = _rec("project/aegis/desc")
    await store.upsert(rec)
    fetched = await store.get_by_key("project/aegis/desc", "global")
    assert fetched is not None
    assert fetched.id == rec.id


@pytest.mark.asyncio
async def test_get_by_key_missing_returns_none(store: SQLiteMemoryStore):
    result = await store.get_by_key("nonexistent/key", "global")
    assert result is None


@pytest.mark.asyncio
async def test_get_missing_raises(store: SQLiteMemoryStore):
    with pytest.raises(MemoryNotFoundError):
        await store.get(uuid.uuid4())


@pytest.mark.asyncio
async def test_upsert_same_id_bumps_version(store: SQLiteMemoryStore):
    rec = _rec()
    stored = await store.upsert(rec)
    assert stored.version == 1
    # Second upsert with same ID
    stored2 = await store.upsert(stored)
    assert stored2.version == 2


@pytest.mark.asyncio
async def test_version_history_saved(store: SQLiteMemoryStore):
    rec = _rec()
    stored = await store.upsert(rec)
    stored2 = await store.upsert(stored)
    history = await store.get_version_history(rec.id)
    assert len(history) >= 1
    assert history[0].version == 1


@pytest.mark.asyncio
async def test_soft_delete(store: SQLiteMemoryStore):
    rec = _rec()
    await store.upsert(rec)
    deleted = await store.delete(rec.id)
    assert deleted is True
    fetched = await store.get(rec.id)
    assert fetched.status == MemoryStatus.DELETED


@pytest.mark.asyncio
async def test_hard_delete(store: SQLiteMemoryStore):
    rec = _rec()
    await store.upsert(rec)
    removed = await store.hard_delete(rec.id)
    assert removed is True
    with pytest.raises(MemoryNotFoundError):
        await store.get(rec.id)


@pytest.mark.asyncio
async def test_list_records_by_tier(store: SQLiteMemoryStore):
    r1 = _rec("a", MemoryTier.T1_SESSION)
    r2 = _rec("b", MemoryTier.T3_SEMANTIC)
    await store.upsert(r1)
    await store.upsert(r2)
    results = await store.list_records(tiers=[MemoryTier.T1_SESSION])
    assert any(r.id == r1.id for r in results)
    assert not any(r.id == r2.id for r in results)


@pytest.mark.asyncio
async def test_list_records_excludes_deleted(store: SQLiteMemoryStore):
    rec = _rec()
    await store.upsert(rec)
    await store.delete(rec.id)
    results = await store.list_records()
    assert not any(r.id == rec.id for r in results)


@pytest.mark.asyncio
async def test_keyword_search(store: SQLiteMemoryStore):
    rec = _rec(content="Python 3.12 supports type parameter syntax")
    # Must be ACTIVE for FTS search
    active_rec = rec.model_copy(update={"status": MemoryStatus.ACTIVE})
    await store.upsert(active_rec)
    results = await store.keyword_search("type parameter")
    assert any(r.id == rec.id for r in results)


@pytest.mark.asyncio
async def test_count_by_tier(store: SQLiteMemoryStore):
    for i in range(3):
        await store.upsert(_rec(f"k/{i}", MemoryTier.T1_SESSION))
    counts = await store.count(tiers=[MemoryTier.T1_SESSION])
    assert counts.get("T1_session", 0) == 3


@pytest.mark.asyncio
async def test_touch_access(store: SQLiteMemoryStore):
    rec = _rec()
    await store.upsert(rec)
    await store.touch_access(rec.id)
    fetched = await store.get(rec.id)
    assert fetched.access_count == 1
    assert fetched.last_accessed_at is not None


@pytest.mark.asyncio
async def test_store_not_initialized_raises():
    store = SQLiteMemoryStore(path=None)
    with pytest.raises(MemoryStorageError):
        await store.get(uuid.uuid4())
