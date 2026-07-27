"""AEGIS — Personal Adaptive AI Operating System.

Prompt 02 exposes only the public Core Runtime API surface.
All L3+ subsystems are not implemented here; see docs/09_ROADMAP.md.

Public API (L1 + L2 Foundation per Prompt 02):
  - CoreRuntime / RuntimeState / Supervisor
  - Service / ModuleLifecycle / HealthProvider interfaces
  - HealthAggregator / HealthState / HealthReport
  - AegisError hierarchy / ErrorCode
  - ConfigLoader / ImmutableConfigSnapshot
  - StructuredLogger / LogLevel / Redactor / get_logger
  - CorrelationContext (async-safe contextvar-based)
  - CoreEventBus / EventEnvelope / Topic / Priority
  - DIContainer / Lifetime / Scope
  - BackgroundTaskManager / TaskState / RetryPolicy
  - PluginLoader (manifest-only skeleton)
  - SQLiteKVStore / SQLiteDocStore + NoOp* stubs
  - FileSecretVault / Hasher / redaction
"""

from __future__ import annotations

from aegis.l1_core.di.container import DIContainer, Lifetime, Scope
from aegis.l1_core.errors.base import (
    AegisError,
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
from aegis.l1_core.errors.codes import ErrorCode
from aegis.l1_core.health import (
    ComponentHealth,
    HealthAggregator,
    HealthCheck,
    HealthReport,
    HealthState,
)
from aegis.l1_core.interfaces.base import (
    HealthProvider,
    ModuleLifecycle,
    Pluggable,
    Service,
    ServiceInfo,
)
from aegis.l1_core.runtime import CoreRuntime, RuntimeState
from aegis.l1_core.supervisor import Supervisor
from aegis.l2_foundation.config import ConfigLoader, ImmutableConfigSnapshot, load_config
from aegis.l2_foundation.crypto import (
    FileSecretVault,
    Hasher,
    Redactor,
    redact_value,
    secret_ref,
)
from aegis.l2_foundation.event_bus import (
    CRITICAL,
    DEFAULT_TOPIC,
    HIGH,
    LOW,
    NORMAL,
    CoreEventBus,
    EventEnvelope,
    Priority,
    Topic,
)
from aegis.l2_foundation.persistence import (
    NoOpGraphStore,
    NoOpVectorStore,
    SQLiteDocStore,
    SQLiteKVStore,
)
from aegis.l2_foundation.plugin_loader import PluginLoader, PluginManifest, SandboxTier
from aegis.l2_foundation.scheduler import (
    BackgroundTaskManager,
    RetryPolicy,
    TaskInfo,
    TaskState,
    run_with_retry,
)
from aegis.l2_foundation.telemetry.context import CorrelationContext, new_correlation
from aegis.l2_foundation.telemetry.logger import (
    DevelopmentFormatter,
    FileSink,
    JSONFormatter,
    LogLevel,
    StreamSink,
    StructuredLogger,
    configure_root_logger,
    get_logger,
)

__all__ = [
    # Runtime (L1)
    "CoreRuntime",
    "RuntimeState",
    "Supervisor",
    "Service",
    "ServiceInfo",
    "ModuleLifecycle",
    "HealthProvider",
    "Pluggable",
    # Errors (L1)
    "AegisError",
    "ConfigurationError",
    "ValidationError",
    "NotFoundError",
    "LifecycleError",
    "InitializationError",
    "StartupTimeoutError",
    "ShutdownTimeoutError",
    "RuntimeShutdownError",
    "ExecutionError",
    "StoreError",
    "EventBusError",
    "TimeoutError",
    "RecoveryError",
    "InternalError",
    "ErrorSeverity",
    "RetryHint",
    "ErrorCode",
    # Health (L1)
    "HealthAggregator",
    "HealthReport",
    "HealthCheck",
    "HealthState",
    "ComponentHealth",
    # DI (L1)
    "DIContainer",
    "Lifetime",
    "Scope",
    # Config (L2)
    "ConfigLoader",
    "ImmutableConfigSnapshot",
    "load_config",
    # Logging / Correlation (L2)
    "StructuredLogger",
    "LogLevel",
    "get_logger",
    "configure_root_logger",
    "JSONFormatter",
    "DevelopmentFormatter",
    "StreamSink",
    "FileSink",
    "CorrelationContext",
    "new_correlation",
    "Redactor",
    "redact_value",
    "secret_ref",
    "Hasher",
    "FileSecretVault",
    # Events (L2)
    "CoreEventBus",
    "EventEnvelope",
    "Topic",
    "Priority",
    "DEFAULT_TOPIC",
    "LOW",
    "NORMAL",
    "HIGH",
    "CRITICAL",
    # Scheduling (L2)
    "BackgroundTaskManager",
    "TaskState",
    "TaskInfo",
    "RetryPolicy",
    "run_with_retry",
    # Plugin (L2)
    "PluginLoader",
    "PluginManifest",
    "SandboxTier",
    # Persistence (L2)
    "SQLiteKVStore",
    "SQLiteDocStore",
    "NoOpVectorStore",
    "NoOpGraphStore",
]

__version__ = "0.1.0"  # Prompt 02
