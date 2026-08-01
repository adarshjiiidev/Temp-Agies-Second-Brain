"""L4 Memory — ContextBuilder: 5-stage recall pipeline for AI context assembly.

Implements the Retrieval Pipeline per 06_MEMORY_KNOWLEDGE.md §3.1:

  Stage 1: Query Decomposition — determine which tiers to query.
  Stage 2: Per-Tier Retrieval — retrieve candidates per tier.
  Stage 3: Rerank — cross-tier rerank with confidence/privacy/provenance/staleness.
  Stage 4: Context Window Budget — pack bounded tokens per tier.
  Stage 5: Assemble Typed Context Package — structured sections for LLM prompt.

Privacy invariant (§3.2):
  P0 DEVICE_LOCAL_ONLY memory NEVER reaches cloud prompt context.
  This class enforces the exclusion. The AIKernel is the final enforcement
  point, but ContextBuilder pre-filters so that P0 records never appear
  in any ContextPackage targeted at a cloud model.

Import safety: l4_memory.* + stdlib ONLY. No L3 imports.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from aegis.l4_memory.models import MemoryRecord
from aegis.l4_memory.search import SearchQuery, SearchResult
from aegis.l4_memory.types import (
    Importance,
    MemoryStatus,
    MemoryTier,
    ProvenanceKind,
    SearchMode,
)

__all__ = [
    "ContextRequest",
    "ContextSection",
    "ContextPackage",
    "ContextBuilder",
]

# ---------------------------------------------------------------------------
# Token budget per tier (per §3.1 Stage 4)
# ---------------------------------------------------------------------------

_DEFAULT_TIER_TOKEN_BUDGET: dict[MemoryTier, int] = {
    MemoryTier.T0_WORKING:      0,       # never persisted — in-context only
    MemoryTier.T1_SESSION:      2048,
    MemoryTier.T2_EPISODIC:     1024,
    MemoryTier.T3_SEMANTIC:     1024,
    MemoryTier.T4_PROCEDURAL:   1024,
    MemoryTier.T5_PERSONAL:     512,     # spec: "T5 max 512 tok"
    MemoryTier.T6_ENVIRONMENTAL: 256,
    MemoryTier.T7_PROJECT:      512,     # spec: "T7 max 512 tok"
    MemoryTier.T8_SKILL:        256,
}

# Approx chars → tokens ratio (conservative)
_CHARS_PER_TOKEN = 3.5

# ---------------------------------------------------------------------------
# ContextRequest
# ---------------------------------------------------------------------------


@dataclass
class ContextRequest:
    """Input to ContextBuilder describing what context is needed.

    Args:
        query:              The natural-language query or task description.
        tiers:              Tiers to retrieve from (None = all active tiers).
        namespace:          Memory namespace (default: "global").
        project_id:         Restrict project memory to this project.
        session_id:         Restrict session memory to this session.
        target_privacy_tier: The routing privacy tier for this context package.
                             P0 = local-only; P2 = standard cloud.
                             Records with higher privacy than target are EXCLUDED.
        max_total_tokens:   Total token budget for all tiers (None = no global limit).
        tier_token_budgets: Override per-tier budgets.
        min_confidence:     Minimum confidence score for included records.
        include_draft:      Include DRAFT records (default: False).
        include_archived:   Include ARCHIVED records (default: False).
        max_records_per_tier: Max candidate records per tier before token budgeting.
    """

    query: str
    tiers: list[MemoryTier] | None = None
    namespace: str = "global"
    project_id: str | None = None
    session_id: str | None = None
    target_privacy_tier: str = "P2"
    max_total_tokens: int | None = 6144
    tier_token_budgets: dict[MemoryTier, int] | None = None
    min_confidence: float = 0.3
    include_draft: bool = False
    include_archived: bool = False
    max_records_per_tier: int = 30


# ---------------------------------------------------------------------------
# ContextSection
# ---------------------------------------------------------------------------


@dataclass
class ContextSection:
    """A single tier's worth of memory content in the assembled context."""

    tier: MemoryTier
    tier_label: str
    records: list[MemoryRecord]
    token_estimate: int
    was_truncated: bool = False

    def render_text(self) -> str:
        """Render this section as a labeled text block for LLM injection."""
        if not self.records:
            return ""
        lines = [
            f"### MEMORY [{self.tier_label}]",
        ]
        if self.was_truncated:
            lines.append("(truncated — not all records shown)")
        for rec in self.records:
            prov = rec.provenance.primary.kind.value
            conf = f"{rec.confidence:.2f}"
            content_str = _content_to_str(rec.content)
            lines.append(
                f"- [{rec.importance.value.upper()}] [{prov}] [conf={conf}] {content_str}"
            )
            if rec.summary:
                lines.append(f"  Summary: {rec.summary}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# ContextPackage
# ---------------------------------------------------------------------------


@dataclass
class ContextPackage:
    """The fully assembled context ready for injection into an AI prompt.

    Produced by ContextBuilder after the 5-stage recall pipeline.
    """

    query: str
    sections: list[ContextSection]
    total_token_estimate: int
    privacy_tier: str
    build_latency_ms: float
    excluded_p0_count: int = 0       # Number of P0 records excluded for cloud routing
    metadata: dict[str, Any] = field(default_factory=dict)

    def render_system_block(self) -> str:
        """Render all sections as a single text block for system_instruction."""
        parts = []
        for section in self.sections:
            rendered = section.render_text()
            if rendered:
                parts.append(rendered)
        if not parts:
            return ""
        header = "## AEGIS MEMORY CONTEXT\n"
        footer = "\n### END MEMORY CONTEXT"
        return header + "\n\n".join(parts) + footer

    @property
    def is_empty(self) -> bool:
        return all(not s.records for s in self.sections)


# ---------------------------------------------------------------------------
# ContextBuilder
# ---------------------------------------------------------------------------


class ContextBuilder:
    """5-stage recall pipeline producing ContextPackage for AI prompts.

    Usage::

        builder = ContextBuilder(manager)
        package = await builder.build(ContextRequest(
            query="What did we discuss about the AI Kernel?",
            project_id="aegis",
            session_id="session_abc",
        ))
        # Inject into AIRequest:
        ai_request = AIRequest(
            messages=[...],
            system_instruction=package.render_system_block(),
        )
    """

    def __init__(self, manager: Any) -> None:  # manager: MemoryManager
        self._mgr = manager

    async def build(self, request: ContextRequest) -> ContextPackage:
        """Execute 5-stage recall pipeline and return ContextPackage."""
        start = time.monotonic()

        # Stage 1: Determine which tiers to query
        tiers = self._stage1_decompose(request)

        # Stage 2: Per-tier retrieval
        candidates_by_tier = await self._stage2_retrieve(request, tiers)

        # Stage 3: Rerank within each tier
        ranked_by_tier = self._stage3_rerank(candidates_by_tier, request)

        # Stage 4: Apply token budgets
        budgeted, excluded_p0 = self._stage4_budget(ranked_by_tier, request)

        # Stage 5: Assemble context package
        sections, total_tokens = self._stage5_assemble(budgeted, request)

        elapsed_ms = (time.monotonic() - start) * 1000

        return ContextPackage(
            query=request.query,
            sections=sections,
            total_token_estimate=total_tokens,
            privacy_tier=request.target_privacy_tier,
            build_latency_ms=elapsed_ms,
            excluded_p0_count=excluded_p0,
            metadata={"tiers_queried": [t.value for t in tiers]},
        )

    # ------------------------------------------------------------------
    # Stage 1: Query Decomposition
    # ------------------------------------------------------------------

    def _stage1_decompose(self, request: ContextRequest) -> list[MemoryTier]:
        """Determine which tiers to query. T0 is never queried (in-context only)."""
        if request.tiers:
            return [t for t in request.tiers if t is not MemoryTier.T0_WORKING]

        # Default: query all durable tiers
        return [
            MemoryTier.T1_SESSION,
            MemoryTier.T2_EPISODIC,
            MemoryTier.T3_SEMANTIC,
            MemoryTier.T4_PROCEDURAL,
            MemoryTier.T5_PERSONAL,
            MemoryTier.T6_ENVIRONMENTAL,
            MemoryTier.T7_PROJECT,
            MemoryTier.T8_SKILL,
        ]

    # ------------------------------------------------------------------
    # Stage 2: Per-Tier Retrieval
    # ------------------------------------------------------------------

    async def _stage2_retrieve(
        self, request: ContextRequest, tiers: list[MemoryTier]
    ) -> dict[MemoryTier, list[SearchResult]]:
        """Execute a search query per tier, collect candidate results."""
        results: dict[MemoryTier, list[SearchResult]] = {}

        for tier in tiers:
            query = SearchQuery(
                text=request.query if request.query else None,
                mode=SearchMode.HYBRID if request.query else SearchMode.METADATA,
                tiers=[tier],
                namespace=request.namespace,
                project_id=request.project_id if tier in (
                    MemoryTier.T7_PROJECT, MemoryTier.T1_SESSION
                ) else None,
                session_id=request.session_id if tier in (
                    MemoryTier.T1_SESSION,
                ) else None,
                min_confidence=request.min_confidence,
                include_draft=request.include_draft,
                limit=request.max_records_per_tier,
            )
            tier_results = await self._mgr.search(query)
            results[tier] = tier_results

        return results

    # ------------------------------------------------------------------
    # Stage 3: Rerank
    # ------------------------------------------------------------------

    def _stage3_rerank(
        self,
        candidates: dict[MemoryTier, list[SearchResult]],
        request: ContextRequest,
    ) -> dict[MemoryTier, list[SearchResult]]:
        """Apply cross-tier reranking rules per §3.1:
          - Privacy tier compliance: exclude records above target_privacy_tier
          - Staleness penalty for T3/T6
          - Provenance quality boost
          - Sort by score descending within each tier
        """
        target_order = _privacy_order(request.target_privacy_tier)
        reranked: dict[MemoryTier, list[SearchResult]] = {}

        for tier, results in candidates.items():
            reranked_tier: list[SearchResult] = []
            for result in results:
                rec = result.record
                rec_order = _privacy_order(rec.privacy_tier)

                # Privacy compliance: records MORE private than target are excluded
                # P0 (order=0) is more private than P2 (order=2)
                if rec_order < target_order:
                    # P0 record cannot go to P2 target (cloud)
                    continue

                # Staleness penalty for T3 Semantic and T6 Environmental
                score = result.score
                if tier in (MemoryTier.T3_SEMANTIC, MemoryTier.T6_ENVIRONMENTAL):
                    age_days = (time.time() - rec.updated_at) / 86400
                    if age_days > 90:
                        score *= 0.7
                    elif age_days > 365:
                        score *= 0.4

                # hide_from_llm tags: exclude entirely
                if "hide_from_llm" in rec.tags:
                    continue

                reranked_tier.append(SearchResult(
                    record=rec,
                    score=score,
                    matched_mode=result.matched_mode,
                ))

            reranked_tier.sort(key=lambda r: r.score, reverse=True)
            reranked[tier] = reranked_tier

        return reranked

    # ------------------------------------------------------------------
    # Stage 4: Token Budget
    # ------------------------------------------------------------------

    def _stage4_budget(
        self,
        ranked: dict[MemoryTier, list[SearchResult]],
        request: ContextRequest,
    ) -> tuple[dict[MemoryTier, tuple[list[SearchResult], bool]], int]:
        """Apply per-tier token budgets. Returns (budgeted, excluded_p0_count)."""
        budgets = request.tier_token_budgets or _DEFAULT_TIER_TOKEN_BUDGET
        global_remaining = request.max_total_tokens
        excluded_p0 = 0
        budgeted: dict[MemoryTier, tuple[list[SearchResult], bool]] = {}

        for tier, results in ranked.items():
            tier_budget = budgets.get(tier, 512)
            included: list[SearchResult] = []
            tier_tokens = 0
            was_truncated = False

            for result in results:
                rec = result.record
                # Count P0 exclusions for audit
                if rec.privacy_tier == "P0" and _privacy_order(request.target_privacy_tier) > 0:
                    excluded_p0 += 1
                    continue

                est = _estimate_tokens(rec)
                if tier_tokens + est > tier_budget:
                    was_truncated = True
                    break
                if global_remaining is not None and (
                    sum(
                        sum(_estimate_tokens(r.record) for r in inc_list)
                        for inc_list, _ in budgeted.values()
                        if inc_list
                    ) + tier_tokens + est
                ) > global_remaining:
                    was_truncated = True
                    break

                included.append(result)
                tier_tokens += est

            budgeted[tier] = (included, was_truncated)

        return budgeted, excluded_p0

    # ------------------------------------------------------------------
    # Stage 5: Assemble
    # ------------------------------------------------------------------

    def _stage5_assemble(
        self,
        budgeted: dict[MemoryTier, tuple[list[SearchResult], bool]],
        request: ContextRequest,
    ) -> tuple[list[ContextSection], int]:
        """Build ContextSection list and total token estimate."""
        sections: list[ContextSection] = []
        total_tokens = 0

        tier_labels: dict[MemoryTier, str] = {
            MemoryTier.T1_SESSION:      "Session",
            MemoryTier.T2_EPISODIC:     "Episodic",
            MemoryTier.T3_SEMANTIC:     "Semantic",
            MemoryTier.T4_PROCEDURAL:   "Procedural",
            MemoryTier.T5_PERSONAL:     "Personal",
            MemoryTier.T6_ENVIRONMENTAL:"Environmental",
            MemoryTier.T7_PROJECT:      "Project",
            MemoryTier.T8_SKILL:        "Skill",
        }

        for tier, (results, truncated) in budgeted.items():
            if not results:
                continue
            records = [r.record for r in results]
            est = sum(_estimate_tokens(rec) for rec in records)
            total_tokens += est
            sections.append(ContextSection(
                tier=tier,
                tier_label=tier_labels.get(tier, tier.value),
                records=records,
                token_estimate=est,
                was_truncated=truncated,
            ))

        return sections, total_tokens


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _privacy_order(tier: str) -> int:
    """Lower = more private. P0=0, P1=1, P2=2, P3=3."""
    return {"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(tier, 2)


def _estimate_tokens(record: MemoryRecord) -> int:
    """Rough token estimate for a MemoryRecord."""
    content_str = _content_to_str(record.content)
    summary_str = record.summary or ""
    total_chars = len(content_str) + len(summary_str) + 50  # label overhead
    return max(1, int(total_chars / _CHARS_PER_TOKEN))


def _content_to_str(content: Any) -> str:
    """Convert record content to a string representation."""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        parts = []
        for k, v in content.items():
            parts.append(f"{k}: {v}")
        return "; ".join(parts)
    return str(content)
