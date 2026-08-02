"""Integration tests — L6 Decision Engine & Scoring."""

from __future__ import annotations

import pytest

from aegis.l6_planning.decomposition.task_decomposer import TaskDecomposer
from aegis.l6_planning.planning.goal_engine import GoalEngine
from aegis.l6_planning.reasoning.decision_engine import DecisionEngine
from aegis.l6_planning.reasoning.scoring import ScoringEngine
from aegis.l6_planning.types import PlanningStrategy, RiskLevel, ScoringWeights


@pytest.fixture
def goal_engine():
    return GoalEngine()


@pytest.fixture
def decomposer():
    return TaskDecomposer()


@pytest.fixture
def decision_engine():
    return DecisionEngine()


@pytest.fixture
def scorer():
    return ScoringEngine()


class TestScoringEngine:
    def test_score_returns_valid_range(self, scorer):
        score = scorer.score(
            plan_id="p1",
            task_count=8,
            approval_points=2,
            estimated_seconds=3600,
            risk_level=RiskLevel.MEDIUM,
            internet_required=False,
        )
        assert 0.0 <= score.composite_score <= 1.0
        assert 0.0 <= score.quality <= 1.0
        assert 0.0 <= score.risk <= 1.0

    def test_low_risk_scores_higher_risk_dimension(self, scorer):
        low = scorer.score("low", 5, 0, 600, RiskLevel.LOW, False)
        high = scorer.score("high", 5, 0, 600, RiskLevel.CRITICAL, False)
        assert low.risk > high.risk

    def test_internet_reduces_privacy_score(self, scorer):
        local = scorer.score("local", 5, 0, 600, RiskLevel.LOW, False)
        net = scorer.score("net", 5, 0, 600, RiskLevel.LOW, True)
        assert local.privacy > net.privacy

    def test_fewer_seconds_scores_higher_speed(self, scorer):
        fast = scorer.score("fast", 5, 0, 60, RiskLevel.LOW, False)
        slow = scorer.score("slow", 5, 0, 86400, RiskLevel.LOW, False)
        assert fast.speed > slow.speed

    def test_strategy_weights_applied(self, scorer):
        fastest_weights = ScoringWeights.for_strategy(PlanningStrategy.FASTEST)
        cheapest_weights = ScoringWeights.for_strategy(PlanningStrategy.CHEAPEST)
        assert fastest_weights.speed > cheapest_weights.speed
        assert cheapest_weights.cost > fastest_weights.cost

    def test_high_confidence_improves_quality(self, scorer):
        high_conf = scorer.score("hi", 5, 0, 600, RiskLevel.LOW, False, confidence=0.9)
        low_conf = scorer.score("lo", 5, 0, 600, RiskLevel.LOW, False, confidence=0.3)
        assert high_conf.quality > low_conf.quality


class TestDecisionEngine:
    def test_score_plan_returns_plan_score(self, goal_engine, decomposer, decision_engine, simple_goal):
        mission = goal_engine.create_mission(simple_goal)
        decomp = decomposer.decompose(mission)
        score = decision_engine.score_plan(mission, decomp)
        assert score.plan_id == mission.mission_id
        assert 0.0 <= score.composite_score <= 1.0

    def test_rank_plans_sorts_descending(self, scorer, decision_engine):
        scores = [
            scorer.score("a", 5, 0, 600, RiskLevel.LOW, False, confidence=0.9),
            scorer.score("b", 5, 0, 600, RiskLevel.HIGH, True, confidence=0.5),
        ]
        ranked = decision_engine.rank_plans(scores)
        assert ranked[0].composite_score >= ranked[-1].composite_score

    def test_select_best_single_plan(self, scorer, decision_engine):
        score = scorer.score("only", 5, 0, 600, RiskLevel.LOW, False)
        best, trace = decision_engine.select_best([score])
        assert best is not None
        assert best.plan_id == "only"
        assert len(trace) > 0

    def test_select_best_from_multiple(self, scorer, decision_engine):
        scores = [
            scorer.score("good", 8, 1, 600, RiskLevel.LOW, False, confidence=0.9),
            scorer.score("bad", 3, 5, 86400, RiskLevel.CRITICAL, True, confidence=0.3),
        ]
        best, trace = decision_engine.select_best(scores)
        assert best is not None
        assert best.plan_id == "good"

    def test_compare_plans_returns_matrix(self, scorer, decision_engine):
        scores = [
            scorer.score("p1", 5, 0, 600, RiskLevel.LOW, False),
            scorer.score("p2", 10, 3, 3600, RiskLevel.HIGH, True),
        ]
        matrix = decision_engine.compare_plans(scores)
        assert len(matrix.entries) > 0
        assert matrix.recommended_plan_id in ("p1", "p2")

    def test_empty_scores_returns_none(self, decision_engine):
        best, trace = decision_engine.select_best([])
        assert best is None
