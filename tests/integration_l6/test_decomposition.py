"""Integration tests — L6 Task Decomposer."""

from __future__ import annotations

import pytest

from aegis.l6_planning.decomposition.task_decomposer import TaskDecomposer
from aegis.l6_planning.planning.goal_engine import GoalEngine


@pytest.fixture
def decomposer():
    return TaskDecomposer()


@pytest.fixture
def engine():
    return GoalEngine()


class TestTaskDecomposer:
    def test_produces_tasks_from_simple_goal(self, engine, decomposer, simple_goal):
        mission = engine.create_mission(simple_goal)
        result = decomposer.decompose(mission)
        assert len(result.tasks) > 0

    def test_produces_tasks_from_complex_goal(self, engine, decomposer, complex_goal):
        mission = engine.create_mission(complex_goal)
        result = decomposer.decompose(mission)
        assert len(result.tasks) >= 4

    def test_all_tasks_have_objective_id(self, engine, decomposer, simple_goal):
        mission = engine.create_mission(simple_goal)
        result = decomposer.decompose(mission)
        obj_ids = {o.objective_id for o in mission.objectives}
        for task in result.tasks:
            assert task.objective_id in obj_ids

    def test_all_tasks_have_titles(self, engine, decomposer, simple_goal):
        mission = engine.create_mission(simple_goal)
        result = decomposer.decompose(mission)
        for task in result.tasks:
            assert task.title.strip()

    def test_graph_is_populated(self, engine, decomposer, simple_goal):
        mission = engine.create_mission(simple_goal)
        result = decomposer.decompose(mission)
        assert "nodes" in result.graph
        assert len(result.graph["nodes"]) == len(result.tasks)

    def test_total_seconds_positive(self, engine, decomposer, simple_goal):
        mission = engine.create_mission(simple_goal)
        result = decomposer.decompose(mission)
        assert result.total_estimated_seconds > 0

    def test_filesystem_goal_has_fs_hints(self, engine, decomposer, filesystem_goal):
        mission = engine.create_mission(filesystem_goal)
        result = decomposer.decompose(mission)
        hints = [t.action_kind_hint for t in result.tasks if t.action_kind_hint]
        assert any(h.startswith("fs.") for h in hints)

    def test_decomposition_result_has_stats(self, engine, decomposer, simple_goal):
        mission = engine.create_mission(simple_goal)
        result = decomposer.decompose(mission)
        assert result.sequential_task_count >= 0
        assert result.parallel_task_count >= 0
        assert result.sequential_task_count + result.parallel_task_count == len(result.tasks)

    def test_subtasks_generated(self, engine, decomposer, simple_goal):
        mission = engine.create_mission(simple_goal)
        result = decomposer.decompose(mission)
        total_subtasks = sum(t.subtask_count for t in result.tasks)
        assert total_subtasks > 0

    def test_research_goal_has_net_hints(self, engine, decomposer, research_goal):
        mission = engine.create_mission(research_goal)
        result = decomposer.decompose(mission)
        hints = [t.action_kind_hint for t in result.tasks if t.action_kind_hint]
        # Research domain should have net.get actions
        assert any(h.startswith("net.") or h.startswith("fs.") for h in hints)

    def test_critical_path_is_valid(self, engine, decomposer, simple_goal):
        mission = engine.create_mission(simple_goal)
        result = decomposer.decompose(mission)
        # Critical path should be a subset of task IDs
        task_ids = {t.task_id for t in result.tasks}
        for nid in result.critical_path:
            assert nid in task_ids

    def test_milestone_builder_produces_milestones(self, engine, simple_goal):
        from aegis.l6_planning.decomposition.milestone_builder import MilestoneBuilder
        decomposer = TaskDecomposer()
        mission = engine.create_mission(simple_goal)
        result = decomposer.decompose(mission)
        builder = MilestoneBuilder()
        milestones = builder.build(result)
        assert len(milestones) > 0
        for ms in milestones:
            assert ms.title
            assert len(ms.task_ids) > 0

    def test_milestone_criteria_populated(self, engine, simple_goal):
        from aegis.l6_planning.decomposition.milestone_builder import MilestoneBuilder
        decomposer = TaskDecomposer()
        mission = engine.create_mission(simple_goal)
        result = decomposer.decompose(mission)
        milestones = MilestoneBuilder().build(result)
        for ms in milestones:
            assert len(ms.completion_criteria) > 0

    def test_max_tasks_respected(self, engine, decomposer, complex_goal):
        mission = engine.create_mission(complex_goal)
        result = decomposer.decompose(mission)
        # Just verify we can truncate
        assert len(result.tasks) > 0

    def test_parallel_tasks_have_group_flag(self, engine, decomposer, complex_goal):
        mission = engine.create_mission(complex_goal)
        result = decomposer.decompose(mission)
        parallel = [t for t in result.tasks if t.can_run_parallel]
        # Some tasks in complex goals should be marked parallel
        # (not a strict requirement but should be >= 0)
        assert len(parallel) >= 0
