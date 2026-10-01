"""L4 Memory — SearchEngine: keyword, metadata, and hybrid search.

Implements the retrieval layer per 06_MEMORY_KNOWLEDGE.md §3.
Supports:
  - KEYWORD: FTS5 full-text search (delegates to SQLiteMemoryStore)
  - METADATA: structured filter-only (no text query)
  - HYBRID: keyword + metadata combined
  - SEMANTIC: interface stub only (vector search deferred to P07)
  - GRAPH: delegated to KnowledgeGraph.bfs()

Every result carries a relevance score composed of:
  confidence × importance_weight × recency_factor × provenance_quality

Import safety: l4_memory.* + stdlib ONLY.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from aegis.l4_memory.exceptions import MemorySearchError
from aegis.l4_memory.models import MemoryRecord
from aegis.l4_memory.types import (
    Importance,
    MemoryStatus,
    MemoryTier,
    ProvenanceKind,
    SearchMode,
)

__all__ = ["SearchQuery", "SearchResult", "SearchEngine"]

# ---------------------------------------------------------------------------
# Provenance quality weights (higher = more trusted source)
# ---------------------------------------------------------------------------

_PROVENANCE_QUALITY: dict[ProvenanceKind, float] = {
    ProvenanceKind.USER_CONFIRMED:       1.0,
    ProvenanceKind.USER_PROVIDED:        0.95,
    ProvenanceKind.CORROBORATED:         0.85,
    ProvenanceKind.FILE_DERIVED:         0.75,
    ProvenanceKind.CODE_DERIVED:         0.70,
    ProvenanceKind.TOOL_DERIVED:         0.65,
    ProvenanceKind.WEB_DERIVED:          0.60,
    ProvenanceKind.CONVERSATION_DERIVED: 0.55,
    ProvenanceKind.SCANNER_DERIVED:      0.50,
    ProvenanceKind.SYSTEM_GENERATED:     0.40,
    ProvenanceKind.MODEL_INFERRED:       0.30,
}

_IMPORTANCE_WEIGHT: dict[Importance, float] = {
    Importance.CRITICAL: 2.0,
    Importance.HIGH:     1.5,
    Importance.NORMAL:   1.0,
    Importance.LOW:      0.5,
}

# ---------------------------------------------------------------------------
# SearchQuery
# ---------------------------------------------------------------------------


@dataclass
class SearchQuery:
    """Search query for the memory search engine.

    Fields:
        text:          Text to search (used in KEYWORD / HYBRID modes).
        mode:          Search mode (KEYWORD, METADATA, HYBRID, SEMANTIC, GRAPH).
        tiers:         Restrict to specific memory tiers.
        namespace:     Restrict to namespace.
        project_id:    Restrict to project.
        session_id:    Restrict to session.
        min_confidence: Filter records below this confidence.
        min_importance: Filter below this importance level.
        privacy_tiers:  Restrict to specific privacy tiers (e.g. ["P2", "P3"]).
        exclude_privacy_tiers: Exclude these privacy tiers (e.g. ["P0"] for cloud safety).
        include_draft:  Include DRAFT records (default: False).
        tags:           Required tags (all must be present).
        limit:          Max results.
        offset:         Pagination offset.
        recency_weight: How much to weight recent records (0..1).
        start_time:     Only return records updated after this timestamp.
        end_time:       Only return records updated before this timestamp.
    """

    text: str | None = None
    mode: SearchMode = SearchMode.KEYWORD
    tiers: list[MemoryTier] | None = None
    namespace: str | None = None
    project_id: str | None = None
    session_id: str | None = None
    min_confidence: float | None = None
    min_importance: Importance | None = None
    privacy_tiers: list[str] | None = None
    exclude_privacy_tiers: list[str] | None = None
    include_draft: bool = False
    tags: frozenset[str] = field(default_factory=frozenset)
    limit: int = 20
    offset: int = 0
    recency_weight: float = 0.3
    start_time: float | None = None
    end_time: float | None = None


# ---------------------------------------------------------------------------
# SearchResult
# ---------------------------------------------------------------------------


@dataclass
class SearchResult:
    """A single search result with relevance score and match metadata."""

    record: MemoryRecord
    score: float
    matched_mode: SearchMode
    match_metadata: dict[str, Any] = field(default_factory=dict)

    def __lt__(self, other: "SearchResult") -> bool:
        return self.score < other.score


# ---------------------------------------------------------------------------
# SearchEngine
# ---------------------------------------------------------------------------


class SearchEngine:
    """Multi-mode memory search engine.

    Delegates to SQLiteMemoryStore for FTS5 and metadata queries, then
    applies a composite relevance scoring formula across results.
    """

    def __init__(self, store: Any) -> None:  # store: SQLiteMemoryStore
        self._store = store

    async def execute(self, query: SearchQuery) -> list[SearchResult]:
        """Execute a search query and return scored, sorted results."""
        if query.mode is SearchMode.SEMANTIC:
            raise MemorySearchError(
                "Semantic (vector) search is not yet implemented in P04. "
                "Use SearchMode.KEYWORD or SearchMode.HYBRID. "
                "Vector search ships in P07."
            )

        if query.mode is SearchMode.GRAPH:
            raise MemorySearchError(
                "Graph search must be performed via MemoryManager.graph.bfs(). "
                "Use SearchMode.KEYWORD, METADATA, or HYBRID for text/metadata queries."
            )

        if query.mode is SearchMode.KEYWORD:
            records = await self._keyword_search(query)
        elif query.mode is SearchMode.METADATA:
            records = await self._metadata_search(query)
        elif query.mode is SearchMode.HYBRID:
            records = await self._hybrid_search(query)
        else:
            records = await self._metadata_search(query)

        # Apply post-filters and score
        results: list[SearchResult] = []
        for rec in records:
            if not self._passes_filters(rec, query):
                continue
            score = self._compute_score(rec, query)
            results.append(SearchResult(
                record=rec,
                score=score,
                matched_mode=query.mode,
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[query.offset: query.offset + query.limit]

    # ------------------------------------------------------------------
    # Per-mode retrieval
    # ------------------------------------------------------------------

    async def _keyword_search(self, query: SearchQuery) -> list[MemoryRecord]:
        if not query.text:
            return await self._metadata_search(query)
        status = None if query.include_draft else MemoryStatus.ACTIVE
        return await self._store.keyword_search(
            query.text,
            tiers=query.tiers,
            namespace=query.namespace,
            status=status,
            limit=query.limit * 3,  # fetch extra for post-filter
        )

    async def _metadata_search(self, query: SearchQuery) -> list[MemoryRecord]:
        status = None if query.include_draft else MemoryStatus.ACTIVE
        return await self._store.list_records(
            tiers=query.tiers,
            namespace=query.namespace,
            project_id=query.project_id,
            session_id=query.session_id,
            status=status,
            min_confidence=query.min_confidence,
            limit=query.limit * 3,
        )

    async def _hybrid_search(self, query: SearchQuery) -> list[MemoryRecord]:
        """Combine keyword and metadata results, deduplicate by ID."""
        kw_results = await self._keyword_search(query)
        meta_results = await self._metadata_search(query)

        seen: set[UUID] = set()
        combined: list[MemoryRecord] = []
        for rec in kw_results + meta_results:
            if rec.id not in seen:
                seen.add(rec.id)
                combined.append(rec)
        return combined

    # ------------------------------------------------------------------
    # Post-filters
    # ------------------------------------------------------------------

    def _passes_filters(self, rec: MemoryRecord, query: SearchQuery) -> bool:
        """Return True if record passes all query filters."""
        # Privacy tier inclusion filter
        if query.privacy_tiers and rec.privacy_tier not in query.privacy_tiers:
            return False

        # Privacy tier exclusion filter (e.g. exclude P0 for cloud routing)
        if query.exclude_privacy_tiers and rec.privacy_tier in query.exclude_privacy_tiers:
            return False

        # Importance filter
        if query.min_importance is not None:
            if rec.importance.ordinal < query.min_importance.ordinal:
                return False

        # Tags filter (all required tags must be present)
        if query.tags and not query.tags.issubset(rec.tags):
            return False

        # Project filter
        if query.project_id and rec.project_id != query.project_id:
            return False

        # Session filter
        if query.session_id and rec.session_id != query.session_id:
            return False

        # Time range filter
        if query.start_time and rec.updated_at < query.start_time:
            return False
        if query.end_time and rec.updated_at > query.end_time:
            return False

        # Exclude expired
        if rec.is_expired and not rec.is_decay_immune:
            return False

        return True

    # ------------------------------------------------------------------
    # Relevance scoring
    # ------------------------------------------------------------------

    def _compute_score(self, rec: MemoryRecord, query: SearchQuery) -> float:
        """Composite relevance score.

        Score = confidence × importance_weight × recency_factor × provenance_quality
        """
        confidence = rec.confidence  # 0..1

        importance_w = _IMPORTANCE_WEIGHT.get(rec.importance, 1.0)

        # Recency factor: exponential decay from now
        now = time.time()
        age_days = (now - rec.updated_at) / 86400.0
        half_life = 90.0  # days — same as DecayPolicy default
        recency = 0.5 ** (age_days / half_life) if age_days > 0 else 1.0

        # Provenance quality
        prov_q = _PROVENANCE_QUALITY.get(rec.provenance.primary.kind, 0.5)

        # Pinned / critical get a boost
        pin_boost = 1.5 if rec.is_decay_immune else 1.0

        # Blend recency weight with confidence
        rw = query.recency_weight
        blended = (1 - rw) * confidence + rw * recency

        score = blended * importance_w * prov_q * pin_boost

        # Normalize to 0..1 range (max theoretical = 1×2×1×1.5 = 3)
        return min(score / 3.0, 1.0)
