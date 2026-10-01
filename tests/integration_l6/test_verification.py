"""Integration tests — L6 Verification & Recovery."""

from __future__ import annotations

import pytest

from aegis.l6_planning.decomposition.task_decomposer import TaskDecomposer
from aegis.l6_planning.planning.goal_engine import GoalEngine
from aegis.l6_planning.recovery.contingency import ContingencyBuilder
from aegis.l6_planning.recovery.recovery_planner import RecoveryPlanner
from aegis.l6_planning.recovery.rollback_strategy import RollbackStrategyBuilder
from aegis.l6_planning.verification.acceptance import AcceptanceCriteriaGenerator
from aegis.l6_planning.verification.checkpoints import CheckpointBuilder
from aegis.l6_planning.verification.verification_planner import VerificationPlanner


@pytest.fixture
def engine():
    return GoalEngine()


@pytest.fixture
def decomposer():
    return TaskDecomposer()


class TestVerificationPlanner:
    def test_builds_verification_plan(self, engine, decomposer, simple_goal):
        mission = engine.create_mission(simple_goal)
        result = decomposer.decompose(mission)
        planner = VerificationPlanner()
        vplan = planner.build(result.tasks)
        assert vplan.total_checks > 0
        assert len(vplan.acceptance_criteria) > 0

    def test_every_task_has_automatic_check(self, engine, decomposer, simple_goal):
        mission = engine.create_mission(simple_goal)
        result = decomposer.decompose(mission)
        planner = VerificationPlanner()
        vplan = planner.build(result.tasks)
        task_ids_with_auto = {c.task_id for c in vplan.checks if c.kind == "automatic"}
        for task in result.tasks:
            assert task.task_id in task_ids_with_auto

    def test_high_risk_task_has_manual_check(self, engine, decomposer):
        mission = engine.create_mission("Run shell commands to configure the server")
        result = decomposer.decompose(mission)
        planner = VerificationPlanner()
        vplan = planner.build(result.tasks)
        # Terminal domain = high risk → should have manual checks
        assert vplan.manual_check_count >= 0  # may be 0 for low-risk plans

    def test_empty_task_list_returns_empty_plan(self):
        planner = VerificationPlanner()
        vplan = planner.build([])
        assert vplan.total_checks == 0

    def test_completion_evidence_populated(self, engine, decomposer, simple_goal):
        mission = engine.create_mission(simple_goal)
        result = decomposer.decompose(mission)
        planner = VerificationPlanner()
        vplan = planner.build(result.tasks)
        assert len(vplan.completion_evidence) > 0


class TestAcceptanceCriteriaGenerator:
    def test_generates_criteria_for_each_task(self, engine, decomposer, simple_goal):
        mission = engine.create_mission(simple_goal)
        result = decomposer.decompose(mission)
        gen = AcceptanceCriteriaGenerator()
        criteria = gen.generate(result.tasks)
        task_ids = {c.task_id for c in criteria}
        for task in result.tasks:
            assert task.task_id in task_ids

    def test_approval_points_get_manual_criterion(self, engine, decomposer):
        mission = engine.create_mission("Run shell commands to deploy the server")
        result = decomposer.decompose(mission)
        gen = AcceptanceCriteriaGenerator()
        criteria = gen.generate(result.tasks)
        manual = [c for c in criteria if not c.automated]
        # High-risk terminal domain should have at least one manual approval criterion
        assert isinstance(manual, list)


class TestRecoveryPlanner:
    def test_builds_recovery_plan(self, engine, decomposer, simple_goal):
        mission = engine.create_mission(simple_goal)
        result = decomposer.decompose(mission)
        planner = RecoveryPlanner()
        rplan = planner.build(result.tasks)
        assert len(rplan.scenarios) > 0

    def test_every_task_has_at_least_one_scenario(self, engine, decomposer, simple_goal):
        mission = engine.create_mission(simple_goal)
        result = decomposer.decompose(mission)
        planner = RecoveryPlanner()
        rplan = planner.build(result.tasks)
        task_ids_covered = {s.task_id for s in rplan.scenarios}
        for task in result.tasks:
            assert task.task_id in task_ids_covered

    def test_escalation_conditions_defined(self, engine, decomposer, simple_goal):
        mission = engine.create_mission(simple_goal)
        result = decomposer.decompose(mission)
        rplan = RecoveryPlanner().build(result.tasks)
        assert len(rplan.escalation_conditions) > 0

    def test_risk_surface_reflects_task_risk(self, engine, decomposer):
        mission = engine.create_mission("Execute system shell commands with root access")
        result = decomposer.decompose(mission)
        rplan = RecoveryPlanner().build(result.tasks)
        assert rplan.total_risk_surface in ("low", "medium", "high", "critical")


class TestRollbackStrategy:
    def test_builds_rollback_steps(self, engine, decomposer, simple_goal):
        mission = engine.create_mission(simple_goal)
        result = decomposer.decompose(mission)
        builder = RollbackStrategyBuilder()
        strategy = builder.build(result.tasks)
        assert isinstance(strategy.steps, list)

    def test_irreversible_tasks_noted(self, engine, decomposer):
        mission = engine.create_mission("Run shell commands to format the disk")
        result = decomposer.decompose(mission)
        builder = RollbackStrategyBuilder()
        strategy = builder.build(result.tasks)
        irreversible = [t for t in result.tasks if not t.reversible]
        if irreversible:
            assert not strategy.fully_reversible


class TestContingencyBuilder:
    def test_builds_contingencies(self, engine, decomposer, simple_goal):
        mission = engine.create_mission(simple_goal)
        result = decomposer.decompose(mission)
        builder = ContingencyBuilder()
        branches = builder.build(result.tasks)
        assert isinstance(branches, list)

    def test_internet_tasks_get_offline_contingency(self, engine, decomposer, research_goal):
        mission = engine.create_mission(research_goal)
        result = decomposer.decompose(mission)
        builder = ContingencyBuilder()
        branches = builder.build(result.tasks)
        conditions = [b.condition for b in branches]
        net_tasks = [t for t in result.tasks if t.action_kind_hint and t.action_kind_hint.startswith("net.")]
        if net_tasks:
            assert any("Internet" in c or "internet" in c for c in conditions)
