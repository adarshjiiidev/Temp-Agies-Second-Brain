"""Integration tests — L6 PlannerService (full API)."""

from __future__ import annotations

import pytest

from aegis.l6_planning import PlannerContext, PlannerService, PlanningResult
from aegis.l6_planning.exceptions import PlanAlreadyCancelledError, PlanNotFoundError
from aegis.l6_planning.types import PlanState, PlanningStrategy


class TestPlannerServiceCreate:
    @pytest.mark.asyncio
    async def test_create_returns_planning_result(self, planner_service, simple_goal):
        result = await planner_service.create_plan(simple_goal)
        assert isinstance(result, PlanningResult)

    @pytest.mark.asyncio
    async def test_create_state_is_ready(self, planner_service, simple_goal):
        result = await planner_service.create_plan(simple_goal)
        assert result.state == PlanState.READY

    @pytest.mark.asyncio
    async def test_create_has_tasks(self, planner_service, simple_goal):
        result = await planner_service.create_plan(simple_goal)
        assert result.task_count > 0

    @pytest.mark.asyncio
    async def test_create_has_milestones(self, planner_service, simple_goal):
        result = await planner_service.create_plan(simple_goal)
        assert len(result.milestones) > 0

    @pytest.mark.asyncio
    async def test_create_has_execution_order(self, planner_service, simple_goal):
        result = await planner_service.create_plan(simple_goal)
        assert result.step_count > 0

    @pytest.mark.asyncio
    async def test_create_has_confidence(self, planner_service, simple_goal):
        result = await planner_service.create_plan(simple_goal)
        assert 0.0 <= result.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_create_has_reflection(self, planner_service, simple_goal):
        result = await planner_service.create_plan(simple_goal)
        assert result.reflection_report is not None

    @pytest.mark.asyncio
    async def test_create_with_offline_context(self, planner_service, simple_goal, offline_context):
        result = await planner_service.create_plan(simple_goal, offline_context)
        assert result.strategy in (PlanningStrategy.OFFLINE_FIRST, PlanningStrategy.PRIVACY_FIRST)

    @pytest.mark.asyncio
    async def test_create_stores_plan_in_session(self, planner_service, simple_goal):
        result = await planner_service.create_plan(simple_goal)
        retrieved = planner_service.get_session().get(result.plan_id)
        assert retrieved.plan_id == result.plan_id


class TestPlannerServiceReview:
    @pytest.mark.asyncio
    async def test_review_returns_updated_plan(self, planner_service, simple_goal):
        created = await planner_service.create_plan(simple_goal)
        reviewed = await planner_service.review_plan(created.plan_id)
        assert reviewed.plan_id == created.plan_id
        assert reviewed.reflection_report is not None

    @pytest.mark.asyncio
    async def test_review_unknown_plan_raises(self, planner_service):
        with pytest.raises(PlanNotFoundError):
            await planner_service.review_plan("nonexistent-plan-id")


class TestPlannerServiceCancel:
    @pytest.mark.asyncio
    async def test_cancel_plan(self, planner_service, simple_goal):
        created = await planner_service.create_plan(simple_goal)
        cancelled = await planner_service.cancel_plan(created.plan_id)
        assert cancelled.state == PlanState.CANCELLED

    @pytest.mark.asyncio
    async def test_double_cancel_raises(self, planner_service, simple_goal):
        created = await planner_service.create_plan(simple_goal)
        await planner_service.cancel_plan(created.plan_id)
        with pytest.raises(PlanAlreadyCancelledError):
            await planner_service.cancel_plan(created.plan_id)

    @pytest.mark.asyncio
    async def test_cancel_unknown_raises(self, planner_service):
        with pytest.raises(PlanNotFoundError):
            await planner_service.cancel_plan("unknown-xyz")


class TestPlannerServiceEstimate:
    @pytest.mark.asyncio
    async def test_estimate_returns_estimate(self, planner_service, simple_goal):
        estimate = await planner_service.estimate_plan(simple_goal)
        assert estimate.total_tasks > 0
        assert estimate.estimated_total_seconds > 0

    @pytest.mark.asyncio
    async def test_estimate_invalid_goal_returns_zero_confidence(self, planner_service):
        estimate = await planner_service.estimate_plan("")
        assert estimate.confidence == 0.0


class TestPlannerServiceSummary:
    @pytest.mark.asyncio
    async def test_summary_is_string(self, planner_service, simple_goal):
        result = await planner_service.create_plan(simple_goal)
        summary = result.summary()
        assert isinstance(summary, str)
        assert result.plan_id[:8] in summary

    @pytest.mark.asyncio
    async def test_metrics_updated_after_create(self, planner_service, simple_goal):
        before = planner_service.metrics.total_plans_created
        await planner_service.create_plan(simple_goal)
        assert planner_service.metrics.total_plans_created == before + 1
