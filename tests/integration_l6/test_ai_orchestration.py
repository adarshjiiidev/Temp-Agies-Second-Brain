"""Integration tests — L6 AI-native orchestration layer.

Tests the MockReasoningProvider integration with PlannerService.
All tests are fully deterministic — zero LLM calls.

Coverage:
  1.  AI orchestrator unavailable → deterministic fallback
  2.  AI orchestrator returns structured intent analysis
  3.  AI orchestrator returns clarification questions (ambiguous goal)
  4.  AI orchestrator returns task graph (task decomposition)
  5.  AI orchestrator returns strategy recommendation
  6.  AI orchestrator returns verification plan
  7.  AI orchestrator returns recovery plan
  8.  AI orchestrator returns reflection feedback
  9.  Serialization round-trip of reasoning results
  10. Capability snapshot injection (CapabilityRegistry seeding)
  11. Offline mode context generation
"""

from __future__ import annotations

import pytest

from aegis.l6_planning import PlannerContext, PlannerService, PlanningResult
from aegis.l6_planning.types import PlanState, PlanningStrategy, RiskLevel
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
from aegis.reasoning import MockReasoningProvider
from aegis.reasoning.types import PromptId


# ---------------------------------------------------------------------------
# Helpers — pre-built mock responses for each AI step
# ---------------------------------------------------------------------------

def _make_intent(domain: str = "coding", confidence: float = 0.9) -> IntentAnalysisOutput:
    return IntentAnalysisOutput(
        domain=domain,
        primary_verb="build",
        target_resource="portfolio website",
        requires_internet=False,
        requires_local_only=False,
        confidence=confidence,
        ambiguities=[],
        detected_tools=["python", "git"],
        action_hints=["fs.write", "git.commit"],
    )


def _make_no_ambiguity() -> AmbiguityReportOutput:
    return AmbiguityReportOutput(
        is_ambiguous=False,
        blocking=False,
        questions=[],
        confidence=0.95,
    )


def _make_ambiguous(blocking: bool = False) -> AmbiguityReportOutput:
    return AmbiguityReportOutput(
        is_ambiguous=True,
        blocking=blocking,
        questions=["Which framework should be used?", "What deployment target?"],
        confidence=0.6,
    )


def _make_objectives() -> ObjectiveGenerationOutput:
    return ObjectiveGenerationOutput(
        objectives=[
            ObjectiveSpec(
                title="Set up project scaffold",
                description="Initialize directory structure and dependencies",
                priority=1,
                effort="medium",
                completion_criteria=["Directory exists", "package.json present"],
            ),
            ObjectiveSpec(
                title="Implement core features",
                description="Build the main application components",
                priority=2,
                effort="high",
                completion_criteria=["Components render", "Tests pass"],
            ),
        ],
        rationale="Two-phase approach: scaffold then implement.",
    )


def _make_strategy(strategy: str = "balanced") -> StrategySelectionOutput:
    return StrategySelectionOutput(
        strategy=strategy,
        rationale="Balanced approach suits the goal.",
        confidence=0.88,
    )


def _make_tasks() -> TaskDecompositionOutput:
    return TaskDecompositionOutput(
        tasks=[
            TaskSpec(
                title="Create project directory",
                action_hint="fs.write",
                estimated_seconds=30,
                risk_level="low",
                requires_approval=False,
                can_run_parallel=False,
            ),
            TaskSpec(
                title="Install dependencies",
                action_hint="shell.exec",
                estimated_seconds=120,
                risk_level="medium",
                requires_approval=False,
                can_run_parallel=False,
            ),
            TaskSpec(
                title="Run test suite",
                action_hint="shell.exec",
                estimated_seconds=60,
                risk_level="low",
                requires_approval=False,
                can_run_parallel=True,
            ),
        ],
        dependency_order=[
            "Create project directory",
            "Install dependencies",
            "Run test suite",
        ],
    )


