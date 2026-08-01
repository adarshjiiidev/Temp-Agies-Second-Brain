"""Tests for KnowledgeGraph — entity/relationship CRUD, BFS traversal, draft edges."""

from __future__ import annotations

import time
import uuid

import pytest
import pytest_asyncio

import aiosqlite

from aegis.l4_memory.graph import KnowledgeGraph
from aegis.l4_memory.store import SQLiteMemoryStore, _SCHEMA
from aegis.l4_memory.models import KGEntity, KGRelationship, ProvenanceChain
from aegis.l4_memory.types import EntityKind, ProvenanceKind, RelationshipKind
from aegis.l4_memory.exceptions import MemoryNotFoundError


def _entity(kind: EntityKind = EntityKind.PROJECT, key: str = "project:aegis") -> KGEntity:
    now = time.time()
    return KGEntity(
        id=uuid.uuid4(),
        kind=kind,
        key=key,
        label=key.split(":")[-1].title(),
        namespace="global",
        created_at=now,
        updated_at=now,
    )


def _relationship(
    subject: KGEntity,
    obj: KGEntity,
    kind: RelationshipKind = RelationshipKind.USES,
) -> KGRelationship:
    now = time.time()
    prov = ProvenanceChain.single(kind=ProvenanceKind.SYSTEM_GENERATED, subject="test")
    return KGRelationship(
        id=uuid.uuid4(),
        subject_id=subject.id,
        object_id=obj.id,
        kind=kind,
        confidence=0.9,
        provenance=prov,
        created_at=now,
        updated_at=now,
    )


@pytest_asyncio.fixture
async def kg():
    """In-memory KnowledgeGraph backed by SQLiteMemoryStore connection."""
    store = SQLiteMemoryStore(path=None)
    await store.initialize()
    graph = KnowledgeGraph(store._conn)
    yield graph
    await store.close()


pytestmark = pytest.mark.asyncio


async def test_upsert_and_get_entity(kg: KnowledgeGraph):
    ent = _entity()
    await kg.upsert_entity(ent)
    fetched = await kg.get_entity(ent.id)
    assert fetched.id == ent.id
    assert fetched.key == ent.key


async def test_get_entity_missing_raises(kg: KnowledgeGraph):
    with pytest.raises(MemoryNotFoundError):
        await kg.get_entity(uuid.uuid4())


async def test_get_entity_by_key(kg: KnowledgeGraph):
    ent = _entity(key="project:mytestproject")
    await kg.upsert_entity(ent)
    fetched = await kg.get_entity_by_key("project:mytestproject")
    assert fetched is not None
    assert fetched.id == ent.id


async def test_get_entity_by_key_missing_returns_none(kg: KnowledgeGraph):
    result = await kg.get_entity_by_key("nonexistent:key")
    assert result is None


async def test_list_entities(kg: KnowledgeGraph):
    for i in range(4):
        await kg.upsert_entity(_entity(EntityKind.TECHNOLOGY, f"tech:{i}"))
    results = await kg.list_entities(kind=EntityKind.TECHNOLOGY)
    assert len(results) == 4


async def test_delete_entity(kg: KnowledgeGraph):
    ent = _entity()
    await kg.upsert_entity(ent)
    deleted = await kg.delete_entity(ent.id)
    assert deleted is True
    with pytest.raises(MemoryNotFoundError):
        await kg.get_entity(ent.id)


async def test_upsert_relationship(kg: KnowledgeGraph):
    e1 = _entity(EntityKind.PROJECT, "project:aegis")
    e2 = _entity(EntityKind.TECHNOLOGY, "tech:python")
    await kg.upsert_entity(e1)
    await kg.upsert_entity(e2)
    rel = _relationship(e1, e2, RelationshipKind.USES)
    await kg.upsert_relationship(rel)
    fetched = await kg.get_relationship(rel.id)
    assert fetched.id == rel.id
    assert fetched.kind == RelationshipKind.USES


async def test_get_relationship_missing_raises(kg: KnowledgeGraph):
    with pytest.raises(MemoryNotFoundError):
        await kg.get_relationship(uuid.uuid4())


async def test_delete_relationship(kg: KnowledgeGraph):
    e1 = _entity(key="proj:a")
    e2 = _entity(key="proj:b")
    await kg.upsert_entity(e1)
    await kg.upsert_entity(e2)
    rel = _relationship(e1, e2)
    await kg.upsert_relationship(rel)
    deleted = await kg.delete_relationship(rel.id)
    assert deleted is True
    with pytest.raises(MemoryNotFoundError):
        await kg.get_relationship(rel.id)


