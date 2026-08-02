"""Integration tests — L6 Strategy Engine."""

from __future__ import annotations

import pytest

from aegis.l6_planning.planning.goal_engine import GoalEngine
from aegis.l6_planning.state.planner_context import PlannerContext
from aegis.l6_planning.strategy.strategy_engine import StrategyEngine
from aegis.l6_planning.types import Constraint, ConstraintKind, PlanningStrategy


@pytest.fixture
def engine():
    return GoalEngine()


@pytest.fixture
def strategy_engine():
    return StrategyEngine()


class TestStrategySelection:
    def test_user_preference_wins(self, engine, strategy_engine, simple_goal):
        mission = engine.create_mission(simple_goal)
        strategy = strategy_engine.select_strategy(mission, user_preference=PlanningStrategy.CHEAPEST)
        assert strategy == PlanningStrategy.CHEAPEST

    def test_privacy_constraint_selects_privacy_first(self, engine, strategy_engine, simple_goal):
        constraint = Constraint(kind=ConstraintKind.PRIVACY, description="No cloud", hard=True)
        mission = engine.create_mission(simple_goal, constraints=[constraint])
        strategy = strategy_engine.select_strategy(mission)
        assert strategy == PlanningStrategy.PRIVACY_FIRST

    def test_offline_constraint_selects_offline_first(self, engine, strategy_engine, simple_goal):
        constraint = Constraint(kind=ConstraintKind.OFFLINE, description="Offline", hard=True)
        mission = engine.create_mission(simple_goal, constraints=[constraint])
        strategy = strategy_engine.select_strategy(mission)
        assert strategy == PlanningStrategy.OFFLINE_FIRST

    def test_battery_low_context_selects_energy_saving(self, engine, strategy_engine, simple_goal):
        mission = engine.create_mission(simple_goal)
        strategy = strategy_engine.select_strategy(mission, context={"battery_low": True})
        assert strategy == PlanningStrategy.ENERGY_SAVING

    def test_deadline_urgent_context_selects_fastest(self, engine, strategy_engine, simple_goal):
        mission = engine.create_mission(simple_goal)
        strategy = strategy_engine.select_strategy(mission, context={"deadline_urgent": True})
        assert strategy == PlanningStrategy.FASTEST

    def test_cost_sensitive_context_selects_cheapest(self, engine, strategy_engine, simple_goal):
        mission = engine.create_mission(simple_goal)
        strategy = strategy_engine.select_strategy(mission, context={"cost_sensitive": True})
        assert strategy == PlanningStrategy.CHEAPEST

    def test_coding_domain_defaults_to_developer_mode(self, engine, strategy_engine):
        mission = engine.create_mission("Build a Python module with tests and documentation")
        strategy = strategy_engine.select_strategy(mission)
        assert strategy == PlanningStrategy.DEVELOPER_MODE

    def test_research_domain_defaults_to_research_mode(self, engine, strategy_engine, research_goal):
        mission = engine.create_mission(research_goal)
        strategy = strategy_engine.select_strategy(mission)
        assert strategy == PlanningStrategy.RESEARCH_MODE

    def test_all_strategies_have_descriptions(self):
        for strategy in PlanningStrategy:
            assert len(strategy.description) > 0

    def test_scoring_weights_for_all_strategies(self):
        from aegis.l6_planning.types import ScoringWeights
        for strategy in PlanningStrategy:
            weights = ScoringWeights.for_strategy(strategy)
            total = weights.quality + weights.speed + weights.cost + weights.risk + weights.privacy + weights.success_probability
            assert 0.99 <= total <= 1.01, f"Weights for {strategy} don't sum to ~1: {total}"

    def test_offline_intent_selects_offline_first(self, engine, strategy_engine, simple_goal):
        mission = engine.create_mission(simple_goal, context={"force_offline": True})
        strategy = strategy_engine.select_strategy(mission)
        assert strategy in (PlanningStrategy.OFFLINE_FIRST, PlanningStrategy.PRIVACY_FIRST)

    def test_describe_strategy_returns_string(self, strategy_engine):
        desc = strategy_engine.describe_strategy(PlanningStrategy.BALANCED)
        assert isinstance(desc, str) and len(desc) > 0
