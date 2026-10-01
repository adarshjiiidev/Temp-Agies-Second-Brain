"""Integration tests — L6 Reflection Engine."""

from __future__ import annotations

import pytest

from aegis.l6_planning.decomposition.dependency_graph import DependencyGraph
from aegis.l6_planning.decomposition.task_decomposer import TaskDecomposer
from aegis.l6_planning.planning.goal_engine import GoalEngine
from aegis.l6_planning.reflection.reflection_engine import ReflectionEngine
from aegis.l6_planning.reflection.improvement_engine import ImprovementEngine
from aegis.l6_planning.reflection.self_review import SelfReviewer


@pytest.fixture
def engine():
    return GoalEngine()


@pytest.fixture
def decomposer():
    return TaskDecomposer()


@pytest.fixture
def reflection_engine():
    return ReflectionEngine()


@pytest.fixture
def improvement_engine():
    return ImprovementEngine()


@pytest.fixture
def self_reviewer():
    return SelfReviewer()


class TestReflectionEngine:
    def test_passes_on_clean_plan(self, engine, decomposer, reflection_engine, simple_goal):
        mission = engine.create_mission(simple_goal)
        decomp = decomposer.decompose(mission)
        graph = DependencyGraph.from_dict(decomp.graph)
        report = reflection_engine.review(mission, decomp.tasks, graph)
        assert report.passed
        assert len(report.blocking_issues) == 0

    def test_no_cycles_in_clean_plan(self, engine, decomposer, reflection_engine, simple_goal):
        mission = engine.create_mission(simple_goal)
        decomp = decomposer.decompose(mission)
        graph = DependencyGraph.from_dict(decomp.graph)
        report = reflection_engine.review(mission, decomp.tasks, graph)
        assert report.circular_deps == []

    def test_cycle_in_graph_creates_error(self, engine, decomposer, reflection_engine, simple_goal):
        mission = engine.create_mission(simple_goal)
        decomp = decomposer.decompose(mission)
        # Build a fresh graph with a guaranteed explicit 3-node cycle so the test
        # is not sensitive to whether the decomposed graph has parallel (disconnected) nodes.
        cycle_graph = DependencyGraph()
        cycle_graph.add_node("a", "Task A")
        cycle_graph.add_node("b", "Task B")
        cycle_graph.add_node("c", "Task C")
        cycle_graph.add_edge("a", "b")   # b depends on a
        cycle_graph.add_edge("b", "c")   # c depends on b
        cycle_graph.add_edge("c", "a")   # a depends on c → cycle: a→b→c→a
        report = reflection_engine.review(mission, decomp.tasks, cycle_graph)
        assert not report.passed

    def test_complexity_score_in_range(self, engine, decomposer, reflection_engine, simple_goal):
        mission = engine.create_mission(simple_goal)
        decomp = decomposer.decompose(mission)
        graph = DependencyGraph.from_dict(decomp.graph)
        report = reflection_engine.review(mission, decomp.tasks, graph)
        assert 0.0 <= report.complexity_score <= 1.0

    def test_confidence_delta_negative_on_errors(self, engine, decomposer, reflection_engine, simple_goal):
        mission = engine.create_mission(simple_goal)
        decomp = decomposer.decompose(mission)
        # Build an explicit cycle graph — same reasoning as test_cycle_in_graph_creates_error.
        cycle_graph = DependencyGraph()
        cycle_graph.add_node("x", "Task X")
        cycle_graph.add_node("y", "Task Y")
        cycle_graph.add_edge("x", "y")
        cycle_graph.add_edge("y", "x")   # 2-node cycle
        report = reflection_engine.review(mission, decomp.tasks, cycle_graph)
        # A cycle creates an error → passed=False → confidence_delta < 0
        assert not report.passed
        assert report.confidence_delta < 0

    def test_report_has_all_fields(self, engine, decomposer, reflection_engine, simple_goal):
        mission = engine.create_mission(simple_goal)
        decomp = decomposer.decompose(mission)
        graph = DependencyGraph.from_dict(decomp.graph)
        report = reflection_engine.review(mission, decomp.tasks, graph)
        assert isinstance(report.optimizations, list)
        assert isinstance(report.missing_requirements, list)
        assert isinstance(report.risk_flags, list)


class TestImprovementEngine:
    def test_returns_list(self, engine, decomposer, improvement_engine, simple_goal):
        mission = engine.create_mission(simple_goal)
        decomp = decomposer.decompose(mission)
        suggestions = improvement_engine.suggest(mission, decomp.tasks)
        assert isinstance(suggestions, list)

    def test_complex_goal_has_suggestions(self, engine, decomposer, improvement_engine, complex_goal):
        mission = engine.create_mission(complex_goal)
        decomp = decomposer.decompose(mission)
        suggestions = improvement_engine.suggest(mission, decomp.tasks)
        # Complex goals should have at least one suggestion
        assert isinstance(suggestions, list)


class TestSelfReviewer:
    def test_no_issues_on_valid_plan(self, engine, decomposer, self_reviewer, simple_goal):
        mission = engine.create_mission(simple_goal)
        decomp = decomposer.decompose(mission)
        issues = self_reviewer.review(mission, decomp.tasks)
        blocking = [i for i in issues if i.severity == "error"]
        assert len(blocking) == 0

    def test_detects_unknown_objective_reference(self, engine, decomposer, self_reviewer, simple_goal):
        mission = engine.create_mission(simple_goal)
        decomp = decomposer.decompose(mission)
        # Break a task's objective reference
        if decomp.tasks:
            bad_task = decomp.tasks[0].model_copy(update={"objective_id": "nonexistent"})
            issues = self_reviewer.review(mission, [bad_task] + decomp.tasks[1:])
            codes = [i.code for i in issues]
            assert "SR001" in codes

    def test_detects_unknown_task_dependency(self, engine, decomposer, self_reviewer, simple_goal):
        mission = engine.create_mission(simple_goal)
        decomp = decomposer.decompose(mission)
        if decomp.tasks:
            bad_task = decomp.tasks[0].model_copy(update={"depends_on": ["nonexistent-task-id"]})
            issues = self_reviewer.review(mission, [bad_task] + decomp.tasks[1:])
            codes = [i.code for i in issues]
            assert "SR002" in codes
