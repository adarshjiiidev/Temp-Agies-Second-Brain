"""L2 Persistence: in-process SQLite-backed KVStore + DocStore.

Fully implements the L1 Protocols declared in l1_core.interfaces.storage.
Future layers can swap-in networked stores without breaking contracts.

Prompt 02 SCOPE: VectorStore / GraphStore are NOT implemented (they require embeddings/ML).
We provide typed NoOp* classes with typed NotImplementedError so L3+ can replace them cleanly.
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator

import aiosqlite

from aegis.l1_core.errors import ErrorCode, NotFoundError, StoreError
from aegis.l2_foundation.telemetry.logger import get_logger

log = get_logger(__name__)


@dataclass
class DocRecord:
    """SQLiteDocStore local document (synchronous mirror of L1 DocStore semantics)."""
    doc_id: str
    uri: str | None = None
    title: str | None = None
    content: str | None = None
    content_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float | None = None
    updated_at: float | None = None


# ---------- aiosqlite convenience wrapper ----------

_SCHEMA_KV = """
CREATE TABLE IF NOT EXISTS kv_store (
    namespace TEXT NOT NULL,
    k TEXT NOT NULL,
    v BLOB NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (namespace, k)
);
CREATE INDEX IF NOT EXISTS idx_kv_ns ON kv_store(namespace);

