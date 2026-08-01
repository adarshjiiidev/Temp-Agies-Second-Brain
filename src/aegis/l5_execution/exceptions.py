"""L5 Execution Engine — Exceptions.

All exceptions raised within the Execution Engine inherit from
ExecutionEngineError.  Each class maps to a specific stage failure.

Error code convention: E_EXE_XXXXXX

Import safety: stdlib only.
"""

from __future__ import annotations

from uuid import UUID

__all__ = [
    "ExecutionEngineError",
    "PermissionDeniedError",
    "PolicyViolationError",
    "ApprovalRequiredError",
    "SandboxEscapeError",
    "ExecutorNotFoundError",
    "AuditIntegrityError",
    "VerificationFailedError",
    "RollbackError",
    "ExecutionTimeoutError",
    "ExecutorError",
    "PipelineError",
    "ResourceScopeError",
]


class ExecutionEngineError(Exception):
    """Base class for all L5 Execution Engine errors.

    Carries a machine-readable ``error_code`` and the ``action_id`` that
    triggered the error, so callers can correlate with the audit log.
    """

    error_code: str = "E_EXE_UNKNOWN"

    def __init__(
        self,
        message: str,
        *,
        action_id: UUID | str | None = None,
        stage: str | None = None,
        detail: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.action_id = action_id
        self.stage = stage
        self.detail = detail or {}

    def __str__(self) -> str:
        parts = [f"[{self.error_code}] {super().__str__()}"]
        if self.action_id:
            parts.append(f"(action={self.action_id!s:.8})")
        if self.stage:
            parts.append(f"(stage={self.stage})")
        return " ".join(parts)


class PermissionDeniedError(ExecutionEngineError):
    """Raised at Stage 1 when the SVRC check produces DENY.

    The action must be logged in the audit chain as DENIED before raising.
    """

    error_code = "E_EXE_PERM_DENIED"

    def __init__(
        self,
        message: str,
        *,
        actor: str | None = None,
        verb: str | None = None,
        resource: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(message, **kwargs)
        self.actor = actor
        self.verb = verb
        self.resource = resource


class PolicyViolationError(ExecutionEngineError):
    """Raised at Stage 3 when the Policy Engine returns DENY.

    Distinct from PermissionDeniedError: permission checks are capability-
    based; policy violations are risk/business-rule based.
    """

    error_code = "E_EXE_POLICY_VIOLATION"

    def __init__(
        self,
        message: str,
        *,
        rule_id: str | None = None,
        risk_level: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(message, **kwargs)
        self.rule_id = rule_id
        self.risk_level = risk_level


class ApprovalRequiredError(ExecutionEngineError):
    """Raised when a CRITICAL-risk action requires explicit user approval.

    Carries an ``approval_request_id`` that can be used to correlate with
    the approval flow managed by the L2 EventBus.  The action is NOT
    executed until approval is granted.
    """

    error_code = "E_EXE_APPROVAL_REQUIRED"

    def __init__(
        self,
        message: str,
        *,
        approval_request_id: str | None = None,
        risk_level: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(message, **kwargs)
        self.approval_request_id = approval_request_id
        self.risk_level = risk_level


class SandboxEscapeError(ExecutionEngineError):
    """Raised when a sandbox escape attempt is detected.

    This is a CRITICAL security event.  The error is always written to
    the audit log as an ``ESCAPE_ATTEMPT`` entry before the exception
    propagates.
    """

    error_code = "E_EXE_SANDBOX_ESCAPE"

    def __init__(
        self,
        message: str,
        *,
        sandbox_tier: str | None = None,
        escape_pattern: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(message, **kwargs)
        self.sandbox_tier = sandbox_tier
        self.escape_pattern = escape_pattern


class ExecutorNotFoundError(ExecutionEngineError):
    """Raised when the Executor Registry cannot find a handler for the ActionKind."""

    error_code = "E_EXE_NO_EXECUTOR"

    def __init__(
        self,
        message: str,
        *,
        action_kind: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(message, **kwargs)
        self.action_kind = action_kind


class AuditIntegrityError(ExecutionEngineError):
    """Raised by AuditVerifier when a chain integrity violation is detected.

    This may indicate log tampering, deletion, or out-of-order entries.
    """

    error_code = "E_EXE_AUDIT_INTEGRITY"

    def __init__(
        self,
        message: str,
        *,
        entry_id: str | None = None,
        expected_hash: str | None = None,
        actual_hash: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(message, **kwargs)
        self.entry_id = entry_id
        self.expected_hash = expected_hash
        self.actual_hash = actual_hash


class VerificationFailedError(ExecutionEngineError):
    """Raised at Stage 7 when post-execution assertions fail.

    If the executor supports rollback, a RollbackEngine run is triggered
    before this exception propagates.
    """

    error_code = "E_EXE_VERIFY_FAILED"

    def __init__(
        self,
        message: str,
        *,
        assertion_name: str | None = None,
        expected: object = None,
        actual: object = None,
        **kwargs,
    ) -> None:
        super().__init__(message, **kwargs)
        self.assertion_name = assertion_name
        self.expected = expected
        self.actual = actual


class RollbackError(ExecutionEngineError):
    """Raised when a rollback attempt fails or is not supported.

    When raised, the audit log must contain a ROLLBACK_FAILED or
    ROLLBACK_UNSUPPORTED entry.
    """

    error_code = "E_EXE_ROLLBACK_FAILED"


class ExecutionTimeoutError(ExecutionEngineError):
    """Raised when an executor exceeds its allocated time budget."""

    error_code = "E_EXE_TIMEOUT"

    def __init__(
        self,
        message: str,
        *,
        timeout_seconds: float | None = None,
        **kwargs,
    ) -> None:
        super().__init__(message, **kwargs)
        self.timeout_seconds = timeout_seconds


class ExecutorError(ExecutionEngineError):
    """Raised by an executor when the underlying operation fails."""

    error_code = "E_EXE_EXECUTOR_FAILED"


class PipelineError(ExecutionEngineError):
    """Raised when the pipeline itself encounters an internal error
    (distinct from business-logic errors in individual stages)."""

    error_code = "E_EXE_PIPELINE_ERROR"


class ResourceScopeError(ExecutionEngineError):
    """Raised when a resource path escapes its granted scope.

    Example: executor tries to access ``/etc/passwd`` but grant only covers
    ``~/Projects/**``.
    """

    error_code = "E_EXE_SCOPE_VIOLATION"
