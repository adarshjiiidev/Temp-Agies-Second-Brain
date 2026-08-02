"""Integration tests — L6 Goal Engine."""

from __future__ import annotations

import pytest

from aegis.l6_planning.exceptions import PlanGoalInvalidError
from aegis.l6_planning.planning.goal_engine import GoalEngine
from aegis.l6_planning.types import PlanningStrategy


class TestGoalEngineCreateMission:
    def test_creates_mission_from_simple_goal(self, goal_engine, simple_goal):
        mission = goal_engine.create_mission(simple_goal)
        assert mission.mission_id.startswith("msn-")
        assert mission.title
        assert mission.user_goal_text == simple_goal
        assert mission.parsed_intent is not None

    def test_creates_mission_with_objectives(self, goal_engine, simple_goal):
        mission = goal_engine.create_mission(simple_goal)
        assert len(mission.objectives) >= 2

    def test_creates_mission_from_complex_goal(self, goal_engine, complex_goal):
        mission = goal_engine.create_mission(complex_goal)
        assert mission.objective_count >= 2

    def test_creates_mission_with_strategy(self, goal_engine, simple_goal):
        mission = goal_engine.create_mission(simple_goal, strategy=PlanningStrategy.FASTEST)
        assert mission.strategy == PlanningStrategy.FASTEST

    def test_creates_mission_with_deadline(self, goal_engine, simple_goal):
        import time
        deadline = time.time() + 3600
        mission = goal_engine.create_mission(simple_goal, deadline=deadline)
        assert mission.has_deadline
        assert mission.deadline == deadline

    def test_empty_goal_raises(self, goal_engine):
        with pytest.raises(PlanGoalInvalidError):
            goal_engine.create_mission("")

    def test_whitespace_only_goal_raises(self, goal_engine):
        with pytest.raises(PlanGoalInvalidError):
            goal_engine.create_mission("   ")

    def test_very_short_goal_raises(self, goal_engine):
        with pytest.raises(PlanGoalInvalidError):
            goal_engine.create_mission("AB")

    def test_mission_has_parsed_intent(self, goal_engine, simple_goal):
        mission = goal_engine.create_mission(simple_goal)
        assert mission.parsed_intent.raw_text == simple_goal

    def test_research_goal_creates_research_objectives(self, goal_engine, research_goal):
        mission = goal_engine.create_mission(research_goal)
        # Should have research domain objectives
        assert mission.objective_count >= 2
        titles = [o.title for o in mission.objectives]
        assert any(titles)

    def test_objectives_ordered_by_priority(self, goal_engine, simple_goal):
        mission = goal_engine.create_mission(simple_goal)
        priorities = [o.priority for o in mission.objectives]
        assert priorities == sorted(priorities)


class TestGoalEngineValidation:
    def test_validate_valid_mission(self, goal_engine, simple_goal):
        mission = goal_engine.create_mission(simple_goal)
        issues = goal_engine.validate_mission(mission)
        blocking = [i for i in issues if i.is_blocking()]
        assert len(blocking) == 0

    def test_validate_detects_unknown_obj_dependency(self, goal_engine, simple_goal):
        mission = goal_engine.create_mission(simple_goal)
        # Inject an invalid dependency
        obj = mission.objectives[0]
        obj_mod = obj.model_copy(update={"dependencies": ["nonexistent-id"]})
        mission_mod = mission.model_copy(update={"objectives": [obj_mod] + mission.objectives[1:]})
        issues = goal_engine.validate_mission(mission_mod)
        codes = [i.code for i in issues]
        assert "V005" in codes


class TestGoalEngineRefinement:
    def test_refine_mission_bumps_version(self, goal_engine, simple_goal):
        mission = goal_engine.create_mission(simple_goal)
        refined = goal_engine.refine_mission(mission, "Also add error handling")
        assert refined.version > mission.version

    def test_refine_empty_feedback_unchanged(self, goal_engine, simple_goal):
        mission = goal_engine.create_mission(simple_goal)
        refined = goal_engine.refine_mission(mission, "")
        assert refined.version == mission.version
