"""L6 Planning Engine — Scoring Engine.

Computes multi-dimensional scores for plans using configurable weights.
All scores are in [0, 1] where higher = better.

Magic constants remediation (H9): All unnamed numeric thresholds have been
extracted to ``ScoringConfig`` so they can be overridden at injection time
without modifying this module.

Import safety: stdlib + pydantic + l6_planning.types only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from aegis.l6_planning.types import (
    PlanScore,
    PlanningStrategy,
    RiskLevel,
    ScoringWeights,
)

__all__ = ["ScoringEngine", "ScoringConfig"]


@dataclass
class ScoringConfig:
    """Named, overridable constants for ScoringEngine heuristics.

    Every value that was previously a bare magic number is documented
    here with its rationale. Override at injection time to tune scoring
    without editing this module.

    Usage::

        config = ScoringConfig(
            quality_confidence_weight=0.7,   # value confidence more
            quality_thoroughness_weight=0.2,
        )
        engine = ScoringEngine(config=config)

    Architecture: these are ``tunable weights``, not intelligence.
    They define what "quality" and "speed" mean numerically.
    """

    # ── Quality dimension ──────────────────────────────────────────────
    # Max tasks that contributes to "thoroughness" (15 = sufficiently large plan)
    quality_max_tasks_for_thoroughness: int = 15
    # Per-approval-point bonus cap and per-point weight
    quality_approval_bonus_cap: float = 0.20
    quality_approval_per_point: float = 0.05
    # Weighted mix: confidence=0.6, thoroughness=0.3, approval=0.1
    quality_confidence_weight: float = 0.60
    quality_thoroughness_weight: float = 0.30
    quality_approval_weight: float = 0.10

    # ── Cost dimension ────────────────────────────────────────────────
    # Per-task penalty (higher task count = higher cost estimate)
    cost_per_task_penalty: float = 0.03
    cost_task_penalty_cap: float = 0.50
    # Flat penalty for plans requiring internet
    cost_internet_penalty: float = 0.10

    # ── Risk score (inverted — lower risk = higher score) ─────────────
    risk_score_low: float = 1.00
    risk_score_medium: float = 0.70
    risk_score_high: float = 0.40
    risk_score_critical: float = 0.10

    # ── Privacy dimension ─────────────────────────────────────────────
    privacy_score_with_internet: float = 0.40
    privacy_score_local_only: float = 1.00

    # ── Success probability factors ───────────────────────────────────
    # Per-approval-point penalty on success probability
    success_approval_penalty_per_point: float = 0.05
    success_min_approval_factor: float = 0.70
    # Per-task complexity penalty on success probability
    success_complexity_per_task: float = 0.02
    success_min_complexity_factor: float = 0.60

    # ── Speed dimension: log10-based decay ────────────────────────────
    # log10(estimated_seconds) / speed_log_divisor subtracted from 1.0
    # log10(60)=1.78→score≈0.64; log10(3600)=3.56→score≈0.29; log10(86400)=4.93→score≈0.01
    speed_log_divisor: float = 5.0

    @classmethod
    def default(cls) -> "ScoringConfig":
        """Return the default scoring config (equivalent to pre-H9 magic numbers)."""
        return cls()


class ScoringEngine:
    """Computes PlanScore for a plan given its metrics and weights.

    Usage::

        engine = ScoringEngine()
        score = engine.score(
            plan_id="abc",
            task_count=10,
            approval_points=2,
            estimated_seconds=3600,
            risk_level=RiskLevel.MEDIUM,
            internet_required=False,
            strategy=PlanningStrategy.BALANCED,
        )

    To customise scoring behaviour::

        config = ScoringConfig(quality_confidence_weight=0.8)
        engine = ScoringEngine(config=config)
    """

    def __init__(self, config: ScoringConfig | None = None) -> None:
        self._cfg = config or ScoringConfig.default()

    def score(
        self,
        plan_id: str,
        task_count: int,
        approval_points: int,
        estimated_seconds: float,
        risk_level: RiskLevel,
        internet_required: bool,
        strategy: PlanningStrategy = PlanningStrategy.BALANCED,
        confidence: float = 0.7,
        weights: ScoringWeights | None = None,
    ) -> PlanScore:
        """Compute a PlanScore for a plan.

        Args:
            plan_id: Unique plan identifier.
            task_count: Total number of tasks.
            approval_points: Number of human approval required steps.
            estimated_seconds: Total estimated duration.
            risk_level: Maximum risk level across all tasks.
            internet_required: Whether the plan requires internet.
            strategy: Strategy used (determines default weights).
            confidence: Planner confidence in the plan (0–1).
            weights: Optional custom scoring weights.

        Returns:
            PlanScore with individual dimension scores and composite.
        """
        w = weights or ScoringWeights.for_strategy(strategy)

        quality = self._quality_score(task_count, approval_points, confidence)
        speed = self._speed_score(estimated_seconds)
        cost = self._cost_score(task_count, internet_required)
        risk = self._risk_score(risk_level)
        privacy = self._privacy_score(internet_required)
        success_prob = self._success_probability(confidence, risk_level, approval_points, task_count)

        composite = (
            w.quality * quality
            + w.speed * speed
            + w.cost * cost
            + w.risk * risk
            + w.privacy * privacy
            + w.success_probability * success_prob
        )
        # Normalize composite to [0, 1]
        weight_sum = w.quality + w.speed + w.cost + w.risk + w.privacy + w.success_probability
        composite = composite / weight_sum if weight_sum > 0 else 0.5

        return PlanScore(
            plan_id=plan_id,
            quality=round(quality, 4),
            speed=round(speed, 4),
            cost=round(cost, 4),
            risk=round(risk, 4),
            privacy=round(privacy, 4),
            success_probability=round(success_prob, 4),
            composite_score=round(min(1.0, max(0.0, composite)), 4),
            weights_used=w,
        )

    # ------------------------------------------------------------------
    # Dimension scorers — all constants from self._cfg (ScoringConfig)
    # ------------------------------------------------------------------

    def _quality_score(self, task_count: int, approval_points: int, confidence: float) -> float:
        """Higher quality = more tasks (thoroughness) + high confidence.

        Formula: confidence_weight * confidence
                 + thoroughness_weight * min(1, tasks / max_tasks)
                 + approval_weight * min(cap, points * per_point)
        """
        cfg = self._cfg
        thoroughness = min(1.0, task_count / cfg.quality_max_tasks_for_thoroughness)
        approval_bonus = min(cfg.quality_approval_bonus_cap, approval_points * cfg.quality_approval_per_point)
        return (
            cfg.quality_confidence_weight * confidence
            + cfg.quality_thoroughness_weight * thoroughness
            + cfg.quality_approval_weight * approval_bonus
        )

    def _speed_score(self, estimated_seconds: float) -> float:
        """Higher speed score = fewer estimated seconds.

        log10-based: 60s → ~0.64, 3600s → ~0.29, 86400s → ~0.01
        """
        if estimated_seconds <= 0:
            return 1.0
        score = 1.0 - (math.log10(max(1, estimated_seconds)) / self._cfg.speed_log_divisor)
        return max(0.0, min(1.0, score))

    def _cost_score(self, task_count: int, internet_required: bool) -> float:
        """Higher cost score = lower estimated resource usage."""
        cfg = self._cfg
        task_penalty = min(cfg.cost_task_penalty_cap, task_count * cfg.cost_per_task_penalty)
        internet_penalty = cfg.cost_internet_penalty if internet_required else 0.0
        return max(0.0, 1.0 - task_penalty - internet_penalty)

    def _risk_score(self, risk_level: RiskLevel) -> float:
        """Higher risk score = lower risk (risk is inverted for scoring)."""
        cfg = self._cfg
        return {
            RiskLevel.LOW:      cfg.risk_score_low,
            RiskLevel.MEDIUM:   cfg.risk_score_medium,
            RiskLevel.HIGH:     cfg.risk_score_high,
            RiskLevel.CRITICAL: cfg.risk_score_critical,
        }[risk_level]

    def _privacy_score(self, internet_required: bool) -> float:
        """Higher privacy score = more local/private."""
        cfg = self._cfg
        return cfg.privacy_score_with_internet if internet_required else cfg.privacy_score_local_only

    def _success_probability(
        self, confidence: float, risk_level: RiskLevel, approval_points: int, task_count: int
    ) -> float:
        """Estimate probability of plan success."""
        cfg = self._cfg
        base = confidence * self._risk_score(risk_level)
        approval_factor = max(
            cfg.success_min_approval_factor,
            1.0 - approval_points * cfg.success_approval_penalty_per_point,
        )
        complexity_factor = max(
            cfg.success_min_complexity_factor,
            1.0 - task_count * cfg.success_complexity_per_task,
        )
        return min(1.0, base * approval_factor * complexity_factor)
