"""L6 Planning Engine — Tradeoff Analyzer.

Performs explicit time-vs-cost-vs-quality tradeoff analysis between
two or more plans to help the DecisionEngine justify its choice.

Import safety: stdlib + pydantic + l6_planning.types only.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from aegis.l6_planning.types import PlanScore

__all__ = ["TradeoffMatrix", "TradeoffAnalyzer"]


class TradeoffEntry(BaseModel):
    """One dimension of a plan comparison."""

    dimension: str
    winner_plan_id: str
    winner_value: float
    loser_plan_id: str
    loser_value: float
    delta: float
    significance: str   # "high", "medium", "low"


class TradeoffMatrix(BaseModel):
    """Full tradeoff comparison between two or more plans."""

    plan_ids: list[str]
    entries: list[TradeoffEntry] = Field(default_factory=list)
    recommended_plan_id: str = ""
    recommendation_reason: str = ""

    def summary_for(self, plan_id: str) -> str:
        wins = [e.dimension for e in self.entries if e.winner_plan_id == plan_id]
        losses = [e.dimension for e in self.entries if e.loser_plan_id == plan_id]
        return f"Better in: {', '.join(wins) or 'none'}. Worse in: {', '.join(losses) or 'none'}."


class TradeoffAnalyzer:
    """Compares plans across dimensions and builds a TradeoffMatrix.

    Usage::

        analyzer = TradeoffAnalyzer()
        matrix = analyzer.compare([score_a, score_b])
    """

    SIGNIFICANCE_THRESHOLD_HIGH = 0.20
    SIGNIFICANCE_THRESHOLD_MEDIUM = 0.08

    def compare(self, scores: list[PlanScore]) -> TradeoffMatrix:
        """Compare multiple plan scores and produce a TradeoffMatrix.

        Args:
            scores: List of PlanScore objects (minimum 2).

        Returns:
            TradeoffMatrix with per-dimension winners and recommendation.
        """
        if len(scores) < 2:
            if scores:
                return TradeoffMatrix(
                    plan_ids=[scores[0].plan_id],
                    recommended_plan_id=scores[0].plan_id,
                    recommendation_reason="Only one plan available.",
                )
            return TradeoffMatrix(plan_ids=[])

        plan_ids = [s.plan_id for s in scores]
        dimensions = ["quality", "speed", "cost", "risk", "privacy", "success_probability"]
        entries: list[TradeoffEntry] = []

        for dim in dimensions:
            values = [(s.plan_id, getattr(s, dim)) for s in scores]
            values.sort(key=lambda x: x[1], reverse=True)
            winner_id, winner_val = values[0]
            loser_id, loser_val = values[-1]
            delta = winner_val - loser_val

            significance = (
                "high" if delta >= self.SIGNIFICANCE_THRESHOLD_HIGH
                else "medium" if delta >= self.SIGNIFICANCE_THRESHOLD_MEDIUM
                else "low"
            )
            entries.append(TradeoffEntry(
                dimension=dim,
                winner_plan_id=winner_id,
                winner_value=round(winner_val, 4),
                loser_plan_id=loser_id,
                loser_value=round(loser_val, 4),
                delta=round(delta, 4),
                significance=significance,
            ))

        # Pick recommendation by composite score
        best = max(scores, key=lambda s: s.composite_score)
        win_dims = [e.dimension for e in entries if e.winner_plan_id == best.plan_id and e.significance != "low"]
        reason = (
            f"Plan {best.plan_id!r} has the highest composite score ({best.composite_score:.3f})"
            + (f", leading in: {', '.join(win_dims)}" if win_dims else ".")
        )

        return TradeoffMatrix(
            plan_ids=plan_ids,
            entries=entries,
            recommended_plan_id=best.plan_id,
            recommendation_reason=reason,
        )
