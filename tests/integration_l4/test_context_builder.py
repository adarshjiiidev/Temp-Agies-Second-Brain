"""Tests for ContextBuilder — 5-stage recall pipeline, token budgets, P0 exclusion."""

from __future__ import annotations

import time
import uuid

import pytest

from aegis.l4_memory import (
    MemoryManager,
    MemoryStatus,
    MemoryTier,
    MemoryKind,
    Importance,
)
from aegis.l4_memory.context import ContextBuilder, ContextRequest, ContextPackage


pytestmark = pytest.mark.asyncio


async def _seed_active(manager: MemoryManager, make_record, **kwargs):
    """Helper: store + promote to ACTIVE. Passes user_confirmed for T5 Personal."""
    rec = make_record(**kwargs)
    stored = await manager.store(rec)
    needs_confirm = rec.tier is MemoryTier.T5_PERSONAL
    return await manager.promote(stored.id, MemoryStatus.ACTIVE, user_confirmed=needs_confirm)


async def test_build_empty_context(manager: MemoryManager, make_record):
    """ContextBuilder should return empty ContextPackage when no memories stored."""
    builder = ContextBuilder(manager)
    pkg = await builder.build(ContextRequest(query="What do you know?"))
    assert pkg.is_empty
    assert pkg.total_token_estimate == 0


async def test_build_with_session_records(manager: MemoryManager, make_record):
    await _seed_active(
        manager, make_record,
        key="ctx/session/1",
        tier=MemoryTier.T1_SESSION,
        content="We discussed the architecture of the AI Kernel today.",
        session_id="session_test_001",
    )
    builder = ContextBuilder(manager)
    pkg = await builder.build(ContextRequest(
        query="architecture discussion",
        tiers=[MemoryTier.T1_SESSION],
        session_id="session_test_001",
    ))
    assert not pkg.is_empty
    assert pkg.total_token_estimate > 0


async def test_p0_excluded_from_cloud_target(manager: MemoryManager, make_record):
    """P0 records must never appear in a ContextPackage targeting P2 (cloud)."""
    await _seed_active(
        manager, make_record,
        key="ctx/private/p0",
        tier=MemoryTier.T5_PERSONAL,
        privacy_tier="P0",
        is_draft=True,
        status=MemoryStatus.DRAFT,
    )
    # Promote with user confirmation (T5 requirement)
    recs = await manager.list_records(tiers=[MemoryTier.T5_PERSONAL])
    if recs:
        try:
            await manager.promote(recs[0].id, MemoryStatus.ACTIVE, user_confirmed=True)
        except Exception:
            pass

    builder = ContextBuilder(manager)
    pkg = await builder.build(ContextRequest(
        query="personal preferences",
        target_privacy_tier="P2",  # cloud target
        tiers=[MemoryTier.T5_PERSONAL],
    ))
    # P0 should be excluded
    for section in pkg.sections:
        for record in section.records:
            assert record.privacy_tier != "P0", \
                f"P0 record {record.id} leaked into cloud-target context!"


async def test_p0_allowed_for_local_target(manager: MemoryManager, make_record):
    """P0 records should appear in context when target is also P0 (local)."""
    rec = make_record(
        key="ctx/p0_local",
        tier=MemoryTier.T3_SEMANTIC,
        privacy_tier="P0",
        content="This is a private local-only fact.",
    )
    stored = await manager.store(rec)
    await manager.promote(stored.id, MemoryStatus.ACTIVE)

    builder = ContextBuilder(manager)
    pkg = await builder.build(ContextRequest(
        query="private fact",
        target_privacy_tier="P0",  # local model target
        tiers=[MemoryTier.T3_SEMANTIC],
    ))
    all_ids = {r.id for s in pkg.sections for r in s.records}
    # P0 record should be present (target is local)
    assert rec.id in all_ids


async def test_render_system_block(manager: MemoryManager, make_record):
    await _seed_active(
        manager, make_record,
        key="ctx/render/1",
        tier=MemoryTier.T3_SEMANTIC,
        content="AEGIS uses a layered architecture.",
        summary="Layered architecture fact",
    )
    builder = ContextBuilder(manager)
    pkg = await builder.build(ContextRequest(
        query="architecture",
        tiers=[MemoryTier.T3_SEMANTIC],
    ))
    rendered = pkg.render_system_block()
    assert "AEGIS MEMORY CONTEXT" in rendered
    assert "Semantic" in rendered


async def test_hide_from_llm_tag_excluded(manager: MemoryManager, make_record):
    """Records tagged hide_from_llm must never appear in context."""
    rec = make_record(
        key="ctx/hidden",
        tier=MemoryTier.T3_SEMANTIC,
        tags=frozenset(["hide_from_llm"]),
        content="This should never appear in any AI prompt.",
    )
    stored = await manager.store(rec)
    await manager.promote(stored.id, MemoryStatus.ACTIVE)

    builder = ContextBuilder(manager)
    pkg = await builder.build(ContextRequest(query="hidden content"))
    all_ids = {r.id for s in pkg.sections for r in s.records}
    assert rec.id not in all_ids


async def test_tier_decomposition_excludes_t0(manager: MemoryManager):
    """T0 Working memory is never queried (in-context only)."""
    builder = ContextBuilder(manager)
    req = ContextRequest(query="test", tiers=None)
    tiers = builder._stage1_decompose(req)
    from aegis.l4_memory.types import MemoryTier as MT
    assert MT.T0_WORKING not in tiers


async def test_context_build_latency_recorded(manager: MemoryManager, make_record):
    builder = ContextBuilder(manager)
    pkg = await builder.build(ContextRequest(query="test latency"))
    assert pkg.build_latency_ms >= 0


async def test_context_section_render_text(manager: MemoryManager, make_record):
    await _seed_active(
        manager, make_record,
        key="ctx/section/1",
        tier=MemoryTier.T2_EPISODIC,
        content="Implemented Prompt 03 AI Kernel.",
        importance=Importance.HIGH,
    )
    builder = ContextBuilder(manager)
    pkg = await builder.build(ContextRequest(
        query="prompt 03",
        tiers=[MemoryTier.T2_EPISODIC],
    ))
    for section in pkg.sections:
        text = section.render_text()
        if section.records:
            assert "MEMORY" in text
            assert "HIGH" in text or "high" in text.lower()


async def test_multiple_tiers_assembled(manager: MemoryManager, make_record):
    """Both T1 and T3 records should appear in the package."""
    t1 = make_record(key="multi/t1", tier=MemoryTier.T1_SESSION,
                     content="Session event 1")
    t3 = make_record(key="multi/t3", tier=MemoryTier.T3_SEMANTIC,
                     content="Semantic fact 1")
    for r in [t1, t3]:
        stored = await manager.store(r)
        await manager.promote(stored.id, MemoryStatus.ACTIVE)

    builder = ContextBuilder(manager)
    pkg = await builder.build(ContextRequest(
        query="event fact",
        tiers=[MemoryTier.T1_SESSION, MemoryTier.T3_SEMANTIC],
    ))
    tier_names = {s.tier for s in pkg.sections}
    assert MemoryTier.T1_SESSION in tier_names
    assert MemoryTier.T3_SEMANTIC in tier_names
