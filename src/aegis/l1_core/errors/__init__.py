"""L1 Typed Error Taxonomy per Prompt 01 §02.
All AEGIS errors inherit from AegisError; never raise bare Exception across module boundaries."""

from aegis.l1_core.errors.base import (
    AegisError,
    AIStructuredOutputError,
    AIStructuredRetriesExhaustedError,
    ConfigurationError,
    ErrorSeverity,
    EventBusError,
    ExecutionError,
    InitializationError,
    InternalError,
    LifecycleError,
    NotFoundError,
    RecoveryError,
    RetryHint,
    RuntimeShutdownError,
    ShutdownTimeoutError,
    StartupTimeoutError,
    StoreError,
    TimeoutError,
    ValidationError,
)
from aegis.l1_core.errors.classify import classify_error
from aegis.l1_core.errors.codes import ErrorCode

__all__ = [
    "AegisError",
    "ErrorSeverity",
    "RetryHint",
    "ErrorCode",
    # Subclasses — Prompt 02 concrete errors
    "InitializationError",
    "LifecycleError",
    "StartupTimeoutError",
    "ShutdownTimeoutError",
    "RuntimeShutdownError",
    "ConfigurationError",
    "ValidationError",
    "NotFoundError",
    "EventBusError",
    "ExecutionError",
    "StoreError",
    "TimeoutError",
    "RecoveryError",
    "InternalError",
    # L3 AI Structured Output errors
    "AIStructuredOutputError",
    "AIStructuredRetriesExhaustedError",
    # Classifier
    "classify_error",
]
