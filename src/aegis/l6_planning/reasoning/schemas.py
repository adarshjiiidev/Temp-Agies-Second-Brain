"""L6 Planning Engine — AI Reasoning Output Schemas.

Defines the structured Pydantic models that AI reasoning calls must return.
These are the contracts between the LLM and the deterministic planning pipeline.

Every schema is:
  - Strict (required fields have no defaults that could hide LLM failures)
  - Validated (Pydantic enforces types at parse time)
  - Documented (field descriptions are used in prompt schema injection)

Import safety: stdlib + pydantic + l6_planning.types only.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

__all__ = [
    "IntentAnalysisOutput",
    "AmbiguityReportOutput",
    "RequirementExtractionOutput",
    "ObjectiveSpec",
    "ObjectiveGenerationOutput",
    "TaskSpec",
    "TaskDecompositionOutput",
    "StrategySelectionOutput",
    "MilestoneSpec",
    "MilestoneGenerationOutput",
    "TradeoffNarrationOutput",
    "RecoveryScenarioSpec",
    "RecoveryPlanningOutput",
    "ReflectionInsightOutput",
    "VerificationCriterionSpec",
    "VerificationCriteriaOutput",
    "RiskAssessmentOutput",
]


# ---------------------------------------------------------------------------
# Intent Analysis
# ---------------------------------------------------------------------------

class IntentAnalysisOutput(BaseModel):
    """Structured output from the intent_analysis_v1 prompt."""
    domain: str = Field(description="Primary domain: coding|research|filesystem|browser|terminal|finance|automation|planning|communication|creative|data|mixed|unknown")
    primary_verb: str = Field(description="Main action verb, lowercase lemmatised")
    target_resource: str | None = Field(default=None, description="What the action operates on")
    requires_internet: bool = Field(description="True if goal clearly requires internet")
    requires_local_only: bool = Field(description="True if goal explicitly restricts to offline")
    confidence: float = Field(description="0.0–1.0 confidence in this classification")
    ambiguities: list[str] = Field(default_factory=list, description="Specific unclear aspects")
    detected_tools: list[str] = Field(default_factory=list, description="Tool names detected")
    action_hints: list[str] = Field(default_factory=list, description="L5 action kind prefixes")


# ---------------------------------------------------------------------------
# Ambiguity Detection
# ---------------------------------------------------------------------------

class AmbiguityReportOutput(BaseModel):
    """Structured output from the ambiguity_detection_v1 prompt."""
    is_ambiguous: bool
    blocking: bool = Field(description="True if planning cannot proceed without clarification")
    questions: list[str] = Field(default_factory=list, description="Targeted clarification questions")
    confidence: float = Field(description="Confidence in ambiguity assessment, 0.0–1.0")
    conflict_detected: bool = Field(default=False, description="True if goal has contradictory requirements")


# ---------------------------------------------------------------------------
# Requirement Extraction
# ---------------------------------------------------------------------------

class RequirementExtractionOutput(BaseModel):
    """Structured output from the requirement_extraction_v1 prompt."""
    permissions_needed: list[str] = Field(default_factory=list)
    internet_required: bool = False
    offline_capable: bool = True
    max_risk_level: str = Field(default="medium", description="low|medium|high|critical")
    human_approval_points: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Objective Generation
# ---------------------------------------------------------------------------

class ObjectiveSpec(BaseModel):
    """Specification for a single objective from AI."""
    title: str
    description: str
    priority: int = Field(ge=1, le=10)
    effort: str = Field(description="trivial|low|medium|high|very_high")
    depends_on_titles: list[str] = Field(default_factory=list)
    completion_criteria: list[str] = Field(default_factory=list)


class ObjectiveGenerationOutput(BaseModel):
    """Structured output from the objective_generation_v1 prompt."""
    objectives: list[ObjectiveSpec]
    rationale: str = Field(default="", description="Brief explanation of the objective set")


# ---------------------------------------------------------------------------
# Task Decomposition
# ---------------------------------------------------------------------------

class TaskSpec(BaseModel):
    """Specification for a single task from AI decomposition."""
    title: str
    action_hint: str = Field(description="L5 action kind prefix: fs.read, shell.exec, etc.")
    estimated_seconds: int = Field(default=300, ge=1)
    risk_level: str = Field(default="low", description="low|medium|high|critical")
    requires_approval: bool = False
    can_run_parallel: bool = False
    rationale: str = Field(default="")


class TaskDecompositionOutput(BaseModel):
    """Structured output from the task_decomposition_v1 prompt."""
    tasks: list[TaskSpec]
    dependency_order: list[str] = Field(
        default_factory=list,
        description="Task titles in execution order (first = first to run)"
    )
    notes: str = Field(default="")


# ---------------------------------------------------------------------------
# Strategy Selection
# ---------------------------------------------------------------------------

class StrategySelectionOutput(BaseModel):
    """Structured output from the strategy_selection_v1 prompt."""
    strategy: str = Field(description="balanced|developer_mode|research_mode|privacy_first|offline_first|speed_first|safe_mode")
    rationale: str
    confidence: float = Field(ge=0.0, le=1.0)
    alternative: str | None = Field(default=None, description="Second-best strategy if applicable")


# ---------------------------------------------------------------------------
# Milestone Generation
# ---------------------------------------------------------------------------

class MilestoneSpec(BaseModel):
    """Specification for a single milestone from AI."""
    title: str
    description: str
    task_titles: list[str] = Field(description="Titles of tasks grouped under this milestone")
    completion_criteria: list[str] = Field(default_factory=list)
    is_checkpoint: bool = False


class MilestoneGenerationOutput(BaseModel):
    """Structured output from the milestone_generation_v1 prompt."""
    milestones: list[MilestoneSpec]


# ---------------------------------------------------------------------------
# Tradeoff Narration
# ---------------------------------------------------------------------------

class TradeoffNarrationOutput(BaseModel):
    """Structured output from the tradeoff_narration_v1 prompt."""
    summary: str = Field(description="1–2 sentence plain-English summary of the tradeoffs")
    recommendation: str = Field(description="Which plan is recommended and why")
    key_differences: list[str] = Field(default_factory=list, description="Top 3 differentiating factors")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# Recovery Planning
# ---------------------------------------------------------------------------

class RecoveryScenarioSpec(BaseModel):
    """Specification for a single failure scenario from AI."""
    failure_mode: str = Field(description="What can go wrong")
    affected_task_hints: list[str] = Field(default_factory=list, description="Action hints of affected tasks")
    probability: str = Field(default="medium", description="low|medium|high")
    recovery_strategy: str = Field(description="How to recover")
    rollback_possible: bool = True
    estimated_recovery_seconds: int = Field(default=300, ge=0)


class RecoveryPlanningOutput(BaseModel):
    """Structured output from the recovery_planning_v1 prompt."""
    scenarios: list[RecoveryScenarioSpec]
    global_fallback: str = Field(default="Cancel plan and report failure to user")


# ---------------------------------------------------------------------------
# Reflection
# ---------------------------------------------------------------------------

class ReflectionInsightOutput(BaseModel):
    """Structured output from the reflection_v1 prompt."""
    issues: list[dict[str, str]] = Field(
        default_factory=list,
        description="Each: {category, severity, message} — severity: info|warning|error"
    )
    suggestions: list[str] = Field(default_factory=list, description="Optimization suggestions")
    confidence_adjustment: float = Field(
        default=0.0, ge=-0.5, le=0.1,
        description="Positive or negative delta to apply to plan confidence"
    )
    quality_assessment: str = Field(default="", description="1–2 sentence qualitative plan review")
    passed: bool = Field(description="True if plan quality is acceptable to proceed")


# ---------------------------------------------------------------------------
# Verification Criteria
# ---------------------------------------------------------------------------

class VerificationCriterionSpec(BaseModel):
    """Specification for a single verification check from AI."""
    task_title: str = Field(description="Task this check applies to")
    check_description: str = Field(description="What to verify")
    check_type: str = Field(default="output_exists", description="output_exists|assertion|manual_review|idempotency|performance|security")
    severity: str = Field(default="warning", description="info|warning|error|critical")
    automated: bool = Field(default=True, description="Can this be checked automatically?")


class VerificationCriteriaOutput(BaseModel):
    """Structured output from the verification_criteria_v1 prompt."""
    criteria: list[VerificationCriterionSpec]
    overall_strategy: str = Field(default="", description="Brief description of the verification approach")


# ---------------------------------------------------------------------------
# Risk Assessment (L5 shadow)
# ---------------------------------------------------------------------------

class RiskAssessmentOutput(BaseModel):
    """Structured output from the risk_assessment_v1 prompt.

    Used by L5 risk reasoning (Phase E). Included here for schema completeness.
    """
    risk_level: str = Field(description="low|medium|high|critical")
    factors: list[dict[str, Any]] = Field(default_factory=list, description="Risk factors with weights")
    rationale: str = Field(description="Plain-English risk explanation")
    mitigation_suggestions: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
