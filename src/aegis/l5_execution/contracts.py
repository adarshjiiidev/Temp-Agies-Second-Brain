"""L5 Execution Engine — Pydantic Contracts.

Serialisable request / response models used across all pipeline stages.
Every cross-stage boundary uses these typed models — no raw dicts.

Import safety: pydantic + stdlib + l5_execution.types ONLY.
"""

from __future__ import annotations

import time
import uuid
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from aegis.l5_execution.types import (
    ActionKind,
    AuditStage,
    ExecutionStatus,
    PermissionDecision,
    RiskLevel,
    SandboxTier,
    VerificationResult,
)

__all__ = [
    "SVRCRequest",
    "SVRCDecision",
    "RiskAssessment",
    "PolicyDecision",
    "PolicyRule",
    "ExecutorManifest",
    "SandboxContext",
    "ActionRequest",
    "ActionResponse",
    "ApprovalRequest",
    "RollbackRecord",
    "AuditEntryModel",
]


# ---------------------------------------------------------------------------
# SVRC models (Stage 1 — Permission Engine)
# ---------------------------------------------------------------------------


class SVRCRequest(BaseModel):
    """Subject / Verb / Resource / Context permission check request."""

    model_config = {"frozen": True}

    subject: str = Field(description="Who (e.g. 'system:planner', 'plugin:obsidian')")
    verb: str = Field(description="SVRC verb (e.g. 'fs.write', 'git.push')")
    resource: str = Field(description="What is targeted (e.g. 'fs:~/Projects/**')")
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Why / under what policy (reason, plan_id, approval, etc.)",
    )
    action_id: UUID = Field(default_factory=uuid.uuid4)
    request_time: float = Field(default_factory=time.time)


class SVRCDecision(BaseModel):
    """Result of a SVRC permission check."""

    model_config = {"frozen": True}

    decision: PermissionDecision
    allowed: bool
    reason: str
    grant_id: str | None = None
    required_sandbox_tier: SandboxTier | None = None
    approval_request_id: str | None = None
    ttl_seconds: float | None = None  # remaining TTL of the matching grant
    checked_at: float = Field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Risk models (Stage 2 — Risk Analyzer)
# ---------------------------------------------------------------------------


class RiskAssessment(BaseModel):
    """Risk score assigned to an action by the Risk Analyzer."""

    model_config = {"frozen": True}

    action_id: UUID
    risk_level: RiskLevel
    score: float = Field(ge=0.0, le=1.0, description="Normalised risk score 0–1")
    factors: list[str] = Field(default_factory=list, description="Risk factors applied")
    reversible: bool = True
    blast_radius: str = "local"  # "local" | "project" | "system" | "network"
    assessed_at: float = Field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Policy models (Stage 3 — Policy Engine)
# ---------------------------------------------------------------------------


class PolicyRule(BaseModel):
    """A single declarative policy rule evaluated by the Policy Engine.

    Rules are evaluated in priority order (lower = higher priority).
    The first matching rule wins.
    """

    model_config = {"frozen": True}

    rule_id: str
    name: str
    priority: int = Field(default=100, ge=0, le=9999)
    enabled: bool = True

    # Match conditions (all non-None conditions must match)
    match_verbs: list[str] | None = None       # e.g. ["fs.delete", "fs.write"]
    match_actors: list[str] | None = None      # e.g. ["plugin:*", "system:planner"]
    match_risk_levels: list[RiskLevel] | None = None
    match_resources: list[str] | None = None   # glob patterns

    # Decision
    decision: PermissionDecision               # ALLOW | DENY | NEEDS_APPROVAL | SANDBOX_REQUIRED
    required_sandbox_tier: SandboxTier | None = None
    reason: str = "Policy rule match"

    # Approval override: even with ALLOW, force approval for these conditions
    force_approval_on_critical: bool = True


class PolicyDecision(BaseModel):
    """Result of policy evaluation for an action."""

    model_config = {"frozen": True}

    action_id: UUID
    decision: PermissionDecision
    allowed: bool
    reason: str
    rule_id: str | None = None
    required_sandbox_tier: SandboxTier | None = None
    requires_approval: bool = False
    decided_at: float = Field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Executor models (Stage 4/5/6)
# ---------------------------------------------------------------------------


