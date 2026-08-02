"""Integration tests — L6 Constraints & Requirements."""

from __future__ import annotations

import pytest

from aegis.l6_planning.intent.requirement_extractor import RequirementExtractor
from aegis.l6_planning.intent.intent_parser import IntentParser
from aegis.l6_planning.planning.goal_engine import GoalEngine
from aegis.l6_planning.types import Constraint, ConstraintKind, RiskLevel


@pytest.fixture
def parser():
    return IntentParser()


@pytest.fixture
def extractor():
    return RequirementExtractor()


@pytest.fixture
def engine():
    return GoalEngine()


class TestRequirementExtractor:
    def test_coding_domain_extracts_fs_permissions(self, parser, extractor):
        intent = parser.parse("Build a Python module and save it to disk")
        reqs = extractor.extract(intent)
        assert any("fs." in p for p in reqs.permissions_needed)

    def test_browser_domain_requires_internet(self, parser, extractor):
        intent = parser.parse("Browse the web and scrape product data")
        reqs = extractor.extract(intent)
        assert reqs.internet_required

    def test_local_only_disables_internet(self, parser, extractor):
        intent = parser.parse("Organise local files in offline mode")
        reqs = extractor.extract(intent)
        assert not reqs.internet_required
        assert reqs.offline_capable

    def test_terminal_domain_is_high_risk(self, parser, extractor):
        intent = parser.parse("Run shell commands to configure the server")
        reqs = extractor.extract(intent)
        assert reqs.max_risk_level >= RiskLevel.HIGH

    def test_finance_domain_requires_approval(self, parser, extractor):
        intent = parser.parse("Execute stock trades in my portfolio")
        reqs = extractor.extract(intent)
        assert len(reqs.human_approval_points) > 0
        assert reqs.max_risk_level == RiskLevel.CRITICAL

    def test_conflicting_constraints_noted(self, parser, extractor):
        intent = parser.parse("Download web data in offline mode without internet")
        reqs = extractor.extract(intent)
        # Should note the conflict
        assert len(reqs.notes) > 0

    def test_docker_tool_adds_docker_permission(self, parser, extractor):
        intent = parser.parse("Deploy application using docker containers")
        reqs = extractor.extract(intent)
        assert any("docker" in p for p in reqs.permissions_needed)
        assert reqs.max_risk_level >= RiskLevel.HIGH


class TestConstraintModels:
    def test_hard_constraint_str(self):
        c = Constraint(kind=ConstraintKind.BUDGET, description="Max $5", hard=True, value=5.0, unit="USD")
        assert "HARD" in str(c)
        assert "budget" in str(c)

    def test_soft_constraint_str(self):
        c = Constraint(kind=ConstraintKind.RESOURCE, description="Prefer local", hard=False)
        assert "SOFT" in str(c)

    def test_constraint_has_unique_id(self):
        c1 = Constraint(kind=ConstraintKind.PRIVACY, description="No cloud")
        c2 = Constraint(kind=ConstraintKind.PRIVACY, description="No cloud")
        assert c1.constraint_id != c2.constraint_id

    def test_privacy_constraint_added_for_local_only_goal(self, engine):
        mission = engine.create_mission("Analyse files locally without internet in offline mode")
        kinds = [c.kind for c in mission.constraints]
        assert ConstraintKind.PRIVACY in kinds

    def test_resource_constraint_added_for_internet_goal(self, engine):
        mission = engine.create_mission("Search the web and download research papers")
        kinds = [c.kind for c in mission.constraints]
        assert ConstraintKind.RESOURCE in kinds
