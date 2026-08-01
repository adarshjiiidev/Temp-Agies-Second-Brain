"""L4 Memory — SQLite-backed async memory store.

Implements durable persistence for all 9 memory tiers (T0–T8) using
aiosqlite with WAL mode. Provides:
  - CRUD operations on MemoryRecord (stored as JSON blobs).
  - FTS5 full-text index on content + summary for keyword search.
  - Metadata filtering (tier, status, importance, privacy_tier, namespace).
  - Version history table (append-only previous states).
  - Atomic upsert-by-key: same key = version bump.
  - In-memory mode for tests (path=None).

Import safety: l4_memory.types + l4_memory.models + l4_memory.exceptions
+ aiosqlite + stdlib ONLY. No L1/L2/L3 imports.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any
from uuid import UUID

import aiosqlite

from aegis.l4_memory.exceptions import (
    MemoryAlreadyExistsError,
    MemoryNotFoundError,
    MemoryStorageError,
)
from aegis.l4_memory.models import MemoryRecord, MemoryVersion
from aegis.l4_memory.types import (
    Importance,
    MemoryStatus,
    MemoryTier,
)

__all__ = ["SQLiteMemoryStore", "InMemoryStore"]

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS memory_records (
    id          TEXT PRIMARY KEY,
    key_        TEXT NOT NULL,
    namespace   TEXT NOT NULL DEFAULT 'global',
    tier        TEXT NOT NULL,
    kind        TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'draft',
    importance  TEXT NOT NULL DEFAULT 'normal',
    privacy_tier TEXT NOT NULL DEFAULT 'P2',
    confidence  REAL NOT NULL DEFAULT 0.5,
    is_pinned   INTEGER NOT NULL DEFAULT 0,
    is_draft    INTEGER NOT NULL DEFAULT 1,
    version     INTEGER NOT NULL DEFAULT 1,
    session_id  TEXT,
    project_id  TEXT,
    user_id     TEXT,
    tags        TEXT NOT NULL DEFAULT '[]',
    source      TEXT,
    expires_at  REAL,
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL,
    last_accessed_at REAL,
    access_count INTEGER NOT NULL DEFAULT 0,
    content_json TEXT NOT NULL,
    summary     TEXT,
    provenance_json TEXT NOT NULL,
    related_ids_json TEXT NOT NULL DEFAULT '[]'
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_mem_key_ns
    ON memory_records(key_, namespace);
CREATE INDEX IF NOT EXISTS idx_mem_tier
    ON memory_records(tier, status);
CREATE INDEX IF NOT EXISTS idx_mem_status
    ON memory_records(status);
CREATE INDEX IF NOT EXISTS idx_mem_project
    ON memory_records(project_id);
CREATE INDEX IF NOT EXISTS idx_mem_session
    ON memory_records(session_id);
CREATE INDEX IF NOT EXISTS idx_mem_expires
    ON memory_records(expires_at);
CREATE INDEX IF NOT EXISTS idx_mem_namespace
    ON memory_records(namespace);

CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
    id UNINDEXED,
    content_text,
    summary_text,
    tags_text,
    tokenize='porter ascii'
);

CREATE TRIGGER IF NOT EXISTS mem_fts_insert AFTER INSERT ON memory_records BEGIN
    INSERT INTO memory_fts(id, content_text, summary_text, tags_text)
    VALUES (new.id,
            COALESCE(CAST(new.content_json AS TEXT), ''),
            COALESCE(new.summary, ''),
            COALESCE(new.tags, ''));
END;

CREATE TRIGGER IF NOT EXISTS mem_fts_update AFTER UPDATE ON memory_records BEGIN
    DELETE FROM memory_fts WHERE id = old.id;
    INSERT INTO memory_fts(id, content_text, summary_text, tags_text)
    VALUES (new.id,
            COALESCE(CAST(new.content_json AS TEXT), ''),
            COALESCE(new.summary, ''),
            COALESCE(new.tags, ''));
END;

CREATE TRIGGER IF NOT EXISTS mem_fts_delete AFTER DELETE ON memory_records BEGIN
    DELETE FROM memory_fts WHERE id = old.id;
END;

CREATE TABLE IF NOT EXISTS memory_versions (
    id          TEXT NOT NULL,
    version     INTEGER NOT NULL,
    content_json TEXT NOT NULL,
    importance  TEXT NOT NULL,
    confidence  REAL NOT NULL,
    status      TEXT NOT NULL,
    updated_at  REAL NOT NULL,
    updated_by  TEXT NOT NULL,
    change_note TEXT,
    PRIMARY KEY (id, version)
);

CREATE TABLE IF NOT EXISTS kg_entities (
    id          TEXT PRIMARY KEY,
    kind        TEXT NOT NULL,
    key_        TEXT NOT NULL,
    label       TEXT NOT NULL,
    namespace   TEXT NOT NULL DEFAULT 'global',
    privacy_tier TEXT NOT NULL DEFAULT 'P2',
    attrs_json  TEXT NOT NULL DEFAULT '{}',
    source_memory_id TEXT,
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_kg_ent_key
    ON kg_entities(key_, namespace);
CREATE INDEX IF NOT EXISTS idx_kg_ent_kind
    ON kg_entities(kind);

CREATE TABLE IF NOT EXISTS kg_relationships (
    id          TEXT PRIMARY KEY,
    subject_id  TEXT NOT NULL,
    object_id   TEXT NOT NULL,
    kind        TEXT NOT NULL,
    custom_kind TEXT,
    confidence  REAL NOT NULL DEFAULT 0.8,
    is_draft    INTEGER NOT NULL DEFAULT 0,
    privacy_tier TEXT NOT NULL DEFAULT 'P2',
    attrs_json  TEXT NOT NULL DEFAULT '{}',
    provenance_json TEXT NOT NULL DEFAULT '{}',
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL,
    version     INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (subject_id) REFERENCES kg_entities(id),
    FOREIGN KEY (object_id)  REFERENCES kg_entities(id)
);

CREATE INDEX IF NOT EXISTS idx_kg_rel_subject
    ON kg_relationships(subject_id, is_draft);
CREATE INDEX IF NOT EXISTS idx_kg_rel_object
    ON kg_relationships(object_id, is_draft);
CREATE INDEX IF NOT EXISTS idx_kg_rel_kind
    ON kg_relationships(kind);
"""

