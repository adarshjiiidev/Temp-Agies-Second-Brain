"""Integration tests — L6 AI Reasoning Provider path.

Verifies the AI-driven planning pipeline using MockReasoningProvider.
These tests exercise the NEW code paths introduced in the AI-Native redesign.

Key invariants verified:
  1. MockReasoningProvider is called with the correct prompt IDs.
  2. AI outputs are correctly converted to L6 domain models.
  3. The deterministic fallback activates when the provider is unavailable.
  4. All existing 726 tests continue to pass (covered by unchanged test files).
  5. Strategy enum mapping from AI strings works correctly.
  6. Reflection and ambiguity outputs are surfaced in the PlanningResult.

Import safety: test helpers + aegis.reasoning + aegis.l6_planning only.
"""

from __future__ import annotations

import pytest

from aegis.reasoning.mock_provider import MockReasoningProvider
from aegis.reasoning.provider import ReasoningUnavailableError
from aegis.reasoning.types import PromptId

from aegis.l6_planning.orchestration.planner_service import PlannerService
from aegis.l6_planning.state.planner_context import PlannerContext
from aegis.l6_planning.types import PlanningStrategy, PlanState
from aegis.l6_planning.reasoning.schemas import (
    IntentAnalysisOutput,
    AmbiguityReportOutput,
    ObjectiveGenerationOutput,
    ObjectiveSpec,
    TaskDecompositionOutput,
    TaskSpec,
    StrategySelectionOutput,
    VerificationCriteriaOutput,
    VerificationCriterionSpec,
    RecoveryPlanningOutput,
    RecoveryScenarioSpec,
    ReflectionInsightOutput,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_provider() -> MockReasoningProvider:
    """Build a fully pre-configured MockReasoningProvider for a coding goal."""
    provider = MockReasoningProvider()

    # 1. Intent analysis
    provider.register_fixed(
        PromptId.INTENT_ANALYSIS,
        IntentAnalysisOutput(
            domain="coding",
            primary_verb="build",
            target_resource="python module",
            requires_internet=False,
            requires_local_only=False,
            confidence=0.92,
            ambiguities=[],
            detected_tools=["python", "pytest"],
            action_hints=["fs.write", "shell.exec"],
        ),
    )

    # 2. Ambiguity detection — clear goal, not blocking
    provider.register_fixed(
        PromptId.AMBIGUITY_DETECTION,
        AmbiguityReportOutput(
            is_ambiguous=False,
            blocking=False,
            questions=[],
            confidence=0.95,
            conflict_detected=False,
        ),
    )

    # 3. Objective generation — 3 objectives
    provider.register_fixed(
        PromptId.OBJECTIVE_GENERATION,
        ObjectiveGenerationOutput(
            objectives=[
                ObjectiveSpec(
                    title="Understand requirements",
                    description="Analyse the project requirements and scope",
                    priority=1,
                    effort="low",
                    depends_on_titles=[],
                    completion_criteria=["Requirements document exists"],
                ),
                ObjectiveSpec(
                    title="Implement core module",
                    description="Write the Python module with tests",
                    priority=2,
                    effort="high",
                    depends_on_titles=["Understand requirements"],
                    completion_criteria=["All tests pass", "Coverage >= 80%"],
                ),
                ObjectiveSpec(
                    title="Review and refine",
                    description="Code review and final quality check",
                    priority=3,
                    effort="medium",
                    depends_on_titles=["Implement core module"],
                    completion_criteria=["No critical issues"],
                ),
            ],
            rationale="Standard coding workflow for a Python module",
        ),
    )

    # 4. Strategy selection
    provider.register_fixed(
        PromptId.STRATEGY_SELECTION,
        StrategySelectionOutput(
            strategy="developer_mode",
            rationale="Coding domain with local tools",
            confidence=0.88,
            alternative="balanced",
        ),
    )

    # 5. Task decomposition — 4 tasks
    provider.register_fixed(
        PromptId.TASK_DECOMPOSITION,
        TaskDecompositionOutput(
            tasks=[
                TaskSpec(
                    title="Read existing codebase",
                    action_hint="fs.read",
                    estimated_seconds=120,
                    risk_level="low",
                    requires_approval=False,
                    can_run_parallel=False,
                    rationale="Understand existing code before writing",
                ),
                TaskSpec(
                    title="Write core module",
                    action_hint="fs.write",
                    estimated_seconds=900,
                    risk_level="low",
                    requires_approval=False,
                    can_run_parallel=False,
                    rationale="Main implementation task",
                ),
                TaskSpec(
                    title="Run test suite",
                    action_hint="shell.exec",
                    estimated_seconds=300,
                    risk_level="medium",
                    requires_approval=False,
                    can_run_parallel=False,
                    rationale="Verify implementation correctness",
                ),
                TaskSpec(
                    title="Generate code review report",
                    action_hint="fs.write",
                    estimated_seconds=180,
                    risk_level="low",
                    requires_approval=False,
                    can_run_parallel=True,
                    rationale="Document findings",
                ),
            ],
            dependency_order=[
                "Read existing codebase",
                "Write core module",
                "Run test suite",
                "Generate code review report",
            ],
            notes="Standard Python module workflow",
        ),
    )

    # 6. Verification criteria
    provider.register_fixed(
        PromptId.VERIFICATION_CRITERIA,
        VerificationCriteriaOutput(
            criteria=[
                VerificationCriterionSpec(
                    task_title="Write core module",
                    check_description="Module file exists and is importable",
                    check_type="output_exists",
                    severity="error",
                    automated=True,
                ),
                VerificationCriterionSpec(
                    task_title="Run test suite",
                    check_description="All tests pass with exit code 0",
                    check_type="assertion",
                    severity="critical",
                    automated=True,
                ),
            ],
            overall_strategy="Verify file existence then run tests",
        ),
    )

    # 7. Recovery planning
    provider.register_fixed(
        PromptId.RECOVERY_PLANNING,
        RecoveryPlanningOutput(
            scenarios=[
                RecoveryScenarioSpec(
                    failure_mode="Test suite fails due to import error",
                    affected_task_hints=["shell.exec"],
                    probability="medium",
                    recovery_strategy="Check module imports and re-run",
                    rollback_possible=True,
                    estimated_recovery_seconds=180,
                ),
            ],
            global_fallback="Pause plan and prompt user for manual intervention",
        ),
    )

    # 8. Reflection
    provider.register_fixed(
        PromptId.REFLECTION,
        ReflectionInsightOutput(
            issues=[],
            suggestions=["Consider adding type hints to public API"],
            confidence_adjustment=0.02,
            quality_assessment="Well-structured coding plan with clear objectives",
            passed=True,
        ),
    )

    return provider


# ---------------------------------------------------------------------------
# Core AI path tests
# ---------------------------------------------------------------------------

class TestMockReasoningProvider:
    """Unit tests for MockReasoningProvider itself."""

    @pytest.mark.asyncio
    async def test_fixed_response_is_returned(self):
        provider = MockReasoningProvider()
        expected = IntentAnalysisOutput(
            domain="coding", primary_verb="build",
            requires_internet=False, requires_local_only=False,
            confidence=0.9, ambiguities=[],
        )
        provider.register_fixed(PromptId.INTENT_ANALYSIS, expected)
        result = await provider.reason(PromptId.INTENT_ANALYSIS, {}, IntentAnalysisOutput)
        assert result is expected

    @pytest.mark.asyncio
    async def test_call_count_is_tracked(self):
        provider = MockReasoningProvider()
        provider.register_fixed(
            PromptId.INTENT_ANALYSIS,
            IntentAnalysisOutput(
                domain="coding", primary_verb="build",
                requires_internet=False, requires_local_only=False,
                confidence=0.9,
            ),
        )
        await provider.reason(PromptId.INTENT_ANALYSIS, {"a": "1"}, IntentAnalysisOutput)
        await provider.reason(PromptId.INTENT_ANALYSIS, {"a": "2"}, IntentAnalysisOutput)
        assert provider.call_count(PromptId.INTENT_ANALYSIS) == 2

    @pytest.mark.asyncio
    async def test_last_variables_recorded(self):
        provider = MockReasoningProvider()
        provider.register_fixed(
            PromptId.INTENT_ANALYSIS,
            IntentAnalysisOutput(
                domain="research", primary_verb="find",
                requires_internet=True, requires_local_only=False,
                confidence=0.7,
            ),
        )
        await provider.reason(
            PromptId.INTENT_ANALYSIS,
            {"goal_text": "find papers", "context_json": "{}"},
            IntentAnalysisOutput,
        )
        vars_ = provider.last_variables(PromptId.INTENT_ANALYSIS)
        assert vars_["goal_text"] == "find papers"

    @pytest.mark.asyncio
    async def test_unavailable_raises_error(self):
        provider = MockReasoningProvider()
        provider.set_available(False)
        with pytest.raises(ReasoningUnavailableError):
            await provider.reason(PromptId.INTENT_ANALYSIS, {}, IntentAnalysisOutput)

    @pytest.mark.asyncio
    async def test_unregistered_prompt_raises_error(self):
        provider = MockReasoningProvider()
        with pytest.raises(ReasoningUnavailableError, match="no factory registered"):
            await provider.reason("nonexistent_prompt_v1", {}, IntentAnalysisOutput)

    @pytest.mark.asyncio
    async def test_factory_callable_receives_variables(self):
        provider = MockReasoningProvider()
        received: dict = {}

        def factory(variables, schema):
            received.update(variables)
            return schema(
                domain="coding", primary_verb="test",
                requires_internet=False, requires_local_only=False,
                confidence=0.8,
            )

        provider.register(PromptId.INTENT_ANALYSIS, factory)
        await provider.reason(
            PromptId.INTENT_ANALYSIS,
            {"key": "value"},
            IntentAnalysisOutput,
        )
        assert received["key"] == "value"

    def test_reset_clears_call_history(self):
        provider = MockReasoningProvider()
        provider._call_counts["test"] = 5
        provider.reset()
        assert provider.call_count("test") == 0


# ---------------------------------------------------------------------------
# Full AI planning pipeline tests
# ---------------------------------------------------------------------------

class TestAIPlannerPipeline:
    """End-to-end tests of the AI-driven create_plan() pipeline."""

    @pytest.mark.asyncio
    async def test_ai_plan_returns_ready_state(self):
        provider = _make_provider()
        service = PlannerService(reasoning_provider=provider)
        result = await service.create_plan("Build a Python data-processing module")
        assert result.state == PlanState.READY

    @pytest.mark.asyncio
    async def test_ai_plan_uses_ai_strategy(self):
        """AI selected 'developer_mode' — should be in the result."""
        provider = _make_provider()
        service = PlannerService(reasoning_provider=provider)
        result = await service.create_plan("Build a Python data-processing module")
        assert result.strategy == PlanningStrategy.DEVELOPER_MODE

    @pytest.mark.asyncio
    async def test_ai_plan_has_ai_objectives(self):
        """Plan objectives come from the AI's ObjectiveGenerationOutput."""
        provider = _make_provider()
        service = PlannerService(reasoning_provider=provider)
        result = await service.create_plan("Build a Python data-processing module")
        objective_titles = [o.title for o in result.mission.objectives]
        # AI returned 3 objectives
        assert len(result.mission.objectives) == 3
        assert any("Understand" in t for t in objective_titles)
        assert any("core module" in t for t in objective_titles)

    @pytest.mark.asyncio
    async def test_ai_plan_has_ai_tasks(self):
        """Plan tasks come from the AI's TaskDecompositionOutput."""
        provider = _make_provider()
        service = PlannerService(reasoning_provider=provider)
        result = await service.create_plan("Build a Python data-processing module")
        task_titles = [t.title for t in result.tasks]
        assert "Read existing codebase" in task_titles
        assert "Write core module" in task_titles
        assert "Run test suite" in task_titles

    @pytest.mark.asyncio
    async def test_ai_plan_has_verification_checks(self):
        """VerificationPlan comes from the AI's VerificationCriteriaOutput."""
        provider = _make_provider()
        service = PlannerService(reasoning_provider=provider)
        result = await service.create_plan("Build a Python data-processing module")
        assert result.verification_plan is not None
        assert result.verification_plan.total_checks >= 1

    @pytest.mark.asyncio
    async def test_ai_plan_has_recovery_scenarios(self):
        """RecoveryPlan comes from the AI's RecoveryPlanningOutput."""
        provider = _make_provider()
        service = PlannerService(reasoning_provider=provider)
        result = await service.create_plan("Build a Python data-processing module")
        assert result.recovery_plan is not None
        assert len(result.recovery_plan.scenarios) >= 1

    @pytest.mark.asyncio
    async def test_ai_plan_reflection_passed(self):
        """Reflection report uses AI insights (passed=True in mock)."""
        provider = _make_provider()
        service = PlannerService(reasoning_provider=provider)
        result = await service.create_plan("Build a Python data-processing module")
        assert result.reflection_report is not None
        assert result.reflection_report.passed is True

    @pytest.mark.asyncio
    async def test_all_prompt_ids_called(self):
        """Verify the AI pipeline calls all 8 prompt IDs exactly once."""
        provider = _make_provider()
        service = PlannerService(reasoning_provider=provider)
        await service.create_plan("Build a Python data-processing module")

        expected_prompts = [
            PromptId.INTENT_ANALYSIS,
            PromptId.AMBIGUITY_DETECTION,
            PromptId.OBJECTIVE_GENERATION,
            PromptId.STRATEGY_SELECTION,
            PromptId.TASK_DECOMPOSITION,
            PromptId.VERIFICATION_CRITERIA,
            PromptId.RECOVERY_PLANNING,
            PromptId.REFLECTION,
        ]
        for pid in expected_prompts:
            assert provider.call_count(pid) == 1, \
                f"Expected {pid!r} to be called once, got {provider.call_count(pid)}"

    @pytest.mark.asyncio
    async def test_intent_analysis_receives_goal_text(self):
        """The goal text is passed correctly as a variable to intent analysis."""
        provider = _make_provider()
        service = PlannerService(reasoning_provider=provider)
        goal = "Build a Python data-processing module"
        await service.create_plan(goal)
        vars_ = provider.last_variables(PromptId.INTENT_ANALYSIS)
        assert vars_["goal_text"] == goal

    @pytest.mark.asyncio
    async def test_result_has_positive_confidence(self):
        """Confidence should be > 0 when AI reasoning succeeds."""
        provider = _make_provider()
        service = PlannerService(reasoning_provider=provider)
        result = await service.create_plan("Build a Python data-processing module")
        assert result.confidence > 0.0

    @pytest.mark.asyncio
    async def test_result_stored_in_session(self):
        """Plan is stored in the session after AI creation."""
        provider = _make_provider()
        service = PlannerService(reasoning_provider=provider)
        result = await service.create_plan("Build a Python data-processing module")
        retrieved = service.get_session().get(result.plan_id)
        assert retrieved.plan_id == result.plan_id


# ---------------------------------------------------------------------------
# Fallback behaviour tests
# ---------------------------------------------------------------------------

class TestAIProviderFallback:
    """Verify the deterministic fallback is used when AI is unavailable."""

    @pytest.mark.asyncio
    async def test_unavailable_provider_falls_back_to_deterministic(self):
        """When provider.is_available=False, deterministic path is used."""
        provider = MockReasoningProvider()
        provider.set_available(False)
        service = PlannerService(reasoning_provider=provider)
        # Should NOT raise; falls back to deterministic
        result = await service.create_plan("Build a Python module")
        assert result.state == PlanState.READY
        # No AI calls were made
        assert provider.call_count(PromptId.INTENT_ANALYSIS) == 0

    @pytest.mark.asyncio
    async def test_no_provider_uses_deterministic(self):
        """PlannerService() with no provider runs full deterministic pipeline."""
        service = PlannerService()  # no reasoning_provider
        result = await service.create_plan("Analyse some CSV files")
        assert result.state == PlanState.READY
        assert result.mission is not None
        assert len(result.tasks) > 0

    @pytest.mark.asyncio
    async def test_mid_pipeline_failure_falls_back(self):
        """If AI raises ReasoningUnavailableError mid-pipeline, fallback is used."""
        provider = MockReasoningProvider()
        call_count = {"n": 0}

        def intent_then_fail(variables, schema):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return schema(
                    domain="coding", primary_verb="build",
                    requires_internet=False, requires_local_only=False,
                    confidence=0.9,
                )
            raise ReasoningUnavailableError("simulated mid-pipeline failure")

        provider.register(PromptId.INTENT_ANALYSIS, intent_then_fail)
        provider.register(PromptId.AMBIGUITY_DETECTION, intent_then_fail)  # will fail on 2nd call

        service = PlannerService(reasoning_provider=provider)
        result = await service.create_plan("Build a web scraper")
        # Should succeed via deterministic fallback
        assert result.state == PlanState.READY

    @pytest.mark.asyncio
    async def test_deterministic_plan_has_same_structure(self):
        """Deterministic plan has the same structural guarantees as AI plan."""
        service = PlannerService()
        result = await service.create_plan("Research quantum computing papers")
        assert result.state == PlanState.READY
        assert result.mission is not None
        assert result.tasks is not None
        assert result.verification_plan is not None
        assert result.recovery_plan is not None
        assert result.reflection_report is not None


# ---------------------------------------------------------------------------
# Strategy mapping tests
# ---------------------------------------------------------------------------

class TestStrategyMapping:
    """Unit tests for _parse_strategy helper."""

    def test_known_strategies_map_correctly(self):
        from aegis.l6_planning.orchestration.planner_service import _parse_strategy
        cases = [
            ("balanced", PlanningStrategy.BALANCED),
            ("developer_mode", PlanningStrategy.DEVELOPER_MODE),
            ("research_mode", PlanningStrategy.RESEARCH_MODE),
            ("privacy_first", PlanningStrategy.PRIVACY_FIRST),
            ("offline_first", PlanningStrategy.OFFLINE_FIRST),
            ("speed_first", PlanningStrategy.FASTEST),
            ("safe_mode", PlanningStrategy.BALANCED),
        ]
        for ai_str, expected in cases:
            assert _parse_strategy(ai_str, None) == expected, \
                f"Expected {expected} for {ai_str!r}"

    def test_case_insensitive_mapping(self):
        from aegis.l6_planning.orchestration.planner_service import _parse_strategy
        assert _parse_strategy("DEVELOPER_MODE", None) == PlanningStrategy.DEVELOPER_MODE
        assert _parse_strategy("Balanced", None) == PlanningStrategy.BALANCED

    def test_unknown_falls_back_to_user_preference(self):
        from aegis.l6_planning.orchestration.planner_service import _parse_strategy
        result = _parse_strategy("quantum_mode", PlanningStrategy.RESEARCH_MODE)
        assert result == PlanningStrategy.RESEARCH_MODE

    def test_unknown_with_no_preference_falls_back_to_balanced(self):
        from aegis.l6_planning.orchestration.planner_service import _parse_strategy
        result = _parse_strategy("quantum_mode", None)
        assert result == PlanningStrategy.BALANCED


# ---------------------------------------------------------------------------
# Reasoning package smoke tests
# ---------------------------------------------------------------------------

class TestReasoningPackageImports:
    """Verify the new reasoning package imports cleanly."""

    def test_import_reasoning_provider(self):
        from aegis.reasoning import ReasoningProvider
        assert ReasoningProvider is not None

    def test_import_mock_provider(self):
        from aegis.reasoning import MockReasoningProvider
        assert MockReasoningProvider is not None

    def test_import_prompt_id(self):
        from aegis.reasoning import PromptId
        assert PromptId.INTENT_ANALYSIS == "intent_analysis_v1"

    def test_import_schemas(self):
        from aegis.l6_planning.reasoning.schemas import IntentAnalysisOutput
        obj = IntentAnalysisOutput(
            domain="coding", primary_verb="build",
            requires_internet=False, requires_local_only=False,
            confidence=0.9,
        )
        assert obj.domain == "coding"