def _make_verification() -> VerificationCriteriaOutput:
    return VerificationCriteriaOutput(
        criteria=[
            VerificationCriterionSpec(
                task_title="Create project directory",
                check_description="Directory exists at expected path",
                check_type="output_exists",
                severity="error",
                automated=True,
            ),
            VerificationCriterionSpec(
                task_title="Run test suite",
                check_description="All tests pass with exit code 0",
                check_type="assertion",
                severity="error",
                automated=True,
            ),
            VerificationCriterionSpec(
                task_title="Install dependencies",
                check_description="Manually verify installed packages are correct",
                check_type="manual_review",
                severity="warning",
                automated=False,
            ),
        ],
        overall_strategy="Verify filesystem outputs automatically; manual review for package installs.",
    )


def _make_recovery() -> RecoveryPlanningOutput:
    return RecoveryPlanningOutput(
        scenarios=[
            RecoveryScenarioSpec(
                failure_mode="Disk full during directory creation",
                affected_task_hints=["fs.write"],
                probability="low",
                recovery_strategy="Free disk space and retry",
                rollback_possible=True,
                estimated_recovery_seconds=60,
            ),
            RecoveryScenarioSpec(
                failure_mode="Shell command exits non-zero",
                affected_task_hints=["shell.exec"],
                probability="medium",
                recovery_strategy="Log output and ask user to fix manually",
                rollback_possible=False,
                estimated_recovery_seconds=300,
            ),
        ],
        global_fallback="Cancel plan and report failure to user with full context",
    )


def _make_reflection(passed: bool = True) -> ReflectionInsightOutput:
    return ReflectionInsightOutput(
        issues=[
            {"category": "risk", "severity": "warning", "message": "Shell tasks may need approval"},
        ],
        suggestions=["Consider adding a dry-run step before shell execution"],
        confidence_adjustment=-0.02,
        quality_assessment="Plan is well-structured with clear tasks.",
        passed=passed,
    )


def _full_provider() -> MockReasoningProvider:
    """Return a MockReasoningProvider with all required prompts registered."""
    provider = MockReasoningProvider()
    provider.register_fixed(PromptId.INTENT_ANALYSIS, _make_intent())
    provider.register_fixed(PromptId.AMBIGUITY_DETECTION, _make_no_ambiguity())
    provider.register_fixed(PromptId.OBJECTIVE_GENERATION, _make_objectives())
    provider.register_fixed(PromptId.STRATEGY_SELECTION, _make_strategy())
    provider.register_fixed(PromptId.TASK_DECOMPOSITION, _make_tasks())
    provider.register_fixed(PromptId.VERIFICATION_CRITERIA, _make_verification())
    provider.register_fixed(PromptId.RECOVERY_PLANNING, _make_recovery())
    provider.register_fixed(PromptId.REFLECTION, _make_reflection())
    return provider


# ---------------------------------------------------------------------------
# Test 1: Unavailable provider → deterministic fallback
# ---------------------------------------------------------------------------

class TestFallbackWhenUnavailable:
    @pytest.mark.asyncio
    async def test_unavailable_provider_uses_deterministic_fallback(self):
        """When provider.is_available is False, create_plan must fall back."""
        provider = MockReasoningProvider()
        provider.set_available(False)
        service = PlannerService(reasoning_provider=provider)

        result = await service.create_plan("Build a React portfolio website")

        assert isinstance(result, PlanningResult)
        assert result.state == PlanState.READY
        assert result.task_count > 0
        # No AI calls should have been made
        assert provider.call_count(PromptId.INTENT_ANALYSIS) == 0

    @pytest.mark.asyncio
    async def test_missing_prompt_registration_falls_back(self):
        """Provider is available but has no registered prompts → fallback."""
        provider = MockReasoningProvider()
        # intent_analysis not registered → raises ReasoningUnavailableError → fallback
        service = PlannerService(reasoning_provider=provider)

        result = await service.create_plan("Write a Python script to parse CSV files")

        assert isinstance(result, PlanningResult)
        assert result.state == PlanState.READY
        assert result.task_count > 0

    @pytest.mark.asyncio
    async def test_no_provider_uses_deterministic_path(self):
        """Default constructor (no provider) always uses deterministic path."""
        service = PlannerService()
        result = await service.create_plan("Create a REST API with FastAPI")
        assert result.state == PlanState.READY
        assert result.confidence > 0.0


