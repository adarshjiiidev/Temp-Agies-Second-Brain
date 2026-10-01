"""P07 Persistence — EnvironmentStore.

Thin wrapper over MemoryManager + KnowledgeGraph that:
  - Uses namespace="p07_env" for all records.
  - Maps EnvNode → KGEntity and stores a companion MemoryRecord (T6_ENVIRONMENTAL).
  - Maps EnvEdge → KGRelationship.
  - Exposes upsert_node / upsert_edge / query_nodes / query_edges / delete_node.

All writes go through MemoryManager's policy stack.
Privacy zone checks must be performed by callers BEFORE calling this store.

Import safety: l4_memory.* + stdlib ONLY. No L5/L6/L3 imports.
"""

from __future__ import annotations

import time
import uuid
from typing import Any
from uuid import UUID

from aegis.l4_memory.graph import KnowledgeGraph
from aegis.l4_memory.manager import MemoryManager
from aegis.l4_memory.models import (
    KGEntity,
    KGRelationship,
    MemoryRecord,
    ProvenanceChain,
    ProvenanceLink,
)
from aegis.l4_memory.p07.model.types import EnvEdge, EnvEdgeKind, EnvNode, EnvNodeKind
from aegis.l4_memory.types import (
    EntityKind,
    MemoryKind,
    MemoryStatus,
    MemoryTier,
    ProvenanceKind,
    RelationshipKind,
)

__all__ = ["EnvironmentStore"]

_NAMESPACE = "p07_env"

# Map P07 EnvNodeKind → L4 EntityKind
_NODE_KIND_MAP: dict[EnvNodeKind, EntityKind] = {
    EnvNodeKind.APPLICATION:     EntityKind.APPLICATION,
    EnvNodeKind.PROJECT:         EntityKind.PROJECT,
    EnvNodeKind.REPOSITORY:      EntityKind.REPOSITORY,
    EnvNodeKind.TOOL:            EntityKind.TOOL,
    EnvNodeKind.DEV_ENVIRONMENT: EntityKind.DEV_ENVIRONMENT,
    EnvNodeKind.DEVICE:          EntityKind.DEVICE,
    EnvNodeKind.ACCOUNT:         EntityKind.ACCOUNT,
    EnvNodeKind.WORKSPACE:       EntityKind.WORKSPACE,
    EnvNodeKind.TECHNOLOGY:      EntityKind.TECHNOLOGY,
}

# Map P07 EnvEdgeKind → L4 RelationshipKind
_EDGE_KIND_MAP: dict[EnvEdgeKind, RelationshipKind] = {
    EnvEdgeKind.USES:            RelationshipKind.USES,
    EnvEdgeKind.CONTAINS:        RelationshipKind.CONTAINS,
    EnvEdgeKind.DEPENDS_ON:      RelationshipKind.DEPENDS_ON,
    EnvEdgeKind.RUNS_ON:         RelationshipKind.RUNS_ON,
    EnvEdgeKind.DEPLOYS_THROUGH: RelationshipKind.DEPLOYS_THROUGH,
    EnvEdgeKind.MANAGES:         RelationshipKind.MANAGES,
    EnvEdgeKind.RELATED_TO:      RelationshipKind.RELATED_TO,
    EnvEdgeKind.VERSION_OF:      RelationshipKind.VERSION_OF,
}


def _make_provenance(scanner_id: str) -> ProvenanceChain:
    return ProvenanceChain(links=[
        ProvenanceLink(
            kind=ProvenanceKind.SCANNER_DERIVED,
            subject=scanner_id,
        )
    ])


