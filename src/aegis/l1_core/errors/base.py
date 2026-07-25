"""L1 Core typed error hierarchy.
Every AEGIS error:
  - is typed (specific subclass)
  - is structured (component, operation, correlation context)
  - is loggable (to_dict / user_safe_message)
  - preserves root cause
  - has severity and a retry hint
Secrets are NEVER propagated via error messages; crypto/redact is called on every error payload
when converted to user-facing string."""
from __future__ import annotations

import contextlib
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID


class ErrorSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RetryHint(str, Enum):
    NO_RETRY = "no_retry"
    RETRY_TRANSIENT = "retry_transient"
    RETRY_BACKOFF = "retry_backoff"
    RETRY_NEW_SCOPE = "retry_new_scope"  # new scope only (e.g. fresh session)


@dataclass
class ErrorContext:
    """Standardized, redacted context attached to every AegisError."""

    component: str = "unknown"
    operation: str = "unknown"
    correlation_id: UUID | None = None
    request_id: UUID | None = None
    task_id: UUID | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class AegisError(Exception):
    """Root of the typed error hierarchy. NEVER raise bare Exception across module boundaries."""

    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    retry_hint: RetryHint = RetryHint.NO_RETRY
    error_code: str = "E00001"

    def __init__(
        self,
        message: str,
        *,
        context: ErrorContext | None = None,
        cause: BaseException | None = None,
        user_safe_message: str | None = None,
        severity: ErrorSeverity | None = None,
        retry_hint: RetryHint | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.context: ErrorContext = context or ErrorContext()
        self.__cause__ = cause
        self.user_safe_message: str = user_safe_message or message
        self.error_id: UUID = uuid.uuid4()
        if severity is not None:
            self.severity = severity
        if retry_hint is not None:
            self.retry_hint = retry_hint
        if error_code is not None:
            self.error_code = error_code

    def to_dict(self, *, redact_sensitive: bool = True) -> dict[str, Any]:
        d: dict[str, Any] = {
            "error_id": str(self.error_id),
            "error_code": self.error_code,
            "severity": self.severity.value,
            "retry_hint": self.retry_hint.value,
            "component": self.context.component,
            "operation": self.context.operation,
            "correlation_id": str(self.context.correlation_id) if self.context.correlation_id else None,
            "request_id": str(self.context.request_id) if self.context.request_id else None,
            "task_id": str(self.context.task_id) if self.context.task_id else None,
            "message": self.user_safe_message if redact_sensitive else self.message,
            "extra": self.context.extra if not redact_sensitive else self._safe_extra(),
        }
        if self.__cause__ is not None:
            with contextlib.suppress(Exception):
                d["cause"] = {
                    "type": type(self.__cause__).__name__,
                    "message": str(self.__cause__) if not redact_sensitive else "[cause redacted]",
                }
        return d

    def _safe_extra(self) -> dict[str, Any]:
        """Minimal fallback — the real redactor (crypto module) is used by log formatter in L2."""
        safe: dict[str, Any] = {}
        for k, v in self.context.extra.items():
            key = k.lower()
            if any(s in key for s in ("secret", "password", "token", "api_key", "private", "credential")):
                safe[k] = "<REDACTED>"
            else:
                safe[k] = v
        return safe

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"[{self.error_code}] {self.user_safe_message} (id={self.error_id})"


# -------- Subclasses for Prompt 02 concrete failures --------

class InitializationError(AegisError):
    error_code = "E10105"
    severity = ErrorSeverity.HIGH
    retry_hint = RetryHint.RETRY_TRANSIENT


class LifecycleError(AegisError):
    severity = ErrorSeverity.HIGH


class StartupTimeoutError(LifecycleError):
    error_code = "E10103"
    retry_hint = RetryHint.NO_RETRY


class ShutdownTimeoutError(LifecycleError):
    error_code = "E10104"
    retry_hint = RetryHint.NO_RETRY


class RuntimeShutdownError(LifecycleError):
    error_code = "E10102"
    retry_hint = RetryHint.NO_RETRY


class ConfigurationError(AegisError):
    error_code = "E20101"
    severity = ErrorSeverity.HIGH
    retry_hint = RetryHint.NO_RETRY


class ValidationError(AegisError):
    error_code = "E00003"
    retry_hint = RetryHint.NO_RETRY


class NotFoundError(AegisError):
    error_code = "E00004"
    retry_hint = RetryHint.NO_RETRY


class EventBusError(AegisError):
    error_code = "E20201"
    severity = ErrorSeverity.MEDIUM


class ExecutionError(AegisError):
    # Forward-declared L3 error type; useful even though Executor is not implemented in P02
    error_code = "E00001"


class StoreError(AegisError):
    error_code = "E20401"
    severity = ErrorSeverity.MEDIUM
    retry_hint = RetryHint.RETRY_TRANSIENT


class TimeoutError(AegisError):
    error_code = "E00002"
    retry_hint = RetryHint.RETRY_BACKOFF


class RecoveryError(AegisError):
    error_code = "E10111"
    severity = ErrorSeverity.HIGH


class InternalError(AegisError):
    error_code = "E00001"
    severity = ErrorSeverity.CRITICAL