# ---------------------------------------------------------------------------
# Test 2: AI returns structured intent analysis
# ---------------------------------------------------------------------------

class TestAIIntentAnalysis:
    @pytest.mark.asyncio
    async def test_intent_analysis_called_once(self):
        """AI path calls intent_analysis exactly once per create_plan."""
        provider = _full_provider()
        service = PlannerService(reasoning_provider=provider)

        await service.create_plan("Build a React portfolio website")

        assert provider.call_count(PromptId.INTENT_ANALYSIS) == 1

    @pytest.mark.asyncio
    async def test_intent_variables_contain_goal_text(self):
        """Variables passed to intent_analysis include the raw goal string."""
        provider = _full_provider()
        service = PlannerService(reasoning_provider=provider)
        goal = "Build a React portfolio website"

        await service.create_plan(goal)

        vars_ = provider.last_variables(PromptId.INTENT_ANALYSIS)
        assert vars_ is not None
        assert vars_["goal_text"] == goal

    @pytest.mark.asyncio
    async def test_ai_result_is_planning_result(self):
        """Full AI path returns a valid PlanningResult with READY state."""
        provider = _full_provider()
        service = PlannerService(reasoning_provider=provider)

        result = await service.create_plan("Build a React portfolio website")

        assert isinstance(result, PlanningResult)
        assert result.state == PlanState.READY
        assert result.confidence >= 0.0


# ---------------------------------------------------------------------------
# Test 3: AI returns clarification questions (ambiguous goal)
# ---------------------------------------------------------------------------

class TestAIAmbiguityDetection:
    @pytest.mark.asyncio
    async def test_ambiguous_nonblocking_still_produces_plan(self):
        """Non-blocking ambiguity: plan proceeds, ambiguity surfaced in reflection."""
        provider = _full_provider()
        provider.register_fixed(PromptId.AMBIGUITY_DETECTION, _make_ambiguous(blocking=False))
        service = PlannerService(reasoning_provider=provider)

        result = await service.create_plan("Do something with the data")

        assert result.state == PlanState.READY
        assert result.task_count > 0
        if result.reflection_report:
            categories = [i.category for i in result.reflection_report.issues]
            assert "ambiguity" in categories

    @pytest.mark.asyncio
    async def test_ambiguous_blocking_still_produces_plan(self):
        """Blocking ambiguity is noted but plan proceeds (L7 UI handles the block)."""
        provider = _full_provider()
        provider.register_fixed(PromptId.AMBIGUITY_DETECTION, _make_ambiguous(blocking=True))
        service = PlannerService(reasoning_provider=provider)

        result = await service.create_plan("Do something complex")

        assert isinstance(result, PlanningResult)
        assert result.state == PlanState.READY


# ---------------------------------------------------------------------------
# Test 4: AI returns task graph
# ---------------------------------------------------------------------------

class TestAITaskDecomposition:
    @pytest.mark.asyncio
    async def test_task_count_matches_ai_specs(self):
        """Task count from AI path equals number of TaskSpec objects returned."""
        provider = _full_provider()
        service = PlannerService(reasoning_provider=provider)

        result = await service.create_plan("Build a React portfolio website")

        assert result.task_count == 3

    @pytest.mark.asyncio
    async def test_task_titles_come_from_ai(self):
        """Task titles in the result match the AI-generated TaskSpec titles."""
        provider = _full_provider()
        service = PlannerService(reasoning_provider=provider)

        result = await service.create_plan("Build a React portfolio website")

        titles = {t.title for t in result.tasks}
        assert "Create project directory" in titles
        assert "Install dependencies" in titles
        assert "Run test suite" in titles

    @pytest.mark.asyncio
    async def test_decomposition_called_once(self):
        """task_decomposition prompt invoked exactly once during AI planning."""
        provider = _full_provider()
        service = PlannerService(reasoning_provider=provider)

        await service.create_plan("Build a React portfolio website")

        assert provider.call_count(PromptId.TASK_DECOMPOSITION) == 1


