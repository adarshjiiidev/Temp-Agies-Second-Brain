"""L6 Planning Engine — Scoring Engine.

Computes multi-dimensional scores for plans using configurable weights.
All scores are in [0, 1] where higher = better.

Import safety: stdlib + pydantic + l6_planning.types only.
"""

from __future__ import annotations

from aegis.l6_planning.types import (
    PlanScore,
    PlanningStrategy,
    RiskLevel,
    ScoringWeights,
)

__all__ = ["ScoringEngine"]


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
    """

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
    # Dimension scorers
    # ------------------------------------------------------------------

    def _quality_score(self, task_count: int, approval_points: int, confidence: float) -> float:
        """Higher quality = more tasks (thoroughness) + high confidence."""
        thoroughness = min(1.0, task_count / 15.0)   # 15 tasks = max thoroughness
        approval_bonus = min(0.2, approval_points * 0.05)
        return 0.6 * confidence + 0.3 * thoroughness + 0.1 * approval_bonus

    def _speed_score(self, estimated_seconds: float) -> float:
        """Higher speed score = fewer estimated seconds."""
        if estimated_seconds <= 0:
            return 1.0
        # 60s = 1.0, 3600s = 0.5, 86400s = 0.1
        import math
        score = 1.0 - (math.log10(max(1, estimated_seconds)) / 5.0)
        return max(0.0, min(1.0, score))

    def _cost_score(self, task_count: int, internet_required: bool) -> float:
        """Higher cost score = lower estimated resource usage."""
        task_penalty = min(0.5, task_count * 0.03)
        internet_penalty = 0.1 if internet_required else 0.0
        return max(0.0, 1.0 - task_penalty - internet_penalty)

    def _risk_score(self, risk_level: RiskLevel) -> float:
        """Higher risk score = lower risk (risk is inverted for scoring)."""
        return {
            RiskLevel.LOW: 1.0,
            RiskLevel.MEDIUM: 0.70,
            RiskLevel.HIGH: 0.40,
            RiskLevel.CRITICAL: 0.10,
        }[risk_level]

    def _privacy_score(self, internet_required: bool) -> float:
        """Higher privacy score = more local/private."""
        return 0.4 if internet_required else 1.0

    def _success_probability(
        self, confidence: float, risk_level: RiskLevel, approval_points: int, task_count: int
    ) -> float:
        """Estimate probability of plan success."""
        base = confidence * self._risk_score(risk_level)
        approval_factor = max(0.7, 1.0 - approval_points * 0.05)
        complexity_factor = max(0.6, 1.0 - task_count * 0.02)
        return min(1.0, base * approval_factor * complexity_factor)
