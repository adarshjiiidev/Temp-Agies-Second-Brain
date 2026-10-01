"""Tests for MemoryManager — full policy gate, lifecycle, expiry, pin, archive."""

from __future__ import annotations

import time
import uuid

import pytest

from aegis.l4_memory import (
    MemoryManager,
    MemoryRecord,
    MemoryStatus,
    MemoryTier,
    MemoryKind,
    Importance,
    MemoryPolicy,
)
from aegis.l4_memory.exceptions import (
    MemoryNotFoundError,
    MemoryPolicyViolationError,
    MemoryStatusError,
    MemoryStorageError,
    MemoryVersionConflictError,
)


pytestmark = pytest.mark.asyncio


async def test_store_and_retrieve(manager: MemoryManager, make_record):
    rec = make_record()
    stored = await manager.store(rec)
    assert stored.id == rec.id
    fetched = await manager.get(stored.id)
    assert fetched.id == stored.id


async def test_get_by_key(manager: MemoryManager, make_record):
    rec = make_record(key="project/aegis/main")
    await manager.store(rec)
    fetched = await manager.get_by_key("project/aegis/main")
    assert fetched is not None
    assert fetched.key == "project/aegis/main"


async def test_get_missing_raises(manager: MemoryManager):
    with pytest.raises(MemoryNotFoundError):
        await manager.get(uuid.uuid4())


async def test_get_deleted_not_retrievable(manager: MemoryManager, make_record):
    rec = make_record()
    stored = await manager.store(rec)
    await manager.delete(stored.id)
    with pytest.raises(MemoryNotFoundError):
        await manager.get(stored.id)


async def test_update_bumps_version(manager: MemoryManager, make_record):
    rec = make_record()
    stored = await manager.store(rec)
    updated = await manager.update(stored.id, content="Updated content", change_note="test update")
    assert updated.version == 2
    assert updated.content == "Updated content"


async def test_update_version_conflict(manager: MemoryManager, make_record):
    rec = make_record()
    stored = await manager.store(rec)
    with pytest.raises(MemoryVersionConflictError):
        await manager.update(stored.id, content="oops", expected_version=99)


async def test_delete(manager: MemoryManager, make_record):
    rec = make_record()
    stored = await manager.store(rec)
    result = await manager.delete(stored.id)
    assert result is True


async def test_promote_draft_to_active(manager: MemoryManager, make_record):
    rec = make_record(is_draft=True, status=MemoryStatus.DRAFT)
    stored = await manager.store(rec)
    promoted = await manager.promote(stored.id, MemoryStatus.ACTIVE)
    assert promoted.status == MemoryStatus.ACTIVE
    assert promoted.is_draft is False


async def test_promote_invalid_transition_raises(manager: MemoryManager, make_record):
    # DELETED → ACTIVE is not allowed
    rec = make_record(status=MemoryStatus.ACTIVE)
    stored = await manager.store(rec)
    # First delete it
    await manager.delete(stored.id)
    deleted = await manager.list_records(status=MemoryStatus.DELETED)
    assert any(r.id == stored.id for r in deleted)
    # Now try invalid transition
    with pytest.raises(MemoryStatusError):
        await manager.promote(stored.id, MemoryStatus.ACTIVE)


async def test_t5_personal_must_be_draft(manager: MemoryManager, make_record):
    """T5 Personal cannot be stored as ACTIVE directly — policy gate."""
    rec = make_record(
        tier=MemoryTier.T5_PERSONAL,
        is_draft=False,
        status=MemoryStatus.ACTIVE,
    )
    with pytest.raises(MemoryPolicyViolationError):
        await manager.store(rec)


async def test_t5_personal_promote_requires_user_confirmation(manager: MemoryManager, make_record):
    rec = make_record(tier=MemoryTier.T5_PERSONAL, is_draft=True, status=MemoryStatus.DRAFT)
    stored = await manager.store(rec)
    # Without user_confirmed → raises
    with pytest.raises(MemoryPolicyViolationError):
        await manager.promote(stored.id, MemoryStatus.ACTIVE)


async def test_t5_personal_promote_with_user_confirmation(manager: MemoryManager, make_record):
    rec = make_record(tier=MemoryTier.T5_PERSONAL, is_draft=True, status=MemoryStatus.DRAFT)
    stored = await manager.store(rec)
    promoted = await manager.promote(stored.id, MemoryStatus.ACTIVE, user_confirmed=True)
    assert promoted.status == MemoryStatus.ACTIVE


async def test_archive_and_restore(manager: MemoryManager, make_record):
    rec = make_record(status=MemoryStatus.ACTIVE, is_draft=False)
    stored = await manager.store(rec)
    # Promote to active first
    active = await manager.promote(stored.id, MemoryStatus.ACTIVE)
    archived = await manager.archive(active.id)
    assert archived.status == MemoryStatus.ARCHIVED
    restored = await manager.restore(archived.id)
    assert restored.status == MemoryStatus.ACTIVE


async def test_pin_and_unpin(manager: MemoryManager, make_record):
    rec = make_record()
    stored = await manager.store(rec)
    pinned = await manager.pin(stored.id)
    assert pinned.is_pinned is True
    unpinned = await manager.unpin(stored.id)
    assert unpinned.is_pinned is False


async def test_expire_due(manager: MemoryManager, make_record):
    past_time = time.time() - 86400  # expired 1 day ago
    rec = make_record(status=MemoryStatus.ACTIVE, is_draft=False, expires_at=past_time)
    stored = await manager.store(rec)
    # Promote to active
    active = await manager.promote(stored.id, MemoryStatus.ACTIVE)
    count = await manager.expire_due()
    assert count >= 1


async def test_version_history(manager: MemoryManager, make_record):
    rec = make_record()
    stored = await manager.store(rec)
    await manager.update(stored.id, content="v2")
    await manager.update(stored.id, content="v3")
    history = await manager.get_version_history(stored.id)
    assert len(history) >= 2


async def test_meta_snapshot(manager: MemoryManager, make_record):
    for i in range(3):
        rec = make_record(key=f"k/{i}")
        await manager.store(rec)
    snap = await manager.get_meta_snapshot()
    assert snap["total_records"] == 3


async def test_manager_not_initialized_raises():
    mgr = MemoryManager(db_path=None)
    with pytest.raises(MemoryStorageError):
        await mgr.store(MemoryManager.__new__(MemoryManager))  # type: ignore


async def test_manager_list_records(manager: MemoryManager, make_record):
    for i in range(5):
        await manager.store(make_record(key=f"list/test/{i}", tier=MemoryTier.T1_SESSION))
    records = await manager.list_records(tiers=[MemoryTier.T1_SESSION])
    assert len(records) >= 5
