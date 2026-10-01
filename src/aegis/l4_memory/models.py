"""L4 Memory core data models — MemoryRecord, ProvenanceChain, KGEntity, KGRelationship.

All models use Pydantic v2 for validation + JSON serialization.
They are IMMUTABLE by default — updates create new MemoryVersion objects.

Design principles:
  - Every record has provenance (non-optional ProvenanceChain).
  - Importance and confidence are distinct fields with independent semantics.
  - Privacy tier is a mandatory field on every MemoryRecord.
  - Version history is built into MemoryRecord.version + MemoryVersion list.
  - Records are never overwritten in place — updates increment version.

Import safety: l4_memory.types only + pydantic + stdlib.
"""

from __future__ import annotations

import time
import uuid
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from aegis.l4_memory.types import (
    ConfidenceLevel,
    EntityKind,
    Importance,
    MemoryKind,
    MemoryStatus,
    MemoryTier,
    ProvenanceKind,
    RelationshipKind,
)

__all__ = [
    "ProvenanceLink",
    "ProvenanceChain",
    "MemoryVersion",
    "MemoryRecord",
    "KGEntity",
    "KGRelationship",
    "Citation",
    "AccessLogEntry",
]

# ---------------------------------------------------------------------------
# Privacy tier import — use a string sentinel to avoid L3 circular dep.
# PrivacyTier values: "P0", "P1", "P2", "P3"
# ---------------------------------------------------------------------------

_VALID_PRIVACY_TIERS = frozenset({"P0", "P1", "P2", "P3"})
_DEFAULT_PRIVACY_TIER = "P2"


def _validate_privacy_tier(v: str) -> str:
    if v not in _VALID_PRIVACY_TIERS:
        raise ValueError(f"privacy_tier must be one of {sorted(_VALID_PRIVACY_TIERS)}, got {v!r}")
    return v


# ---------------------------------------------------------------------------
# ProvenanceLink — one link in the provenance chain
# ---------------------------------------------------------------------------

class ProvenanceLink(BaseModel):
    """A single link in a ProvenanceChain.

    Answers: who/what contributed this piece of information, from what source,
    at what time, and via what mechanism?
    """

    model_config = {"frozen": True}

    kind: ProvenanceKind
    subject: str = Field(description="Who/what wrote this (user_id, model_id, scanner_id, tool_id)")
    source_ref: str | None = Field(
        default=None,
        description="URL, file path, conversation_id, LLM completion_id, etc.",
    )
    timestamp: float = Field(default_factory=time.time)
    note: str | None = None


# ---------------------------------------------------------------------------
# ProvenanceChain — ordered chain of provenance links
# ---------------------------------------------------------------------------

class ProvenanceChain(BaseModel):
    """Ordered chain of ProvenanceLinks.

    The first link is the primary source. Additional links capture
    corroboration, user confirmation, or promotion events.
    """

    model_config = {"frozen": True}

    links: tuple[ProvenanceLink, ...] = Field(min_length=1)

    @classmethod
    def single(
        cls,
        kind: ProvenanceKind,
        subject: str,
        source_ref: str | None = None,
        note: str | None = None,
    ) -> "ProvenanceChain":
        """Convenience factory for single-link provenance."""
        return cls(
            links=(
                ProvenanceLink(
                    kind=kind,
                    subject=subject,
                    source_ref=source_ref,
                    note=note,
                ),
            )
        )

    def extend(self, link: ProvenanceLink) -> "ProvenanceChain":
        """Return a new ProvenanceChain with an additional link appended."""
        return ProvenanceChain(links=(*self.links, link))

    @property
    def primary(self) -> ProvenanceLink:
        return self.links[0]

    @property
    def is_user_provided(self) -> bool:
        return any(
            lnk.kind in {ProvenanceKind.USER_PROVIDED, ProvenanceKind.USER_CONFIRMED}
            for lnk in self.links
        )


# ---------------------------------------------------------------------------
# Citation — supporting evidence for a semantic fact (T3)
# ---------------------------------------------------------------------------

class Citation(BaseModel):
    """Supporting citation for a semantic memory fact."""

    model_config = {"frozen": True}

    source_ref: str = Field(description="URL, DOI, file path, memory_id reference")
    title: str | None = None
    excerpt: str | None = None
    accessed_at: float = Field(default_factory=time.time)


# ---------------------------------------------------------------------------
# MemoryVersion — snapshot of a previous record state
# ---------------------------------------------------------------------------

class MemoryVersion(BaseModel):
    """Immutable snapshot of a MemoryRecord at a previous version number.

    MemoryManager creates a MemoryVersion on every update before modifying
    the record, preserving full history.
    """

    model_config = {"frozen": True}

    version: int
    content: Any
    importance: Importance
    confidence: float
    status: MemoryStatus
    updated_at: float
    updated_by: str
    change_note: str | None = None


# ---------------------------------------------------------------------------
# AccessLogEntry — one retrieval/access event
# ---------------------------------------------------------------------------

class AccessLogEntry(BaseModel):
    """Single access event logged against a MemoryRecord."""

    model_config = {"frozen": True}

    accessed_at: float = Field(default_factory=time.time)
    accessor: str = Field(description="Who accessed this: user_id, system, manager")
    access_type: str = "read"  # read / search_hit / context_inject
    query_ref: str | None = None  # Search query or context request ID


# ---------------------------------------------------------------------------
# MemoryRecord — the canonical memory object
# ---------------------------------------------------------------------------

