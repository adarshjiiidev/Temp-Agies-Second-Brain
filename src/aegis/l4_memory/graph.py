"""L4 Memory — Knowledge Graph (SQLite adjacency table + in-memory traversal).

Implements the KG layer per 06_MEMORY_KNOWLEDGE.md §5:
  - SQLite nodes (kg_entities) and edges (kg_relationships) tables.
  - CRUD for KGEntity and KGRelationship.
  - Draft edge support: auto-suggested edges NOT traversed by default.
  - Neighborhood traversal (BFS, configurable depth, directed/undirected).
  - Path existence check between two entities.
  - No NetworkX dependency in P04 (pure Python BFS; NetworkX deferred to P05+).

Import safety: l4_memory.models + l4_memory.types + l4_memory.exceptions
+ aiosqlite + stdlib ONLY.
"""

from __future__ import annotations

import json
import time
from collections import deque
from typing import Any
from uuid import UUID

import aiosqlite

from aegis.l4_memory.exceptions import KnowledgeGraphError, MemoryNotFoundError
from aegis.l4_memory.models import KGEntity, KGRelationship, ProvenanceChain
from aegis.l4_memory.types import EntityKind, RelationshipKind

__all__ = ["KnowledgeGraph"]


# ---------------------------------------------------------------------------
# Row helpers
# ---------------------------------------------------------------------------


def _row_to_entity(row: dict[str, Any]) -> KGEntity:
    return KGEntity(
        id=UUID(row["id"]),
        kind=EntityKind(row["kind"]),
        key=row["key_"],
        label=row["label"],
        namespace=row.get("namespace", "global"),
        privacy_tier=row.get("privacy_tier", "P2"),
        attributes=json.loads(row.get("attrs_json") or "{}"),
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
        source_memory_id=UUID(row["source_memory_id"]) if row.get("source_memory_id") else None,
    )


def _entity_to_params(entity: KGEntity) -> dict[str, Any]:
    return {
        "id": str(entity.id),
        "kind": entity.kind.value,
        "key_": entity.key,
        "label": entity.label,
        "namespace": entity.namespace,
        "privacy_tier": entity.privacy_tier,
        "attrs_json": json.dumps(entity.attributes, default=str),
        "source_memory_id": str(entity.source_memory_id) if entity.source_memory_id else None,
        "created_at": entity.created_at,
        "updated_at": entity.updated_at,
    }


def _row_to_relationship(row: dict[str, Any]) -> KGRelationship:
    provenance = ProvenanceChain.model_validate(
        json.loads(row.get("provenance_json") or '{"links":[{"kind":"system_generated","subject":"kg"}]}')
    )
    return KGRelationship(
        id=UUID(row["id"]),
        subject_id=UUID(row["subject_id"]),
        object_id=UUID(row["object_id"]),
        kind=RelationshipKind(row["kind"]),
        custom_kind=row.get("custom_kind"),
        confidence=float(row.get("confidence", 0.8)),
        privacy_tier=row.get("privacy_tier", "P2"),
        attributes=json.loads(row.get("attrs_json") or "{}"),
        provenance=provenance,
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
        version=int(row.get("version", 1)),
    )


def _rel_to_params(rel: KGRelationship, is_draft: bool = False) -> dict[str, Any]:
    return {
        "id": str(rel.id),
        "subject_id": str(rel.subject_id),
        "object_id": str(rel.object_id),
        "kind": rel.kind.value,
        "custom_kind": rel.custom_kind,
        "confidence": rel.confidence,
        "is_draft": int(is_draft),
        "privacy_tier": rel.privacy_tier,
        "attrs_json": json.dumps(rel.attributes, default=str),
        "provenance_json": rel.provenance.model_dump_json(),
        "created_at": rel.created_at,
        "updated_at": rel.updated_at,
        "version": rel.version,
    }


# ---------------------------------------------------------------------------
# KnowledgeGraph
# ---------------------------------------------------------------------------


