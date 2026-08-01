"""Tests for SearchEngine — keyword, metadata, hybrid search modes, scoring."""

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
    SearchMode,
)
from aegis.l4_memory.search import SearchQuery
from aegis.l4_memory.exceptions import MemorySearchError


pytestmark = pytest.mark.asyncio


async def test_keyword_search_finds_content(manager: MemoryManager, make_record):
    rec = make_record(
        key="search/python_facts",
        tier=MemoryTier.T3_SEMANTIC,
        content="Python 3.12 introduced type parameter syntax for PEP 695",
        status=MemoryStatus.ACTIVE,
        is_draft=False,
    )
    await manager.store(rec)
    # Promote to ACTIVE
    await manager.promote(rec.id, MemoryStatus.ACTIVE)

    results = await manager.search(SearchQuery(
        text="type parameter",
        mode=SearchMode.KEYWORD,
        tiers=[MemoryTier.T3_SEMANTIC],
    ))
    assert any(r.record.id == rec.id for r in results)


async def test_metadata_search_by_tier(manager: MemoryManager, make_record):
    rec1 = make_record(key="meta/t3/fact", tier=MemoryTier.T3_SEMANTIC)
    rec2 = make_record(key="meta/t1/session", tier=MemoryTier.T1_SESSION)
    for r in [rec1, rec2]:
        stored = await manager.store(r)
        await manager.promote(stored.id, MemoryStatus.ACTIVE)

    results = await manager.search(SearchQuery(
        mode=SearchMode.METADATA,
        tiers=[MemoryTier.T3_SEMANTIC],
    ))
    ids = {r.record.id for r in results}
    assert rec1.id in ids
    assert rec2.id not in ids


async def test_hybrid_search(manager: MemoryManager, make_record):
    rec = make_record(
        key="hybrid/aegis/arch",
        tier=MemoryTier.T3_SEMANTIC,
        content="AEGIS uses a 7-layer architecture with L4 Memory engine",
        tags=frozenset(["architecture", "aegis"]),
    )
    stored = await manager.store(rec)
    await manager.promote(stored.id, MemoryStatus.ACTIVE)

    results = await manager.search(SearchQuery(
        text="7-layer architecture",
        mode=SearchMode.HYBRID,
        tags=frozenset(["architecture"]),
    ))
    assert len(results) >= 1


async def test_semantic_search_raises_not_implemented(manager: MemoryManager):
    with pytest.raises(MemorySearchError, match="not yet implemented"):
        await manager.search(SearchQuery(
            text="some query",
            mode=SearchMode.SEMANTIC,
        ))


async def test_graph_search_raises_not_implemented(manager: MemoryManager):
    with pytest.raises(MemorySearchError, match="graph"):
        await manager.search(SearchQuery(
            text="node query",
            mode=SearchMode.GRAPH,
        ))


async def test_search_excludes_deleted(manager: MemoryManager, make_record):
    rec = make_record(key="search/deleted")
    stored = await manager.store(rec)
    await manager.promote(stored.id, MemoryStatus.ACTIVE)
    await manager.delete(stored.id)

    results = await manager.search(SearchQuery(mode=SearchMode.METADATA))
    ids = {r.record.id for r in results}
    assert rec.id not in ids


async def test_search_excludes_expired(manager: MemoryManager, make_record):
    past = time.time() - 3600  # already expired
    rec = make_record(key="search/expired", expires_at=past)
    stored = await manager.store(rec)
    await manager.promote(stored.id, MemoryStatus.ACTIVE)

    results = await manager.search(SearchQuery(mode=SearchMode.METADATA))
    ids = {r.record.id for r in results}
    assert rec.id not in ids


async def test_search_result_scores_ordered(manager: MemoryManager, make_record):
    """Higher importance records should score higher."""
    low_rec = make_record(
        key="score/low",
        importance=Importance.LOW,
        confidence=0.3,
    )
    high_rec = make_record(
        key="score/high",
        importance=Importance.HIGH,
        confidence=0.9,
    )
    for r in [low_rec, high_rec]:
        stored = await manager.store(r)
        await manager.promote(stored.id, MemoryStatus.ACTIVE)

    results = await manager.search(SearchQuery(mode=SearchMode.METADATA))
    assert len(results) >= 2
    # Scores should be descending
    scores = [r.score for r in results]
    assert all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))


async def test_search_privacy_tier_filter(manager: MemoryManager, make_record):
    p0_rec = make_record(key="priv/p0", privacy_tier="P0")
    p2_rec = make_record(key="priv/p2", privacy_tier="P2")
    for r in [p0_rec, p2_rec]:
        stored = await manager.store(r)
        await manager.promote(stored.id, MemoryStatus.ACTIVE)

    # Exclude P0 explicitly
    results = await manager.search(SearchQuery(
        mode=SearchMode.METADATA,
        exclude_privacy_tiers=["P0"],
    ))
    ids = {r.record.id for r in results}
    assert p0_rec.id not in ids
    assert p2_rec.id in ids


async def test_search_min_confidence_filter(manager: MemoryManager, make_record):
    low = make_record(key="conf/low", confidence=0.2)
    high = make_record(key="conf/high", confidence=0.9)
    for r in [low, high]:
        stored = await manager.store(r)
        await manager.promote(stored.id, MemoryStatus.ACTIVE)

    results = await manager.search(SearchQuery(
        mode=SearchMode.METADATA,
        min_confidence=0.5,
    ))
    ids = {r.record.id for r in results}
    assert low.id not in ids
    assert high.id in ids


async def test_search_tag_filter(manager: MemoryManager, make_record):
    tagged = make_record(key="tag/yes", tags=frozenset(["important", "aegis"]))
    untagged = make_record(key="tag/no")
    for r in [tagged, untagged]:
        stored = await manager.store(r)
        await manager.promote(stored.id, MemoryStatus.ACTIVE)

    results = await manager.search(SearchQuery(
        mode=SearchMode.METADATA,
        tags=frozenset(["important"]),
    ))
    ids = {r.record.id for r in results}
    assert tagged.id in ids
    assert untagged.id not in ids
