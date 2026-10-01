"""L4 Memory & Knowledge Engine — enumerations and primitive types.

All enums are string-valued so they JSON-serialize cleanly and can survive
storage round-trips without deserialization magic.

Import safety: stdlib only. Zero L3/L2/L1 imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


__all__ = [
    "MemoryTier",
    "MemoryKind",
    "Importance",
    "ConfidenceLevel",
    "ProvenanceKind",
    "MemoryStatus",
    "RelationshipKind",
    "EntityKind",
    "SearchMode",
    "ContextSection",
    "ImportSource",
]


# ---------------------------------------------------------------------------
# MemoryTier — the 9-tier volatility hierarchy from docs/06_MEMORY_KNOWLEDGE.md
# ---------------------------------------------------------------------------

class MemoryTier(str, Enum):
    """9-tier memory hierarchy. Lower ordinal = more volatile.

    T0 Working → T8 Skill (most durable, most validated).
    Prompt 04 fully implements T0-T3. T4-T8 defined but not fully backed.
    """

    T0_WORKING = "T0_working"          # In-context; TTL = end of turn
    T1_SESSION = "T1_session"          # One boot-shutdown cycle; 30d after end
    T2_EPISODIC = "T2_episodic"        # Cross-session event log; 2y default TTL
    T3_SEMANTIC = "T3_semantic"        # Stable facts; forever unless stale/deleted
    T4_PROCEDURAL = "T4_procedural"    # Learned workflows; forever unless deprecated
    T5_PERSONAL = "T5_personal"        # User preferences; never auto-forget
    T6_ENVIRONMENTAL = "T6_environmental"  # Digital env observations; 90d freshness
    T7_PROJECT = "T7_project"          # Scoped to one project/repo
    T8_SKILL = "T8_skill"              # Registered capability + harness history

    @property
    def default_ttl_seconds(self) -> float | None:
        """Default TTL in seconds. None = keep forever."""
        _ttls: dict[str, float | None] = {
            "T0_working": 300.0,             # 5 minutes
            "T1_session": 86400 * 30,        # 30 days after session end
            "T2_episodic": 86400 * 730,      # 2 years
            "T3_semantic": None,             # Forever
            "T4_procedural": None,
            "T5_personal": None,
            "T6_environmental": 86400 * 90,  # 90 days
            "T7_project": None,
            "T8_skill": None,
        }
        return _ttls.get(self.value)

    @property
    def requires_user_confirmation_to_promote(self) -> bool:
        """T5 Personal always requires explicit user confirmation before promotion."""
        return self in {MemoryTier.T5_PERSONAL}

    @property
    def is_volatile(self) -> bool:
        return self in {MemoryTier.T0_WORKING, MemoryTier.T1_SESSION}


# ---------------------------------------------------------------------------
# MemoryKind — logical content type within a tier
# ---------------------------------------------------------------------------

class MemoryKind(str, Enum):
    """What the memory record conceptually represents."""

    FACT = "fact"               # Verified/cited factual statement
    OBSERVATION = "observation" # Single raw observation (not yet corroborated)
    INFERENCE = "inference"     # Model-inferred conclusion (lower confidence by default)
    PREFERENCE = "preference"   # User preference or style choice
    HYPOTHESIS = "hypothesis"   # Unconfirmed supposition needing investigation
    EVENT = "event"             # Something that happened (T2 episodic)
    PROCEDURE = "procedure"     # Step-by-step workflow (T4)
    ENVIRONMENT = "environment" # Environmental scan result (T6)
    PROJECT_CONTEXT = "project_context"  # Project metadata (T7)
    SKILL = "skill"             # Registered skill capability (T8)
    CONVERSATION = "conversation"  # Raw conversation turn (T1)
    DECISION = "decision"       # Explicit decision record
    GOAL = "goal"               # User goal
    ANNOTATION = "annotation"   # User note attached to another record


# ---------------------------------------------------------------------------
# Importance — independent of relevance and confidence
# ---------------------------------------------------------------------------

class Importance(str, Enum):
    """Memory importance. NOT the same as relevance or confidence.

    Pinned/CRITICAL memories are immune to decay regardless of access frequency.
    Do not confuse with QualityTier (AI Kernel) — this is purely about memory retention.
    """

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"   # Protected: never auto-archived, never auto-expired

    @property
    def decay_immune(self) -> bool:
        """CRITICAL memories are exempt from automatic decay."""
        return self is Importance.CRITICAL

    @property
    def ordinal(self) -> int:
        return {"low": 0, "normal": 1, "high": 2, "critical": 3}[self.value]


# ---------------------------------------------------------------------------
# ConfidenceLevel — named buckets for confidence float (0..1)
# ---------------------------------------------------------------------------

class ConfidenceLevel(str, Enum):
    """Named confidence buckets. Stored alongside float confidence for readability.

    A memory CAN be HIGH importance and LOW confidence simultaneously.
    Never conflate the two.
    """

    VERY_LOW = "very_low"     # 0.0 – 0.20: LLM guess, unverified inference
    LOW = "low"               # 0.20 – 0.40: single observation, no corroboration
    MEDIUM = "medium"         # 0.40 – 0.70: corroborated but not user-verified
    HIGH = "high"             # 0.70 – 0.90: user-verified or strongly corroborated
    VERY_HIGH = "very_high"   # 0.90 – 1.00: user explicitly confirmed, cited source

    @classmethod
    def from_float(cls, value: float) -> "ConfidenceLevel":
        if value < 0.20:
            return cls.VERY_LOW
        if value < 0.40:
            return cls.LOW
        if value < 0.70:
            return cls.MEDIUM
        if value < 0.90:
            return cls.HIGH
        return cls.VERY_HIGH


# ---------------------------------------------------------------------------
# ProvenanceKind — where did this memory come from?
# ---------------------------------------------------------------------------

class ProvenanceKind(str, Enum):
    """Origin category for a memory record or provenance chain link.

    FACT vs INFERENCE vs USER_PROVIDED distinction is critical to prevent
    autonomous systems from treating model inferences as verified facts.
    """

    USER_PROVIDED = "user_provided"         # User typed / said it
    CONVERSATION_DERIVED = "conversation_derived"  # Extracted from conversation
    FILE_DERIVED = "file_derived"           # Extracted from a file/document
    CODE_DERIVED = "code_derived"           # Extracted from codebase
    TOOL_DERIVED = "tool_derived"           # Output of a CLI/tool run
    WEB_DERIVED = "web_derived"             # Fetched from web
    MODEL_INFERRED = "model_inferred"       # LLM generated / inferred
    SYSTEM_GENERATED = "system_generated"   # Automatic system observation
    SCANNER_DERIVED = "scanner_derived"     # Environment scanner result
    USER_CONFIRMED = "user_confirmed"       # Explicitly validated by user
    CORROBORATED = "corroborated"           # ≥2 independent sources agree
    OBSERVER_DERIVED = "observer_derived"   # P07 behavior observer event


# ---------------------------------------------------------------------------
# MemoryStatus — lifecycle state of a record
# ---------------------------------------------------------------------------

class MemoryStatus(str, Enum):
    """Lifecycle state of a MemoryRecord.

    DRAFT → ACTIVE ← → ARCHIVED → DELETED (soft)
    PINNED is a flag overlay on ACTIVE (managed separately).
    """

    DRAFT = "draft"           # Newly created, not promoted; low-confidence candidate
    ACTIVE = "active"         # Live, accessible record
    ARCHIVED = "archived"     # Retained but excluded from normal retrieval
    EXPIRED = "expired"       # TTL elapsed; soft-deleted, not immediately purged
    DELETED = "deleted"       # Soft-deleted; can be restored within grace period
    PENDING_REVIEW = "pending_review"  # Needs user confirmation before promotion

    @property
    def is_retrievable(self) -> bool:
        return self is MemoryStatus.ACTIVE


# ---------------------------------------------------------------------------
# EntityKind — knowledge graph node types
# ---------------------------------------------------------------------------

class EntityKind(str, Enum):
    """KG entity type. Extensible — unknown kinds stored as CUSTOM."""

    PROJECT = "project"
    REPOSITORY = "repository"
    DOCUMENT = "document"
    PERSON = "person"               # EXPLICIT ENROLLMENT ONLY per §5.1
    TOOL = "tool"
    SKILL = "skill"
    TECHNOLOGY = "technology"
    CONCEPT = "concept"
    SOFTWARE = "software"
    DECISION = "decision"
    EXPERIMENT = "experiment"
    API = "api"
    FILE = "file"
    MEMORY_RECORD = "memory_record"  # KG node wrapping a MemoryRecord reference
    CUSTOM = "custom"
    # P07 — environment model additions
    APPLICATION = "application"      # Installed/runnable application
    DEVICE = "device"                # Physical or virtual hardware device
    DEV_ENVIRONMENT = "dev_environment"  # Python venv, conda env, nvm, etc.
    ACCOUNT = "account"              # User account (local or service)
    WORKSPACE = "workspace"          # IDE workspace / working directory grouping


# ---------------------------------------------------------------------------
# RelationshipKind — knowledge graph edge types
# ---------------------------------------------------------------------------

class RelationshipKind(str, Enum):
    """KG relationship/edge type. Directed: (subject --[rel]--> object)."""

    USES = "uses"
    DEPENDS_ON = "depends_on"
    IMPLEMENTED_BY = "implemented_by"
    RESEARCHED = "researched"
    IMPLEMENTED = "implemented"
    RELATED_TO = "related_to"
    CONTAINS = "contains"
    AUTHORED_BY = "authored_by"
    CITES = "cites"
    CONFLICTS_WITH = "conflicts_with"
    CONFIRMS = "confirms"
    LEARNED_FROM = "learned_from"
    VERSION_OF = "version_of"
    ASSIGNED_TO = "assigned_to"
    WORKS_ON = "works_on"
    BELONGS_TO = "belongs_to"
    TAGGED_WITH = "tagged_with"
    CUSTOM = "custom"
    # P07 — environment relationship additions
    RUNS_ON = "runs_on"              # Application runs on device/OS
    DEPLOYS_THROUGH = "deploys_through"  # Project deploys through tool/env
    MANAGES = "manages"             # Account/tool manages another entity


# ---------------------------------------------------------------------------
# SearchMode — what kind of search to use
# ---------------------------------------------------------------------------

class SearchMode(str, Enum):
    """How to match memories. Vector/semantic deferred to Prompt 05+."""

    KEYWORD = "keyword"          # FTS / substring match on content
    METADATA = "metadata"        # Filter on structured fields only
    HYBRID = "hybrid"            # Keyword + metadata combined
    SEMANTIC = "semantic"        # Vector similarity (NOT YET IMPLEMENTED — interface only)
    GRAPH = "graph"              # KG traversal starting from entity


# ---------------------------------------------------------------------------
# ContextSection — used by ContextBuilder to label assembled memory sections
# ---------------------------------------------------------------------------

class ContextSection(str, Enum):
    """Labeled sections in a ContextPackage."""

    WORKING = "working_memory"
    SESSION = "session_memory"
    EPISODIC = "recent_events"
    SEMANTIC = "relevant_facts"
    PROCEDURAL = "relevant_procedures"
    PERSONAL = "user_preferences"
    PROJECT = "project_context"
    ENVIRONMENTAL = "environment"
    SKILL = "available_skills"


# ---------------------------------------------------------------------------
# ImportSource — future KnowledgeImporter source types
# ---------------------------------------------------------------------------

class ImportSource(str, Enum):
    """Provenance source category for KnowledgeImporter adapters (Prompt 05+)."""

    FILE = "file"
    DOCUMENT = "document"
    CODEBASE = "codebase"
    CONVERSATION = "conversation"
    OBSIDIAN = "obsidian"
    GIT_REPOSITORY = "git_repository"
    WEB_PAGE = "web_page"
    EMAIL = "email"
    DATABASE = "database"
    CUSTOM = "custom"
