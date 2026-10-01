"""G1: Full AI-chain integration test.

Tests PlannerService -> KernelReasoningProvider pipeline.

Design: We mock KernelReasoningProvider.reason() to return real Pydantic schema
objects directly, bypassing the kernel's structured-output retry loop. This lets
us control the exact return value for each of the 8 AI prompts and verify G2
alignment and other pipeline invariants cleanly.

Verified schema fields (from source - aegis.l6_planning.reasoning.schemas):
- IntentAnalysisOutput: domain, primary_verb, requires_internet, requires_local_only,
  confidence, ambiguities=[], detected_tools=[], action_hints=[]
- AmbiguityReportOutput: is_ambiguous, blocking, questions=[], confidence, conflict_detected=False
- ObjectiveGenerationOutput: objectives=[ObjectiveSpec(title, description, priority, effort,
  depends_on_titles=[], completion_criteria=[])], rationale=''
- StrategySelectionOutput: strategy, rationale, confidence, alternative=None
- TaskDecompositionOutput: tasks=[TaskSpec(title, action_hint, ...)], dependency_order=[], notes=''
- VerificationCriteriaOutput: criteria=[VerificationCriterionSpec(task_title, check_description,...)], overall_strategy=''
- RecoveryPlanningOutput: scenarios=[RecoveryScenarioSpec(failure_mode, recovery_strategy,...)], global_fallback=...
- ReflectionInsightOutput: passed (REQUIRED), issues=[], suggestions=[], quality_assessment='', confidence_adjustment=0.0

No live network calls.
"""

from __future__ import annotations

import pytest

from aegis.l3_intelligence.ai_kernel.accounting import CostAccountant
from aegis.l3_intelligence.ai_kernel.kernel import AIKernel
from aegis.l3_intelligence.ai_kernel.providers.base import ProviderRegistry
from aegis.l3_intelligence.ai_kernel.providers.fake import FakeProvider, FakeResponse
from aegis.l3_intelligence.ai_kernel.registry import (
    ModelCapability, ModelMetadata, ModelRegistry,
)
from aegis.l3_intelligence.ai_kernel.types import DeploymentKind, PrivacyTier, TaskType
from aegis.l1_core.interfaces.llm import ModelHealth
from aegis.reasoning.kernel_provider import KernelReasoningProvider
from aegis.reasoning.provider import ReasoningUnavailableError
from aegis.l6_planning.orchestration.planner_service import PlannerService
from aegis.l6_planning.state.planner_context import PlannerContext
from aegis.l6_planning.types import PlanningStrategy, PlanState
from aegis.l6_planning.reasoning.schemas import (
    IntentAnalysisOutput,
    AmbiguityReportOutput,
    ObjectiveSpec,
    ObjectiveGenerationOutput,
    StrategySelectionOutput,
    TaskSpec,
    TaskDecompositionOutput,
    VerificationCriterionSpec,
    VerificationCriteriaOutput,
    RecoveryScenarioSpec,
    RecoveryPlanningOutput,
    ReflectionInsightOutput,
)


# ---------------------------------------------------------------------------
# Kernel / provider helpers
# ---------------------------------------------------------------------------

def _local_meta(model_id: str = "fake-local") -> ModelMetadata:
    return ModelMetadata(
        model_id=model_id,
        provider_id="fake",
        family="fake",
        display_name=model_id,
        deployment=DeploymentKind.LOCAL,
        context_window=8192,
        output_limit=4096,
        capabilities={ModelCapability.REASONING.value},
        cost_per_input_1k=0.0,
        cost_per_output_1k=0.0,
        latency_first_ms_p50=10,
        supported_privacy_tiers={PrivacyTier.P0, PrivacyTier.P1, PrivacyTier.P2, PrivacyTier.P3},
        reliability_score=0.95,
        structural_compliance_score=0.95,
        health=ModelHealth.HEALTHY,
        quality_scores={TaskType.REASON: 0.9},
    )


def _build_kernel_with_fake() -> tuple[AIKernel, FakeProvider]:
    fake = FakeProvider(
        provider_id="fake",
        model_ids=["fake-local"],
        default_response=FakeResponse(content="{}"),
    )
    reg = ModelRegistry()
    reg.register(_local_meta())
    prov_reg = ProviderRegistry()
    prov_reg.register("fake", fake)
    kernel = AIKernel(registry=reg, provider_registry=prov_reg, accountant=CostAccountant())
    return kernel, fake


