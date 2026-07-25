"""L1 Error classifier.
Maps arbitrary caught exceptions → (severity, retry_hint, suggested AegisError class)."""
from __future__ import annotations

from dataclasses import dataclass

from aegis.l1_core.errors.base import (
    AegisError,
    ConfigurationError,
    ErrorSeverity,
    ExecutionError,
    InternalError,
    NotFoundError,
    RecoveryError,
    RetryHint,
    TimeoutError,
    ValidationError,
)


@dataclass(frozen=True)
class Classification:
    severity: ErrorSeverity
    retry_hint: RetryHint
    error_class: type[AegisError]


_async_timeout_names = {"TimeoutError", "asyncio.exceptions.TimeoutError"}
_validation_names = {"ValidationError", "ValueError", "pydantic.ValidationError"}
_not_found_names = {"FileNotFoundError", "KeyError", "LookupError"}
_config_names = {"ConfigException", "ConfigurationError"}


def classify_error(exc: BaseException) -> Classification:
    if isinstance(exc, AegisError):
        return Classification(exc.severity, exc.retry_hint, type(exc))
    name = type(exc).__name__
    mod = type(exc).__module__ or ""
    fqcn = f"{mod}.{name}"

    if name == "TimeoutError" or fqcn in _async_timeout_names or "Timeout" in name:
        return Classification(ErrorSeverity.MEDIUM, RetryHint.RETRY_BACKOFF, TimeoutError)
    if fqcn in _validation_names or name in _validation_names or "Validation" in name:
        return Classification(ErrorSeverity.MEDIUM, RetryHint.NO_RETRY, ValidationError)
    if name in _not_found_names:
        return Classification(ErrorSeverity.LOW, RetryHint.NO_RETRY, NotFoundError)
    if name in _config_names:
        return Classification(ErrorSeverity.HIGH, RetryHint.NO_RETRY, ConfigurationError)
    if fqcn.startswith("aegis.l1_core.errors.Recovery"):
        return Classification(ErrorSeverity.HIGH, RetryHint.NO_RETRY, RecoveryError)
    if isinstance(exc, (RuntimeError,)) and "recovery" in str(exc).lower():
        return Classification(ErrorSeverity.HIGH, RetryHint.NO_RETRY, RecoveryError)
    if isinstance(exc, OSError):
        return Classification(ErrorSeverity.MEDIUM, RetryHint.RETRY_TRANSIENT, ExecutionError)
    return Classification(ErrorSeverity.MEDIUM, RetryHint.NO_RETRY, InternalError)
