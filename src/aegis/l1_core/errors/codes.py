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

    def __str__(self) -> str:
        return self.code


class ErrorCode:
    """Namespace for all standardized error codes. New codes added here ONLY, never ad-hoc strings.

    Supports both named access (ErrorCode.VALIDATION_FAILED) and numeric string access
    (ErrorCode.E20104) via __getattr__ fallback — both forms resolve to the same ErrorCodeEntry.
    """

    # L1 Lifecycle (E101xx)
    RUNTIME_ALREADY_STARTED = ErrorCodeEntry("E10101", "Runtime already started", retryable=False)
    RUNTIME_NOT_RUNNING = ErrorCodeEntry("E10102", "Runtime is not running", retryable=False)
    STARTUP_TIMEOUT = ErrorCodeEntry(
        "E10103", "Startup timed out", default_severity="high", retryable=False
    )
    SHUTDOWN_TIMEOUT = ErrorCodeEntry(
        "E10104", "Shutdown timed out", default_severity="high", retryable=False
    )
    INITIALIZATION_FAILED = ErrorCodeEntry(
        "E10105", "Service initialization failed", default_severity="high", retryable=True
    )
    START_FAILED = ErrorCodeEntry(
        "E10106", "Service start failed", default_severity="high", retryable=True
    )
    STOP_FAILED = ErrorCodeEntry(
        "E10107", "Service stop failed", default_severity="medium", retryable=False
    )
    PARTIALLY_INITIALIZED = ErrorCodeEntry(
        "E10108",
        "Runtime in partially initialized state — refusing further actions",
        default_severity="high",
        retryable=False,
    )
    CIRCULAR_DEPENDENCY = ErrorCodeEntry(
        "E10109", "Circular dependency detected in service graph", retryable=False
    )
    SERVICE_NOT_FOUND = ErrorCodeEntry("E10110", "Service not found in registry", retryable=False)
    RECOVERY_FAILED = ErrorCodeEntry(
        "E10111",
        "Service recovery failed after max attempts",
        default_severity="high",
        retryable=False,
    )

    # L1 Errors / DI (E102xx)
    DI_NOT_REGISTERED = ErrorCodeEntry(
        "E10201", "Dependency not registered in container", retryable=False
    )
    DI_CIRCULAR = ErrorCodeEntry(
        "E10202", "Circular dependency detected in DI resolution", retryable=False
    )
    DI_SCOPE_MISMATCH = ErrorCodeEntry("E10203", "DI lifetime scope mismatch", retryable=False)

    # L2 Configuration (E201xx)
    CONFIG_INVALID = ErrorCodeEntry("E20101", "Configuration failed validation", retryable=False)
    CONFIG_FILE_NOT_FOUND = ErrorCodeEntry(
        "E20102", "Configuration file not found", retryable=False
    )
    CONFIG_SCHEMA_MISMATCH = ErrorCodeEntry(
        "E20103", "Config schema version mismatch", retryable=True
    )
    CONFIG_SECRET_REF_INVALID = ErrorCodeEntry(
        "E20104", "Invalid secret:// reference in config", retryable=False
    )

    # L2 Event Bus (E202xx)
    EVENT_BUS_NOT_STARTED = ErrorCodeEntry("E20201", "Event bus not started", retryable=True)
    EVENT_DLQ_ENQUEUED = ErrorCodeEntry(
        "E20202",
        "Event moved to dead-letter queue after handler failures",
        default_severity="medium",
        retryable=False,
    )
    EVENT_PERSIST_FAILED = ErrorCodeEntry(
        "E20203",
        "Failed to persist event to durable log",
        default_severity="high",
        retryable=True,
    )

    # L2 Scheduler (E203xx)
    TASK_CANCELLED = ErrorCodeEntry("E20301", "Background task was cancelled", retryable=False)
    TASK_FAILED = ErrorCodeEntry("E20302", "Background task failed", retryable=True)
    TASK_QUEUE_FULL = ErrorCodeEntry("E20303", "Task queue full", retryable=True)

    # L2 Storage (E204xx)
    STORE_ERROR = ErrorCodeEntry("E20401", "Storage operation failed", retryable=True)

    # L2 Crypto / Secrets (E205xx)
    SECRET_NOT_FOUND = ErrorCodeEntry(
        "E20501", "Secret reference not found in vault", retryable=False
    )
    CRYPTO_ERROR = ErrorCodeEntry(
        "E20502", "Cryptographic operation failed", default_severity="high", retryable=False
    )

    # L2 Plugin (E206xx)
    PLUGIN_MANIFEST_MISSING = ErrorCodeEntry("E20601", "Plugin manifest missing", retryable=False)
    PLUGIN_MANIFEST_INVALID = ErrorCodeEntry("E20602", "Plugin manifest invalid", retryable=False)
    PLUGIN_PERMISSION_UNKNOWN = ErrorCodeEntry(
        "E20603",
        "Plugin requests unknown permission — deny by default",
        default_severity="high",
        retryable=False,
    )
    PLUGIN_LOAD_FAILED = ErrorCodeEntry("E20604", "Plugin load failed", retryable=True)

    # L3 AI Kernel / Providers (E301xx)
    AI_KERNEL_NOT_STARTED = ErrorCodeEntry("E30101", "AI Kernel not started", retryable=True)
    AI_PROVIDER_NOT_AVAILABLE = ErrorCodeEntry(
        "E30102", "AI provider not available", default_severity="high", retryable=True
    )
    AI_PROVIDER_ERROR = ErrorCodeEntry(
        "E30103", "AI provider returned error", default_severity="medium", retryable=True
    )
    AI_INFERENCE_FAILED = ErrorCodeEntry(
        "E30104", "AI inference failed", default_severity="high", retryable=True
    )
    AI_ALL_PROVIDERS_EXHAUSTED = ErrorCodeEntry(
        "E30105",
        "All eligible providers/models exhausted — cannot fulfil request",
        default_severity="high",
        retryable=False,
    )
    AI_OFFLINE_BLOCKED = ErrorCodeEntry(
        "E30106", "Offline mode and no local model eligible", retryable=False
    )

    # L3 AI Router / Routing (E302xx)
    AI_ROUTER_NO_ELIGIBLE_MODEL = ErrorCodeEntry(
        "E30201", "No model in registry satisfies request requirements", retryable=False
    )
    AI_ROUTER_INSUFFICIENT_CONTEXT = ErrorCodeEntry(
        "E30202", "Model context window insufficient for request", retryable=False
    )
    AI_ROUTER_PRIVACY_VIOLATION = ErrorCodeEntry(
        "E30203",
        "Privacy tier requires local-only but no local model eligible",
        default_severity="high",
        retryable=False,
    )
    AI_ROUTER_REQUIRED_CAPABILITY_MISSING = ErrorCodeEntry(
        "E30204", "No model in registry has required capability", retryable=False
    )
    AI_ROUTER_NO_LOCAL_MODEL = ErrorCodeEntry(
        "E30205",
        "P0 privacy requires LOCAL model but none available",
        default_severity="high",
        retryable=False,
    )

    # L3 AI Keys / Key Management (E303xx)
    AI_KEY_INVALID = ErrorCodeEntry(
        "E30301", "Provider API key invalid or revoked", default_severity="high", retryable=False
    )
    AI_KEY_ROTATION_EXHAUSTED = ErrorCodeEntry(
        "E30302", "All API keys for a provider are exhausted, disabled, or in cooldown",
        default_severity="high",
        retryable=False,
    )
    AI_KEY_RATE_LIMITED = ErrorCodeEntry(
        "E30303", "Provider API key rate-limited — try another key or wait", retryable=True
    )
    AI_KEY_QUOTA_EXHAUSTED = ErrorCodeEntry(
        "E30304", "Provider API key quota exhausted", retryable=False
    )

    # L3 AI Cost / Budget (E304xx)
    AI_BUDGET_EXHAUSTED = ErrorCodeEntry(
        "E30401", "AI usage budget exhausted", default_severity="high", retryable=False
    )
    AI_BUDGET_TASK_LIMIT = ErrorCodeEntry(
        "E30402", "Per-task AI cost budget limit reached", retryable=False
    )
    AI_BUDGET_DAILY_LIMIT = ErrorCodeEntry(
        "E30403", "Daily AI usage budget exhausted", default_severity="medium", retryable=False
    )
    AI_BUDGET_PROJECT_LIMIT = ErrorCodeEntry(
        "E30404", "Project AI budget exhausted", retryable=False
    )
    AI_COST_ESTIMATE_OVER_LIMIT = ErrorCodeEntry(
        "E30405", "Estimated inference cost exceeds allowed budget threshold", retryable=False
    )

    # L3 AI Structured Output / Parsing (E305xx)
    AI_STRUCTURED_PARSE_FAILED = ErrorCodeEntry(
        "E30501", "LLM output failed to parse as structured format", retryable=True
    )
    AI_STRUCTURED_VALIDATION_FAILED = ErrorCodeEntry(
        "E30502", "LLM output parsed but failed schema validation", retryable=True
    )
    AI_STRUCTURED_RETRIES_EXHAUSTED = ErrorCodeEntry(
        "E30503",
        "Structured output retries exhausted — still not schema-compliant",
        default_severity="high",
        retryable=False,
    )

    # L3 AI Rate Limits & Provider Failures (E306xx — classified categories)
    AI_RATE_LIMITED = ErrorCodeEntry(
        "E30601", "Rate-limited by provider — backoff", default_severity="medium", retryable=True
    )
    AI_QUOTA_EXCEEDED = ErrorCodeEntry(
        "E30602", "Provider quota exceeded", default_severity="medium", retryable=False
    )
    AI_AUTHENTICATION_FAILED = ErrorCodeEntry(
        "E30603", "Provider authentication failed", default_severity="high", retryable=False
    )
    AI_PROVIDER_UNAVAILABLE = ErrorCodeEntry(
        "E30604",
        "Provider unavailable (network/5xx/outage)",
        default_severity="medium",
        retryable=True,
    )
    AI_INVALID_REQUEST = ErrorCodeEntry(
        "E30605", "Provider rejected request as invalid", retryable=False
    )
    AI_MODEL_UNAVAILABLE = ErrorCodeEntry(
        "E30606", "Requested model unavailable via provider", retryable=True
    )
    AI_REQUEST_CANCELLED = ErrorCodeEntry(
        "E30607", "In-flight AI request was cancelled", retryable=False
    )

    # L6 Planning — Goal & Intent (E601xx)
    PLAN_GOAL_INVALID = ErrorCodeEntry(
        "E60101", "Goal text is empty or invalid", retryable=False
    )
    PLAN_AMBIGUOUS_INTENT = ErrorCodeEntry(
        "E60102", "Intent is ambiguous — clarification required", default_severity="low", retryable=False
    )

    # L6 Planning — Decomposition (E602xx)
    PLAN_CIRCULAR_DEPENDENCY = ErrorCodeEntry(
        "E60201", "Circular dependency detected in task graph", default_severity="high", retryable=False
    )
    PLAN_DECOMPOSITION_FAILED = ErrorCodeEntry(
        "E60202", "Goal could not be decomposed into tasks", default_severity="high", retryable=False
    )

    # L6 Planning — Strategy & Decision (E603xx)
    PLAN_NO_VIABLE_STRATEGY = ErrorCodeEntry(
        "E60301", "No viable planning strategy found for constraints", retryable=False
    )
    PLAN_CONSTRAINT_VIOLATED = ErrorCodeEntry(
        "E60302", "Plan violates one or more hard constraints", default_severity="high", retryable=False
    )

    # L6 Planning — Planner Service (E605xx)
    PLAN_NOT_FOUND = ErrorCodeEntry(
        "E60501", "Plan ID not found in active session", default_severity="low", retryable=False
    )
    PLAN_ALREADY_CANCELLED = ErrorCodeEntry(
        "E60502", "Plan is already cancelled", default_severity="low", retryable=False
    )
    PLAN_SESSION_EXPIRED = ErrorCodeEntry(
        "E60503", "Planning session has expired", retryable=False
    )

    # Generic / Uncategorized (E000xx)
    INTERNAL_ERROR = ErrorCodeEntry(
        "E00001", "Internal error — details in context", default_severity="high", retryable=False
    )
    TIMEOUT = ErrorCodeEntry(
        "E00002", "Operation timed out", default_severity="medium", retryable=True
    )
    VALIDATION_FAILED = ErrorCodeEntry("E00003", "Validation failed", retryable=False)
    NOT_FOUND = ErrorCodeEntry("E00004", "Resource not found", retryable=False)


def _bootstrap_error_code_numeric_aliases() -> None:
    for attr in list(vars(ErrorCode)):
        val = getattr(ErrorCode, attr, None)
        if isinstance(val, ErrorCodeEntry):
            setattr(ErrorCode, val.code, val)


_bootstrap_error_code_numeric_aliases()

ERROR_CODE_REGISTRY: dict[str, ErrorCodeEntry] = {
    attr: getattr(ErrorCode, attr)
    for attr in dir(ErrorCode)
    if isinstance(getattr(ErrorCode, attr), ErrorCodeEntry)
}
