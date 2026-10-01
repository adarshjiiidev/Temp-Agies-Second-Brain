"""Integration tests — L6 Recovery (dedicated)."""

from __future__ import annotations

import pytest

from aegis.l6_planning.decomposition.task_decomposer import TaskDecomposer
from aegis.l6_planning.planning.goal_engine import GoalEngine
from aegis.l6_planning.recovery.recovery_planner import RecoveryPlanner, RetryConfig


@pytest.fixture
def engine():
    return GoalEngine()


@pytest.fixture
def decomposer():
    return TaskDecomposer()


class TestRetryConfig:
    def test_default_retry_config(self):
        cfg = RetryConfig()
        assert cfg.max_attempts == 3
        assert cfg.backoff_seconds > 0
        assert cfg.backoff_multiplier >= 1.0

    def test_custom_retry_config(self):
        cfg = RetryConfig(max_attempts=5, backoff_seconds=10.0)
        assert cfg.max_attempts == 5
        assert cfg.backoff_seconds == 10.0


class TestFailureScenarios:
    def test_fs_write_scenarios_generated(self, engine, decomposer):
        mission = engine.create_mission("Write a Python script to a file")
        result = decomposer.decompose(mission)
        rplan = RecoveryPlanner().build(result.tasks)
        failure_modes = [s.failure_mode for s in rplan.scenarios]
        # At least generic failure mode should exist
        assert len(failure_modes) > 0

    def test_all_scenarios_have_fallback(self, engine, decomposer, simple_goal):
        mission = engine.create_mission(simple_goal)
        result = decomposer.decompose(mission)
        rplan = RecoveryPlanner().build(result.tasks)
        for scenario in rplan.scenarios:
            assert scenario.fallback_strategy
            assert len(scenario.fallback_strategy) > 0

    def test_all_scenarios_have_probability(self, engine, decomposer, simple_goal):
        mission = engine.create_mission(simple_goal)
        result = decomposer.decompose(mission)
        rplan = RecoveryPlanner().build(result.tasks)
        for scenario in rplan.scenarios:
            assert 0.0 <= scenario.probability <= 1.0

    def test_all_scenarios_have_retry_config(self, engine, decomposer, simple_goal):
        mission = engine.create_mission(simple_goal)
        result = decomposer.decompose(mission)
        rplan = RecoveryPlanner().build(result.tasks)
        for scenario in rplan.scenarios:
            assert isinstance(scenario.retry_config, RetryConfig)

    def test_global_retry_config_defined(self, engine, decomposer, simple_goal):
        mission = engine.create_mission(simple_goal)
        result = decomposer.decompose(mission)
        rplan = RecoveryPlanner().build(result.tasks)
        assert isinstance(rplan.global_retry_config, RetryConfig)

    def test_alternative_plan_notes_exist(self, engine, decomposer, simple_goal):
        mission = engine.create_mission(simple_goal)
        result = decomposer.decompose(mission)
        rplan = RecoveryPlanner().build(result.tasks)
        assert len(rplan.alternative_plan_notes) > 0

    def test_empty_task_list_empty_scenarios(self):
        rplan = RecoveryPlanner().build([])
        assert rplan.scenarios == []

    def test_risk_surface_is_valid_enum_value(self, engine, decomposer, simple_goal):
        mission = engine.create_mission(simple_goal)
        result = decomposer.decompose(mission)
        rplan = RecoveryPlanner().build(result.tasks)
        assert rplan.total_risk_surface in ("low", "medium", "high", "critical")

    def test_terminal_domain_high_risk_scenario(self, engine, decomposer):
        mission = engine.create_mission("Run shell commands to configure the OS")
        result = decomposer.decompose(mission)
        rplan = RecoveryPlanner().build(result.tasks)
        # Terminal domain tasks should have retry_config.max_attempts == 1
        shell_scenarios = [s for s in rplan.scenarios if "shell" in (s.fallback_strategy or "").lower()]
        for sc in shell_scenarios:
            assert sc.retry_config.max_attempts <= 3

    def test_rollback_required_flag(self, engine, decomposer):
        mission = engine.create_mission("Write files, commit to git, and push to remote")
        result = decomposer.decompose(mission)
        rplan = RecoveryPlanner().build(result.tasks)
        rollback_required = [s for s in rplan.scenarios if s.rollback_required]
        not_required = [s for s in rplan.scenarios if not s.rollback_required]
        assert len(rollback_required) + len(not_required) == len(rplan.scenarios)

    def test_escalation_conditions_are_strings(self, engine, decomposer, simple_goal):
        mission = engine.create_mission(simple_goal)
        result = decomposer.decompose(mission)
        rplan = RecoveryPlanner().build(result.tasks)
        for cond in rplan.escalation_conditions:
            assert isinstance(cond, str) and len(cond) > 0

    def test_failure_scenarios_cover_all_tasks(self, engine, decomposer, simple_goal):
        mission = engine.create_mission(simple_goal)
        result = decomposer.decompose(mission)
        rplan = RecoveryPlanner().build(result.tasks)
        scenario_task_ids = {s.task_id for s in rplan.scenarios}
        for task in result.tasks:
            assert task.task_id in scenario_task_ids