# ---------------------------------------------------------------------------
# Row → MemoryRecord helpers
# ---------------------------------------------------------------------------


def _row_to_record(row: dict[str, Any]) -> MemoryRecord:
    """Convert a database row dict to a MemoryRecord."""
    from aegis.l4_memory.models import ProvenanceChain

    content = json.loads(row["content_json"])
    provenance_data = json.loads(row["provenance_json"])
    related_ids_raw = json.loads(row.get("related_ids_json") or "[]")
    tags_raw = json.loads(row.get("tags") or "[]")

    # Reconstruct provenance (stored as serialized chain)
    provenance = ProvenanceChain.model_validate(provenance_data)

    return MemoryRecord(
        id=UUID(row["id"]),
        key=row["key_"],
        namespace=row["namespace"],
        tier=MemoryTier(row["tier"]),
        kind=row["kind"],
        status=MemoryStatus(row["status"]),
        importance=Importance(row["importance"]),
        privacy_tier=row["privacy_tier"],
        confidence=float(row["confidence"]),
        is_pinned=bool(row["is_pinned"]),
        is_draft=bool(row["is_draft"]),
        version=int(row["version"]),
        session_id=row.get("session_id"),
        project_id=row.get("project_id"),
        user_id=row.get("user_id"),
        tags=frozenset(tags_raw),
        source=row.get("source"),
        expires_at=row.get("expires_at"),
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
        last_accessed_at=row.get("last_accessed_at"),
        access_count=int(row.get("access_count") or 0),
        content=content,
        summary=row.get("summary"),
        provenance=provenance,
        related_ids=frozenset(UUID(rid) for rid in related_ids_raw),
        version_history=tuple(),  # version history loaded separately
    )


def _record_to_params(record: MemoryRecord) -> dict[str, Any]:
    """Convert a MemoryRecord to SQL parameter dict."""
    return {
        "id": str(record.id),
        "key_": record.key,
        "namespace": record.namespace,
        "tier": record.tier.value,
        "kind": record.kind if isinstance(record.kind, str) else record.kind.value,
        "status": record.status.value,
        "importance": record.importance.value,
        "privacy_tier": record.privacy_tier,
        "confidence": record.confidence,
        "is_pinned": int(record.is_pinned),
        "is_draft": int(record.is_draft),
        "version": record.version,
        "session_id": record.session_id,
        "project_id": record.project_id,
        "user_id": record.user_id,
        "tags": json.dumps(sorted(record.tags)),
        "source": record.source,
        "expires_at": record.expires_at,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "last_accessed_at": record.last_accessed_at,
        "access_count": record.access_count,
        "content_json": json.dumps(record.content, default=str),
        "summary": record.summary,
        "provenance_json": record.provenance.model_dump_json(),
        "related_ids_json": json.dumps([str(rid) for rid in sorted(record.related_ids, key=str)]),
    }


