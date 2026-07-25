"""L1 Storage interfaces — PROTOCOLS ONLY.
Concrete implementations live in L2 persistence module (SQLite default per Prompt 01 §03).
These are stable contracts that future backends (Postgres, Neo4j, Redis plugins…) implement."""
from __future__ import annotations

from abc import abstractmethod
from typing import Any, AsyncIterator, Iterable, Protocol, runtime_checkable


@runtime_checkable
class KVStore(Protocol):
    """Simple typed key-value store with versioned keys and optional TTL."""

    @abstractmethod
    async def get(self, key: str) -> bytes | None: ...

    @abstractmethod
    async def put(self, key: str, value: bytes, *, ttl_seconds: float | None = None) -> None: ...

    @abstractmethod
    async def delete(self, key: str) -> bool: ...

    @abstractmethod
    async def exists(self, key: str) -> bool: ...

    @abstractmethod
    async def scan_prefix(self, prefix: str) -> AsyncIterator[str]:  # type: ignore[type-var]
        yield ""  # pragma: no cover


@runtime_checkable
class DocStore(Protocol):
    """Document store: JSON-serializable documents with full-text search capability."""

    @abstractmethod
    async def insert(self, doc_id: str, document: dict[str, Any]) -> None: ...

    @abstractmethod
    async def get(self, doc_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    async def delete(self, doc_id: str) -> bool: ...

    @abstractmethod
    async def search(
        self,
        *,
        query_text: str | None = None,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]: ...


Vector = list[float]


@runtime_checkable
class VectorStore(Protocol):
    """Vector similarity search store.
    Prompt 02: concrete implementation is a pure in-memory fallback stub.
    Qdrant local-mode integration ships in Prompt 04 (Memory Engine milestone)."""

    @abstractmethod
    async def upsert(self, id: str, vector: Vector, metadata: dict[str, Any] | None = None) -> None:
        ...

    @abstractmethod
    async def search(
        self, vector: Vector, *, top_k: int = 10, filters: dict[str, Any] | None = None
    ) -> list[tuple[str, float, dict[str, Any]]]:
        """(id, score, metadata) tuples, highest similarity first."""


@runtime_checkable
class GraphStore(Protocol):
    """Typed Knowledge Graph store. Nodes/edges are typed entities/relations per Prompt 01 §06.5."""

    @abstractmethod
    async def add_node(
        self, node_id: str, kind: str, key: str, attrs: dict[str, Any] | None = None, label: str = ""
    ) -> None: ...

    @abstractmethod
    async def add_edge(
        self,
        src_id: str,
        dst_id: str,
        rel_type: str,
        attrs: dict[str, Any] | None = None,
        is_draft: bool = True,
    ) -> None: ...

    @abstractmethod
    async def neighbors(self, node_id: str) -> list[tuple[str, str, dict[str, Any]]]:
        """Returns (neighbor_id, rel_type, attrs) list."""

    @abstractmethod
    async def shortest_path(
        self, src_id: str, dst_id: str, max_depth: int = 6
    ) -> list[tuple[str, str]] | None:
        """Returns list of (node_id, rel_to_next) tuples including src and dst."""
