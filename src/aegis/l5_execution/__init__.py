"""L5 Execution Engine — Project AEGIS.

The Execution Engine is the secure, audited action layer for AEGIS.  It converts
approved typed Action objects into real-world effects through a mandatory 7-stage
pipeline:

  Stage 1  Permission Engine  — SVRC: Subject / Verb / Resource / Context check
  Stage 2  Risk Analyzer      — Score: LOW / MEDIUM / HIGH / CRITICAL
  Stage 3  Policy Engine      — allow / deny / confirm / sandbox-tier decision
  Stage 4  Executor Registry  — route to the correct executor plugin
  Stage 5  Sandbox Manager    — wrap in T1/T2/T3/T4 sandbox per policy
  Stage 6  Executor           — filesystem / git / python / browser / etc.
  Stage 7  Audit + Verify     — append-only hash chain + post-exec assertion

No stage may be skipped.  Every stage produces a typed record in the audit log.

Import safety: l5_execution imports l1_core, l2_foundation, l3_intelligence,
l4_memory — and NOTHING above L5.  No L6/L7 imports permitted.

Designed for Prompt 05 of the AEGIS roadmap (docs/09_ROADMAP.md §PROMPT 05).
"""

from __future__ import annotations

from aegis.l5_execution.contracts import (
    ActionRequest,
    ActionResponse,
    ApprovalRequest,
    ExecutorManifest,
    PolicyRule,
    RollbackRecord,
    SVRCDecision,
    SVRCRequest,
)
from aegis.l5_execution.exceptions import (
    ApprovalRequiredError,
    AuditIntegrityError,
    ExecutionEngineError,
    ExecutorNotFoundError,
    PermissionDeniedError,
    PolicyViolationError,
    RollbackError,
    SandboxEscapeError,
    VerificationFailedError,
)
from aegis.l5_execution.pipeline import ExecutionPipeline
from aegis.l5_execution.types import (
    Action,
    ActionKind,
    ActionResult,
    ExecutionStatus,
    PermissionDecision,
    RiskLevel,
    SandboxTier,
    VerificationResult,
)

__all__ = [
    # Pipeline
    "ExecutionPipeline",
    # Core types
    "Action",
    "ActionKind",
    "ActionResult",
    "ExecutionStatus",
    "PermissionDecision",
    "RiskLevel",
    "SandboxTier",
    "VerificationResult",
    # Contracts
    "ActionRequest",
    "ActionResponse",
    "ApprovalRequest",
    "SVRCRequest",
    "SVRCDecision",
    "PolicyRule",
    "ExecutorManifest",
    "RollbackRecord",
    # Exceptions
    "ExecutionEngineError",
    "PermissionDeniedError",
    "PolicyViolationError",
    "ApprovalRequiredError",
    "SandboxEscapeError",
    "ExecutorNotFoundError",
    "AuditIntegrityError",
    "VerificationFailedError",
    "RollbackError",
]

__version__ = "0.1.0"  # Prompt 05