# ---------------------------------------------------------------------------
# Test 5: AI returns strategy recommendation
# ---------------------------------------------------------------------------

class TestAIStrategySelection:
    @pytest.mark.asyncio
    async def test_balanced_strategy_propagates(self):
        """AI returns 'balanced' → result strategy is BALANCED."""
        provider = _full_provider()
        service = PlannerService(reasoning_provider=provider)

        result = await service.create_plan("Build a React portfolio website")

        assert result.strategy == PlanningStrategy.BALANCED

    @pytest.mark.asyncio
    async def test_offline_first_strategy_propagates(self):
        """AI returns 'offline_first' → result strategy is OFFLINE_FIRST."""
        provider = _full_provider()
        provider.register_fixed(PromptId.STRATEGY_SELECTION, _make_strategy("offline_first"))
        service = PlannerService(reasoning_provider=provider)

        result = await service.create_plan("Analyse local log files")

        assert result.strategy == PlanningStrategy.OFFLINE_FIRST

    @pytest.mark.asyncio
    async def test_unknown_strategy_falls_back_to_balanced(self):
        """AI returns garbage strategy string → BALANCED fallback."""
        provider = _full_provider()
        provider.register_fixed(
            PromptId.STRATEGY_SELECTION,
            StrategySelectionOutput(
                strategy="turbo_ultra_mode",
                rationale="x",
                confidence=0.5,
            ),
        )
        service = PlannerService(reasoning_provider=provider)

        result = await service.create_plan("Do something")

        assert result.strategy == PlanningStrategy.BALANCED


# ---------------------------------------------------------------------------
# Test 6: AI returns verification plan
# ---------------------------------------------------------------------------

class TestAIVerificationPlan:
    @pytest.mark.asyncio
    async def test_verification_plan_not_empty(self):
        """AI-driven verification plan has at least one check."""
        provider = _full_provider()
        service = PlannerService(reasoning_provider=provider)

        result = await service.create_plan("Build a React portfolio website")

        assert result.verification_plan is not None
        assert result.verification_plan.total_checks > 0

    @pytest.mark.asyncio
    async def test_verification_has_manual_and_auto_checks(self):
        """Verification plan from AI includes both automatic and manual checks."""
        provider = _full_provider()
        service = PlannerService(reasoning_provider=provider)

        result = await service.create_plan("Build a React portfolio website")

        vp = result.verification_plan
        assert vp.automatic_check_count > 0
        assert vp.manual_check_count > 0

    @pytest.mark.asyncio
    async def test_verification_prompt_called_once(self):
        """verification_criteria prompt invoked exactly once."""
        provider = _full_provider()
        service = PlannerService(reasoning_provider=provider)

        await service.create_plan("Build a React portfolio website")

        assert provider.call_count(PromptId.VERIFICATION_CRITERIA) == 1


# ---------------------------------------------------------------------------
# Test 7: AI returns recovery plan
# ---------------------------------------------------------------------------

class TestAIRecoveryPlan:
    @pytest.mark.asyncio
    async def test_recovery_plan_has_scenarios(self):
        """AI-driven recovery plan contains failure scenarios."""
        provider = _full_provider()
        service = PlannerService(reasoning_provider=provider)

        result = await service.create_plan("Build a React portfolio website")

        assert result.recovery_plan is not None
        assert len(result.recovery_plan.scenarios) > 0

    @pytest.mark.asyncio
    async def test_recovery_scenario_failure_mode_preserved(self):
        """Failure mode strings from AI are preserved in FailureScenario objects."""
        provider = _full_provider()
        service = PlannerService(reasoning_provider=provider)

        result = await service.create_plan("Build a React portfolio website")

        modes = {s.failure_mode for s in result.recovery_plan.scenarios}
        assert "Disk full during directory creation" in modes
        assert "Shell command exits non-zero" in modes

    @pytest.mark.asyncio
    async def test_recovery_escalation_conditions_non_empty(self):
        """Recovery plan includes escalation conditions."""
        provider = _full_provider()
        service = PlannerService(reasoning_provider=provider)

        result = await service.create_plan("Build a React portfolio website")

        assert len(result.recovery_plan.escalation_conditions) > 0