class MemoryRecord(BaseModel):
    """Canonical AEGIS memory record.

    Invariants:
      - id is immutable after creation.
      - version is monotonically increasing; updated via MemoryManager.update().
      - provenance is non-optional; every record must have at least one ProvenanceLink.
      - importance and confidence are INDEPENDENT fields.
      - privacy_tier is a string sentinel ("P0"/"P1"/"P2"/"P3").
      - Pinned records (is_pinned=True) are excluded from decay/expiration loops.
      - CRITICAL importance implies decay_immune=True regardless of is_pinned.
    """

    model_config = {"protected_namespaces": ()}

    # Identity
    id: UUID = Field(default_factory=uuid.uuid4)
    key: str = Field(
        description=(
            "Stable human-readable key for this record. Same key = version update. "
            "Format: {namespace}/{kind}/{slug} e.g. 'project/aegis/description'"
        )
    )
    namespace: str = Field(default="global", description="Logical namespace; project_id for T7 records")

    # Content
    tier: MemoryTier
    kind: MemoryKind
    content: Any = Field(description="Structured or text content; tier-specific semantics")
    summary: str | None = Field(default=None, description="Short human-readable summary of content")

    # Source / associations
    source: str | None = Field(default=None, description="Raw source reference (file, URL, session_id)")
    session_id: str | None = None
    project_id: str | None = None
    user_id: str | None = None
    tags: frozenset[str] = Field(default_factory=frozenset)

    # Confidence + Importance (DISTINCT — do not confuse)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    importance: Importance = Importance.NORMAL

    # Privacy (string sentinel, not L3 enum, to avoid L4→L3 circular dep)
    privacy_tier: str = Field(default=_DEFAULT_PRIVACY_TIER)

    # Status + lifecycle
    status: MemoryStatus = MemoryStatus.DRAFT
    is_pinned: bool = False
    is_draft: bool = True

    # Versioning
    version: int = Field(default=1, ge=1)
    version_history: tuple[MemoryVersion, ...] = Field(default_factory=tuple)

    # Provenance (non-optional — every record must have origin)
    provenance: ProvenanceChain

    # Citations (T3 semantic facts may cite sources)
    citations: tuple[Citation, ...] = Field(default_factory=tuple)

    # Timestamps
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    last_accessed_at: float | None = None
    expires_at: float | None = Field(default=None, description="Unix timestamp; None = no expiration")

    # Access history (lightweight — full audit in separate store if needed)
    access_count: int = Field(default=0, ge=0)

    # Relationships (memory-level links, distinct from KG edges)
    related_ids: frozenset[UUID] = Field(default_factory=frozenset)

    @field_validator("privacy_tier", mode="before")
    @classmethod
    def _validate_privacy_tier(cls, v: Any) -> str:
        return _validate_privacy_tier(str(v))

    @property
    def confidence_level(self) -> ConfidenceLevel:
        return ConfidenceLevel.from_float(self.confidence)

    @property
    def is_decay_immune(self) -> bool:
        """True if this record must be excluded from automatic decay/expiration."""
        return self.is_pinned or self.importance is Importance.CRITICAL

    @property
    def is_retrievable(self) -> bool:
        return self.status.is_retrievable

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() >= self.expires_at

    def with_defaults_for_tier(self) -> "MemoryRecord":
        """Return a copy with TTL defaulted to tier default if not already set."""
        if self.expires_at is not None:
            return self
        ttl = self.tier.default_ttl_seconds
        if ttl is None:
            return self
        return self.model_copy(update={"expires_at": self.created_at + ttl})


# ---------------------------------------------------------------------------
# KGEntity — knowledge graph node
# ---------------------------------------------------------------------------

class KGEntity(BaseModel):
    """A node in the AEGIS Knowledge Graph.

    Nodes represent real-world entities (projects, documents, people, etc.)
    and can be linked by KGRelationships.
    """

    model_config = {"frozen": True}

    id: UUID = Field(default_factory=uuid.uuid4)
    kind: EntityKind
    key: str = Field(description="Stable unique key within namespace: 'project:aegis'")
    label: str
    namespace: str = "global"
    attributes: dict[str, Any] = Field(default_factory=dict)
    privacy_tier: str = Field(default=_DEFAULT_PRIVACY_TIER)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    source_memory_id: UUID | None = Field(
        default=None,
        description="MemoryRecord that this entity was derived from, if any",
    )

    @field_validator("privacy_tier", mode="before")
    @classmethod
    def _validate_pt(cls, v: Any) -> str:
        return _validate_privacy_tier(str(v))


# ---------------------------------------------------------------------------
# KGRelationship — knowledge graph directed edge
# ---------------------------------------------------------------------------

class KGRelationship(BaseModel):
    """A directed typed edge in the Knowledge Graph.

    (subject_id --[kind {confidence, provenance}]--> object_id)
    """

    model_config = {"frozen": True}

    id: UUID = Field(default_factory=uuid.uuid4)
    subject_id: UUID = Field(description="Source entity id")
    object_id: UUID = Field(description="Target entity id")
    kind: RelationshipKind
    custom_kind: str | None = Field(
        default=None,
        description="Used when kind=CUSTOM to store the actual relation name",
    )
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    provenance: ProvenanceChain
    attributes: dict[str, Any] = Field(default_factory=dict)
    privacy_tier: str = Field(default=_DEFAULT_PRIVACY_TIER)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    version: int = Field(default=1, ge=1)

    @field_validator("privacy_tier", mode="before")
    @classmethod
    def _validate_pt(cls, v: Any) -> str:
        return _validate_privacy_tier(str(v))

    @property
    def relation_label(self) -> str:
        if self.kind is RelationshipKind.CUSTOM and self.custom_kind:
            return self.custom_kind
        return self.kind.value
