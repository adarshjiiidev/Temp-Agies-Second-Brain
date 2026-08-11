"""L3 AI Kernel Model Registry (Prompt 03 §8 + §9).

Declarative, data-driven model catalog with capability matching — NO hardcoded
routing logic lives here. Every model is described by a ModelMetadata record,
and the ModelRegistry exposes composable filters (capabilities, modalities,
context window, deployment kind, privacy tiers, provider/model allow/deny
lists, preferred model pinning) that the Router consumes to produce a candidate
shortlist. Scoring itself is the Router's responsibility; this module only
answers "which models are eligible" and "how well does this model match the
declared capability requirements".

§8 ModelMetadata = normalized catalog schema (provider, context, costs,
capabilities, privacy tiers, health, per-task quality priors).

§9 filter_candidates() = 10-stage hard filter pipeline in strict order
(offline → deployment → P0 local-only → privacy tier rank → capabilities →
modalities → context → deny → allow → preferred prepend).

This module MUST stay import-safe: it imports ONLY from ai_kernel.types (L3
primitive enums), aegis.l1_core.interfaces.llm (ModelHealth forward-decl),
stdlib, and pydantic. It MUST NOT import contracts, kernel, router, or
provider modules to eliminate circular-import risk.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from aegis.l1_core.interfaces.llm import ModelHealth
from aegis.l3_intelligence.ai_kernel.types import (
    DeploymentKind,
    PrivacyTier,
    TaskType,
)


# ---------------------------------------------------------------------------
# ModelCapability — Prompt 03 §8.1 normalized capability vocabulary.
# Every capability string in ModelMetadata.capabilities SHOULD be a member of
# this enum; free-form strings are also accepted for vendor-specific extras.
# ---------------------------------------------------------------------------


class ModelCapability(str, Enum):
    """Prompt 03 §8.1 normalized model capability vocabulary.

    Router filter_candidates() stage 5 does set-subset matching against
    model.capabilities; using these enum members guarantees string
    consistency across the system.
    """

    REASONING = "reasoning"
    CODING = "coding"
    STRUCTURED_OUTPUT_JSON = "structured_output_json"
    FUNCTION_CALLING = "function_calling"
    VISION = "vision"
    AUDIO = "audio"
    STREAMING = "streaming"
    LONG_CONTEXT = "long_context"
    TOOL_USE = "tool_use"
    EMBEDDING = "embedding"
    CODE_INTERPRETER = "code_interpreter"
    SEARCH = "search"


# ---------------------------------------------------------------------------
# ModelMetadata — Prompt 03 §8 single catalog entry (Pydantic v2, mutable
# fields so health/counters can be updated in-place by the registry).
# ---------------------------------------------------------------------------


def _default_all_privacy_tiers() -> set[PrivacyTier]:
    return {PrivacyTier.P0, PrivacyTier.P1, PrivacyTier.P2, PrivacyTier.P3}


class ModelMetadata(BaseModel):
    """Prompt 03 §8 declarative model catalog entry.

    One record per (provider_id, model_id) tuple. Registry keys on this
    composite. All cost/latency figures are p50 baselines used by Router
    Stage 4 scoring; real runtime values feed AIMetricsRegistry and
    gradually override these priors via quality_score_for() heuristics.
    """

    model_config = ConfigDict(
        frozen=False,
        extra="forbid",
        arbitrary_types_allowed=True,
        protected_namespaces=(),
    )

    # ---- Identity -------------------------------------------------------
    model_id: str
    provider_id: str
    family: str
    display_name: str

    # ---- Deployment / scale --------------------------------------------
    deployment: DeploymentKind
    context_window: int = Field(..., ge=1)
    output_limit: int = Field(..., ge=1)

    # ---- Modalities / capabilities -------------------------------------
    modalities: set[str] = Field(default_factory=lambda: {"text"})
    capabilities: set[str] = Field(default_factory=set)

    # ---- Cost (USD) ----------------------------------------------------
    cost_per_input_1k: float = Field(default=0.0, ge=0.0)
    cost_per_output_1k: float = Field(default=0.0, ge=0.0)

    # ---- Performance ---------------------------------------------------
    latency_first_ms_p50: int = Field(default=0, ge=0)
    throughput_tps_p50: int = Field(default=0, ge=0)

    # ---- Privacy -------------------------------------------------------
    supported_privacy_tiers: set[PrivacyTier] = Field(
        default_factory=_default_all_privacy_tiers
    )

    # ---- Quality priors ------------------------------------------------
    reliability_score: float = Field(default=0.5, ge=0.0, le=1.0)
    structural_compliance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    quality_scores: dict[TaskType, float] = Field(default_factory=dict)

    # ---- Health --------------------------------------------------------
    health: ModelHealth = Field(default=ModelHealth.UNKNOWN)
    last_health_check: float = Field(default=0.0, ge=0.0)

    # ---- Tags / extras -------------------------------------------------
    tags: set[str] = Field(default_factory=set)
    extra: dict[str, Any] = Field(default_factory=dict)

    # ---- Validators ----------------------------------------------------

    @field_validator("supported_privacy_tiers")
    @classmethod
    def _privacy_tiers_nonempty(cls, v: set[PrivacyTier]) -> set[PrivacyTier]:
        if not v:
            raise ValueError("supported_privacy_tiers must be non-empty")
        return v

    @field_validator("quality_scores")
    @classmethod
    def _quality_scores_bounded(
        cls, v: dict[TaskType, float]
    ) -> dict[TaskType, float]:
        for k, val in v.items():
            if not (0.0 <= val <= 1.0):
                raise ValueError(
                    f"quality_scores[{k!r}]={val} must be in [0.0, 1.0]"
                )
        return v


# ---------------------------------------------------------------------------
# Internal state bag — tracks per-(provider,model) outcome counters outside
# the Pydantic model so record_outcome() does not mutate validated fields.
# ---------------------------------------------------------------------------


@dataclass
class _ModelRuntimeState:
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    total_failures: int = 0
    total_successes: int = 0


# ---------------------------------------------------------------------------
# ModelRegistry — Prompt 03 §9 data-driven candidate filter.
#
# NOT a Pydantic model. Mutable state: _models dict, _model_state counters.
# ---------------------------------------------------------------------------


class ModelRegistry:
    """Prompt 03 §9 model catalog + declarative candidate filter.

    Responsibilities:
      * Register / unregister ModelMetadata records (composite key:
        (provider_id, model_id) — duplicates raise ValueError).
      * Introspection: list_all, list_for_provider, get.
      * filter_candidates(): 10-stage hard filter pipeline matching the
        exact ordering in Prompt 03 §9.1.
      * Helpers used by Router scoring: capability_match_score,
        estimate_cost, estimate_context_ok, quality_score_for.
      * Runtime accounting: update_health, record_outcome.
    """

    def __init__(
        self, models: list[ModelMetadata] | None = None
    ) -> None:
        self._models: dict[tuple[str, str], ModelMetadata] = {}
        self._model_state: dict[tuple[str, str], _ModelRuntimeState] = {}

        if models:
            for m in models:
                self.register(m)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, model: ModelMetadata) -> None:
        key = (model.provider_id, model.model_id)
        if key in self._models:
            raise ValueError(
                f"Duplicate model registration: provider={model.provider_id!r} "
                f"model_id={model.model_id!r}"
            )
        self._models[key] = model
        if key not in self._model_state:
            self._model_state[key] = _ModelRuntimeState()

    def unregister(self, model_id: str, provider_id: str) -> bool:
        key = (provider_id, model_id)
        existed = key in self._models
        if existed:
            del self._models[key]
            self._model_state.pop(key, None)
        return existed

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def get(
        self, model_id: str, provider_id: str | None = None
    ) -> ModelMetadata | None:
        if provider_id is not None:
            return self._models.get((provider_id, model_id))
        for (pid, mid), m in self._models.items():
            if mid == model_id:
                return m
        return None

    def list_all(self) -> list[ModelMetadata]:
        return list(self._models.values())

    def list_for_provider(self, provider_id: str) -> list[ModelMetadata]:
        return [
            m for (pid, _), m in self._models.items() if pid == provider_id
        ]

    # ------------------------------------------------------------------
    # §9 filter_candidates() — 10-stage hard filter in strict order.
    # ------------------------------------------------------------------

    def filter_candidates(
        self,
        *,
        required_capabilities: set[str] | None = None,
        required_modalities: set[str] | None = None,
        min_context: int | None = None,
        allowed_providers: list[str] | None = None,
        denied_providers: list[str] | None = None,
        preferred_model: str | None = None,
        denied_models: list[str] | None = None,
        required_deployment: DeploymentKind | None = None,
        privacy_tier: PrivacyTier = PrivacyTier.STANDARD,
        offline: bool = False,
    ) -> list[ModelMetadata]:
        req_caps: set[str] = required_capabilities or set()
        req_mods: set[str] = required_modalities or {"text"}
        deny_provs: set[str] = set(denied_providers or [])
        allow_provs: set[str] = set(allowed_providers or [])
        deny_models: set[str] = set(denied_models or [])

        candidates = list(self._models.values())
        filtered: list[ModelMetadata] = []

        for model in candidates:
            # Stage 1: offline → LOCAL deployment only
            if offline and model.deployment is not DeploymentKind.LOCAL:
                continue

            # Stage 2: explicit required_deployment filter
            if (
                required_deployment is not None
                and model.deployment is not required_deployment
            ):
                continue

            # Stage 3: P0 privacy → LOCAL deployment AND P0 in supported tiers
            if privacy_tier.is_local_mandatory:
                if model.deployment is not DeploymentKind.LOCAL:
                    continue
                if privacy_tier not in model.supported_privacy_tiers:
                    continue

            # Stage 4: P1/P2/P3 privacy tier via numeric_rank set containment
            if not privacy_tier.is_local_mandatory:
                allowed_rank = privacy_tier.numeric_rank
                model_eligible_ranks = {
                    t.numeric_rank for t in model.supported_privacy_tiers
                }
                if allowed_rank not in model_eligible_ranks:
                    continue

            # Stage 5: required_capabilities ⊆ model.capabilities
            if not req_caps.issubset(model.capabilities):
                continue

            # Stage 6: required_modalities ⊆ model.modalities
            if not req_mods.issubset(model.modalities):
                continue

            # Stage 7: min_context window
            if min_context is not None and model.context_window < min_context:
                continue

            # Stage 8: denied providers / models
            if model.provider_id in deny_provs:
                continue
            if model.model_id in deny_models:
                continue

            # Stage 9: allowed providers (non-empty → whitelist)
            if allow_provs and model.provider_id not in allow_provs:
                continue

            filtered.append(model)

        # Stage 10: preferred_model (if set AND still in filtered → prepend)
        if preferred_model:
            preferred_idx: int | None = None
            for i, m in enumerate(filtered):
                if m.model_id == preferred_model:
                    preferred_idx = i
                    break
            if preferred_idx is not None:
                pref = filtered.pop(preferred_idx)
                filtered.insert(0, pref)

        return filtered

    # ------------------------------------------------------------------
    # Scoring helpers (used by Router Stage 4)
    # ------------------------------------------------------------------

    def capability_match_score(
        self, model: ModelMetadata, required_capabilities: set[str]
    ) -> float:
        if not required_capabilities:
            return 1.0
        matched = required_capabilities & set(model.capabilities)
        return len(matched) / len(required_capabilities)

    def estimate_cost(
        self, model: ModelMetadata, tok_in: int, tok_out_est: int
    ) -> float:
        return (
            (max(tok_in, 0) / 1000.0) * model.cost_per_input_1k
            + (max(tok_out_est, 0) / 1000.0) * model.cost_per_output_1k
        )

    def estimate_context_ok(
        self,
        model: ModelMetadata,
        tok_in: int,
        tok_out_est: int,
        headroom: float = 1.2,
    ) -> bool:
        needed = max(tok_in, 0) + int(max(tok_out_est, 0) * headroom)
        return needed <= model.context_window

    # ------------------------------------------------------------------
    # Health & outcome accounting
    # ------------------------------------------------------------------

    def update_health(
        self,
        model_id: str,
        provider_id: str,
        health: ModelHealth,
        ts: float | None = None,
    ) -> bool:
        key = (provider_id, model_id)
        model = self._models.get(key)
        if model is None:
            return False
        model.health = health
        model.last_health_check = ts if ts is not None else time.time()
        return True

    def record_outcome(
        self, model_id: str, provider_id: str, success: bool
    ) -> None:
        key = (provider_id, model_id)
        state = self._model_state.get(key)
        if state is None:
            if key not in self._models:
                return
            state = _ModelRuntimeState()
            self._model_state[key] = state

        if success:
            state.consecutive_successes += 1
            state.consecutive_failures = 0
            state.total_successes += 1
        else:
            state.consecutive_failures += 1
            state.consecutive_successes = 0
            state.total_failures += 1

    # ------------------------------------------------------------------
    # Quality scoring heuristic
    # ------------------------------------------------------------------

    def quality_score_for(
        self, model: ModelMetadata, task_type: TaskType
    ) -> float:
        preset = model.quality_scores.get(task_type)
        if preset is not None:
            return preset

        structural = model.structural_compliance_score
        reliability = model.reliability_score
        has_long_context = (
            ModelCapability.LONG_CONTEXT.value in model.capabilities
            or "long_context" in model.capabilities
        )
        long_context_bonus = 0.5 if has_long_context else 0.0

        # reliability must contribute EXACTLY ONCE (structural*0.35 + reliability*0.35 + long_context_bonus)
        # Bug H12: the bare `+ reliability` below was a double-count — fixed 2026-08-08.
        score = (
            structural * 0.35
            + reliability * 0.35
            + long_context_bonus
        )

        if score < 0.0:
            return 0.0
        if score > 1.0:
            return 1.0
        if score == 0.0:
            return 0.5
        return score


__all__ = [
    "ModelCapability",
    "ModelMetadata",
    "ModelRegistry",
]