async def test_get_neighbors_outgoing(kg: KnowledgeGraph):
    proj = _entity(EntityKind.PROJECT, "project:aegis2")
    tech1 = _entity(EntityKind.TECHNOLOGY, "tech:sqliteA")
    tech2 = _entity(EntityKind.TECHNOLOGY, "tech:pythonA")
    for e in [proj, tech1, tech2]:
        await kg.upsert_entity(e)
    await kg.upsert_relationship(_relationship(proj, tech1))
    await kg.upsert_relationship(_relationship(proj, tech2))

    neighbors = await kg.get_neighbors(proj.id, direction="outgoing")
    neighbor_ids = {e.id for _, e in neighbors}
    assert tech1.id in neighbor_ids
    assert tech2.id in neighbor_ids


async def test_draft_edges_excluded_by_default(kg: KnowledgeGraph):
    e1 = _entity(key="src:entity")
    e2 = _entity(key="dst:entity")
    await kg.upsert_entity(e1)
    await kg.upsert_entity(e2)
    rel = _relationship(e1, e2)
    await kg.upsert_relationship(rel, is_draft=True)

    neighbors = await kg.get_neighbors(e1.id, include_draft=False)
    assert len(neighbors) == 0


async def test_draft_edges_included_when_requested(kg: KnowledgeGraph):
    e1 = _entity(key="src2:entity")
    e2 = _entity(key="dst2:entity")
    await kg.upsert_entity(e1)
    await kg.upsert_entity(e2)
    rel = _relationship(e1, e2)
    await kg.upsert_relationship(rel, is_draft=True)

    neighbors = await kg.get_neighbors(e1.id, include_draft=True)
    assert len(neighbors) == 1


async def test_confirm_draft_edge(kg: KnowledgeGraph):
    e1 = _entity(key="src3:entity")
    e2 = _entity(key="dst3:entity")
    await kg.upsert_entity(e1)
    await kg.upsert_entity(e2)
    rel = _relationship(e1, e2)
    await kg.upsert_relationship(rel, is_draft=True)

    confirmed = await kg.confirm_draft_edge(rel.id)
    assert confirmed is True
    # Now should appear in non-draft query
    neighbors = await kg.get_neighbors(e1.id, include_draft=False)
    assert len(neighbors) == 1


async def test_bfs_traversal(kg: KnowledgeGraph):
    # A → B → C (chain)
    a = _entity(key="node:A")
    b = _entity(key="node:B")
    c = _entity(key="node:C")
    for e in [a, b, c]:
        await kg.upsert_entity(e)
    await kg.upsert_relationship(_relationship(a, b))
    await kg.upsert_relationship(_relationship(b, c))

    reachable = await kg.bfs(a.id, max_depth=3)
    reachable_ids = {e.id for e in reachable}
    assert b.id in reachable_ids
    assert c.id in reachable_ids


async def test_bfs_max_depth_respected(kg: KnowledgeGraph):
    # A → B → C (chain), max_depth=1 should only reach B
    a = _entity(key="depth:A")
    b = _entity(key="depth:B")
    c = _entity(key="depth:C")
    for e in [a, b, c]:
        await kg.upsert_entity(e)
    await kg.upsert_relationship(_relationship(a, b))
    await kg.upsert_relationship(_relationship(b, c))

    reachable = await kg.bfs(a.id, max_depth=1)
    reachable_ids = {e.id for e in reachable}
    assert b.id in reachable_ids
    assert c.id not in reachable_ids


async def test_path_exists(kg: KnowledgeGraph):
    x = _entity(key="path:X")
    y = _entity(key="path:Y")
    await kg.upsert_entity(x)
    await kg.upsert_entity(y)
    await kg.upsert_relationship(_relationship(x, y))

    assert await kg.path_exists(x.id, y.id) is True


async def test_path_not_exists(kg: KnowledgeGraph):
    x = _entity(key="nopath:X")
    y = _entity(key="nopath:Y")
    await kg.upsert_entity(x)
    await kg.upsert_entity(y)
    # No edge between them
    assert await kg.path_exists(x.id, y.id) is False


async def test_count_entities_and_relationships(kg: KnowledgeGraph):
    e1 = _entity(key="count:E1")
    e2 = _entity(key="count:E2")
    await kg.upsert_entity(e1)
    await kg.upsert_entity(e2)
    rel = _relationship(e1, e2)
    await kg.upsert_relationship(rel)

    assert await kg.count_entities() >= 2
    assert await kg.count_relationships() >= 1
