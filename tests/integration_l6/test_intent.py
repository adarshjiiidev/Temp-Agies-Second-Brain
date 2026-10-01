"""Integration tests — L6 Intent Parser & Ambiguity Detector."""

from __future__ import annotations

import pytest

from aegis.l6_planning.intent.ambiguity_detector import AmbiguityDetector
from aegis.l6_planning.intent.intent_parser import IntentParser
from aegis.l6_planning.types import IntentDomain


@pytest.fixture
def parser():
    return IntentParser()


@pytest.fixture
def detector():
    return AmbiguityDetector()


class TestIntentParser:
    def test_coding_domain(self, parser):
        intent = parser.parse("Build a React portfolio website with TypeScript")
        assert intent.domain == IntentDomain.CODING
        assert intent.confidence > 0.4

    def test_research_domain(self, parser):
        intent = parser.parse("Research the latest machine learning papers on transformers")
        assert intent.domain == IntentDomain.RESEARCH

    def test_filesystem_domain(self, parser):
        intent = parser.parse("Organise my files and folders by date")
        assert intent.domain == IntentDomain.FILESYSTEM

    def test_browser_domain(self, parser):
        intent = parser.parse("Browse the web and find the best Python tutorials")
        assert intent.domain == IntentDomain.BROWSER

    def test_terminal_domain(self, parser):
        intent = parser.parse("Run the bash commands to install dependencies")
        assert intent.domain == IntentDomain.TERMINAL

    def test_finance_domain(self, parser):
        intent = parser.parse("Analyse my stock portfolio and calculate returns")
        assert intent.domain == IntentDomain.FINANCE

    def test_automation_domain(self, parser):
        intent = parser.parse("Automate my daily workflow for sending emails")
        assert intent.domain == IntentDomain.AUTOMATION

    def test_planning_domain(self, parser):
        intent = parser.parse("Create a project roadmap and plan for my team")
        assert intent.domain == IntentDomain.PLANNING

    def test_detects_internet_requirement(self, parser):
        intent = parser.parse("Download data from the web API endpoint")
        assert intent.requires_internet

    def test_detects_local_only(self, parser):
        intent = parser.parse("Organise my offline local files without internet")
        assert intent.requires_local_only

    def test_extracts_primary_verb(self, parser):
        intent = parser.parse("Build a complete web application")
        assert intent.primary_verb == "build"

    def test_detects_git_tool(self, parser):
        intent = parser.parse("Commit my changes to the git repository")
        assert "git" in intent.detected_tools

    def test_detects_docker_tool(self, parser):
        intent = parser.parse("Deploy the application using docker containers")
        assert "docker" in intent.detected_tools

    def test_context_domain_hint_overrides(self, parser):
        intent = parser.parse("Do something", context={"domain_hint": "research"})
        assert intent.domain == IntentDomain.RESEARCH

    def test_short_goal_is_not_ambiguous_domain(self, parser):
        intent = parser.parse("Build a Python script")
        # Short but specific enough
        assert intent.domain in (IntentDomain.CODING, IntentDomain.TERMINAL)


class TestAmbiguityDetector:
    def test_clear_goal_not_ambiguous(self, parser, detector):
        intent = parser.parse("Build a React portfolio website with TypeScript and deploy to Vercel")
        report = detector.detect(intent)
        # High confidence goal should not be blocking-ambiguous
        assert not report.blocking

    def test_very_short_goal_generates_question(self, parser, detector):
        intent = parser.parse("Do it")
        report = detector.detect(intent)
        assert report.is_ambiguous
        assert report.question_count > 0

    def test_conflicting_constraints_generates_question(self, parser, detector):
        intent = parser.parse("Download files from the internet in offline mode")
        report = detector.detect(intent)
        assert report.is_ambiguous

    def test_report_has_questions_list(self, parser, detector):
        intent = parser.parse("Do")
        report = detector.detect(intent)
        assert isinstance(report.questions, list)
