"""L6 Planning Engine — Decision Engine.

Scores, ranks, and selects the best plan from one or more candidates
using the multi-dimensional ScoringEngine and TradeoffAnalyzer.

Import safety: stdlib + pydantic + l6_planning internal only.
"""

from __future__ import annotations

from aegis.l6_planning.decomposition.task_decomposer import DecompositionResult
from aegis.l6_planning.planning.mission import Mission
from aegis.l6_planning.reasoning.scoring import ScoringEngine
from aegis.l6_planning.reasoning.tradeoffs import TradeoffAnalyzer, TradeoffMatrix
from aegis.l6_planning.types import DecisionTraceEntry, PlanScore, PlanningStrategy, ScoringWeights

__all__ = ["DecisionEngine"]


class DecisionEngine:
    """Scores plans and selects the best candidate.

    Usage::

        engine = DecisionEngine()
        score = engine.score_plan(mission, decomp)
        best, trace = engine.select_best([score_a, score_b])
    """

    def __init__(self) -> None:
        self._scorer = ScoringEngine()
        self._analyzer = TradeoffAnalyzer()

    def score_plan(
        self,
        mission: Mission,
        decomp: DecompositionResult,
        strategy: PlanningStrategy | None = None,
        weights: ScoringWeights | None = None,
    ) -> PlanScore:
        """Compute a PlanScore for a single plan.

        Args:
            mission: The Mission being planned.
            decomp: Decomposition result for this plan.
            strategy: Strategy override (defaults to mission.strategy).
            weights: Custom scoring weights.

        Returns:
            PlanScore for this plan.
        """
        effective_strategy = strategy or mission.strategy

        return self._scorer.score(
            plan_id=mission.mission_id,
            task_count=len(decomp.tasks),
            approval_points=decomp.approval_point_count,
            estimated_seconds=decomp.total_estimated_seconds,
            risk_level=mission.requirements.max_risk_level,
            internet_required=mission.requirements.internet_required,
            strategy=effective_strategy,
            confidence=mission.parsed_intent.confidence,
            weights=weights,
        )

    def rank_plans(self, scores: list[PlanScore]) -> list[PlanScore]:
        """Return scores sorted by composite_score descending.

        Args:
            scores: List of PlanScore objects.

        Returns:
            Sorted list (best first).
        """
        return sorted(scores, key=lambda s: s.composite_score, reverse=True)

    def select_best(
        self, scores: list[PlanScore]
    ) -> tuple[PlanScore | None, list[DecisionTraceEntry]]:
        """Select the best plan from a list of scored candidates.

        Args:
            scores: List of PlanScore objects.

        Returns:
            Tuple of (best PlanScore or None, decision trace entries).
        """
        if not scores:
            return None, []

        if len(scores) == 1:
            trace = [DecisionTraceEntry(
                step="selection",
                decision=f"Selected plan {scores[0].plan_id!r}",
                rationale="Only one plan available.",
                alternatives_considered=[],
                confidence=scores[0].success_probability,
            )]
            return scores[0], trace

        ranked = self.rank_plans(scores)
        best = ranked[0]
        matrix: TradeoffMatrix = self._analyzer.compare(scores)

        trace = [
            DecisionTraceEntry(
                step="scoring",
                decision="Plans scored on 6 dimensions",
                rationale=f"Weights: quality={best.weights_used.quality}, speed={best.weights_used.speed}, "
                          f"cost={best.weights_used.cost}, risk={best.weights_used.risk}, "
                          f"privacy={best.weights_used.privacy}, success={best.weights_used.success_probability}",
                alternatives_considered=[s.plan_id for s in scores],
                confidence=0.9,
            ),
            DecisionTraceEntry(
                step="ranking",
                decision=f"Ranked {len(scores)} plans by composite score",
                rationale=f"Scores: {', '.join(f'{s.plan_id!r}={s.composite_score:.3f}' for s in ranked)}",
                alternatives_considered=[s.plan_id for s in ranked[1:]],
                confidence=0.9,
            ),
            DecisionTraceEntry(
                step="selection",
                decision=f"Selected plan {best.plan_id!r} (composite={best.composite_score:.3f})",
                rationale=matrix.recommendation_reason,
                alternatives_considered=[s.plan_id for s in ranked[1:]],
                confidence=best.success_probability,
            ),
        ]

        return best, trace

    def compare_plans(self, scores: list[PlanScore]) -> TradeoffMatrix:
        """Return a full TradeoffMatrix comparing all plans.

        Args:
            scores: List of PlanScore objects.

        Returns:
            TradeoffMatrix with per-dimension analysis.
        """
        return self._analyzer.compare(scores)
