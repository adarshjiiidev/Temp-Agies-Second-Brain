"""Error code registry.
Format: E{layer}{category}{seq} — layer 1=L1, 2=L2; category 00=general, 01=lifecycle, 02=config, ..."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorCodeEntry:
    code: str
    message: str
    default_severity: str = "medium"
    retryable: bool = False


class ErrorCode:
    """Namespace for all standardized error codes. New codes added here ONLY, never ad-hoc strings."""

    # L1 Lifecycle (E101xx)
    RUNTIME_ALREADY_STARTED = ErrorCodeEntry("E10101", "Runtime already started", retryable=False)
    RUNTIME_NOT_RUNNING = ErrorCodeEntry("E10102", "Runtime is not running", retryable=False)
    STARTUP_TIMEOUT = ErrorCodeEntry("E10103", "Startup timed out", default_severity="high", retryable=False)
    SHUTDOWN_TIMEOUT = ErrorCodeEntry("E10104", "Shutdown timed out", default_severity="high", retryable=False)
    INITIALIZATION_FAILED = ErrorCodeEntry(
        "E10105", "Service initialization failed", default_severity="high", retryable=True
    )
    START_FAILED = ErrorCodeEntry("E10106", "Service start failed", default_severity="high", retryable=True)
    STOP_FAILED = ErrorCodeEntry("E10107", "Service stop failed", default_severity="medium", retryable=False)
    PARTIALLY_INITIALIZED = ErrorCodeEntry(
        "E10108", "Runtime in partially initialized state — refusing further actions",
        default_severity="high", retryable=False,
    )
    CIRCULAR_DEPENDENCY = ErrorCodeEntry(
        "E10109", "Circular dependency detected in service graph", retryable=False
    )
    SERVICE_NOT_FOUND = ErrorCodeEntry("E10110", "Service not found in registry", retryable=False)
    RECOVERY_FAILED = ErrorCodeEntry(
        "E10111", "Service recovery failed after max attempts", default_severity="high", retryable=False
    )

    # L1 Errors / DI (E102xx)
    DI_NOT_REGISTERED = ErrorCodeEntry("E10201", "Dependency not registered in container", retryable=False)
    DI_CIRCULAR = ErrorCodeEntry("E10202", "Circular dependency detected in DI resolution", retryable=False)
    DI_SCOPE_MISMATCH = ErrorCodeEntry("E10203", "DI lifetime scope mismatch", retryable=False)

    # L2 Configuration (E201xx)
    CONFIG_INVALID = ErrorCodeEntry("E20101", "Configuration failed validation", retryable=False)
    CONFIG_FILE_NOT_FOUND = ErrorCodeEntry("E20102", "Configuration file not found", retryable=False)
    CONFIG_SCHEMA_MISMATCH = ErrorCodeEntry("E20103", "Config schema version mismatch", retryable=True)
    CONFIG_SECRET_REF_INVALID = ErrorCodeEntry(
        "E20104", "Invalid secret:// reference in config", retryable=False
    )

    # L2 Event Bus (E202xx)
    EVENT_BUS_NOT_STARTED = ErrorCodeEntry("E20201", "Event bus not started", retryable=True)
    EVENT_DLQ_ENQUEUED = ErrorCodeEntry(
        "E20202", "Event moved to dead-letter queue after handler failures",
        default_severity="medium", retryable=False,
    )
    EVENT_PERSIST_FAILED = ErrorCodeEntry(
        "E20203", "Failed to persist event to durable log",
        default_severity="high", retryable=True,
    )

    # L2 Scheduler (E203xx)
    TASK_CANCELLED = ErrorCodeEntry("E20301", "Background task was cancelled", retryable=False)
    TASK_FAILED = ErrorCodeEntry("E20302", "Background task failed", retryable=True)
    TASK_QUEUE_FULL = ErrorCodeEntry("E20303", "Task queue full", retryable=True)

    # L2 Storage (E204xx)
    STORE_ERROR = ErrorCodeEntry("E20401", "Storage operation failed", retryable=True)

    # L2 Crypto / Secrets (E205xx)
    SECRET_NOT_FOUND = ErrorCodeEntry("E20501", "Secret reference not found in vault", retryable=False)
    CRYPTO_ERROR = ErrorCodeEntry(
        "E20502", "Cryptographic operation failed", default_severity="high", retryable=False
    )

    # L2 Plugin (E206xx)
    PLUGIN_MANIFEST_MISSING = ErrorCodeEntry("E20601", "Plugin manifest missing", retryable=False)
    PLUGIN_MANIFEST_INVALID = ErrorCodeEntry("E20602", "Plugin manifest invalid", retryable=False)
    PLUGIN_PERMISSION_UNKNOWN = ErrorCodeEntry(
        "E20603", "Plugin requests unknown permission — deny by default",
        default_severity="high", retryable=False,
    )
    PLUGIN_LOAD_FAILED = ErrorCodeEntry("E20604", "Plugin load failed", retryable=True)

    # Generic / Uncategorized (E000xx)
    INTERNAL_ERROR = ErrorCodeEntry(
        "E00001", "Internal error — details in context", default_severity="high", retryable=False
    )
    TIMEOUT = ErrorCodeEntry("E00002", "Operation timed out", default_severity="medium", retryable=True)
    VALIDATION_FAILED = ErrorCodeEntry("E00003", "Validation failed", retryable=False)
    NOT_FOUND = ErrorCodeEntry("E00004", "Resource not found", retryable=False)


ERROR_CODE_REGISTRY: dict[str, ErrorCodeEntry] = {
    attr: getattr(ErrorCode, attr) for attr in dir(ErrorCode)
    if isinstance(getattr(ErrorCode, attr), ErrorCodeEntry)
    for attr in [attr]
    # type: ignore[assignment]
}