class _StubTemplate:
    def render(self, variables: dict) -> str:
        return "test prompt"


class _StubLibrary:
    def get(self, template_id: str) -> _StubTemplate:
        return _StubTemplate()


def _make_provider(kernel: AIKernel) -> KernelReasoningProvider:
    return KernelReasoningProvider(
        kernel=kernel,
        prompt_library=_StubLibrary(),  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Schema object factories (use actual field names from source)
# ---------------------------------------------------------------------------

def _intent_obj(
    domain: str = "coding",
    confidence: float = 0.92,
    requires_internet: bool = False,
    requires_local_only: bool = True,
) -> IntentAnalysisOutput:
    return IntentAnalysisOutput(
        domain=domain,
        primary_verb="build",
        requires_internet=requires_internet,
        requires_local_only=requires_local_only,
        confidence=confidence,
        ambiguities=[],
        detected_tools=[],
        action_hints=[],
    )


def _ambiguity_obj() -> AmbiguityReportOutput:
    return AmbiguityReportOutput(
        is_ambiguous=False,
        blocking=False,
        questions=[],
        confidence=0.88,
    )


def _objective_obj(title: str = "Build REST API") -> ObjectiveGenerationOutput:
    return ObjectiveGenerationOutput(
        objectives=[ObjectiveSpec(
            title=title,
            description="Create a FastAPI service",
            priority=1,
            effort="medium",
            depends_on_titles=[],
            completion_criteria=["API returns 200"],
        )],
        rationale="AI-generated",
    )


def _strategy_obj(strategy: str = "SPEED_FIRST") -> StrategySelectionOutput:
    return StrategySelectionOutput(
        strategy=strategy,
        rationale="Optimise for delivery speed",
        confidence=0.80,
    )


def _decomp_obj() -> TaskDecompositionOutput:
    return TaskDecompositionOutput(
        tasks=[TaskSpec(
            title="Set up FastAPI",
            action_hint="filesystem.write",
        )],
        dependency_order=["Set up FastAPI"],
        notes="",
    )


def _verif_obj() -> VerificationCriteriaOutput:
    return VerificationCriteriaOutput(
        criteria=[VerificationCriterionSpec(
            task_title="Set up FastAPI",
            check_description="GET / returns 200",
        )],
        overall_strategy="",
    )


def _recovery_obj() -> RecoveryPlanningOutput:
    return RecoveryPlanningOutput(
        scenarios=[RecoveryScenarioSpec(
            failure_mode="network_error",
            recovery_strategy="Retry once then report failure",
        )],
    )


def _reflection_obj(passed: bool = True) -> ReflectionInsightOutput:
    return ReflectionInsightOutput(
        passed=passed,
        issues=[],
        suggestions=[],
    )


def _full_sequence(
    domain: str = "coding",
    confidence: float = 0.92,
    requires_internet: bool = False,
    requires_local_only: bool = True,
) -> list:
    """Return the 8-item sequence matching planner_service._ai_create_plan order."""
    return [
        _intent_obj(domain=domain, confidence=confidence,
                    requires_internet=requires_internet,
                    requires_local_only=requires_local_only),
        _ambiguity_obj(),
        _objective_obj(),
        _strategy_obj(),
        _decomp_obj(),
        _verif_obj(),
        _recovery_obj(),
        _reflection_obj(),
    ]


def _mock_provider_with_sequence(seq: list) -> KernelReasoningProvider:
    """Build provider whose reason() returns items from seq in order."""
    kernel, _ = _build_kernel_with_fake()
    provider = _make_provider(kernel)
    items = list(seq)

    async def _side_effect(prompt_id, variables, output_schema):
        if items:
            return items.pop(0)
        raise ReasoningUnavailableError("Mock sequence exhausted")

    provider.reason = _side_effect  # type: ignore[method-assign]
    return provider


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFullAIChain:

    @pytest.mark.asyncio
    async def test_ai_path_all_8_prompts_executed(self):
        """AI path calls reason() exactly 8 times (one per pipeline stage)."""
        call_log: list[str] = []
        full_seq = _full_sequence()

        async def _counting_reason(prompt_id, variables, output_schema):
            call_log.append(prompt_id)
            return full_seq[len(call_log) - 1]

        kernel, _ = _build_kernel_with_fake()
        provider = _make_provider(kernel)
        provider.reason = _counting_reason  # type: ignore[method-assign]

        planner = PlannerService(reasoning_provider=provider)
        result = await planner.create_plan(
            goal="Build a local REST API",
            context=PlannerContext(strategy=PlanningStrategy.BALANCED),
        )

        assert result.state == PlanState.READY
        assert result.mission is not None
        assert len(result.tasks) > 0
        assert len(call_log) == 8

    @pytest.mark.asyncio
    async def test_ai_intent_aligns_mission_parsed_intent(self):
        """G2: AI domain/confidence/requires_local_only are authoritative in mission.parsed_intent."""
        provider = _mock_provider_with_sequence(_full_sequence(
            domain="coding",
            confidence=0.92,
            requires_internet=False,
            requires_local_only=True,
        ))
        planner = PlannerService(reasoning_provider=provider)

        result = await planner.create_plan(goal="Build a local API", context=PlannerContext())

        assert result.state == PlanState.READY
        pi = result.mission.parsed_intent
        assert pi.domain.value == "coding"
        assert abs(pi.confidence - 0.92) < 0.01
        assert pi.requires_local_only is True
        assert pi.requires_internet is False

    @pytest.mark.asyncio
    async def test_ai_unavailable_uses_deterministic_fallback(self):
        """Empty model registry -> is_available=False -> deterministic fallback plan."""
        reg = ModelRegistry()
        prov_reg = ProviderRegistry()
        kernel = AIKernel(registry=reg, provider_registry=prov_reg)
        reasoning = _make_provider(kernel)
        assert not reasoning.is_available

        planner = PlannerService(reasoning_provider=reasoning)
        result = await planner.create_plan(goal="Research quantum computing", context=PlannerContext())

        assert result.state == PlanState.READY
        assert result.mission is not None

    @pytest.mark.asyncio
    async def test_reason_raises_falls_back_gracefully(self):
        """reason() raising ReasoningUnavailableError -> deterministic fallback plan."""
        kernel, _ = _build_kernel_with_fake()
        provider = _make_provider(kernel)

        async def _always_fail(prompt_id, variables, output_schema):
            raise ReasoningUnavailableError("Simulated kernel failure")

        provider.reason = _always_fail  # type: ignore[method-assign]

        planner = PlannerService(reasoning_provider=provider)
        result = await planner.create_plan(goal="Organise my notes", context=PlannerContext())

        assert result.state == PlanState.READY
        assert result.mission is not None

    @pytest.mark.asyncio
    async def test_no_reasoning_provider_deterministic_path(self):
        """No reasoning provider -> pure deterministic path -> valid plan."""
        planner = PlannerService()
        result = await planner.create_plan(goal="Schedule a meeting", context=PlannerContext())
        assert result.state == PlanState.READY

    @pytest.mark.asyncio
    async def test_ai_path_objectives_in_mission(self):
        """AI-generated objectives (title='Build REST API') appear in mission.objectives."""
        provider = _mock_provider_with_sequence(_full_sequence())
        planner = PlannerService(reasoning_provider=provider)

        result = await planner.create_plan(goal="Create a web scraper tool", context=PlannerContext())

        assert result.mission is not None
        assert len(result.mission.objectives) >= 1
        assert result.mission.objectives[0].title == "Build REST API"

    @pytest.mark.asyncio
    async def test_ai_path_strategy_in_result(self):
        """AI-selected strategy appears in result.strategy (non-None)."""
        provider = _mock_provider_with_sequence(_full_sequence())
        planner = PlannerService(reasoning_provider=provider)

        result = await planner.create_plan(goal="Build fast API endpoint", context=PlannerContext())

        assert result.strategy is not None

    @pytest.mark.asyncio
    async def test_different_ai_domains_produce_different_intents(self):
        """Research domain from AI appears in mission.parsed_intent.domain."""
        provider = _mock_provider_with_sequence(_full_sequence(domain="research"))
        planner = PlannerService(reasoning_provider=provider)

        result = await planner.create_plan(
            goal="Find and summarise papers on transformers",
            context=PlannerContext(),
        )

        assert result.state == PlanState.READY
        assert result.mission.parsed_intent.domain.value == "research"