CREATE TABLE IF NOT EXISTS doc_store (
    namespace TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    uri TEXT,
    title TEXT,
    content TEXT,
    content_type TEXT,
    metadata_json TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (namespace, doc_id)
);
CREATE INDEX IF NOT EXISTS idx_doc_uri ON doc_store(namespace, uri);
CREATE INDEX IF NOT EXISTS idx_doc_created ON doc_store(namespace, created_at);
"""


class SQLiteKVStore:
    """Synchronous + async-friendly KV store.
    Interface matches L1 KVStore Protocol; implements get/put/delete/keys/contains/clear."""

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path else None  # None => in-memory
        self._sync_conn: sqlite3.Connection | None = None
        self._lock = threading.RLock()
        # Async state (created lazily inside event loop)
        self._async_conn: aiosqlite.Connection | None = None

    # ---------- lifecycle ----------

    def start(self) -> None:
        with self._lock:
            if self._sync_conn is not None:
                return
            self._sync_conn = sqlite3.connect(
                str(self._path) if self._path else ":memory:",
                check_same_thread=False,
                timeout=10.0,
                isolation_level=None,
            )
            self._sync_conn.row_factory = sqlite3.Row
            self._sync_conn.executescript(_SCHEMA_KV)
            self._sync_conn.commit()

    def stop(self) -> None:
        with self._lock:
            if self._sync_conn is not None:
                self._sync_conn.close()
                self._sync_conn = None

    async def astart(self) -> None:
        async with aiosqlite.connect(str(self._path) if self._path else ":memory:") as conn:
            self._async_conn = conn
            await conn.executescript(_SCHEMA_KV)
            await conn.commit()

    async def astop(self) -> None:
        if self._async_conn is not None:
            await self._async_conn.close()
            self._async_conn = None

    # ---------- helpers ----------

    def _ensure_sync(self) -> sqlite3.Connection:
        if self._sync_conn is None:
            self.start()
        assert self._sync_conn is not None
        return self._sync_conn

    def _serialize(self, value: Any) -> bytes:  # noqa: ANN401
        return json.dumps(value, default=str, ensure_ascii=False).encode("utf-8")

    def _deserialize(self, raw: bytes) -> Any:  # noqa: ANN401
        return json.loads(raw.decode("utf-8"))

    # ---------- sync API ----------

    def get(self, key: str, *, namespace: str = "default") -> Any:
        conn = self._ensure_sync()
        with self._lock:
            row = conn.execute(
                "SELECT v FROM kv_store WHERE namespace=? AND k=?", (namespace, key)
            ).fetchone()
        if row is None:
            raise NotFoundError(ErrorCode.E20401, f"kv key {namespace}/{key} not found")
        return self._deserialize(bytes(row["v"]))

    def get_or_default(self, key: str, default: Any, *, namespace: str = "default") -> Any:
        try:
            return self.get(key, namespace=namespace)
        except NotFoundError:
            return default

    def put(self, key: str, value: Any, *, namespace: str = "default") -> None:
        conn = self._ensure_sync()
        with self._lock:
            conn.execute(
                """INSERT INTO kv_store(namespace, k, v, updated_at)
                   VALUES(?, ?, ?, ?)
                   ON CONFLICT(namespace, k) DO UPDATE SET
                   v=excluded.v, updated_at=excluded.updated_at
                """,
                (namespace, key, self._serialize(value), time.time()),
            )

    def contains(self, key: str, *, namespace: str = "default") -> bool:
        conn = self._ensure_sync()
        with self._lock:
            row = conn.execute(
                "SELECT 1 FROM kv_store WHERE namespace=? AND k=?", (namespace, key)
            ).fetchone()
        return row is not None

    def delete(self, key: str, *, namespace: str = "default") -> None:
        conn = self._ensure_sync()
        with self._lock:
            conn.execute(
                "DELETE FROM kv_store WHERE namespace=? AND k=?", (namespace, key)
            )

    def keys(self, *, namespace: str = "default") -> list[str]:
        conn = self._ensure_sync()
        with self._lock:
            rows = conn.execute(
                "SELECT k FROM kv_store WHERE namespace=? ORDER BY k", (namespace,)
            ).fetchall()
        return [r["k"] for r in rows]

    def clear(self, *, namespace: str | None = None) -> None:
        conn = self._ensure_sync()
        with self._lock:
            if namespace is None:
                conn.execute("DELETE FROM kv_store")
            else:
                conn.execute("DELETE FROM kv_store WHERE namespace=?", (namespace,))

    # ---------- async API ----------

    async def aget(self, key: str, *, namespace: str = "default") -> Any:
        if self._async_conn is None:
            await self.astart()
        assert self._async_conn is not None
        async with self._async_conn.execute(
            "SELECT v FROM kv_store WHERE namespace=? AND k=?", (namespace, key)
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            raise NotFoundError(ErrorCode.E20401, f"kv key {namespace}/{key} not found")
        return self._deserialize(bytes(row["v"]))

    async def aput(self, key: str, value: Any, *, namespace: str = "default") -> None:
        if self._async_conn is None:
            await self.astart()
        assert self._async_conn is not None
        await self._async_conn.execute(
            """INSERT INTO kv_store(namespace, k, v, updated_at)
               VALUES(?, ?, ?, ?)
               ON CONFLICT(namespace, k) DO UPDATE SET
               v=excluded.v, updated_at=excluded.updated_at
            """,
            (namespace, key, self._serialize(value), time.time()),
        )
        await self._async_conn.commit()


class SQLiteDocStore:
    """Prompt 02 DocStore implementation — stores free-form text documents.
    Future layer (Prompt 06 Knowledge Graph) can layer embeddings on top."""

    def __init__(self, path: str | Path | None = None) -> None:
        self._kv = SQLiteKVStore(path)

    def start(self) -> None:
        self._kv.start()

    def stop(self) -> None:
        self._kv.stop()

    # ---- helpers ----
    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> DocRecord:
        meta = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
        return DocRecord(
            doc_id=row["doc_id"],
            uri=row["uri"],
            title=row["title"],
            content=row["content"],
            content_type=row["content_type"],
            metadata=meta,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # ---- sync API ----
    def put(self, doc: DocRecord, *, namespace: str = "default") -> None:
        conn = self._kv._ensure_sync()  # noqa: SLF001 - internal access to same DB
        now = time.time()
        with self._kv._lock:  # noqa: SLF001
            conn.execute(
                """INSERT INTO doc_store(
                    namespace, doc_id, uri, title, content, content_type,
                    metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(namespace, doc_id) DO UPDATE SET
                    uri=excluded.uri, title=excluded.title, content=excluded.content,
                    content_type=excluded.content_type, metadata_json=excluded.metadata_json,
                    updated_at=excluded.updated_at
                """,
                (
                    namespace,
                    doc.doc_id,
                    doc.uri,
                    doc.title,
                    doc.content,
                    doc.content_type,
                    json.dumps(doc.metadata or {}, default=str),
                    doc.created_at or now,
                    now,
                ),
            )

    def get(self, doc_id: str, *, namespace: str = "default") -> DocRecord:
        conn = self._kv._ensure_sync()  # noqa: SLF001
        with self._kv._lock:  # noqa: SLF001
            row = conn.execute(
                "SELECT * FROM doc_store WHERE namespace=? AND doc_id=?", (namespace, doc_id)
            ).fetchone()
        if row is None:
            raise NotFoundError(ErrorCode.E20401, f"doc {namespace}/{doc_id} not found")
        return self._row_to_record(row)

    def delete(self, doc_id: str, *, namespace: str = "default") -> None:
        conn = self._kv._ensure_sync()  # noqa: SLF001
        with self._kv._lock:  # noqa: SLF001
            conn.execute(
                "DELETE FROM doc_store WHERE namespace=? AND doc_id=?", (namespace, doc_id)
            )

    def search_by_tag(self, tag: str, *, namespace: str = "default", limit: int = 100) -> list[DocRecord]:
        conn = self._kv._ensure_sync()  # noqa: SLF001
        like = f"%{tag}%"
        with self._kv._lock:  # noqa: SLF001
            rows = conn.execute(
                """SELECT * FROM doc_store
                   WHERE namespace=? AND (title LIKE ? OR content LIKE ? OR metadata_json LIKE ?)
                   ORDER BY updated_at DESC LIMIT ?""",
                (namespace, like, like, like, int(limit)),
            ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def recent(self, *, namespace: str = "default", limit: int = 100) -> list[DocRecord]:
        conn = self._kv._ensure_sync()  # noqa: SLF001
        with self._kv._lock:  # noqa: SLF001
            rows = conn.execute(
                "SELECT * FROM doc_store WHERE namespace=? ORDER BY created_at DESC LIMIT ?",
                (namespace, int(limit)),
            ).fetchall()
        return [self._row_to_record(r) for r in rows]


# Prompt 02 FUTURE stores: explicit NotImplementedError subclasses so L3+ replacement is clean

class NoOpVectorStore:
    """Not implemented — Prompt 07+ only. Raises NotImplementedError on every call."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._reason = "VectorStore requires embeddings; deferred to Prompt 07+"

    async def add(self, *args: Any, **kwargs: Any) -> list[str]:  # noqa: ANN401
        raise NotImplementedError(self._reason)

    async def delete(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        raise NotImplementedError(self._reason)

    async def search(self, *args: Any, **kwargs: Any) -> list[tuple[str, float]]:  # noqa: ANN401
        raise NotImplementedError(self._reason)

    async def aclose(self) -> None:  # noqa: D401 - stub
        pass


class NoOpGraphStore:
    """Not implemented — Prompt 08+ only."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._reason = "GraphStore requires KG schema; deferred to Prompt 08+"

    async def add_node(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        raise NotImplementedError(self._reason)

    async def add_edge(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        raise NotImplementedError(self._reason)

    async def delete_node(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        raise NotImplementedError(self._reason)

    async def shortest_path(self, *args: Any, **kwargs: Any) -> list[str]:  # noqa: ANN401
        raise NotImplementedError(self._reason)

    async def aclose(self) -> None:  # noqa: D401 - stub
        pass
