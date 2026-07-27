# AEGIS Prompt 02 — Core Runtime: Implementation Reference

_Prompt 02 is the foundation runtime layer. This file is the human-readable API contract for modules implemented in Prompt 02. Use this doc when extending Prompt 02 or building Prompt 03 on top of it._

---

## 1. Quick Navigation

| Layer | Module | Entry Class | Test file |
|---|---|---|---|
| L1 | Runtime | `CoreRuntime` | test_runtime_lifecycle.py (6 tests) |
| L1 | DI | `DIContainer`, `Scope`, `Lifetime`, `Lazy` | test_di.py (7) |
| L1 | Errors | `AegisError`, subclasses, `ErrorCode` | tests use errors indirectly throughout |
| L1 | Health | `HealthAggregator`, `HealthReport`, `HealthState` | test_health.py (6) |
| L1 | Recovery | `Supervisor`, `RestartPolicy`, `RecoveryState` | test_recovery.py (2) |
| L2 | Config | `ConfigLoader`, `ImmutableConfigSnapshot`, `load_config` | test_config.py (9) |
| L2 | Logging | `StructuredLogger`, `configure_root_logger`, `get_logger` | test_logging_redaction.py (5) |
| L2 | Correlation | `CorrelationContext`, `new_correlation` | test_correlation.py (6) |
| L2 | Event Bus | `CoreEventBus`, `EventEnvelope`, `Topic`, `Priority` | test_event_bus.py (9) |
| L2 | Crypto/Redact | `Redactor`, `FileSecretVault`, `Hasher`, `redact_value`, `secret_ref` | test_logging_redaction.py + test_config.py cover |
| L2 | Scheduler/Tasks | `BackgroundTaskManager`, `RetryPolicy`, `run_with_retry` | test_background_tasks.py (8) |
| L2 | Persistence | `SQLiteKVStore`, `SQLiteDocStore`, `NoOp*` stubs | skeleton only; L4 will extend |
| L2 | Plugin | `PluginLoader`, `PluginManifest`, `SandboxTier` | skeleton only; deny-by-default enforced |

---

## 2. L1 — Core Runtime API

### 2.1 CoreRuntime

```python
from aegis import CoreRuntime, ServiceInfo, RuntimeState

rt = CoreRuntime(
    startup_timeout=30.0,       # seconds; applied during start() await
    shutdown_timeout=10.0,      # seconds; applied during stop() await
    instance_id="my-instance",  # optional; else auto-generated in config (uuid prefix)
)

sid = rt.register_service(
    service_object,                       # implements Service interface (initialize/start/stop/health)
    depends_on=[sid0, sid1, ...],         # string IDs of prerequisites; raises NotFoundError(E10110) IMMEDIATELY if missing
    info=ServiceInfo(
        service_id="foo",                 # MUST be unique string; is the returned sid slot key
        name="Foo Service",
        version="0.1.0",
    ),
)
# sid == "foo" returned here; rt.slots["foo"] populated as ServiceSlot

async with CorrelationContext.new().enter():
    await rt.start()    # CREATED → INITIALIZING (topological) → STARTING → RUNNING
    assert rt.state == RuntimeState.RUNNING

    state: RuntimeState = rt.state
    overall: HealthState = await rt.overall_health()  # returns HealthState (uses registered HealthAggregator)

    await rt.stop()     # RUNNING → STOPPING → STOPPED; reverse topological teardown
    assert rt.state == RuntimeState.STOPPED

# Double-start prevented: raises AegisError E10101
# stop() when not started: no-op
```

**Health Aggregator Registration (optional but recommended):**
```python
rt.register_health_aggregator(aggregator: HealthAggregator)
# This causes rt.overall_health() to use agg.check_all() aggregation.
# Internal runtime services (2 of them) are auto-registered when you call this. They may return UNKNOWN
# in P02. For assertions in tests/examples, only check YOUR registered components, not overall.
```

---

### 2.2 Dependency Injection

#### Registration conventions (TWO accepted — use whichever fits):

```python
from aegis import DIContainer, Lifetime, Scope

di = DIContainer()

# Convention A (factory 2nd, lifetime keyword)
di.register("foo", lambda: Foo(), lifetime=Lifetime.SINGLETON, dependencies=("bar",))
# Convention B (lifetime 2nd, factory 3rd — used by tests & example)
di.register("foo", Lifetime.SINGLETON, lambda b: Foo(b), deps=["bar"])
# deps= and dependencies= both work.

# Lazy lifetime: injects Lazy[T], resolved on .value access
# Factory lifetime: injects Callable[[], T], user invokes to create
# Transient: new every resolve
# Singleton: one per container, closed when container aclose/close
# Scoped: one per Scope instance, closed on scope aclose/close

s = di.create_scope()        # first-created scope = root scope for singleton resolution stacks
foo = s.resolve("foo")       # triggers resolution + construct
s.close()                    # DISPOSE scoped instances that have close() or aclose() (sync)
await s.aclose()             # async form

di.close()                   # sync root close: closes root_scope then all singletons with close/aclose
await di.aclose()            # async form
```

