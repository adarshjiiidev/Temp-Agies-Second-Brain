"""Integration tests — L6 End-to-end examples with realistic goals."""

from __future__ import annotations

import pytest

from aegis.l6_planning import PlannerContext, PlannerService, PlanningResult
from aegis.l6_planning.types import PlanState, PlanningStrategy


EXAMPLE_GOALS = [
    "Build a React portfolio website with TypeScript and deploy to Vercel",
    "Create an AI chatbot using Python and the OpenAI API",
    "Write a book outline on quantum physics for general readers",
    "Organise my Obsidian vault by topic and create an index note",
    "Research the best investment strategies for a long-term portfolio",
    "Automate my daily backup workflow for important project files",
    "Debug and fix the failing tests in my Django web application",
    "Create a Docker Compose setup for my microservices architecture",
    "Analyse the performance metrics of my PostgreSQL database",
    "Design and implement a CLI tool for batch image processing",
]


@pytest.fixture
def service():
    return PlannerService()


class TestRealisticExamples:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("goal", EXAMPLE_GOALS)
    async def test_each_example_produces_valid_plan(self, service, goal):
        result = await service.create_plan(goal)
        assert isinstance(result, PlanningResult)
        assert result.state == PlanState.READY
        assert result.task_count > 0
        assert 0.0 <= result.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_react_portfolio_has_coding_strategy(self, service):
        result = await service.create_plan(
            "Build a React portfolio website with TypeScript"
        )
        assert result.strategy in (PlanningStrategy.DEVELOPER_MODE, PlanningStrategy.BALANCED)

    @pytest.mark.asyncio
    async def test_research_goal_has_research_strategy(self, service):
        result = await service.create_plan(
            "Research the latest machine learning papers and write a literature review"
        )
        assert result.strategy in (PlanningStrategy.RESEARCH_MODE, PlanningStrategy.BALANCED)

    @pytest.mark.asyncio
    async def test_offline_goal_stays_offline(self, service):
        result = await service.create_plan(
            "Organise my local files without internet access",
            PlannerContext.offline(),
        )
        assert result.strategy in (PlanningStrategy.OFFLINE_FIRST, PlanningStrategy.PRIVACY_FIRST)

    @pytest.mark.asyncio
    async def test_plan_has_recovery_plan(self, service):
        result = await service.create_plan("Build a Python data pipeline")
        assert len(result.recovery_plan.scenarios) > 0

    @pytest.mark.asyncio
    async def test_plan_has_verification_plan(self, service):
        result = await service.create_plan("Implement a REST API with FastAPI")
        assert result.verification_plan.total_checks > 0

    @pytest.mark.asyncio
    async def test_plan_has_milestones(self, service):
        result = await service.create_plan("Create a complete machine learning pipeline")
        assert len(result.milestones) > 0

    @pytest.mark.asyncio
    async def test_plan_reflection_passes(self, service):
        result = await service.create_plan("Write and test a sorting algorithm in Python")
        assert result.reflection_report is not None
        assert result.reflection_report.passed

    @pytest.mark.asyncio
    async def test_plan_has_decision_trace(self, service):
        result = await service.create_plan("Research quantum computing and summarise findings")
        assert len(result.decision_trace) > 0

    @pytest.mark.asyncio
    async def test_plan_no_execution_artefacts(self, service):
        """Verify PlanningResult contains NO execution artefacts."""
        result = await service.create_plan("Build a CLI tool in Python")
        # No field from L5 execution results in the plan
        assert not hasattr(result, "action_result")
        assert not hasattr(result, "executor_name")
        assert not hasattr(result, "audit_entry_ids")
        # Tasks don't contain execution output
        for task in result.tasks:
            assert not hasattr(task, "output")
            assert not hasattr(task, "stdout")
