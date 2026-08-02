"""Shared fixtures for L6 integration tests."""

from __future__ import annotations

import pytest

from aegis.l6_planning import PlannerContext, PlannerService
from aegis.l6_planning.planning.goal_engine import GoalEngine
from aegis.l6_planning.types import Constraint, ConstraintKind, PlanningStrategy


@pytest.fixture
def goal_engine() -> GoalEngine:
    return GoalEngine()


@pytest.fixture
def planner_service() -> PlannerService:
    return PlannerService()


@pytest.fixture
def simple_goal() -> str:
    return "Write a Python script that reads a CSV file and outputs statistics"


@pytest.fixture
def complex_goal() -> str:
    return (
        "Build a full-stack web application with React frontend, "
        "FastAPI backend, PostgreSQL database, Docker deployment, "
        "and comprehensive test suite"
    )


@pytest.fixture
def research_goal() -> str:
    return "Research the latest advances in quantum computing and write a summary report"


@pytest.fixture
def filesystem_goal() -> str:
    return "Organise my Downloads folder by file type and date"


@pytest.fixture
def offline_context() -> PlannerContext:
    return PlannerContext.offline()


@pytest.fixture
def fast_context() -> PlannerContext:
    return PlannerContext.fast()


@pytest.fixture
def private_context() -> PlannerContext:
    return PlannerContext.private()


@pytest.fixture
def budget_constraint() -> Constraint:
    return Constraint(
        kind=ConstraintKind.BUDGET,
        description="Maximum $5 AI cost",
        hard=True,
        value=5.0,
        unit="USD",
    )


@pytest.fixture
def privacy_constraint() -> Constraint:
    return Constraint(
        kind=ConstraintKind.PRIVACY,
        description="No data sent off-device",
        hard=True,
    )