Circular detection: any cycle detected during resolve() inside a scope → ResolutionError E10202 with path.

---

### 2.3 Errors

#### Dual Call Convention (IMPORTANT):

```python
from aegis import AegisError, ValidationError, ErrorCode, ErrorSeverity

# Convention A (classic): (message, *, error_code, …)
raise ValidationError("bad value", error_code="E20104")

# Convention B (entry-first): (ErrorCodeEntry, message, …) — auto maps code, severity, retry hint
raise ValidationError(ErrorCode.E20104, "logging.format invalid: xml")
raise ValidationError(ErrorCode.CONFIG_SECRET_REF_INVALID, "ref broken")  # same entry, both forms work

# Forms below are EQUIVALENT (resolution):
assert ErrorCode.CONFIG_SECRET_REF_INVALID is ErrorCode.E20104   # → True  (BOOTSTRAPPED ALIASES)
assert ErrorCode.CONFIG_SECRET_REF_INVALID.code == "E20104"      # → True
```

Error taxonomy:
```
AegisError (root)
├─ InitializationError  (E10105 HIGH RETRY_TRANSIENT)
├─ LifecycleError
│  ├─ StartupTimeoutError   E10103 NO_RETRY
│  ├─ ShutdownTimeoutError  E10104 NO_RETRY
│  └─ RuntimeShutdownError  E10102 NO_RETRY
├─ ConfigurationError (E20101 HIGH NO_RETRY)
├─ ValidationError    (E00003)
├─ NotFoundError      (E00004)
├─ EventBusError      (E20201)
├─ ExecutionError     (E00001 forward-declared L3)
├─ StoreError         (E20401 RETRY_TRANSIENT)
├─ TimeoutError       (E00002 RETRY_BACKOFF)
├─ RecoveryError      (E10111 HIGH)
└─ InternalError      (E00001 CRITICAL)
```

All errors support: `.to_dict(redact_sensitive=True)`, `.error_code (str)`, `.severity (ErrorSeverity)`, `.retry_hint`, `.context (ErrorContext)`, `.__cause__`.

---

### 2.4 Health

```python
from aegis import HealthAggregator, HealthState, HealthReport

agg = HealthAggregator(default_timeout_seconds=1.0)

# Register check_fn that returns dict {"status": "healthy|degraded|unhealthy|unknown", …any extra fields}
async def db_check() -> dict:
    ok = await ping_db()
    return {"status": "healthy" if ok else "unhealthy", "latency_ms": 12}

agg.register_check("db", db_check, timeout_seconds=2.0)

report: HealthReport = await agg.check_all(aggregate_timeout=3.0)

report.overall                          # HealthState (worst-of: UNHEALTHY>DEGRADED>UNKNOWN>HEALTHY)
report.components                       # list[ComponentHealth], ITERABLE DIRECTLY
for c in report.components:             # → ComponentHealth objects, NOT keys
    c.component, c.state, c.latency_ms, c.details, c.error, c.checked_at

report.by_component                     # dict[str, ComponentHealth]  (NEW property; do not assume order)
report.summary()                        # counts + metadata
```

---

### 2.5 Supervisor / Recovery

```python
from aegis import Supervisor, RestartPolicy, RestartPolicyKind
from aegis.l1_core.supervisor import backoff_seconds

policy = RestartPolicy(
    kind=RestartPolicyKind.ON_FAILURE,
    max_attempts=5,
    base_backoff_seconds=0.25,
    max_backoff_seconds=10.0,
    backoff_multiplier=2.0, jitter_fraction=0.1,  # full names
    # ALSO ACCEPT SHORT: multiplier=2.0, jitter=0.1
    reset_after_seconds=60.0,
)

sup = Supervisor(
    restart_policy=policy,
    watchdog_interval_seconds=0.5,  # also accepts short alias: watchdog_interval=0.5
    on_recovery_hook=...,
    on_failure_give_up=...,
)

# restart_fn accepts EITHER 0-arg or 1-arg (service_id: str). Convention detection is automatic.
async def my_restart(service_id: str):   # 1-arg form works
    await restart_my_svc(service_id)

sup.register(
    my_service,
    service_id="my-svc",
    policy=policy,                       # or restart_policy=policy; both work
    get_state_fn=lambda: my_slot.state,  # MUST return ServiceState enum value
    restart_fn=my_restart,               # or None → uses _default_restart (stop+initialize+start)
)

await sup.start()   # starts async watchdog loop in background task
# ...
await sup.stop()

rs = sup.recovery_state("my-svc")  # RecoveryState (consecutive_failures, total_restarts, history…)
await sup.force_recover("my-svc")  # manual trigger + reset counter (optionally with max_attempts_override)
```