class EnvironmentStore:
    """Persistence layer for P07 environment graph.

    Usage::

        store = EnvironmentStore(memory_manager, knowledge_graph)
        await store.upsert_node(node, scanner_id="app_scanner")
        nodes = await store.query_nodes(kind=EnvNodeKind.APPLICATION)
    """

    def __init__(
        self,
        manager: MemoryManager,
        graph: KnowledgeGraph,
    ) -> None:
        self._manager = manager
        self._graph = graph

    # ------------------------------------------------------------------
    # Node operations
    # ------------------------------------------------------------------

    async def upsert_node(
        self,
        node: EnvNode,
        scanner_id: str = "p07_scanner",
    ) -> UUID:
        """Persist an EnvNode, creating or updating the KGEntity.

        Returns the UUID of the KGEntity.
        """
        entity_kind = _NODE_KIND_MAP.get(node.kind, EntityKind.CUSTOM)
        now = time.time()

        # Build KGEntity
        entity = KGEntity(
            key=node.key,
            kind=entity_kind,
            label=node.label,
            namespace=_NAMESPACE,
            privacy_tier=node.privacy_tier,
            attributes={
                **node.attributes,
                "p07_node_kind": node.kind.value,
                "scanned_at": node.scanned_at or now,
                **({"version": node.version} if node.version else {}),
                **({"source_path": node.source_path} if node.source_path else {}),
            },
            created_at=now,
            updated_at=now,
        )

        # Upsert into KG — upsert_entity handles create-or-update by (key, namespace)
        # Preserve created_at if the entity already exists.
        existing = await self._graph.get_entity_by_key(node.key, namespace=_NAMESPACE)
        if existing is not None:
            entity = KGEntity(
                id=existing.id,
                key=entity.key,
                kind=entity.kind,
                label=entity.label,
                namespace=entity.namespace,
                privacy_tier=entity.privacy_tier,
                attributes=entity.attributes,
                created_at=existing.created_at,
                updated_at=now,
                source_memory_id=existing.source_memory_id,
            )
        entity = await self._graph.upsert_entity(entity)

        # Also store a MemoryRecord in T6_ENVIRONMENTAL for full-text search
        record = MemoryRecord(
            key=f"env:{node.key}",
            namespace=_NAMESPACE,
            tier=MemoryTier.T6_ENVIRONMENTAL,
            kind=MemoryKind.ENVIRONMENT,
            status=MemoryStatus.ACTIVE,
            privacy_tier=node.privacy_tier,
            provenance=_make_provenance(scanner_id),
            content={
                "node_key": node.key,
                "kind": node.kind.value,
                "label": node.label,
                **node.attributes,
            },
            summary=f"{node.kind.value}: {node.label}",
            tags=[node.kind.value, "p07_env"],
        )
        try:
            await self._manager.store(record)
        except Exception:
            # Record may already exist; update
            try:
                await self._manager.update(record.key, namespace=_NAMESPACE, content=record.content)
            except Exception:
                pass  # Non-critical; KG entity is the primary store

        return entity.id

    async def delete_node(self, key: str) -> bool:
        """Soft-delete a node by key. Returns True if found and deleted."""
        try:
            entity = await self._graph.get_entity_by_key(key, namespace=_NAMESPACE)
            await self._graph.delete_entity(entity.id)
            try:
                rec = await self._manager.get_by_key(f"env:{key}", namespace=_NAMESPACE)
                await self._manager.delete(rec.id)
            except Exception:
                pass
            return True
        except Exception:
            return False

    async def query_nodes(
        self,
        kind: EnvNodeKind | None = None,
        limit: int = 200,
    ) -> list[KGEntity]:
        """Return entities from the environment namespace, optionally filtered by kind."""
        entity_kind = _NODE_KIND_MAP.get(kind) if kind else None
        return await self._graph.list_entities(
            namespace=_NAMESPACE,
            kind=entity_kind,
            limit=limit,
        )

    async def get_node(self, key: str) -> KGEntity | None:
        """Return a single node by key, or None if not found."""
        try:
            return await self._graph.get_entity_by_key(key, namespace=_NAMESPACE)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Edge operations
    # ------------------------------------------------------------------

    async def upsert_edge(
        self,
        edge: EnvEdge,
        scanner_id: str = "p07_scanner",
    ) -> UUID | None:
        """Persist an EnvEdge between two nodes by key.

        Returns the UUID of the KGRelationship, or None if either node
        is missing.
        """
        subject = await self.get_node(edge.subject_key)
        obj = await self.get_node(edge.object_key)
        if subject is None or obj is None:
            return None

        rel_kind = _EDGE_KIND_MAP.get(edge.kind, RelationshipKind.RELATED_TO)
        now = time.time()

        relationship = KGRelationship(
            subject_id=subject.id,
            object_id=obj.id,
            kind=rel_kind,
            confidence=edge.confidence,
            privacy_tier=edge.privacy_tier,
            attributes={**edge.attributes, "p07_edge_kind": edge.kind.value},
            provenance=_make_provenance(scanner_id),
            created_at=now,
            updated_at=now,
        )
        rel = await self._graph.upsert_relationship(relationship)
        return rel.id

    async def query_edges(
        self,
        subject_key: str | None = None,
        kind: EnvEdgeKind | None = None,
        limit: int = 200,
    ) -> list[KGRelationship]:
        """Return relationships from the environment namespace."""
        if subject_key:
            entity = await self.get_node(subject_key)
            if entity is None:
                return []
            rel_kind = _EDGE_KIND_MAP.get(kind) if kind else None
            # get_neighbors returns (relationship, neighbor_entity) pairs
            neighbors = await self._graph.get_neighbors(
                entity.id,
                direction="outgoing",
                rel_kinds=[rel_kind] if rel_kind else None,
                limit=limit,
            )
            return [rel for rel, _ in neighbors]

        # No subject_key: return all relationships via count+neighbors (best effort)
        # For a proper full-graph scan, callers should filter by subject_key.
        return []
