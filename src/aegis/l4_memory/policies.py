"""L4 Memory policies — retention, decay, access, archival, merging.

Policies are explicit, named, and composable. They are not buried inside
storage code. Every MemoryManager operation passes through policy gates.

Design:
  - All policies are Pydantic models (serializable, auditable).
  - RetentionPolicy governs TTL overrides per tier/importance.
  - DecayPolicy governs when and how relevance scores decay.
  - AccessPolicy controls who can read/write which tiers.
  - ArchivalPolicy governs the ACTIVE → ARCHIVED transition.
  - MergePolicy controls how conflicting records are merged.

Import safety: l4_memory.types + pydantic + stdlib only.
"""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from aegis.l4_memory.types import (
    ConfidenceLevel,
    Importance,
    MemoryKind,
    MemoryStatus,
    MemoryTier,
    ProvenanceKind,
)

__all__ = [
    "RetentionPolicy",
    "DecayPolicy",
    "AccessPolicy",
    "ArchivalPolicy",
    "MergePolicy",
    "MemoryPolicy",
]


# ---------------------------------------------------------------------------
# RetentionPolicy — TTL and expiration overrides
# ---------------------------------------------------------------------------

class RetentionPolicy(BaseModel):
    """Controls how long memories are kept before expiration.

    Explicit TTL overrides per tier/importance. CRITICAL or pinned records
    are always immune regardless of policy.
    """

    model_config = {"frozen": True}

    name: str = "default_retention"

    # Default TTL overrides (seconds). None = use tier default.
    tier_ttl_overrides: dict[str, float | None] = Field(default_factory=dict)

    # Importance-based TTL multipliers (applied on top of base TTL)
    importance_ttl_multipliers: dict[str, float] = Field(
        default_factory=lambda: {
            "low": 0.5,       # LOW importance retained half as long
            "normal": 1.0,
            "high": 2.0,      # HIGH importance retained 2x as long
            "critical": 0.0,  # CRITICAL: multiplier irrelevant (immune)
        }
    )

    # Hard maximum TTL in seconds (None = no hard max)
    global_max_ttl_seconds: float | None = None

    # Minimum TTL in seconds even for LOW importance records
    global_min_ttl_seconds: float = 60.0 * 60  # 1 hour minimum

    def effective_ttl(
        self, tier: MemoryTier, importance: Importance, base_ttl: float | None
    ) -> float | None:
        """Compute the effective TTL for a record given its tier and importance."""
        if importance is Importance.CRITICAL:
            return None  # Immune from expiration

        # Check tier override
        if tier.value in self.tier_ttl_overrides:
            ttl = self.tier_ttl_overrides[tier.value]
        else:
            ttl = base_ttl

        if ttl is None:
            return None  # Keep forever

        # Apply importance multiplier
        multiplier = self.importance_ttl_multipliers.get(importance.value, 1.0)
        ttl = max(ttl * multiplier, self.global_min_ttl_seconds)

        if self.global_max_ttl_seconds is not None:
            ttl = min(ttl, self.global_max_ttl_seconds)

        return ttl


# ---------------------------------------------------------------------------
# DecayPolicy — relevance score decay (NOT importance decay)
# ---------------------------------------------------------------------------

class DecayPolicy(BaseModel):
    """Controls how relevance scoring decays with time and access patterns.

    Decay affects the score used for retrieval ranking, NOT the retention decision.
    CRITICAL or pinned memories are excluded from score decay to ensure they
    always remain visible even if infrequently accessed.

    Supported decay functions (applied to base relevance score):
      - linear: score = base - decay_rate * age_days
      - exponential: score = base * (half_life_factor ** age_days)
    """

    model_config = {"frozen": True}

    name: str = "default_decay"
    enabled: bool = True
    function: str = Field(default="exponential", pattern="^(linear|exponential)$")

    # exponential: score halves every N days (higher = slower decay)
    half_life_days: float = Field(default=90.0, gt=0.0)

    # linear: score decreases by this per day
    linear_decay_rate: float = Field(default=0.001, ge=0.0)

    # Score floor: never drop below this even if very old
    min_score: float = Field(default=0.05, ge=0.0, le=1.0)

    def compute_score(self, base_score: float, age_seconds: float) -> float:
        """Apply decay to base_score given age in seconds."""
        if not self.enabled:
            return base_score

        age_days = age_seconds / 86400.0

        if self.function == "exponential":
            import math
            factor = 0.5 ** (age_days / self.half_life_days)
            score = base_score * factor
        else:  # linear
            score = base_score - self.linear_decay_rate * age_days

        return max(score, self.min_score)


# ---------------------------------------------------------------------------
# AccessPolicy — who can read/write which tiers
# ---------------------------------------------------------------------------