---

## 3. L2 — Foundation

### 3.1 Configuration

```python
from aegis import ConfigLoader, ImmutableConfigSnapshot, load_config

snap: ImmutableConfigSnapshot = ConfigLoader(
    defaults=...,     # optional user layer-0 overrides (above built-in defaults)
    file_path="config.yaml",   # or None → attempt standard locations (cwd/config.yaml or examples/config.example.yaml)
    env_prefix="AEGIS_",
).build(
    runtime_overrides={"aegis": {"instance_id": "override-id"}}  # highest layer
)

# Layer priority: BUILTIN_DEFAULTS < user defaults < FILE (.yaml/.json) < ENV(AEGIS_* with __ as section splitter) < runtime_overrides < ConfigLoader.set_runtime_override(...)
# Environment variable: AEGIS_LOGGING__LEVEL=DEBUG → snap.logging["level"] == "DEBUG"

# Attribute access → deep copies (mutate returned dict, snapshot unaffected)
flags = snap.feature_flags
flags_again = snap.feature_flags
assert flags is not flags_again      # guaranteed distinct

# Accessors:
snap.get("logging", "level")                 # deep-copied value, with defaults fallback
snap.has_feature("new_ui")
snap.feature("new_ui", default=False)
snap.log_level()                             # → LogLevel enum
snap.data_dir()                              # → Path (resolved; creates if needed)
snap.resolve_secret("scope", "key")          # → plaintext str from FileSecretVault
snap.resolve("secret://file/db_password")    # shorthand
snap.as_dict_raw()                           # deep copy, includes secret:// refs unresolved
snap.as_dict_safe()                          # deep copy, secret:// refs redacted to "<SECRET_REF>"

# Mutate config at runtime (applies to FUTURE .build() calls from same loader — not existing snapshots):
loader = ConfigLoader()
loader.set_runtime_override("logging.level", "DEBUG")   # dotted path
loader.clear_runtime_overrides()
```