class KnowledgeGraph:
    """SQLite-backed Knowledge Graph with in-memory BFS traversal.

    The graph is loaded-on-demand for traversal (subgraph pattern).
    Draft edges (is_draft=True) are stored but NOT traversed by default.

    Args:
        conn: Open aiosqlite connection (shared with SQLiteMemoryStore).
    """

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    # ------------------------------------------------------------------
    # Entity CRUD
    # ------------------------------------------------------------------

    async def upsert_entity(self, entity: KGEntity) -> KGEntity:
        """Insert or update a KGEntity. Keyed on (key, namespace)."""
        params = _entity_to_params(entity)
        now = time.time()

        async with self._conn.execute(
            "SELECT id FROM kg_entities WHERE key_ = ? AND namespace = ?",
            (entity.key, entity.namespace),
        ) as cur:
            existing = await cur.fetchone()

        if existing and existing["id"] != str(entity.id):
            # Key taken by different entity — update in place
            await self._conn.execute(
                """UPDATE kg_entities SET kind=?, label=?, privacy_tier=?,
                   attrs_json=?, source_memory_id=?, updated_at=?
                   WHERE key_=? AND namespace=?""",
                (
                    params["kind"], params["label"], params["privacy_tier"],
                    params["attrs_json"], params["source_memory_id"], now,
                    entity.key, entity.namespace,
                ),
            )
        else:
            await self._conn.execute(
                """INSERT OR REPLACE INTO kg_entities
                   (id, kind, key_, label, namespace, privacy_tier, attrs_json,
                    source_memory_id, created_at, updated_at)
                   VALUES (:id, :kind, :key_, :label, :namespace, :privacy_tier,
                    :attrs_json, :source_memory_id, :created_at, :updated_at)""",
                params,
            )
        await self._conn.commit()
        return entity

    async def get_entity(self, entity_id: UUID) -> KGEntity:
        """Fetch entity by UUID. Raises MemoryNotFoundError if absent."""
        async with self._conn.execute(
            "SELECT * FROM kg_entities WHERE id = ?", (str(entity_id),)
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            raise MemoryNotFoundError(f"KGEntity {entity_id} not found.")
        return _row_to_entity(dict(row))

    async def get_entity_by_key(self, key: str, namespace: str = "global") -> KGEntity | None:
        """Fetch entity by stable key + namespace."""
        async with self._conn.execute(
            "SELECT * FROM kg_entities WHERE key_ = ? AND namespace = ?", (key, namespace)
        ) as cur:
            row = await cur.fetchone()
        return _row_to_entity(dict(row)) if row else None

    async def delete_entity(self, entity_id: UUID) -> bool:
        """Delete entity and all its relationships."""
        cursor = await self._conn.execute(
            "DELETE FROM kg_relationships WHERE subject_id=? OR object_id=?",
            (str(entity_id), str(entity_id)),
        )
        cursor2 = await self._conn.execute(
            "DELETE FROM kg_entities WHERE id=?", (str(entity_id),)
        )
        changed = cursor2.rowcount > 0
        await self._conn.commit()
        return changed

    async def list_entities(
        self,
        *,
        kind: EntityKind | None = None,
        namespace: str | None = None,
        limit: int = 100,
    ) -> list[KGEntity]:
        """List entities with optional filters."""
        where: list[str] = []
        params: list[Any] = []
        if kind is not None:
            where.append("kind = ?")
            params.append(kind.value)
        if namespace is not None:
            where.append("namespace = ?")
            params.append(namespace)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        sql = f"SELECT * FROM kg_entities {clause} ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        async with self._conn.execute(sql, params) as cur:
            rows = await cur.fetchall()
        return [_row_to_entity(dict(row)) for row in rows]

    # ------------------------------------------------------------------
    # Relationship CRUD
    # ------------------------------------------------------------------

    async def upsert_relationship(
        self, rel: KGRelationship, *, is_draft: bool = False
    ) -> KGRelationship:
        """Insert or update a directed relationship edge."""
        params = _rel_to_params(rel, is_draft=is_draft)
        await self._conn.execute(
            """INSERT OR REPLACE INTO kg_relationships
               (id, subject_id, object_id, kind, custom_kind, confidence, is_draft,
                privacy_tier, attrs_json, provenance_json, created_at, updated_at, version)
               VALUES (:id, :subject_id, :object_id, :kind, :custom_kind, :confidence,
                :is_draft, :privacy_tier, :attrs_json, :provenance_json,
                :created_at, :updated_at, :version)""",
            params,
        )
        await self._conn.commit()
        return rel

    async def get_relationship(self, rel_id: UUID) -> KGRelationship:
        async with self._conn.execute(
            "SELECT * FROM kg_relationships WHERE id = ?", (str(rel_id),)
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            raise MemoryNotFoundError(f"KGRelationship {rel_id} not found.")
        return _row_to_relationship(dict(row))

    async def delete_relationship(self, rel_id: UUID) -> bool:
        async with self._conn.execute(
            "DELETE FROM kg_relationships WHERE id = ?", (str(rel_id),)
        ) as cur:
            changed = cur.rowcount > 0
        await self._conn.commit()
        return changed

    async def confirm_draft_edge(self, rel_id: UUID) -> bool:
        """Promote a draft edge to confirmed (is_draft=0)."""
        now = time.time()
        async with self._conn.execute(
            "UPDATE kg_relationships SET is_draft = 0, updated_at = ? WHERE id = ? AND is_draft = 1",
            (now, str(rel_id)),
        ) as cur:
            changed = cur.rowcount > 0
        await self._conn.commit()
        return changed

    async def get_neighbors(
        self,
        entity_id: UUID,
        *,
        direction: str = "outgoing",  # "outgoing" | "incoming" | "both"
        rel_kinds: list[RelationshipKind] | None = None,
        include_draft: bool = False,
        limit: int = 50,
    ) -> list[tuple[KGRelationship, KGEntity]]:
        """Return (relationship, neighbor_entity) pairs for an entity."""
        draft_clause = "" if include_draft else "AND r.is_draft = 0"

        kind_clause = ""
        kind_params: list[Any] = []
        if rel_kinds:
            placeholders = ",".join("?" * len(rel_kinds))
            kind_clause = f"AND r.kind IN ({placeholders})"
            kind_params = [k.value for k in rel_kinds]

        results: list[tuple[KGRelationship, KGEntity]] = []

        if direction in ("outgoing", "both"):
            # Fetch only relationship columns to avoid join column clash
            sql = f"""
                SELECT r.id, r.subject_id, r.object_id, r.kind, r.custom_kind,
                       r.confidence, r.is_draft, r.privacy_tier as rel_privacy_tier,
                       r.attrs_json as rel_attrs_json, r.provenance_json,
                       r.created_at as rel_created_at, r.updated_at as rel_updated_at,
                       r.version as rel_version
                FROM kg_relationships r
                WHERE r.subject_id = ? {draft_clause} {kind_clause}
                LIMIT ?
            """
            params = [str(entity_id)] + kind_params + [limit]
            async with self._conn.execute(sql, params) as cur:
                rel_rows = await cur.fetchall()
            for row in rel_rows:
                d = dict(row)
                rel_d = {
                    "id": d["id"], "subject_id": d["subject_id"],
                    "object_id": d["object_id"], "kind": d["kind"],
                    "custom_kind": d.get("custom_kind"),
                    "confidence": d["confidence"],
                    "privacy_tier": d["rel_privacy_tier"],
                    "attrs_json": d["rel_attrs_json"],
                    "provenance_json": d["provenance_json"],
                    "created_at": d["rel_created_at"],
                    "updated_at": d["rel_updated_at"],
                    "version": d["rel_version"],
                }
                rel = _row_to_relationship(rel_d)
                # Fetch entity separately to avoid column name clash
                async with self._conn.execute(
                    "SELECT * FROM kg_entities WHERE id = ?", (d["object_id"],)
                ) as ecur:
                    erow = await ecur.fetchone()
                if erow:
                    ent = _row_to_entity(dict(erow))
                    results.append((rel, ent))

        if direction in ("incoming", "both"):
            sql = f"""
                SELECT r.id, r.subject_id, r.object_id, r.kind, r.custom_kind,
                       r.confidence, r.is_draft, r.privacy_tier as rel_privacy_tier,
                       r.attrs_json as rel_attrs_json, r.provenance_json,
                       r.created_at as rel_created_at, r.updated_at as rel_updated_at,
                       r.version as rel_version
                FROM kg_relationships r
                WHERE r.object_id = ? {draft_clause} {kind_clause}
                LIMIT ?
            """
            params = [str(entity_id)] + kind_params + [limit]
            async with self._conn.execute(sql, params) as cur:
                rel_rows = await cur.fetchall()
            for row in rel_rows:
                d = dict(row)
                rel_d = {
                    "id": d["id"], "subject_id": d["subject_id"],
                    "object_id": d["object_id"], "kind": d["kind"],
                    "custom_kind": d.get("custom_kind"),
                    "confidence": d["confidence"],
                    "privacy_tier": d["rel_privacy_tier"],
                    "attrs_json": d["rel_attrs_json"],
                    "provenance_json": d["provenance_json"],
                    "created_at": d["rel_created_at"],
                    "updated_at": d["rel_updated_at"],
                    "version": d["rel_version"],
                }
                rel = _row_to_relationship(rel_d)
                async with self._conn.execute(
                    "SELECT * FROM kg_entities WHERE id = ?", (d["subject_id"],)
                ) as ecur:
                    erow = await ecur.fetchone()
                if erow:
                    ent = _row_to_entity(dict(erow))
                    results.append((rel, ent))

        return results[:limit]

    async def bfs(
        self,
        start_entity_id: UUID,
        *,
        max_depth: int = 3,
        rel_kinds: list[RelationshipKind] | None = None,
        include_draft: bool = False,
    ) -> list[KGEntity]:
        """BFS traversal from start entity. Returns all reachable entities."""
        visited: set[str] = {str(start_entity_id)}
        queue: deque[tuple[UUID, int]] = deque([(start_entity_id, 0)])
        result: list[KGEntity] = []

        while queue:
            current_id, depth = queue.popleft()
            if depth >= max_depth:
                continue
            neighbors = await self.get_neighbors(
                current_id,
                direction="outgoing",
                rel_kinds=rel_kinds,
                include_draft=include_draft,
            )
            for _rel, entity in neighbors:
                eid = str(entity.id)
                if eid not in visited:
                    visited.add(eid)
                    result.append(entity)
                    queue.append((entity.id, depth + 1))

        return result

    async def path_exists(
        self,
        from_entity_id: UUID,
        to_entity_id: UUID,
        *,
        max_depth: int = 5,
    ) -> bool:
        """Return True if a path exists between two entities within max_depth."""
        reachable = await self.bfs(from_entity_id, max_depth=max_depth)
        target = str(to_entity_id)
        return any(str(e.id) == target for e in reachable)

    async def count_entities(self, namespace: str | None = None) -> int:
        where = "WHERE namespace = ?" if namespace else ""
        params = [namespace] if namespace else []
        async with self._conn.execute(
            f"SELECT COUNT(*) as cnt FROM kg_entities {where}", params
        ) as cur:
            row = await cur.fetchone()
        return row["cnt"] if row else 0

    async def count_relationships(self, include_draft: bool = False) -> int:
        where = "" if include_draft else "WHERE is_draft = 0"
        async with self._conn.execute(
            f"SELECT COUNT(*) as cnt FROM kg_relationships {where}"
        ) as cur:
            row = await cur.fetchone()
        return row["cnt"] if row else 0
