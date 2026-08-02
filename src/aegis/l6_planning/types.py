"""L6 Planning Engine — Core types and data models.

All fundamental enumerations and value types used across the planning engine.
No business logic. Pure typed data.

Import safety: stdlib + pydantic + aegis.l5_execution.types (read-only reference) only.
"""

from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

__all__ = [
    # Enumerations
    "PlanState",
    "PlanningStrategy",
    "IntentDomain",
    "ConstraintKind",
    "EffortLevel",
    "RiskLevel",
    # Data models
    "EffortEstimate",
    "Constraint",
    "ResourceSpec",
    "ValidationIssue",
    "ClarificationQuestion",
    "ExecutionStep",
    "Milestone",
    "DecisionTraceEntry",
    "PlanEstimate",
    "PlanComparison",
    "ScoringWeights",
    "PlanScore",
]


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class PlanState(str, Enum):
    """Lifecycle state of a plan."""

    DRAFTING = "drafting"
    REVIEWING = "reviewing"
    READY = "ready"
    EXECUTING = "executing"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class PlanningStrategy(str, Enum):
    """High-level strategy that guides task ordering and trade-off decisions."""

    FASTEST = "fastest"
    CHEAPEST = "cheapest"
    HIGHEST_QUALITY = "highest_quality"
    BALANCED = "balanced"
    OFFLINE_FIRST = "offline_first"
    PRIVACY_FIRST = "privacy_first"
    ENERGY_SAVING = "energy_saving"
    DEVELOPER_MODE = "developer_mode"
    RESEARCH_MODE = "research_mode"

    @property
    def description(self) -> str:
        return {
            "fastest": "Optimise for minimum wall-clock time; maximise parallelism.",
            "cheapest": "Minimise token/compute cost; prefer offline tools.",
            "highest_quality": "Maximise output quality; add verification at each step.",
            "balanced": "Balance time, cost, and quality equally.",
            "offline_first": "Prefer local tools and models; avoid network where possible.",
            "privacy_first": "Never send sensitive data off-device; local-only routing.",
            "energy_saving": "Minimise CPU/GPU usage; batch where possible.",
            "developer_mode": "Expose debug info; add extra verification; verbose tracing.",
            "research_mode": "Multi-source gathering; cross-verification; citation tracking.",
        }[self.value]


class IntentDomain(str, Enum):
    """Primary domain category inferred from a goal."""

    CODING = "coding"
    RESEARCH = "research"
    BROWSER = "browser"
    FILESYSTEM = "filesystem"
    TERMINAL = "terminal"
    FINANCE = "finance"
    AUTOMATION = "automation"
    VISION = "vision"
    VOICE = "voice"
    PLANNING = "planning"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class ConstraintKind(str, Enum):
    """Category of a planning constraint."""

    BUDGET = "budget"
    PRIVACY = "privacy"
    OFFLINE = "offline"
    DEADLINE = "deadline"
    OS = "os"
    RESOURCE = "resource"
    SECURITY = "security"
    CUSTOM = "custom"


class EffortLevel(str, Enum):
    """Rough effort band for a task or plan."""

    TRIVIAL = "trivial"        # < 1 minute
    SMALL = "small"            # 1–15 minutes
    MEDIUM = "medium"          # 15m–2 hours
    LARGE = "large"            # 2–8 hours
    EPIC = "epic"              # > 8 hours / multi-day