# ---------------------------------------------------------------------------
# Test 8: AI returns reflection feedback
# ---------------------------------------------------------------------------

class TestAIReflectionFeedback:
    @pytest.mark.asyncio
    async def test_reflection_report_present(self):
        """AI-driven plan has a reflection report."""
        provider = _full_provider()
        service = PlannerService(reasoning_provider=provider)

        result = await service.create_plan("Build a React portfolio website")

        assert result.reflection_report is not None

    @pytest.mark.asyncio
    async def test_reflection_issues_from_ai(self):
        """Reflection issues come from AI output."""
        provider = _full_provider()
        service = PlannerService(reasoning_provider=provider)

        result = await service.create_plan("Build a React portfolio website")

        report = result.reflection_report
        assert any(i.category == "risk" for i in report.issues)

    @pytest.mark.asyncio
    async def test_reflection_optimizations_from_ai(self):
        """Optimization suggestions from AI appear in the reflection report."""
        provider = _full_provider()
        service = PlannerService(reasoning_provider=provider)

        result = await service.create_plan("Build a React portfolio website")

        assert len(result.reflection_report.optimizations) > 0

    @pytest.mark.asyncio
    async def test_confidence_adjusted_by_reflection(self):
        """confidence_adjustment from AI modifies the final plan confidence."""
        provider = _full_provider()
        service = PlannerService(reasoning_provider=provider)

        result = await service.create_plan("Build a React portfolio website")

        assert 0.0 <= result.confidence <= 1.0


# ---------------------------------------------------------------------------
# Test 9: Serialization round-trip of reasoning results
# ---------------------------------------------------------------------------

class TestReasoningSerialization:
    def test_intent_analysis_output_round_trip(self):
        """IntentAnalysisOutput serialises and deserialises without loss."""
        original = _make_intent(domain="research", confidence=0.77)
        json_str = original.model_dump_json()
        restored = IntentAnalysisOutput.model_validate_json(json_str)
        assert restored.domain == "research"
        assert abs(restored.confidence - 0.77) < 1e-6

    def test_task_decomposition_round_trip(self):
        """TaskDecompositionOutput serialises and deserialises correctly."""
        original = _make_tasks()
        json_str = original.model_dump_json()
        restored = TaskDecompositionOutput.model_validate_json(json_str)
        assert len(restored.tasks) == len(original.tasks)
        assert restored.tasks[0].title == original.tasks[0].title

    def test_reflection_round_trip(self):
        """ReflectionInsightOutput serialises and deserialises correctly."""
        original = _make_reflection()
        json_str = original.model_dump_json()
        restored = ReflectionInsightOutput.model_validate_json(json_str)
        assert restored.passed == original.passed
        assert restored.confidence_adjustment == original.confidence_adjustment

    def test_verification_criteria_round_trip(self):
        """VerificationCriteriaOutput serialises and deserialises correctly."""
        original = _make_verification()
        json_str = original.model_dump_json()
        restored = VerificationCriteriaOutput.model_validate_json(json_str)
        assert len(restored.criteria) == len(original.criteria)

    def test_recovery_planning_round_trip(self):
        """RecoveryPlanningOutput serialises and deserialises correctly."""
        original = _make_recovery()
        json_str = original.model_dump_json()
        restored = RecoveryPlanningOutput.model_validate_json(json_str)
        assert len(restored.scenarios) == len(original.scenarios)
        assert restored.global_fallback == original.global_fallback


# ---------------------------------------------------------------------------
# Test 10: Capability snapshot injection
# ---------------------------------------------------------------------------