class ExecutorManifest(BaseModel):
    """Metadata that every executor must declare.

    The Executor Registry uses this to route actions and enforce sandbox
    requirements.
    """

    name: str
    version: str = "0.1.0"
    description: str = ""

    # Which ActionKinds this executor handles
    handles: list[ActionKind]

    # Minimum sandbox tier this executor operates in
    min_sandbox_tier: SandboxTier = SandboxTier.T0_NONE

    # Whether this executor supports best-effort rollback
    supports_rollback: bool = False

    # Whether this executor can run in dry_run mode (no side effects)
    supports_dry_run: bool = True

    # Default timeout for a single execution (seconds; None = no limit)
    default_timeout_seconds: float | None = 30.0

    # Maximum memory allowed (bytes; None = OS default)
    max_memory_bytes: int | None = None

    # Extra capabilities required (declared for audit)
    required_capabilities: list[str] = Field(default_factory=list)

    # Whether this is a stub (interface only; not yet fully implemented)
    is_stub: bool = False


class SandboxContext(BaseModel):
    """Runtime sandbox configuration passed to each executor."""

    model_config = {"frozen": True}

    tier: SandboxTier
    workspace_path: str | None = None  # scratch directory for T2+
    timeout_seconds: float | None = 30.0
    max_memory_bytes: int | None = None
    env_allowlist: list[str] = Field(default_factory=list)
    network_allowed: bool = False
    dry_run: bool = False


# ---------------------------------------------------------------------------
# Pipeline-level models
# ---------------------------------------------------------------------------


class ActionRequest(BaseModel):
    """Serialisable form of an Action for API/queue transport.

    Mirrors :class:`aegis.l5_execution.types.Action` but is Pydantic-serialisable
    for storage in the Execution Queue or audit log.
    """

    actor: str
    kind: ActionKind
    resource: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    action_id: UUID = Field(default_factory=uuid.uuid4)
    created_at: float = Field(default_factory=time.time)
    parent_action_id: UUID | None = None
    user_confirmed: bool = False
    dry_run: bool = False

    @field_validator("actor")
    @classmethod
    def actor_must_be_namespaced(cls, v: str) -> str:
        if ":" not in v:
            raise ValueError(
                f"actor must be namespaced (e.g. 'system:planner'), got: {v!r}"
            )
        return v


class ActionResponse(BaseModel):
    """Serialisable form of an ActionResult for API/queue transport."""

    action_id: UUID
    status: ExecutionStatus
    output: Any = None
    error: str | None = None
    error_code: str | None = None
    risk_level: RiskLevel = RiskLevel.LOW
    sandbox_tier: SandboxTier = SandboxTier.T0_NONE
    permission_decision: PermissionDecision = PermissionDecision.DENY
    verification_result: VerificationResult = VerificationResult.SKIPPED
    audit_entry_ids: list[str] = Field(default_factory=list)
    approval_request_id: str | None = None
    rollback_info: dict[str, Any] | None = None
    started_at: float = Field(default_factory=time.time)
    completed_at: float | None = None
    duration_ms: float | None = None
    executor_name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalRequest(BaseModel):
    """Emitted on the EventBus when a CRITICAL-risk action requires user approval.

    Consumed by the UI layer (P22) to surface a human-readable approval dialog.
    The action is blocked until an ApprovalGranted or ApprovalDenied event
    matching this request_id is received.
    """

    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action_id: UUID
    actor: str
    verb: str
    resource: str
    risk_level: RiskLevel
    reason: str
    context: dict[str, Any] = Field(default_factory=dict)
    requested_at: float = Field(default_factory=time.time)
    expires_at: float | None = None  # None = no expiry


class RollbackRecord(BaseModel):
    """Records what was done during a rollback attempt."""

    action_id: UUID
    executor_name: str
    supported: bool
    succeeded: bool | None = None  # None = not attempted
    steps: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None
    rolled_back_at: float = Field(default_factory=time.time)


class AuditEntryModel(BaseModel):
    """Pydantic model for an audit chain entry (used for serialisation).

    The append-only chain is enforced by AuditChain; this model is used
    for serialisation/deserialisation only.
    """

    entry_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = Field(default_factory=time.time)
    stage: AuditStage
    action_id: str
    actor: str
    verb: str
    resource: str
    decision: str                # ALLOW | DENY | SANDBOX | APPROVE_REQUIRED | etc.
    result: str                  # SUCCESS | FAILURE | ESCAPE_ATTEMPT | etc.
    details: dict[str, Any] = Field(default_factory=dict)
    prev_hash: str               # SHA-256 hex of previous entry
    entry_hash: str              # SHA-256 hex of this entry (computed on insert)
    sequence: int = 0            # monotonically increasing integer
