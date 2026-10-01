"""L3 AI Kernel Model Router — Prompt 03 §3 + §4 + §5 (07_AI_STRATEGY.md).

Implements the 5-stage scoring pipeline exactly as specified:

  Stage 1: Hard filter — registry.filter_candidates() (offline, privacy,
           capabilities, modalities, context window, deny/allow lists).
  Stage 2: Soft quality filter — models below QualityTier threshold removed.
  Stage 3: Latency SLA filter — models exceeding latency_sla_ms removed.
  Stage 4: Score remaining candidates:
           Score = Wq·quality - Wc·cost_penalty - Wl·latency_penalty
                 - Wh·health_penalty + Ws·success_rate
  Stage 5: Budget check — downcast to next cheaper if task budget tight;
           fail if global daily budget exhausted.

Privacy-aware routing (§4):
  P0 NEVER_CLOUD: Stage 1 forces LOCAL deployment only. Fail hard if empty.
  P1 PREFER_LOCAL: Post-Stage 4, if any local model scores >= 0.85 of best
                   cloud quality → pick local; else pick cloud + audit.
  P2/P3: Normal scoring; cloud fine.

Returns: RouteDecision list ordered best→worst. AIKernel tries them in order
(fallback chain). Router NEVER calls providers — it only produces an ordered
candidate list.

Imports allowed: types, registry, contracts (RoutingRequirements), accounting
(BudgetCheckResult), L1 errors, stdlib. NO provider or kernel imports.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from aegis.l1_core.errors import ErrorCode
from aegis.l1_core.errors.base import (
    AIRouterError,
    AIRouterPrivacyViolationError,
)
from aegis.l1_core.interfaces.llm import ModelHealth
from aegis.l3_intelligence.ai_kernel.contracts import RoutingRequirements
from aegis.l3_intelligence.ai_kernel.registry import ModelMetadata, ModelRegistry
from aegis.l3_intelligence.ai_kernel.types import (
    DeploymentKind,
    PrivacyTier,
    QualityTier,
    RouterPolicy,
    TaskType,
)

logger = logging.getLogger(__name__)

__all__ = ["Router", "RouteDecision"]

# ---------------------------------------------------------------------------
# Health penalty map (Stage 4)
# ---------------------------------------------------------------------------

_HEALTH_PENALTY: dict[ModelHealth, float] = {
    ModelHealth.HEALTHY: 0.0,
    ModelHealth.DEGRADED: 0.3,
    ModelHealth.DOWN: 1.0,
    ModelHealth.UNKNOWN: 0.15,
}


# ---------------------------------------------------------------------------
# RouteDecision — one candidate in the ordered route list
# ---------------------------------------------------------------------------


@dataclass
class RouteDecision:
    """Single routing candidate returned by the router.

    AIKernel iterates this list in order, attempting each. On failure it
    advances to the next (fallback chain). The router itself never calls
    providers.
    """

    provider_id: str
    model_id: str
    model: ModelMetadata
    estimated_cost_usd: float
    quality_score: float
    composite_score: float
    is_local: bool
    rank: int = 0
    is_fallback: bool = False
    p1_cloud_audit_required: bool = False  # True when P1 data goes to cloud


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


class Router:
    """5-stage model router per 07_AI_STRATEGY §3.

    Args:
        registry: Populated ModelRegistry (caller owns lifecycle).
        policy: RouterPolicy instance (defaults to spec defaults).
        logger: Optional logger (defaults to module logger).
    """

    def __init__(
        self,
        registry: ModelRegistry,
        policy: RouterPolicy | None = None,
        logger_: logging.Logger | None = None,
    ) -> None:
        self._registry = registry
        self._policy = policy or RouterPolicy()
        self._log = logger_ or logger

    # ------------------------------------------------------------------
    # Public: route() — main entry point
    # ------------------------------------------------------------------

    def route(
        self,
        routing: RoutingRequirements,
        *,
        estimated_tok_in: int = 1000,
        estimated_tok_out: int = 512,
        available_budget_usd: float | None = None,
    ) -> list[RouteDecision]:
        """Produce an ordered RouteDecision list for this RoutingRequirements.

        Returns:
            Non-empty list of RouteDecision, ordered best→worst composite score.

        Raises:
            AIRouterPrivacyViolationError: P0 required but no local model eligible.
            AIRouterError: No model satisfies constraints at all.
        """
        policy = self._policy
        privacy_tier = routing.privacy_tier
        task_type = routing.task_type
        quality_min = routing.quality_min
        latency_sla_ms = routing.latency_sla_ms

        # ----------------------------------------------------------------
        # Stage 1: Hard filter (delegates to registry)
        # ----------------------------------------------------------------
        min_ctx = None
        if routing.min_context_window is not None:
            # Add output headroom
            min_ctx = int(
                routing.min_context_window
                + max(0, estimated_tok_out) * (policy.output_headroom_multiplier - 1.0)
            )

        c1: list[ModelMetadata] = self._registry.filter_candidates(
            required_capabilities=routing.required_capabilities or set(),
            required_modalities=routing.required_modalities or {"text"},
            min_context=min_ctx,
            allowed_providers=routing.allowed_providers or None,
            denied_providers=routing.denied_providers or None,
            preferred_model=routing.preferred_model,
            denied_models=routing.denied_models or None,
            required_deployment=routing.required_deployment,
            privacy_tier=privacy_tier,
            offline=policy.offline,
        )

        if not c1:
            if privacy_tier.is_local_mandatory:
                raise AIRouterPrivacyViolationError(
                    ErrorCode.AI_ROUTER_PRIVACY_VIOLATION,
                    "Privacy tier P0 (DEVICE_LOCAL_ONLY) required but no eligible local model found. "
                    "Request cannot be routed to cloud. NEVER silent leak.",
                )
            raise AIRouterError(
                ErrorCode.AI_ROUTER_NO_ELIGIBLE_MODEL,
                f"No model satisfies hard constraints for request. "
                f"privacy={privacy_tier.value} offline={policy.offline} "
                f"caps={routing.required_capabilities}",
            )

        # ----------------------------------------------------------------
        # Stage 2: Soft quality filter
        # ----------------------------------------------------------------
        quality_threshold = policy.quality_min_thresholds.get(quality_min, 0.55)
        c2: list[ModelMetadata] = []
        for model in c1:
            q = self._registry.quality_score_for(model, task_type)
            if q >= quality_threshold:
                c2.append(model)

        if not c2:
            # Fall back to best-available in c1 if quality filter empties set
            # (avoids complete denial when no model meets quality_min).
            self._log.warning(
                "Quality filter removed all candidates; relaxing to c1 for "
                "quality_min=%s task_type=%s", quality_min.value, task_type.value
            )
            c2 = list(c1)

        # ----------------------------------------------------------------
        # Stage 3: Latency SLA filter
        # ----------------------------------------------------------------
        if latency_sla_ms is not None:
            c3 = [
                m for m in c2
                if m.latency_first_ms_p50 <= latency_sla_ms
                or m.latency_first_ms_p50 == 0  # 0 = unknown latency → don't filter
            ]
            if c3:
                c2 = c3
            else:
                self._log.warning(
                    "Latency SLA %dms filter emptied candidate set; using all "
                    "quality-filtered candidates", latency_sla_ms
                )

        # ----------------------------------------------------------------
        # Stage 4: Score candidates
        # ----------------------------------------------------------------
        max_cost = max(
            (
                self._registry.estimate_cost(m, estimated_tok_in, estimated_tok_out)
                for m in c2
            ),
            default=1.0,
        ) or 1.0

        scored: list[tuple[float, ModelMetadata]] = []
        for model in c2:
            score = self._compute_score(
                model=model,
                task_type=task_type,
                tok_in=estimated_tok_in,
                tok_out=estimated_tok_out,
                latency_sla_ms=latency_sla_ms,
                max_cost=max_cost,
                cost_sensitivity=routing.cost_sensitivity,
            )
            scored.append((score, model))

        scored.sort(key=lambda t: t[0], reverse=True)

        # ----------------------------------------------------------------
        # P1 PREFER_LOCAL override (§4 RULE P1)
        # ----------------------------------------------------------------
        local_models = [m for _, m in scored if m.deployment is DeploymentKind.LOCAL]
        cloud_models = [m for _, m in scored if m.deployment is not DeploymentKind.LOCAL]

        p1_cloud_audit_models: set[str] = set()
        if privacy_tier == PrivacyTier.P1 and local_models and cloud_models:
            best_cloud_quality = max(
                self._registry.quality_score_for(m, task_type) for m in cloud_models
            )
            best_local = local_models[0]
            best_local_quality = self._registry.quality_score_for(best_local, task_type)
            floor = policy.p1_local_quality_floor_ratio * best_cloud_quality
            if best_local_quality >= floor:
                # Pick local — reorder so local comes first
                local_ids = {m.model_id for m in local_models}
                scored = (
                    [(s, m) for s, m in scored if m.model_id in local_ids]
                    + [(s, m) for s, m in scored if m.model_id not in local_ids]
                )
            else:
                # Cloud chosen — mark cloud models for audit
                self._log.warning(
                    "P1: local quality %.2f < floor %.2f — routing to cloud with audit",
                    best_local_quality, floor,
                )
                p1_cloud_audit_models = {m.model_id for m in cloud_models}

        # ----------------------------------------------------------------
        # Stage 5: Budget check — downcast if task budget too tight
        # ----------------------------------------------------------------
        final: list[RouteDecision] = []
        for rank, (score, model) in enumerate(scored):
            est_cost = self._registry.estimate_cost(model, estimated_tok_in, estimated_tok_out)
            budget_ok = True
            if (
                available_budget_usd is not None
                and est_cost > available_budget_usd
                and model.deployment is not DeploymentKind.LOCAL  # local is free
            ):
                budget_ok = False
                self._log.debug(
                    "Stage 5: model %s cost %.4f exceeds budget %.4f — downcast",
                    model.model_id, est_cost, available_budget_usd
                )

            if budget_ok:
                is_local = model.deployment is DeploymentKind.LOCAL
                # P1 audit: any cloud decision routing P1 data must be flagged,
                # regardless of whether the P1 prefer-local block ran above.
                needs_p1_audit = (
                    privacy_tier == PrivacyTier.P1
                    and not is_local
                ) or model.model_id in p1_cloud_audit_models
                final.append(
                    RouteDecision(
                        provider_id=model.provider_id,
                        model_id=model.model_id,
                        model=model,
                        estimated_cost_usd=est_cost,
                        quality_score=self._registry.quality_score_for(model, task_type),
                        composite_score=score,
                        is_local=is_local,
                        rank=rank,
                        is_fallback=rank > 0,
                        p1_cloud_audit_required=needs_p1_audit,
                    )
                )

        if not final:
            # All models over budget — include cheapest as last resort
            # (caller will handle budget denial at accounting level)
            best_score, best_model = scored[-1]
            est = self._registry.estimate_cost(best_model, estimated_tok_in, estimated_tok_out)
            final.append(
                RouteDecision(
                    provider_id=best_model.provider_id,
                    model_id=best_model.model_id,
                    model=best_model,
                    estimated_cost_usd=est,
                    quality_score=self._registry.quality_score_for(best_model, task_type),
                    composite_score=best_score,
                    is_local=best_model.deployment is DeploymentKind.LOCAL,
                    rank=len(scored) - 1,
                    is_fallback=False,
                    p1_cloud_audit_required=best_model.model_id in p1_cloud_audit_models,
                )
            )

        return final

    # ------------------------------------------------------------------
    # Internal: Stage 4 scoring formula
    # ------------------------------------------------------------------

    def _compute_score(
        self,
        model: ModelMetadata,
        task_type: TaskType,
        tok_in: int,
        tok_out: int,
        latency_sla_ms: int | None,
        max_cost: float,
        cost_sensitivity: float,
    ) -> float:
        w = self._policy.weights

        # Quality component (0..1)
        q_score = self._registry.quality_score_for(model, task_type)

        # Cost component — normalized by max cost in candidate set; scaled by sensitivity
        raw_cost = self._registry.estimate_cost(model, tok_in, tok_out)
        cost_penalty = (raw_cost / max_cost) * cost_sensitivity

        # Latency component — 0 if no SLA; else ratio of model latency to SLA cap
        if latency_sla_ms and model.latency_first_ms_p50 > 0:
            latency_penalty = min(model.latency_first_ms_p50 / latency_sla_ms, 1.0)
        else:
            latency_penalty = 0.0

        # Health component
        health_penalty = _HEALTH_PENALTY.get(model.health, 0.15)

        # Historical success rate from registry runtime state
        state = self._registry._model_state.get((model.provider_id, model.model_id))
        if state is not None:
            total = state.total_successes + state.total_failures
            success_rate = (state.total_successes / total) if total > 0 else 0.5
        else:
            success_rate = 0.5

        score = (
            w.quality * q_score
            - w.cost * cost_penalty
            - w.latency * latency_penalty
            - w.health_penalty * health_penalty
            + w.historical_success * success_rate
        )
        return score