class RiskLevel(str, Enum):
    """4-tier risk classification (mirrors L5 RiskLevel for reference in plans)."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def ordinal(self) -> int:
        return {"low": 0, "medium": 1, "high": 2, "critical": 3}[self.value]

    def __ge__(self, other: "RiskLevel") -> bool:  # type: ignore[override]
        return self.ordinal >= other.ordinal

    def __gt__(self, other: "RiskLevel") -> bool:  # type: ignore[override]
        return self.ordinal > other.ordinal

    def __le__(self, other: "RiskLevel") -> bool:  # type: ignore[override]
        return self.ordinal <= other.ordinal

    def __lt__(self, other: "RiskLevel") -> bool:  # type: ignore[override]
        return self.ordinal < other.ordinal


# ---------------------------------------------------------------------------
# Primitive value types
# ---------------------------------------------------------------------------


class EffortEstimate(BaseModel):
    """Human-readable effort estimate for a task or plan."""

    level: EffortLevel
    min_seconds: float = 0.0
    max_seconds: float = 0.0
    best_guess_seconds: float = 0.0
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    @classmethod
    def trivial(cls) -> "EffortEstimate":
        return cls(level=EffortLevel.TRIVIAL, min_seconds=10, max_seconds=60, best_guess_seconds=30)

    @classmethod
    def small(cls) -> "EffortEstimate":
        return cls(level=EffortLevel.SMALL, min_seconds=60, max_seconds=900, best_guess_seconds=300)

    @classmethod
    def medium(cls) -> "EffortEstimate":
        return cls(level=EffortLevel.MEDIUM, min_seconds=900, max_seconds=7200, best_guess_seconds=3600)

    @classmethod
    def large(cls) -> "EffortEstimate":
        return cls(level=EffortLevel.LARGE, min_seconds=7200, max_seconds=28800, best_guess_seconds=14400)

    @classmethod
    def epic(cls) -> "EffortEstimate":
        return cls(level=EffortLevel.EPIC, min_seconds=28800, max_seconds=172800, best_guess_seconds=86400)


class Constraint(BaseModel):
    """A hard or soft constraint on a plan."""

    constraint_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    kind: ConstraintKind
    description: str
    hard: bool = True           # hard = must satisfy; soft = try to satisfy
    value: Any = None           # budget cap, deadline timestamp, etc.
    unit: str | None = None     # "USD", "seconds", "MB", etc.

    def __str__(self) -> str:
        hardness = "HARD" if self.hard else "SOFT"
        return f"[{hardness}/{self.kind.value}] {self.description}"


class ResourceSpec(BaseModel):
    """A resource requirement for a plan or task."""

    name: str
    kind: Literal["tool", "model", "permission", "hardware", "network", "credential"]
    required: bool = True
    description: str = ""
    version_constraint: str | None = None   # e.g., ">=3.10"


class ValidationIssue(BaseModel):
    """A validation warning or error on a plan/mission/task."""

    severity: Literal["error", "warning", "info"]
    code: str
    message: str
    field: str | None = None

    def is_blocking(self) -> bool:
        return self.severity == "error"


class ClarificationQuestion(BaseModel):
    """A clarification question generated when intent is ambiguous."""

    question_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    question: str
    context: str = ""
    options: list[str] = Field(default_factory=list)
    required: bool = True


class ExecutionStep(BaseModel):
    """One step in the final ordered execution plan."""

    step_index: int
    task_id: str
    task_title: str
    parallel_group: int | None = None   # steps with same group can run in parallel
    is_approval_point: bool = False
    risk_level: RiskLevel = RiskLevel.LOW
    estimated_duration_seconds: float = 0.0
    depends_on_steps: list[int] = Field(default_factory=list)
    action_kind_hint: str | None = None  # e.g., "fs.write", "git.commit"

    def __repr__(self) -> str:
        return f"ExecutionStep(#{self.step_index} {self.task_title!r} risk={self.risk_level.value})"


class Milestone(BaseModel):
    """A logical milestone grouping related tasks with completion criteria."""

    milestone_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str
    description: str = ""
    task_ids: list[str] = Field(default_factory=list)
    completion_criteria: list[str] = Field(default_factory=list)
    is_checkpoint: bool = False     # whether this milestone requires explicit verification


class DecisionTraceEntry(BaseModel):
    """One entry in the decision trace — why the planner made a specific choice."""

    step: str
    decision: str
    rationale: str
    alternatives_considered: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    timestamp: float = Field(default_factory=time.time)


class PlanEstimate(BaseModel):
    """High-level estimates for a plan."""

    effort: EffortEstimate
    total_tasks: int = 0
    total_approval_points: int = 0
    parallel_tasks: int = 0
    sequential_tasks: int = 0
    estimated_total_seconds: float = 0.0
    estimated_tokens: int | None = None
    estimated_cost_usd: float | None = None
    confidence: float = Field(default=0.6, ge=0.0, le=1.0)


class PlanComparison(BaseModel):
    """Comparison result between two or more plans."""

    plan_ids: list[str]
    winner_plan_id: str
    scores: dict[str, float]    # plan_id -> composite score
    summary: str
    tradeoffs: dict[str, str]   # plan_id -> tradeoff description


class ScoringWeights(BaseModel):
    """Weights for the multi-objective plan scoring function."""

    quality: float = Field(default=0.25, ge=0.0, le=1.0)
    speed: float = Field(default=0.20, ge=0.0, le=1.0)
    cost: float = Field(default=0.15, ge=0.0, le=1.0)
    risk: float = Field(default=0.20, ge=0.0, le=1.0)
    privacy: float = Field(default=0.10, ge=0.0, le=1.0)
    success_probability: float = Field(default=0.10, ge=0.0, le=1.0)

    @classmethod
    def for_strategy(cls, strategy: PlanningStrategy) -> "ScoringWeights":
        """Return weights tuned for a given strategy."""
        presets: dict[PlanningStrategy, dict[str, float]] = {
            PlanningStrategy.FASTEST: dict(quality=0.10, speed=0.50, cost=0.10, risk=0.15, privacy=0.05, success_probability=0.10),
            PlanningStrategy.CHEAPEST: dict(quality=0.15, speed=0.10, cost=0.50, risk=0.10, privacy=0.05, success_probability=0.10),
            PlanningStrategy.HIGHEST_QUALITY: dict(quality=0.50, speed=0.05, cost=0.05, risk=0.20, privacy=0.10, success_probability=0.10),
            PlanningStrategy.BALANCED: dict(quality=0.25, speed=0.20, cost=0.15, risk=0.20, privacy=0.10, success_probability=0.10),
            PlanningStrategy.OFFLINE_FIRST: dict(quality=0.20, speed=0.15, cost=0.20, risk=0.10, privacy=0.25, success_probability=0.10),
            PlanningStrategy.PRIVACY_FIRST: dict(quality=0.15, speed=0.10, cost=0.05, risk=0.15, privacy=0.45, success_probability=0.10),
            PlanningStrategy.ENERGY_SAVING: dict(quality=0.15, speed=0.15, cost=0.35, risk=0.10, privacy=0.15, success_probability=0.10),
            PlanningStrategy.DEVELOPER_MODE: dict(quality=0.35, speed=0.10, cost=0.05, risk=0.25, privacy=0.10, success_probability=0.15),
            PlanningStrategy.RESEARCH_MODE: dict(quality=0.40, speed=0.05, cost=0.10, risk=0.10, privacy=0.15, success_probability=0.20),
        }
        weights = presets.get(strategy, presets[PlanningStrategy.BALANCED])
        return cls(**weights)


class PlanScore(BaseModel):
    """Multi-dimensional score for a single plan."""

    plan_id: str
    quality: float = Field(ge=0.0, le=1.0)
    speed: float = Field(ge=0.0, le=1.0)
    cost: float = Field(ge=0.0, le=1.0)
    risk: float = Field(ge=0.0, le=1.0)       # higher = less risky
    privacy: float = Field(ge=0.0, le=1.0)
    success_probability: float = Field(ge=0.0, le=1.0)
    composite_score: float = Field(ge=0.0, le=1.0)
    weights_used: ScoringWeights = Field(default_factory=ScoringWeights)

    def __repr__(self) -> str:
        return f"PlanScore(plan={self.plan_id!r:.8} composite={self.composite_score:.3f})"