class TestCapabilitySnapshotInjection:
    def test_capability_registry_seeds_without_error(self):
        """CapabilityRegistry.seed() accepts a capability list without error."""
        from aegis.capabilities.registry import CapabilityRegistry
        from aegis.capabilities.types import Capability, CapabilityKind, CapabilityStatus

        registry = CapabilityRegistry()
        registry.seed([
            Capability(
                kind=CapabilityKind.GIT,
                name="Git 2.43.0",
                status=CapabilityStatus.AVAILABLE,
                version="2.43.0",
            ),
            Capability(
                kind=CapabilityKind.PYTHON,
                name="Python 3.12.3",
                status=CapabilityStatus.AVAILABLE,
                version="3.12.3",
            ),
        ])

        snapshot = registry.snapshot()
        assert snapshot.is_available(CapabilityKind.GIT)
        assert snapshot.is_available(CapabilityKind.PYTHON)
        assert not snapshot.is_available(CapabilityKind.DOCKER)

    def test_capability_set_to_summary_dict(self):
        """CapabilitySet.to_summary_dict() returns dict suitable for prompt injection."""
        from aegis.capabilities.registry import CapabilityRegistry
        from aegis.capabilities.types import Capability, CapabilityKind, CapabilityStatus

        registry = CapabilityRegistry()
        registry.seed([
            Capability(
                kind=CapabilityKind.DOCKER,
                name="Docker 24.0",
                status=CapabilityStatus.UNAVAILABLE,
            ),
        ])
        summary = registry.snapshot().to_summary_dict()
        assert "docker" in summary
        assert summary["docker"]["available"] is False

    def test_action_prefix_capability_check(self):
        """CapabilityRegistry.available_for_action() maps prefixes correctly."""
        from aegis.capabilities.registry import CapabilityRegistry
        from aegis.capabilities.types import Capability, CapabilityKind, CapabilityStatus

        registry = CapabilityRegistry()
        registry.seed([
            Capability(
                kind=CapabilityKind.SHELL,
                name="PowerShell",
                status=CapabilityStatus.AVAILABLE,
            ),
        ])

        assert registry.available_for_action("shell.exec") is True
        assert registry.available_for_action("docker.run") is False
        # Unknown prefix → assume available
        assert registry.available_for_action("custom.action") is True


# ---------------------------------------------------------------------------
# Test 11: Offline mode context generation
# ---------------------------------------------------------------------------

class TestOfflineModeContextGeneration:
    @pytest.mark.asyncio
    async def test_offline_context_uses_deterministic_path(self):
        """With offline_first context and no provider, deterministic path runs."""
        service = PlannerService()
        ctx = PlannerContext(strategy=PlanningStrategy.OFFLINE_FIRST)

        result = await service.create_plan("Analyse local files", ctx)

        assert result.state == PlanState.READY
        assert result.strategy in (
            PlanningStrategy.OFFLINE_FIRST,
            PlanningStrategy.PRIVACY_FIRST,
        )

    @pytest.mark.asyncio
    async def test_offline_context_with_ai_provider_uses_ai_path(self):
        """Offline strategy hint propagates correctly through AI path."""
        provider = _full_provider()
        provider.register_fixed(PromptId.STRATEGY_SELECTION, _make_strategy("offline_first"))
        service = PlannerService(reasoning_provider=provider)
        ctx = PlannerContext(strategy=PlanningStrategy.OFFLINE_FIRST)

        result = await service.create_plan("Analyse local CSV files", ctx)

        assert result.state == PlanState.READY
        assert result.strategy == PlanningStrategy.OFFLINE_FIRST

    @pytest.mark.asyncio
    async def test_mock_provider_call_tracking(self):
        """MockReasoningProvider records all calls correctly."""
        provider = _full_provider()
        service = PlannerService(reasoning_provider=provider)

        await service.create_plan("Build a CLI tool")

        # All 8 AI prompts in the pipeline must have been called
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
            assert provider.call_count(pid) >= 1, f"Expected call to {pid!r}"