class AccessPolicy(BaseModel):
    """Controls access boundaries for memory retrieval and storage.

    The MemoryManager enforces this policy on every store/retrieve call.
    Rules are additive — all applicable rules must pass.
    """

    model_config = {"frozen": True}

    name: str = "default_access"

    # Privacy tier ceiling for retrieval: records with privacy_tier < this are blocked.
    # E.g. max_retrievable_privacy_tier="P2" means P0/P1 records only go to local context.
    max_cloud_privacy_tier: str = "P2"

    # Tiers requiring explicit user opt-in before records can be searched
    requires_opt_in_tiers: frozenset[str] = Field(
        default_factory=lambda: frozenset({"T5_personal"})
    )

    # hide_from_llm: any record tagged with this metadata key is excluded from context
    hide_from_llm_tag: str = "hide_from_llm"

    def allows_cloud_retrieval(self, privacy_tier: str) -> bool:
        """True if a memory with this privacy_tier can be sent to cloud LLM context.

        Privacy order: P0 (most private/local, ordinal=0) < P1 < P2 < P3 (least private, ordinal=3).
        max_cloud_privacy_tier sets the minimum ordinal required for cloud retrieval.
        Records with rec_order >= max_order pass; records below are blocked.

        Examples:
          max_cloud_privacy_tier="P2": P0(0)>=2=False, P1(1)>=2=False, P2(2)>=2=True, P3(3)>=2=True
          max_cloud_privacy_tier="P0": everything >=0 passes (no cloud restriction by ordinal alone)
        """
        tier_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
        max_order = tier_order.get(self.max_cloud_privacy_tier, 2)
        rec_order = tier_order.get(privacy_tier, 0)
        return rec_order >= max_order

    def is_tier_searchable_without_opt_in(self, tier: MemoryTier) -> bool:
        return tier.value not in self.requires_opt_in_tiers


# ---------------------------------------------------------------------------
# ArchivalPolicy — ACTIVE → ARCHIVED transition rules
# ---------------------------------------------------------------------------

class ArchivalPolicy(BaseModel):
    """Controls when memories are archived (soft-removed from default retrieval).

    Archived memories are retained but excluded from normal search.
    They can be restored at any time.
    """

    model_config = {"frozen": True}

    name: str = "default_archival"

    # Archive records not accessed in N days (0 = never auto-archive)
    archive_after_days_not_accessed: float = Field(default=365.0, ge=0.0)

    # Never auto-archive these tiers
    immune_tiers: frozenset[str] = Field(
        default_factory=lambda: frozenset({
            MemoryTier.T5_PERSONAL.value,
            MemoryTier.T7_PROJECT.value,
        })
    )

    def should_archive(
        self,
        tier: MemoryTier,
        is_pinned: bool,
        importance: Importance,
        last_accessed_at: float | None,
        now: float | None = None,
    ) -> bool:
        if is_pinned or importance.decay_immune:
            return False
        if tier.value in self.immune_tiers:
            return False
        if self.archive_after_days_not_accessed <= 0:
            return False
        if last_accessed_at is None:
            return False
        now = now or time.time()
        age_days = (now - last_accessed_at) / 86400.0
        return age_days >= self.archive_after_days_not_accessed


# ---------------------------------------------------------------------------
# MergePolicy — how conflicting records are merged
# ---------------------------------------------------------------------------

class MergePolicy(BaseModel):
    """Controls conflict resolution when two records have the same key.

    Strategy options:
      - keep_highest_confidence: prefer the record with higher confidence score
      - keep_latest: prefer the most recently created/updated record
      - keep_user_provided: prefer records with USER_PROVIDED provenance
      - create_conflict: create a CONFLICTING_WITH relationship; let user resolve
    """

    model_config = {"frozen": True}

    name: str = "default_merge"
    strategy: str = Field(
        default="keep_highest_confidence",
        pattern="^(keep_highest_confidence|keep_latest|keep_user_provided|create_conflict)$",
    )

    # Minimum confidence difference to prefer one over another (otherwise keep_latest)
    confidence_threshold_delta: float = Field(default=0.10, ge=0.0, le=1.0)

    def should_replace(
        self,
        existing_confidence: float,
        new_confidence: float,
        existing_provenance_kind: ProvenanceKind,
        existing_updated_at: float,
        new_updated_at: float,
    ) -> bool:
        """Return True if the new record should replace the existing one."""
        if self.strategy == "keep_latest":
            return new_updated_at > existing_updated_at
        if self.strategy == "keep_user_provided":
            return existing_provenance_kind not in {
                ProvenanceKind.USER_PROVIDED,
                ProvenanceKind.USER_CONFIRMED,
            }
        if self.strategy == "create_conflict":
            return False  # Caller handles conflict edge
        # default: keep_highest_confidence
        delta = new_confidence - existing_confidence
        if abs(delta) < self.confidence_threshold_delta:
            return new_updated_at > existing_updated_at
        return delta > 0


# ---------------------------------------------------------------------------
# MemoryPolicy — composite policy bundle
# ---------------------------------------------------------------------------

class MemoryPolicy(BaseModel):
    """Composite policy bundle. MemoryManager holds one of these.

    Every MemoryManager operation passes through all applicable sub-policies.
    Policies are explicit and serializable — never buried in storage code.
    """

    model_config = {"frozen": True}

    name: str = "default"
    retention: RetentionPolicy = Field(default_factory=RetentionPolicy)
    decay: DecayPolicy = Field(default_factory=DecayPolicy)
    access: AccessPolicy = Field(default_factory=AccessPolicy)
    archival: ArchivalPolicy = Field(default_factory=ArchivalPolicy)
    merge: MergePolicy = Field(default_factory=MergePolicy)

    @classmethod
    def default(cls) -> "MemoryPolicy":
        return cls()

    @classmethod
    def strict_privacy(cls) -> "MemoryPolicy":
        """Policy that treats everything as P0: never allows cloud retrieval."""
        return cls(
            name="strict_privacy",
            access=AccessPolicy(max_cloud_privacy_tier="P0"),
        )

    @classmethod
    def ephemeral(cls) -> "MemoryPolicy":
        """Policy for short-lived test/ephemeral contexts: aggressive TTL."""
        return cls(
            name="ephemeral",
            retention=RetentionPolicy(
                tier_ttl_overrides={t.value: 60.0 for t in MemoryTier},
            ),
            archival=ArchivalPolicy(archive_after_days_not_accessed=1.0),
        )
