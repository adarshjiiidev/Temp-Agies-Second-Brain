"""L4 Memory & Knowledge Engine — public API surface.

Prompt 04 exports. All subsystems are accessible from this package.

Example::

    from aegis.l4_memory import (
        MemoryManager, MemoryRecord, MemoryTier, MemoryKind,
        Importance, MemoryStatus, ProvenanceChain, ProvenanceLink,
        ProvenanceKind, ContextBuilder, ContextRequest, ContextPackage,
        SearchQuery, SearchResult, SearchMode,
        KGEntity, KGRelationship, EntityKind, RelationshipKind,
        MarkdownExporter, ObsidianAdapter,
        MemoryPolicy,
    )
"""

from aegis.l4_memory.context import ContextBuilder, ContextPackage, ContextRequest, ContextSection
from aegis.l4_memory.exceptions import (
    KnowledgeGraphError,
    MemoryAlreadyExistsError,
    MemoryError,
    MemoryNotFoundError,
    MemoryPolicyViolationError,
    MemoryPrivacyViolationError,
    MemorySearchError,
    MemoryStatusError,
    MemoryStorageError,
    MemoryVersionConflictError,
)
from aegis.l4_memory.graph import KnowledgeGraph
from aegis.l4_memory.manager import MemoryManager
from aegis.l4_memory.markdown import MarkdownExporter, ObsidianAdapter, extract_wikilinks
from aegis.l4_memory.models import (
    AccessLogEntry,
    Citation,
    KGEntity,
    KGRelationship,
    MemoryRecord,
    MemoryVersion,
    ProvenanceChain,
    ProvenanceLink,
)
from aegis.l4_memory.policies import (
    AccessPolicy,
    ArchivalPolicy,
    DecayPolicy,
    MemoryPolicy,
    MergePolicy,
    RetentionPolicy,
)
from aegis.l4_memory.search import SearchEngine, SearchQuery, SearchResult
from aegis.l4_memory.store import SQLiteMemoryStore
from aegis.l4_memory.types import (
    ConfidenceLevel,
    ContextSection as ContextSectionLabel,
    EntityKind,
    ImportSource,
    Importance,
    MemoryKind,
    MemoryStatus,
    MemoryTier,
    ProvenanceKind,
    RelationshipKind,
    SearchMode,
)

__all__ = [
    # Manager (main entry point)
    "MemoryManager",
    # Storage
    "SQLiteMemoryStore",
    # KnowledgeGraph
    "KnowledgeGraph",
    # Search
    "SearchEngine",
    "SearchQuery",
    "SearchResult",
    # Context
    "ContextBuilder",
    "ContextRequest",
    "ContextPackage",
    "ContextSection",
    # Markdown / Obsidian
    "MarkdownExporter",
    "ObsidianAdapter",
    "extract_wikilinks",
    # Models
    "MemoryRecord",
    "MemoryVersion",
    "ProvenanceChain",
    "ProvenanceLink",
    "KGEntity",
    "KGRelationship",
    "Citation",
    "AccessLogEntry",
    # Policies
    "MemoryPolicy",
    "RetentionPolicy",
    "DecayPolicy",
    "AccessPolicy",
    "ArchivalPolicy",
    "MergePolicy",
    # Types / Enums
    "MemoryTier",
    "MemoryKind",
    "Importance",
    "ConfidenceLevel",
    "ProvenanceKind",
    "MemoryStatus",
    "EntityKind",
    "RelationshipKind",
    "SearchMode",
    "ContextSectionLabel",
    "ImportSource",
    # Exceptions
    "MemoryError",
    "MemoryNotFoundError",
    "MemoryAlreadyExistsError",
    "MemoryStorageError",
    "MemoryPolicyViolationError",
    "MemoryPrivacyViolationError",
    "MemoryStatusError",
    "MemoryVersionConflictError",
    "MemorySearchError",
    "KnowledgeGraphError",
]
