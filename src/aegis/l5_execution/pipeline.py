"""L5 Execution Engine — Execution Pipeline.

The central orchestrator for all 7 execution stages.

  Stage 1  Permission Engine  — SVRC check (deny-by-default)
  Stage 2  Risk Analyzer      — LOW / MEDIUM / HIGH / CRITICAL
  Stage 3  Policy Engine      — allow / deny / confirm / sandbox-tier
  Stage 4  Executor Registry  — route to executor plugin
  Stage 5  Sandbox Manager    — build SandboxContext for the executor
  Stage 6  Executor           — run the action (with dry-run support)
  Stage 7  Audit + Verify     — hash-chain audit + post-exec assertions

INVARIANTS (enforced here):
  - No stage may be skipped.
  - Every stage produces an audit entry before the next stage begins.
  - SandboxEscapeError → ESCAPE_ATTEMPT audit entry, then re-raise.
  - VerificationFailedError → trigger RollbackEngine, then re-raise.
  - CRITICAL risk without user_confirmed → ApprovalRequiredError.

Import safety: stdlib + l5_execution.* ONLY.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

from aegis.l5_execution.audit.chain import AuditChain
from aegis.l5_execution.contracts import PolicyDecision, SVRCRequest
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
from aegis.l5_execution.executors.base import BaseExecutor
from aegis.l5_execution.executors.browser import BrowserExecutor
from aegis.l5_execution.executors.desktop import DesktopExecutor
from aegis.l5_execution.executors.docker import DockerExecutor
from aegis.l5_execution.executors.filesystem import FilesystemExecutor
from aegis.l5_execution.executors.git import GitExecutor
from aegis.l5_execution.executors.http import HttpExecutor
from aegis.l5_execution.executors.obsidian import ObsidianExecutor
from aegis.l5_execution.executors.python_exec import PythonExecutor
from aegis.l5_execution.executors.shell import ShellExecutor
from aegis.l5_execution.executors.vscode import VSCodeExecutor
from aegis.l5_execution.permission.engine import PermissionEngine
from aegis.l5_execution.policy.engine import PolicyEngine
from aegis.l5_execution.registry.executor_registry import ExecutorRegistry
from aegis.l5_execution.risk.analyzer import RiskAnalyzer
from aegis.l5_execution.rollback.engine import RollbackEngine
from aegis.l5_execution.sandbox.manager import SandboxManager
from aegis.l5_execution.types import (
    Action,
    ActionResult,
    AuditStage,
    ExecutionStatus,
    PermissionDecision,
    RiskLevel,
    SandboxTier,
    VerificationResult,
)
from aegis.l5_execution.verify.assertions import PostExecVerifier

__all__ = ["ExecutionPipeline"]


class ExecutionPipeline:
    """The 7-stage secure execution pipeline.

    Usage::

        pipeline = ExecutionPipeline()
        await pipeline.initialize()

        # Grant a permission
        await pipeline.permission_engine.grant(
            subject="system:planner",
            verbs=["fs.read"],
            resources=["fs:~/Projects/**"],
            granted_by="user:primary",
        )

        # Execute an action
        action = Action(
            actor="system:planner",
            kind=ActionKind.FS_READ,
            resource="fs:~/Projects/AGIES/README.md",
            parameters={"path": "~/Projects/AGIES/README.md"},
        )
        result = await pipeline.execute(action)
        assert result.succeeded
    """

    def __init__(
        self,
        *,
        audit_db_path: str | Path | None = None,
        permission_db_path: str | Path | None = None,
        event_bus: Any = None,
        http_allowlist: set[str] | None = None,
        obsidian_vault: Path | str | None = None,
    ) -> None:
        # Stage 1 — Permission
        self.permission_engine = PermissionEngine(db_path=permission_db_path)

        # Stage 2 — Risk
        self._risk_analyzer = RiskAnalyzer()

        # Stage 3 — Policy
        self._policy_engine = PolicyEngine(event_bus=event_bus)

        # Stage 4 — Executor Registry
        self.registry = ExecutorRegistry()

        # Stage 5 — Sandbox
        self._sandbox_manager = SandboxManager()

        # Stage 7 — Audit
        self._audit = AuditChain(db_path=audit_db_path)

        # Stage 7 — Verify (default: no assertions; callers add their own)
        self._verifier = PostExecVerifier()

        # Rollback
        self._rollback_engine = RollbackEngine()

        # Store params for deferred setup
        self._http_allowlist = http_allowlist
        self._obsidian_vault = obsidian_vault
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize all subsystems."""
        await self.permission_engine.initialize()
        await self._audit.initialize()
        self._register_default_executors()
        self._initialized = True

    async def close(self) -> None:
        """Close all subsystems."""
        await self.permission_engine.close()
        await self._audit.close()

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def execute(self, action: Action) -> ActionResult:
        """Execute an action through all 7 stages.

        This is the ONLY authorised entry point for action execution.
        All stages are mandatory; none may be skipped.

        Returns:
            ActionResult — always returned (never raises for business errors;
            security exceptions (SandboxEscapeError) may propagate).

        Raises:
            PermissionDeniedError: if SVRC denies access.
            ApprovalRequiredError: if CRITICAL risk without confirmation.
            SandboxEscapeError:    if a sandbox escape attempt is detected.
        """
        if not self._initialized:
            raise RuntimeError(
                "ExecutionPipeline not initialized — call await pipeline.initialize() first."
            )

        started_at = time.time()
        audit_ids: list[str] = []

        # =============================================================
        # Stage 1 — Permission Check (SVRC)
        # =============================================================
        svrc_req = SVRCRequest(
            subject=action.actor,
            verb=action.svrc_verb(),
            resource=action.resource,
            context=action.context,
            action_id=action.action_id,
        )
        try:
            perm_decision = await self.permission_engine.check_or_raise(svrc_req)
            entry_id = await self._audit.append(
                stage=AuditStage.PERMISSION,
                action_id=str(action.action_id),
                actor=action.actor,
                verb=action.svrc_verb(),
                resource=action.resource,
                decision=perm_decision.decision.value,
                result="ALLOW",
                details={"grant_id": perm_decision.grant_id},
            )
            audit_ids.append(entry_id)
        except PermissionDeniedError as exc:
            entry_id = await self._audit.append(
                stage=AuditStage.PERMISSION,
                action_id=str(action.action_id),
                actor=action.actor,
                verb=action.svrc_verb(),
                resource=action.resource,
                decision="DENY",
                result="DENIED",
                details={"reason": str(exc)},
            )
            audit_ids.append(entry_id)
            return ActionResult(
                action_id=action.action_id,
                status=ExecutionStatus.DENIED,
                error=str(exc),
                error_code="E_EXE_PERM_DENIED",
                permission_decision=PermissionDecision.DENY,
                audit_entry_ids=audit_ids,
                started_at=started_at,
                completed_at=time.time(),
            )

        # =============================================================
        # Stage 2 — Risk Analysis
        # =============================================================
        risk = self._risk_analyzer.assess(action)
        entry_id = await self._audit.append(
            stage=AuditStage.RISK,
            action_id=str(action.action_id),
            actor=action.actor,
            verb=action.svrc_verb(),
            resource=action.resource,
            decision=risk.risk_level.value,
            result="ASSESSED",
            details={
                "score": risk.score,
                "factors": risk.factors,
                "reversible": risk.reversible,
                "blast_radius": risk.blast_radius,
            },
        )
        audit_ids.append(entry_id)

        # =============================================================
        # Stage 3 — Policy Evaluation
        # =============================================================
        try:
            policy_decision: PolicyDecision = self._policy_engine.evaluate_or_raise(
                action, risk
            )
            entry_id = await self._audit.append(
                stage=AuditStage.POLICY,
                action_id=str(action.action_id),
                actor=action.actor,
                verb=action.svrc_verb(),
                resource=action.resource,
                decision=policy_decision.decision.value,
                result="ALLOW",
                details={"rule_id": policy_decision.rule_id},
            )
            audit_ids.append(entry_id)
        except ApprovalRequiredError as exc:
            entry_id = await self._audit.append(
                stage=AuditStage.POLICY,
                action_id=str(action.action_id),
                actor=action.actor,
                verb=action.svrc_verb(),
                resource=action.resource,
                decision="NEEDS_APPROVAL",
                result="BLOCKED",
                details={"reason": str(exc), "approval_request_id": exc.approval_request_id},
            )
            audit_ids.append(entry_id)
            return ActionResult(
                action_id=action.action_id,
                status=ExecutionStatus.APPROVAL_REQUIRED,
                error=str(exc),
                error_code="E_EXE_APPROVAL_REQUIRED",
                permission_decision=PermissionDecision.NEEDS_APPROVAL,
                risk_level=risk.risk_level,
                approval_request_id=exc.approval_request_id,
                audit_entry_ids=audit_ids,
                started_at=started_at,
                completed_at=time.time(),
            )
        except PolicyViolationError as exc:
            entry_id = await self._audit.append(
                stage=AuditStage.POLICY,
                action_id=str(action.action_id),
                actor=action.actor,
                verb=action.svrc_verb(),
                resource=action.resource,
                decision="DENY",
                result="DENIED",
                details={"reason": str(exc), "rule_id": exc.rule_id},
            )
            audit_ids.append(entry_id)
            return ActionResult(
                action_id=action.action_id,
                status=ExecutionStatus.DENIED,
                error=str(exc),
                error_code="E_EXE_POLICY_VIOLATION",
                permission_decision=PermissionDecision.DENY,
                risk_level=risk.risk_level,
                audit_entry_ids=audit_ids,
                started_at=started_at,
                completed_at=time.time(),
            )

        # =============================================================
        # Stage 4 — Executor Dispatch
        # =============================================================
        try:
            executor = self.registry.resolve(action)
        except ExecutorNotFoundError as exc:
            entry_id = await self._audit.append(
                stage=AuditStage.DISPATCH,
                action_id=str(action.action_id),
                actor=action.actor,
                verb=action.svrc_verb(),
                resource=action.resource,
                decision="NO_EXECUTOR",
                result="FAILED",
                details={"error": str(exc)},
            )
            audit_ids.append(entry_id)
            return ActionResult(
                action_id=action.action_id,
                status=ExecutionStatus.FAILED,
                error=str(exc),
                error_code="E_EXE_NO_EXECUTOR",
                risk_level=risk.risk_level,
                audit_entry_ids=audit_ids,
                started_at=started_at,
                completed_at=time.time(),
            )

        entry_id = await self._audit.append(
            stage=AuditStage.DISPATCH,
            action_id=str(action.action_id),
            actor=action.actor,
            verb=action.svrc_verb(),
            resource=action.resource,
            decision="ROUTED",
            result="SUCCESS",
            details={"executor": executor.manifest.name},
        )
        audit_ids.append(entry_id)

        # =============================================================
        # Stage 5 — Sandbox Context Building
        # =============================================================
        sandbox_ctx = self._sandbox_manager.build_context(action, policy_decision)
        entry_id = await self._audit.append(
            stage=AuditStage.SANDBOX,
            action_id=str(action.action_id),
            actor=action.actor,
            verb=action.svrc_verb(),
            resource=action.resource,
            decision=sandbox_ctx.tier.value,
            result="CONFIGURED",
            details={
                "tier": sandbox_ctx.tier.value,
                "timeout": sandbox_ctx.timeout_seconds,
                "network_allowed": sandbox_ctx.network_allowed,
                "dry_run": sandbox_ctx.dry_run,
            },
        )
        audit_ids.append(entry_id)

        # =============================================================
        # Stage 6 — Execute
        # =============================================================
        try:
            result = await executor.execute(action, sandbox_ctx)
        except SandboxEscapeError as exc:
            entry_id = await self._audit.append(
                stage=AuditStage.EXECUTE,
                action_id=str(action.action_id),
                actor=action.actor,
                verb=action.svrc_verb(),
                resource=action.resource,
                decision="ESCAPE_ATTEMPT",
                result="SANDBOX_ESCAPE",
                details={
                    "sandbox_tier": exc.sandbox_tier,
                    "escape_pattern": exc.escape_pattern,
                    "error": str(exc),
                },
            )
            audit_ids.append(entry_id)
            raise  # Security event — always propagates
        except PermissionDeniedError as exc:
            entry_id = await self._audit.append(
                stage=AuditStage.EXECUTE,
                action_id=str(action.action_id),
                actor=action.actor,
                verb=action.svrc_verb(),
                resource=action.resource,
                decision="DENY",
                result="DENIED",
                details={"error": str(exc)},
            )
            audit_ids.append(entry_id)
            return ActionResult(
                action_id=action.action_id,
                status=ExecutionStatus.DENIED,
                error=str(exc),
                error_code=exc.error_code,
                risk_level=risk.risk_level,
                sandbox_tier=sandbox_ctx.tier,
                audit_entry_ids=audit_ids,
                started_at=started_at,
                completed_at=time.time(),
                executor_name=executor.manifest.name,
            )
        except Exception as exc:
            entry_id = await self._audit.append(
                stage=AuditStage.EXECUTE,
                action_id=str(action.action_id),
                actor=action.actor,
                verb=action.svrc_verb(),
                resource=action.resource,
                decision="FAILED",
                result="FAILURE",
                details={"error": str(exc)},
            )
            audit_ids.append(entry_id)
            return ActionResult(
                action_id=action.action_id,
                status=ExecutionStatus.FAILED,
                error=str(exc),
                error_code="E_EXE_EXECUTOR_FAILED",
                risk_level=risk.risk_level,
                sandbox_tier=sandbox_ctx.tier,
                audit_entry_ids=audit_ids,
                started_at=started_at,
                completed_at=time.time(),
                executor_name=executor.manifest.name,
            )

        # Attach audit IDs and fill timing
        result.audit_entry_ids = audit_ids
        result.risk_level = risk.risk_level
        result.sandbox_tier = sandbox_ctx.tier
        result.permission_decision = PermissionDecision.ALLOW
        result.started_at = started_at

        exec_entry_id = await self._audit.append(
            stage=AuditStage.EXECUTE,
            action_id=str(action.action_id),
            actor=action.actor,
            verb=action.svrc_verb(),
            resource=action.resource,
            decision="EXECUTED",
            result=result.status.value.upper(),
            details={
                "executor": executor.manifest.name,
                "status": result.status.value,
                "error": result.error,
            },
        )
        audit_ids.append(exec_entry_id)

        # =============================================================
        # Stage 7 — Verify + Audit
        # =============================================================
        ver_result, ver_msg = await self._verifier.verify(action, result)
        result.verification_result = ver_result

        if ver_result == VerificationResult.FAILED:
            # Trigger rollback
            rollback_record = await self._rollback_engine.rollback(action, result, executor)
            result.rollback_info = rollback_record.model_dump()
            result.status = (
                ExecutionStatus.ROLLED_BACK
                if rollback_record.succeeded
                else ExecutionStatus.VERIFICATION_FAILED
            )

            entry_id = await self._audit.append(
                stage=AuditStage.ROLLBACK,
                action_id=str(action.action_id),
                actor=action.actor,
                verb=action.svrc_verb(),
                resource=action.resource,
                decision="ROLLBACK_TRIGGERED",
                result="ROLLED_BACK" if rollback_record.succeeded else "ROLLBACK_FAILED",
                details={
                    "verification_message": ver_msg,
                    "rollback_supported": rollback_record.supported,
                    "rollback_succeeded": rollback_record.succeeded,
                },
            )
            audit_ids.append(entry_id)
        else:
            entry_id = await self._audit.append(
                stage=AuditStage.VERIFY,
                action_id=str(action.action_id),
                actor=action.actor,
                verb=action.svrc_verb(),
                resource=action.resource,
                decision="VERIFIED",
                result=ver_result.value.upper(),
                details={"message": ver_msg},
            )
            audit_ids.append(entry_id)

        result.audit_entry_ids = audit_ids
        result.completed_at = time.time()
        result.duration_ms = (result.completed_at - started_at) * 1000
        return result

    # ------------------------------------------------------------------
    # Audit access
    # ------------------------------------------------------------------

    async def audit_entries_for(self, action_id: str) -> list:
        """Return all audit entries for an action."""
        return await self._audit.get_entries_for_action(action_id)

    async def verify_audit_chain(self, last_n: int = 100) -> bool:
        """Quick integrity check of the last N audit entries."""
        return await self._audit.verify_last_n(last_n)

    # ------------------------------------------------------------------
    # Default executor registration
    # ------------------------------------------------------------------

    def _register_default_executors(self) -> None:
        """Register all built-in executors."""
        self.registry.register(FilesystemExecutor())
        self.registry.register(PythonExecutor())
        self.registry.register(GitExecutor())
        self.registry.register(ShellExecutor())
        self.registry.register(ObsidianExecutor(default_vault=self._obsidian_vault))
        self.registry.register(HttpExecutor(allowlist=self._http_allowlist))
        self.registry.register(DockerExecutor())
        # Stubs for future milestones
        self.registry.register(BrowserExecutor)
        self.registry.register(DesktopExecutor)
        self.registry.register(VSCodeExecutor)