Validation performed on every `.build()` (if fails → raises `ValidationError(ErrorCode.E20104, …)`):
- `schema_version` int ≥ 1
- `paths.data_dir` present (auto-resolved in _resolve_paths so shouldn't fail)
- `logging.level` parseable
- `logging.format` ∈ {development, json}
- `aegis.shutdown_timeout_seconds`, `aegis.startup_timeout_seconds` > 0 numeric

---

### 3.2 Structured Logging

```python
from aegis import StructuredLogger, configure_root_logger, LogLevel, get_logger
from pathlib import Path

configure_root_logger(level=LogLevel.INFO, format="json", file=Path("app.log"))

log: StructuredLogger = get_logger("mymodule")
log.info("hello", key1="value1", key2=2)
# JSON → {"event": "hello", "key1": "value1", "key2": 2, "logger": "mymodule", "level": "info",
#         "correlation_id": str (from context), "timestamp": ISO, ...}
try:
    risky()
except Exception as exc:
    log.error("it failed", exc_info=exc)   # → adds error field with type+msg+stack
```

Correlation context auto-injects correlation_id/request_id/task_id into every log record produced inside the context manager span.

Redaction: before serialization into log payload, redactor regex-scrubs known patterns (API keys, passwords, JWT, PII, credit cards, private keys, secret://) → `<REDACTED>` or `<SECRET_REF>`.

---

### 3.3 Correlation Context (PEP 567)

```python
from aegis import CorrelationContext, new_correlation

with new_correlation(metadata={"source": "cli"}) as ctx:
    # All code within this block (including async functions awaited here) inherits ctx.correlation_id
    str(ctx.correlation_id)  # UUID
    ctx.request_id, ctx.task_id, ctx.parent_operation_id, ctx.metadata

    with CorrelationContext.new(inherit=False, metadata={"sub": "op"}).enter() as inner:
        pass  # fresh, not inherited

    with CorrelationContext.fork(metadata={"sub2": "op2"}).enter() as child:
        pass  # child inherits parent correlation_id by default
```

Cross-boundary:
```python
d = ctx.as_dict()  # → serialisable dict for IPC / queue
ctx2 = CorrelationContext.from_dict(d)
```

---

### 3.4 Event Bus

```python
from aegis import CoreEventBus, EventEnvelope, DEFAULT_TOPIC, Priority, Topic

bus = CoreEventBus(durable=False, dead_letter_enabled=True, persistence_path=None, max_history=100_000)
bus.start()

received: list[EventEnvelope] = []
def handler(ev: EventEnvelope) -> None:
    received.append(ev)

bus.subscribe(
    topic=DEFAULT_TOPIC,          # Topic(...) object or string name
    handler=handler,              # sync or async callable — both supported
    priority=Priority.NORMAL,     # LOW → NORMAL → HIGH → CRITICAL (execution order for same publish)
    predicate=None,               # optional fn(ev) -> bool to skip
)

bus.publish(
    ev_or_type=dict or EventEnvelope or "my.type.string",
    payload={"a": 1},
    topic=DEFAULT_TOPIC,
    priority=Priority.NORMAL,
)
# EventEnvelope: event_id (UUID), type, payload, metadata, correlation_id, timestamp, priority, source, topic

# DLQ: handler failure → enqueue bus.dead_letter_queue (list[EventEnvelope]) if enabled.
# Durable mode (durable=True + persistence_path set) → SQLite append log → replay() returns list of historical envelopes.
# Unsubscribe works with the subscription handle returned from subscribe().

await bus.astop()   # graceful (in-flight handlers drained)
```

---

### 3.5 Background Tasks / Retry

```python
from aegis import BackgroundTaskManager, RetryPolicy, TaskState, TaskInfo, run_with_retry

btm = BackgroundTaskManager(
    event_bus=None,
    default_retry=RetryPolicy(max_attempts=3, base_backoff_seconds=0.25, max_backoff_seconds=10.0, multiplier=2, jitter=0.1),
    max_workers=8,   # concurrency cap via semaphore (internal)
)
btm.start()

loop = asyncio.get_running_loop()

async def work() -> str:
    await asyncio.sleep(0.1)
    return "done"

tid = btm.submit(
    loop, work, name="mywork",
    retry=RetryPolicy(max_attempts=1),   # optional override
    on_success=lambda info: ...,
    on_failure=lambda info: print(info.last_error),
)
info: TaskInfo | None = btm.get(tid)
# info.state: TaskState (PENDING / RUNNING / SUCCEEDED / FAILED / CANCELLED)
# info.name, info.result, info.attempts, info.last_error, info.created_at / started_at / finished_at

btm.cancel(tid)               # sends cancel to running task
await btm.graceful_shutdown(timeout=5.0)  # drains queue then waits; stops accepting new

# Standalone retry decorator:
result = await run_with_retry(
    work,
    policy=RetryPolicy(max_attempts=5),
    retryable_exceptions=(IOError, TimeoutError),  # optional whitelist; default = any Exception
)
# Exponential backoff with full jitter applied between retries.
# Raises last exception after max_attempts exhausted.
```

---

## 4. Prompt 02 Extensions (Building Prompt 03 on P02)

To add modules in Prompt 03 AI Kernel, abide by these rules (from Prompt 01 architecture docs):

1. **Dependency direction**: `aegis.l3_kernel.*` imports ONLY `aegis.l1_core.*` interfaces, `aegis.l2_foundation.*` public APIs. Never concrete L1/L2 internal file layout (except explicitly exported interfaces).
2. **All exceptions** cross module boundaries only as AegisError subclasses with an error_code from appropriate layer (L3 = E3…).
3. **All new L3 services** implement `Service` interface; register with CoreRuntime via register_service with explicit depends_on strings.
4. **Use DI Lifetime.SCOPED** for per-request resolution of anything user-facing. Prompt 04 Memory is heavily scoped-tiered (T0 Working needs request scope).
5. **Use CorrelationContext** around every L3 pipeline stage invocation so that logs, events, and errors carry the right correlation_id.
6. **HealthAggregator**: register L3 model-router checks with sensible timeouts (0.5s per provider).
7. **Supervisor**: register model provider services with short watchdog if using streaming sockets that can silently die.

---

## 5. Known Gaps / Future-Facing

- `ImmutableConfigSnapshot` has no `.rebuild(...)` or `ConfigLoader.reload()` public API. Add only if Prompt 02 test requirements explicitly demand (currently not tested).
- Rust FFI Python fallbacks are currently the only exercised paths (aegis_crypto bindings not imported by anything P02).
- `HealthAggregator.snapshot()` (last-seen state) still uses dict-based empty last state; can extend to retain real last components later.
- Supervisor `on_recovery_hook` / `on_give_up` accept sync or async via _maybe_await, but hooks return values are discarded. Correct for P02.