# ---------------------------------------------------------------------------
# SQLiteMemoryStore
# ---------------------------------------------------------------------------


class SQLiteMemoryStore:
    """Async SQLite-backed store for MemoryRecord, KGEntity, KGRelationship.

    Usage::

        store = SQLiteMemoryStore(path="data/memory.db")
        await store.initialize()
        await store.upsert(record)
        rec = await store.get_by_key("project/aegis/desc", "global")
        await store.close()

    Pass path=None for in-memory (test) mode.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = str(path) if path is not None else ":memory:"
        self._conn: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Open connection and apply schema."""
        async with self._lock:
            if self._conn is not None:
                return
            self._conn = await aiosqlite.connect(self._path)
            self._conn.row_factory = aiosqlite.Row
            await self._conn.executescript(_SCHEMA)
            await self._conn.commit()

    async def close(self) -> None:
        async with self._lock:
            if self._conn is not None:
                await self._conn.close()
                self._conn = None

    def _require_conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise MemoryStorageError("SQLiteMemoryStore not initialized. Call await initialize() first.")
        return self._conn

    # ------------------------------------------------------------------
    # MemoryRecord CRUD
    # ------------------------------------------------------------------

    async def upsert(self, record: MemoryRecord) -> MemoryRecord:
        """Insert or version-update a MemoryRecord.

        If a record with the same (key, namespace) exists:
          - Save current state as MemoryVersion.
          - Bump version number.
          - Update in place.

        Returns the stored record (with version updated).
        """
        conn = self._require_conn()
        params = _record_to_params(record)

        async with self._lock:
            # Check for existing by key+namespace
            async with conn.execute(
                "SELECT id, version, content_json, importance, confidence, status, updated_at "
                "FROM memory_records WHERE key_ = :key_ AND namespace = :namespace",
                {"key_": record.key, "namespace": record.namespace},
            ) as cur:
                existing = await cur.fetchone()

            if existing is not None:
                existing_id = existing["id"]
                existing_version = existing["version"]

                # If different UUID → conflict (same key but different identity)
                # For upsert semantics: the key wins; archive old version.
                if existing_id != str(record.id):
                    # Store old state as version history
                    await conn.execute(
                        """INSERT OR IGNORE INTO memory_versions
                           (id, version, content_json, importance, confidence, status, updated_at, updated_by, change_note)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            existing_id,
                            existing_version,
                            existing["content_json"],
                            existing["importance"],
                            existing["confidence"],
                            existing["status"],
                            existing["updated_at"],
                            "system:upsert_key_conflict",
                            "key conflict — superseded by new record",
                        ),
                    )
                    # Delete old record so our new one can take this key
                    await conn.execute(
                        "DELETE FROM memory_records WHERE id = ?", (existing_id,)
                    )
                else:
                    # Same UUID — version bump, save history
                    new_version = existing_version + 1
                    await conn.execute(
                        """INSERT OR IGNORE INTO memory_versions
                           (id, version, content_json, importance, confidence, status, updated_at, updated_by)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            existing_id,
                            existing_version,
                            existing["content_json"],
                            existing["importance"],
                            existing["confidence"],
                            existing["status"],
                            existing["updated_at"],
                            "system:update",
                        ),
                    )
                    params["version"] = new_version
                    record = record.model_copy(update={"version": new_version})
                    params = _record_to_params(record)

            await conn.execute(
                """INSERT OR REPLACE INTO memory_records
                   (id, key_, namespace, tier, kind, status, importance, privacy_tier,
                    confidence, is_pinned, is_draft, version, session_id, project_id,
                    user_id, tags, source, expires_at, created_at, updated_at,
                    last_accessed_at, access_count, content_json, summary,
                    provenance_json, related_ids_json)
                   VALUES
                   (:id, :key_, :namespace, :tier, :kind, :status, :importance, :privacy_tier,
                    :confidence, :is_pinned, :is_draft, :version, :session_id, :project_id,
                    :user_id, :tags, :source, :expires_at, :created_at, :updated_at,
                    :last_accessed_at, :access_count, :content_json, :summary,
                    :provenance_json, :related_ids_json)""",
                params,
            )
            await conn.commit()

        return record

    async def get(self, record_id: UUID) -> MemoryRecord:
        """Fetch a MemoryRecord by UUID. Raises MemoryNotFoundError if absent."""
        conn = self._require_conn()
        async with conn.execute(
            "SELECT * FROM memory_records WHERE id = ?", (str(record_id),)
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            raise MemoryNotFoundError(f"MemoryRecord {record_id} not found.")
        return _row_to_record(dict(row))

    async def get_by_key(self, key: str, namespace: str = "global") -> MemoryRecord | None:
        """Fetch a MemoryRecord by stable key + namespace. Returns None if absent."""
        conn = self._require_conn()
        async with conn.execute(
            "SELECT * FROM memory_records WHERE key_ = ? AND namespace = ?",
            (key, namespace),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return _row_to_record(dict(row))

    async def delete(self, record_id: UUID) -> bool:
        """Soft-delete: set status=DELETED. Returns True if found."""
        conn = self._require_conn()
        now = time.time()
        async with self._lock:
            cursor = await conn.execute(
                "UPDATE memory_records SET status = 'deleted', updated_at = ? WHERE id = ?",
                (now, str(record_id)),
            )
            changed = cursor.rowcount > 0
            await conn.commit()
        return changed

    async def hard_delete(self, record_id: UUID) -> bool:
        """Permanently remove a record (no recovery)."""
        conn = self._require_conn()
        async with self._lock:
            cursor = await conn.execute(
                "DELETE FROM memory_records WHERE id = ?", (str(record_id),)
            )
            changed = cursor.rowcount > 0
            await conn.commit()
        return changed

    async def touch_access(self, record_id: UUID) -> None:
        """Update last_accessed_at and increment access_count."""
        conn = self._require_conn()
        now = time.time()
        # Direct execute (no async-with needed for non-SELECT on plain conn)
        await conn.execute(
            """UPDATE memory_records
               SET last_accessed_at = ?, access_count = access_count + 1
               WHERE id = ?""",
            (now, str(record_id)),
        )
        await conn.commit()

    # ------------------------------------------------------------------
    # Filtering / search
    # ------------------------------------------------------------------

    async def list_records(
        self,
        *,
        tiers: list[MemoryTier] | None = None,
        namespace: str | None = None,
        project_id: str | None = None,
        session_id: str | None = None,
        status: MemoryStatus | None = None,
        importance: Importance | None = None,
        privacy_tier: str | None = None,
        min_confidence: float | None = None,
        include_expired: bool = False,
        include_deleted: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MemoryRecord]:
        """List records with optional filters."""
        conn = self._require_conn()
        where: list[str] = []
        params: list[Any] = []

        if tiers:
            placeholders = ",".join("?" * len(tiers))
            where.append(f"tier IN ({placeholders})")
            params.extend(t.value for t in tiers)

        if namespace is not None:
            where.append("namespace = ?")
            params.append(namespace)

        if project_id is not None:
            where.append("project_id = ?")
            params.append(project_id)

        if session_id is not None:
            where.append("session_id = ?")
            params.append(session_id)

        if status is not None:
            where.append("status = ?")
            params.append(status.value)
        elif not include_deleted:
            where.append("status != 'deleted'")

        if importance is not None:
            where.append("importance = ?")
            params.append(importance.value)

        if privacy_tier is not None:
            where.append("privacy_tier = ?")
            params.append(privacy_tier)

        if min_confidence is not None:
            where.append("confidence >= ?")
            params.append(min_confidence)

        if not include_expired:
            now = time.time()
            where.append(f"(expires_at IS NULL OR expires_at > {now})")

        clause = ("WHERE " + " AND ".join(where)) if where else ""
        query = f"""
            SELECT * FROM memory_records
            {clause}
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        async with conn.execute(query, params) as cur:
            rows = await cur.fetchall()
        return [_row_to_record(dict(row)) for row in rows]

    async def keyword_search(
        self,
        query_text: str,
        *,
        tiers: list[MemoryTier] | None = None,
        namespace: str | None = None,
        status: MemoryStatus | None = None,
        limit: int = 20,
    ) -> list[MemoryRecord]:
        """FTS5 keyword search over content + summary + tags."""
        conn = self._require_conn()

        # Escape FTS5 query (simple: wrap in quotes for phrase search)
        fts_query = '"%s"' % query_text.replace('"', '""')

        where_parts: list[str] = ["memory_fts MATCH ?"]
        fts_params: list[Any] = [fts_query]

        # Join back to base table for metadata filters
        join_where: list[str] = []
        if tiers:
            placeholders = ",".join("?" * len(tiers))
            join_where.append(f"r.tier IN ({placeholders})")
            fts_params.extend(t.value for t in tiers)

        if namespace is not None:
            join_where.append("r.namespace = ?")
            fts_params.append(namespace)

        if status is not None:
            join_where.append("r.status = ?")
            fts_params.append(status.value)
        else:
            join_where.append("r.status = 'active'")

        now = time.time()
        join_where.append(f"(r.expires_at IS NULL OR r.expires_at > {now})")

        join_clause = ("AND " + " AND ".join(join_where)) if join_where else ""

        sql = f"""
            SELECT r.*
            FROM memory_fts
            JOIN memory_records r ON r.id = memory_fts.id
            WHERE memory_fts MATCH ?
            {join_clause}
            ORDER BY rank
            LIMIT ?
        """
        fts_params.append(limit)

        try:
            async with conn.execute(sql, fts_params) as cur:
                rows = await cur.fetchall()
            return [_row_to_record(dict(row)) for row in rows]
        except Exception as exc:
            # FTS5 may not be available in all SQLite builds; graceful fallback
            return await self._fallback_keyword_search(query_text, tiers=tiers, namespace=namespace, limit=limit)

    async def _fallback_keyword_search(
        self,
        query_text: str,
        *,
        tiers: list[MemoryTier] | None = None,
        namespace: str | None = None,
        limit: int = 20,
    ) -> list[MemoryRecord]:
        """LIKE-based fallback if FTS5 is unavailable."""
        conn = self._require_conn()
        like_param = f"%{query_text}%"
        where: list[str] = [
            "(content_json LIKE ? OR summary LIKE ? OR tags LIKE ?)",
            "status = 'active'",
        ]
        params: list[Any] = [like_param, like_param, like_param]

        if tiers:
            placeholders = ",".join("?" * len(tiers))
            where.append(f"tier IN ({placeholders})")
            params.extend(t.value for t in tiers)

        if namespace is not None:
            where.append("namespace = ?")
            params.append(namespace)

        clause = "WHERE " + " AND ".join(where)
        sql = f"SELECT * FROM memory_records {clause} ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)

        async with conn.execute(sql, params) as cur:
            rows = await cur.fetchall()
        return [_row_to_record(dict(row)) for row in rows]

    async def get_version_history(self, record_id: UUID) -> list[MemoryVersion]:
        """Fetch all previous versions for a record (oldest first)."""
        conn = self._require_conn()
        async with conn.execute(
            """SELECT version, content_json, importance, confidence, status,
                      updated_at, updated_by, change_note
               FROM memory_versions WHERE id = ?
               ORDER BY version ASC""",
            (str(record_id),),
        ) as cur:
            rows = await cur.fetchall()

        versions: list[MemoryVersion] = []
        for row in rows:
            versions.append(
                MemoryVersion(
                    version=row["version"],
                    content=json.loads(row["content_json"]),
                    importance=Importance(row["importance"]),
                    confidence=float(row["confidence"]),
                    status=MemoryStatus(row["status"]),
                    updated_at=float(row["updated_at"]),
                    updated_by=row["updated_by"],
                    change_note=row["change_note"],
                )
            )
        return versions

    # ------------------------------------------------------------------
    # KG Entity CRUD (delegated to KnowledgeGraph module; stubs here)
    # ------------------------------------------------------------------

    async def count(
        self,
        *,
        tiers: list[MemoryTier] | None = None,
        namespace: str | None = None,
        status: MemoryStatus | None = None,
    ) -> dict[str, int]:
        """Return counts grouped by tier."""
        conn = self._require_conn()
        where: list[str] = []
        params: list[Any] = []

        if tiers:
            placeholders = ",".join("?" * len(tiers))
            where.append(f"tier IN ({placeholders})")
            params.extend(t.value for t in tiers)
        if namespace is not None:
            where.append("namespace = ?")
            params.append(namespace)
        if status is not None:
            where.append("status = ?")
            params.append(status.value)

        clause = ("WHERE " + " AND ".join(where)) if where else ""
        sql = f"SELECT tier, COUNT(*) as cnt FROM memory_records {clause} GROUP BY tier"

        async with conn.execute(sql, params) as cur:
            rows = await cur.fetchall()
        return {row["tier"]: row["cnt"] for row in rows}
