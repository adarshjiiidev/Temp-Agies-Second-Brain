# PROJECT AEGIS — CURRENT STATE

> ## ⚠️ SUPERSEDED / OUT OF DATE — READ THIS FIRST
>
> On **2026-08-07** a full repository audit was performed (see [`AEGIS_MASTER_AUDIT.md`](./AEGIS_MASTER_AUDIT.md)).
> This file was accurate as of the Prompt 05 Recovery milestone, but the repository has since **moved on**:
> - **L6 is now implemented** (this file's §1/§2 say "L6 NOT STARTED / Prompt 06 not authorised") — this is WRONG.
> - The full test suite **was hanging at L5 integration — FIXED on 2026-08-07 (STAB-01)**. It now completes
>   (~8s): 793 tests on system python, 782 on `.venv` python (pytest/pytest-anyio collection difference).
> - Ruff is now **642** issues (this file says 281).
> - The roadmap defines **23** prompts, not 21.
> - Redesign packages (`reasoning`, `prompts`, `capabilities`) exist on disk.
>
> **The repository is the source of truth.** For current numbers use `AEGIS_MASTER_AUDIT.md`. The detailed
> component inventory (§3) below remains largely useful and is retained for reference.

## 1. Project Status

| Field | Value |
|---|---|
| Project Code Name | AEGIS (Adaptive Executive Governance & Intelligence System) |
| Full Name | Personal Adaptive AI Operating System |
| Current Milestone (docs) | **Prompt 05 — Execution Engine** (COMPLETE, verified) |
| Actual State | **L1–L6 + redesign pkgs implemented** (see top banner + AEGIS_MASTER_AUDIT.md) |
| Next Milestone | Prompt 07 (awaits explicit directive) |
| Total Prompts Planned | 23 per roadmap (docs/09_ROADMAP.md) |
| Working Baseline | HEAD (all fixes applied) |
| Repository Health | **Full suite passes (~8s) since 2026-08-07 STAB-01: 793 tests on system python (782 on `.venv` python); ruff 642; mypy blocked by Windows policy; cargo not installed** |

---

## 2. Milestone Status Matrix

| Prompt | Milestone | Status | Tests | Notes |
|---|---|---|---|---|
| P01 | Foundation Docs & Architecture | ✅ COMPLETE | N/A | 11 docs, ADRs, roadmap, architecture |
| P02 | L1 Core Runtime + L2 Foundation | ✅ COMPLETE | 57/57 | 15 bugs fixed (B1–B15) |
| P03 | AI Kernel (L3) | ✅ COMPLETE | 131/131 | Router, registry, accounting, cache, structured output, scrubber, keys |
| P04 | Memory & Knowledge (L4) | ✅ COMPLETE | 238/238 | Store, graph, context, search, policies, markdown, P0 invariants |
| P05 | Execution Engine (L5) | ✅ COMPLETE | 120/120 | Pipeline, permission, policy, audit, sandbox, executors, rollback; 1 bug fixed (B-L5-001) |
| P06 | Planning (L6) | ✅ IMPLEMENTED (post-P05 Recovery audit) | 180 | Planning engine, 11 subpackages; full suite passes since 2026-08-07 STAB-01 |

### Layer Boundary (Verified)

| Layer | Name | Status |
|---|---|---|
| L1 | Core Runtime | ✅ Complete + Verified |
| L2 | Foundation | ✅ Complete + Verified |
| L3 | AI Kernel | ✅ Complete + Verified |
| L4 | Memory / Knowledge | ✅ Complete + Verified |
| L5 | Execution Engine | ✅ Complete + Verified |
| L6 | Planning / Agents | ✅ Implemented (see top banner) |
| L7 | HCI / UI | 🔲 NOT STARTED |

---

## 3. Completed Components (Prompts 01–05)

### L1 CORE RUNTIME LAYER

| Component | Status | Verification | Key Files |
|---|---|---|---|
| **Runtime Lifecycle FSM** | ✅ COMPLETE | 6 tests pass; example runs end-to-end | [runtime.py](file:///C:/Users/adars/Projects/AGIES/src/aegis/l1_core/runtime.py) |
| — States: CREATED → INIT → START → RUN → STOP → STOPPED | ✅ | test_runtime_lifecycle.py 6/6 | `RuntimeState` enum |
| — Partial INIT rollback | ✅ | test_partial_initialization_rollback | `_topological()` + rollback loop |
| — Dep topological sort (Kahn) | ✅ | test_dependency_topological_missing_raises | `_topological()` inside runtime.py |
| — Reverse-order teardown | ✅ | test_created_to_running_to_stopped (observes stop order via rec) | runtime.py `stop()` |
| — Missing dep → NotFoundError E10110 at register time | ✅ (FIXED) | test_dependency_topological_missing_raises | `register_service()` immediate validation |
| **Dependency Injection** | ✅ COMPLETE | 7/7 tests pass | [container.py](file:///C:/Users/adars/Projects/AGIES/src/aegis/l1_core/di/container.py) |
| — Lifetimes: SINGLETON, SCOPED, TRANSIENT, FACTORY, LAZY | ✅ | 5 tests for each lifetime behaviour | `Lifetime` enum |
| — Circular dep detection (per scope resolution stack) | ✅ | test_circular_dependency_raises | Scope._resolving stack + lock |
| — Scope sync + async close (both) | ✅ (FIXED) | test_scope_close_calls_close_on_instances | Scope.close() sync, Scope.aclose() async |
| — DIContainer sync + async close | ✅ (FIXED) | No RuntimeWarnings in close paths | DIContainer.close() sync + aclose() |
| — register() dual convention (positional factory or positional lifetime) | ✅ (FIXED) | All 7 DI tests use convention B | DI.register() 2nd-arg duck typing |
| — Both `deps=` and `dependencies=` kwargs | ✅ | Mixed tests use both | register() signature accepts both |
| **Typed Error Hierarchy** | ✅ COMPLETE | Config + Runtime + DI use it correctly | [base.py](file:///C:/Users/adars/Projects/AGIES/src/aegis/l1_core/errors/base.py) |
| — AegisError root with severity/retry/code | ✅ | Error used throughout L1/L2 | severity MEDIUM default; retry NO_RETRY default |
| — Dual call convention (message OR ErrorCodeEntry first) | ✅ (FIXED) | test_invalid_logging_format_rejected | `AegisError.__init__` detects ErrorCodeEntry type |
| — Symbolic + numeric ErrorCode access | ✅ (FIXED) | test_invalid_logging_format_rejected uses ErrorCode.E20104 | ErrorCode bootstrap aliases every code |
| **Error Codes Registry** | ✅ COMPLETE | All codes prefixed E{layer}{cat}{seq} | [codes.py](file:///C:/Users/adars/Projects/AGIES/src/aegis/l1_core/errors/codes.py) |
| — L1 Lifecycle E101xx, DI E102xx, L2 Config E201xx, Event E202xx, Scheduler E203xx, Store E204xx, Crypto E205xx, Plugin E206xx, Generic E000xx | ✅ | 30+ codes defined, registry auto-built | ERROR_CODE_REGISTRY dict |
| — `ErrorCode.VALIDATION_FAILED` ↔ `ErrorCode.E20104` equivalence | ✅ | Config tests confirm both forms resolve to same ErrorCodeEntry | Bootstrap `setattr(cls, val.code, val)` |
| **Health Monitoring** | ✅ COMPLETE | 6/6 tests pass (anyio asyncio+trio) | [registry.py](file:///C:/Users/adars/Projects/AGIES/src/aegis/l1_core/health/registry.py) |
| — 4 states: HEALTHY, DEGRADED, UNHEALTHY, UNKNOWN | ✅ | test_four_states_exist | HealthState enum |
| — Aggregation order: UNHEALTHY > DEGRADED > UNKNOWN > HEALTHY | ✅ | Observed in report assertions | `_aggregate()` helper |
| — `HealthAggregator.check_all(aggregate_timeout=)` parameter | ✅ (FIXED) | test_timeout uses kwarg aggregate_timeout=2.0 | check_all signature |
| — Per-check timeout + aggregate timeout | ✅ | test_timeout_turns_into_unhealthy_or_degraded × 2 backends | Both paths wrapped in asyncio.timeout |
| — HealthReport.components is list[ComponentHealth] | ✅ (FIXED) | test iterates `{c.component for c in report.components}` | HealthReport dataclass |
| — .by_component dict accessor | ✅ | Used in example now | @property by_component |
| **Supervisor / Recovery** | ✅ COMPLETE | 2/2 recovery tests pass (anyio asyncio+trio) | [supervisor.py](file:///C:/Users/adars/Projects/AGIES/src/aegis/l1_core/supervisor.py) |
| — Watchdog per-service state polling | ✅ | recovery_started.wait() returns within 2s before timeout | _watchdog_loop sleep then _tick |
| — RestartPolicy kind NEVER / ON_FAILURE / ALWAYS | ✅ | Uses ON_FAILURE in test_supervisor | RestartPolicyKind enum |
| — Exponential backoff + jitter | ✅ | max_backoff cap + multiplier × base + jitter | `backoff_seconds()` deterministic attempt |
| — Dual kwarg policy aliases (multiplier= ↔ backoff_multiplier=, jitter= ↔ jitter_fraction=) | ✅ (FIXED) | RestartPolicy tests pass both names | RestartPolicy.__init__ manual |
| — Supervisor watchdog_interval alias (watchdog_interval= ↔ watchdog_interval_seconds=) | ✅ (FIXED) | test passes watchdog_interval=0.005 | Supervisor.__init__ |
| — register() policy= or restart_policy= kwarg | ✅ (FIXED) | test passes policy=policy | Supervisor.register accepts both |
| — restart_fn(sig): dual convention (accepts service_id arg or not) | ✅ (FIXED) | test restart_fn(service_id: str) signature works | try(sid) / except TypeError → retry no args |
| — _default_restart accepts *args | ✅ (FIXED) | _do(*args, **kwargs) | Correct return type Callable[..., Awaitable] |
| — Max attempts + give-up hook | ✅ | consecutive_failures >= policy.max_attempts triggers on_give_up | consecutive_failures counter |
| **Core Interfaces** | ✅ COMPLETE | All L1/L2 implement Service interface | [base.py](file:///C:/Users/adars/Projects/AGIES/src/aegis/l1_core/interfaces/base.py) |
| — Service.initialize / start / stop / health | ✅ | Runtime calls them in order; service tests mock them | Service protocol |
| — HealthProvider, ModuleLifecycle, Pluggable, ServiceInfo | ✅ | All exported from aegis top-level package | aegis.__init__ __all__ |

### L2 FOUNDATION LAYER

| Component | Status | Verification | Key Files |
|---|---|---|---|
| **Configuration System** | ✅ COMPLETE | 9/9 config tests pass | [loader.py](file:///C:/Users/adars/Projects/AGIES/src/aegis/l2_foundation/config/loader.py) |
| — Layered priority: DEFAULTS < FILE < ENV(AEGIS_) < OVERRIDES | ✅ | test_defaults, test_file_overrides_defaults, test_env_overrides_file, test_runtime_override_applied | ConfigLoader.build() 4-way merge |
| — _resolve_paths: None-aware defaults (not setdefault) | ✅ (FIXED) | Previously caused 8 config tests to fail (fixed: paths were ~/.aegis/data_dir instead of full) | explicit `if not paths.get(key):` |
| — Immutable snapshot: direct attr access deep-copies containers | ✅ (FIXED) | test_snapshot_is_immutable_via_accessors: flags is not flags_again + mutation isolation | `__getattribute__` interceptor for _DICT_FIELDS |
| — Validation: schema_version, paths.data_dir, log level, logging.format, timeouts positive | ✅ | test_invalid_logging_format_rejected rejects bad format | _validate() 5 checks |
| — Secrets store file-backed: data_dir/.env.aegis (scope.key=value) | ✅ | test_secret_store_roundtrip_via_config | _EnvAegisSecretsStore.load() |
| — secret:// scope/id refs never resolved into raw snapshot; as_dict_safe redacts | ✅ | test_secret_ref_not_inlined_in_loggable_dict + L4 Crypto redact | is_secret_ref + _walk() redaction |
| — ConfigLoader.set_runtime_override dotted paths | ✅ | test_runtime_override_applied sets "aegis.instance_id" | set_runtime_override() splits "." |
| **Structured Logging / Telemetry** | ✅ COMPLETE | 5/5 tests pass | [logger.py](file:///C:/Users/adars/Projects/AGIES/src/aegis/l2_foundation/telemetry/logger.py) |
| — StructuredLogger: development (console) + json formatters | ✅ | test_structured_logger_json_has_correlation_and_fields | JSONFormatter + DevelopmentFormatter |
| — Log level filter + parse_level enum | ✅ | test_log_level_filters | LogLevel enum + parse_level |
| — Exceptions logged as structured "error" field | ✅ | test_exception_logged_as_error_field | logger.error + exc_info=True capture |
| — Context propagation (correlation_id, request_id, task_id, metadata) | ✅ | test_correlation 6/6 tests; asyncio.gather + trio + sync | [context.py](file:///C:/Users/adars/Projects/AGIES/src/aegis/l2_foundation/telemetry/context.py) PEP 567 contextvar |
| — new_correlation / fork / enter restores prior | ✅ | test_fork_inherits_correlation_id_by_default, test_enter_restores_previous | CorrelationContext CM |
| **Event Bus** | ✅ COMPLETE | 9/9 tests pass (sync + anyio 2 backends) | [core.py](file:///C:/Users/adars/Projects/AGIES/src/aegis/l2_foundation/event_bus/core.py) |
| — Topic + publish / subscribe + unsubscribe | ✅ | test_publish_sync_collects_to_handlers × 9 bus tests | CoreEventBus class |
| — Sync + Async handler dispatch | ✅ | test_async_handler_invoked × 2 backends | inspect coroutinefunction or sync callable |
| — Handler priority (low → high order execution) | ✅ | test_handler_order_low_to_high | Priority enum LOW/NORMAL/HIGH/CRITICAL |
| — Handler failure → Dead Letter Queue | ✅ | test_handler_failure_moves_to_dlq | EVENT_DLQ_ENQUEUED code E20202 |
| — SQLite-backed durable topics + replay | ✅ | test_sqlite_durable_replay × 2 backends | aiosqlite append-log in event_bus.db |
| — Typed EventEnvelope | ✅ | Test assertions verify envelope structure | EventEnvelope dataclass |
| **Crypto / Secrets / Redaction** (L2 scope only) | ✅ COMPLETE | + logging tests cover | [redact.py](file:///C:/Users/adars/Projects/AGIES/src/aegis/l2_foundation/crypto/redact.py) / [vault.py](file:///C:/Users/adars/Projects/AGIES/src/aegis/l2_foundation/crypto/vault.py) |
| — Pattern-based redaction: API key, password, JWT, Aadhaar, PAN, credit card, private key, secret:// refs | ✅ | test_redact_redacts_api_key_and_password + secret_ref_redacted | regex-based |
| — FileSecretVault (file-backed) scope.key KV | ✅ | Config tests use | FileSecretVault class |
| — Hasher (SHA256 / HMAC) FFI-bound | ✅ | Declared in crypto __init__; FFI via Rust crates | aegis_crypto Rust crate |
| **Background Tasks / Scheduler** | ✅ COMPLETE | 10/10 tests pass (5 asyncio + 5 trio) | [background.py](file:///C:/Users/adars/Projects/AGIES/src/aegis/l2_foundation/scheduler/background.py) |
| — BackgroundTaskManager + TaskInfo + TaskState | ✅ | Tests submit/cancel/result/attempts all | BTM class |
| — Submit + cancel | ✅ | test_cancel_stops_running_task × 2 | cancel() + _tasks[tid].task.cancel() |
| — on_failure hook | ✅ | test_failed_task_invokes_on_failure_hook × 2 | _run catch exception → on_failure callback |
| — RetryPolicy (max_attempts, backoff multiplier, jitter) + run_with_retry | ✅ | test_retry_policy_backoff_grows, test_run_with_retry_succeeds_after_retries × 2 | RetryPolicy dataclass + run_with_retry() |
| — Graceful shutdown timeout | ✅ | Example & tests verify | btm.graceful_shutdown(timeout=2.0) |
| **Persistence** (L2 skeleton only) | ✅ COMPLETE | Interfaces only; no vector store or KG yet | [sql.py](file:///C:/Users/adars/Projects/AGIES/src/aegis/l2_foundation/persistence/sql.py) |
| — SQLiteKVStore / SQLiteDocStore (aiosqlite) | ✅ | NoOpGraphStore / NoOpVectorStore stubs defined, never hit by P02 tests | Persistence interfaces only |
| **Plugin Loader** (L2 skeleton only) | ✅ COMPLETE | Manifest + permission unknown → deny | [loader.py](file:///C:/Users/adars/Projects/AGIES/src/aegis/l2_foundation/plugin_loader/loader.py) |
| — Permission model sandbox tier | ✅ | PLUGIN_PERMISSION_UNKNOWN E20603 high severity deny | PluginLoader |

### RUST FFI CRATES (Prompt 02 skeleton)

Three crates declared in /crates. Cargo not installed on this machine → cannot verify `cargo check`, but all are skeleton and no FFI symbols are called by P02 Python tests (FFI-optional paths).

| Crate | Purpose | Status |
|---|---|---|
| `aegis_ffi_common` | FFI-shared AegisId UUID + FfiError structs | ✅ Skeleton per Prompt 01 (not yet used in tests) |
| `aegis_crypto` | SHA256 / HMAC-SHA256 / AES-256-GCM encrypt+decrypt + PyO3 bindings | ✅ Skeleton (Python hashlib fallback paths exist; crypto Hasher class exported but not yet imported in tests) |
| `aegis_audit_chain` | Append-only hash chain for audit | ✅ Skeleton (Prompt 02 scope only) |

_Rust verification status: BLOCKED — cargo.exe not on PATH. Install Rust toolchain then run `cd crates && cargo check --workspace`._

### L3 AI KERNEL LAYER (Prompt 03)

| Component | Status | Tests | Key Files |
|---|---|---|---|
| **Model Provider Registry** | ✅ COMPLETE | 131 total | `l3_kernel/providers/registry.py` |
| **Router (local-first + cloud fallback)** | ✅ COMPLETE | | `l3_kernel/router/` |
| **Cost / Budget Accounting** | ✅ COMPLETE | | `l3_kernel/accounting/` |
| **Response Cache** | ✅ COMPLETE | | `l3_kernel/cache/` |
| **Structured Output Parser** | ✅ COMPLETE | | `l3_kernel/structured/` |
| **Output Scrubber (PII/secret redaction)** | ✅ COMPLETE | | `l3_kernel/scrubber/` |
| **API Key Manager** | ✅ COMPLETE | | `l3_kernel/keys/` |

### L4 MEMORY & KNOWLEDGE LAYER (Prompt 04)

| Component | Status | Tests | Key Files |
|---|---|---|---|
| **MemoryManager (CRUD + tiers T0–T8)** | ✅ COMPLETE | 238 total | `l4_memory/manager.py` |
| **SearchEngine (keyword, metadata, hybrid)** | ✅ COMPLETE | | `l4_memory/search.py` |
| **ContextBuilder + ContextPackage** | ✅ COMPLETE | | `l4_memory/context.py` |
| **MemoryPolicy (retention, decay, archival, merge)** | ✅ COMPLETE | | `l4_memory/policies.py` |
| **P0 Privacy Invariant** | ✅ COMPLETE | | `tests/integration_l4/test_privacy_p0.py` |
| **Markdown Loader** | ✅ COMPLETE | | `l4_memory/loaders/markdown.py` |

### L5 EXECUTION ENGINE (Prompt 05)

| Component | Status | Tests | Key Files |
|---|---|---|---|
| **ExecutionPipeline (7 stages)** | ✅ COMPLETE | 120 total | `l5_execution/pipeline.py` |
| **PermissionEngine (SVRC deny-by-default)** | ✅ COMPLETE | | `l5_execution/permission/engine.py` |
| **PolicyEngine + BUILTIN_RULES** | ✅ COMPLETE + **B-L5-001 FIXED** | | `l5_execution/policy/rules.py` |
| **RiskAnalyzer (weighted factors)** | ✅ COMPLETE | | `l5_execution/risk/analyzer.py` |
| **AuditChain (hash-chain, tamper-evident)** | ✅ COMPLETE | | `l5_execution/audit/chain.py` |
| **SandboxManager (T1–T3 active, T4 stub)** | ✅ COMPLETE | | `l5_execution/sandbox/manager.py` |
| **Executors (FS, Shell, Git, HTTP, Docker, Browser, Desktop, Python, VSCode, Obsidian)** | ✅ COMPLETE | | `l5_execution/executors/` |
| **RollbackEngine** | ✅ COMPLETE | | `l5_execution/rollback/engine.py` |
| **PostExecVerifier** | ✅ COMPLETE | | `l5_execution/verify/assertions.py` |

---

## 4. Incomplete Components

_Components through L5 implement a verified 7-stage pipeline. The full suite was found hanging at L5
integration in the 2026-08-07 audit; that hang was FIXED (STAB-01, same day) and the full suite now passes.
L6 was implemented after this file's last update._

**Not yet started / incomplete:**
- AI reasoning provider wiring (`reasoning/` kernels broken/missing on `AIKernel`)
- Rust FFI crates — unverified (no Cargo); fail to compile once toolchain available
- L7 HCI / UI — future milestone
- T4 Firecracker sandbox — planned P08+
- Approval token pre-auth mechanism — planned (see TD-06)

---

## 5. Known Issues

### 5.1 Verified Bugs (all fixed; audit trail only)

| # | Bug | Layer | Root Cause | Fixed In |
|---|---|---|---|---|
| B1–B15 | L1/L2 Core Runtime bugs | L1/L2 | See P02 completion report | `PROMPT_02_COMPLETION_REPORT.md` |
| B-L5-001 | `test_approval_required_for_critical_without_confirm` | L5 | Policy rule `builtin-shell-sandbox` used `SANDBOX_REQUIRED` (allowed pipeline to proceed to Stage 6) instead of `NEEDS_APPROVAL`. Shell.exec at HIGH risk reached T2SubprocessSandbox which failed on Windows (echo is a shell builtin). Test expected `APPROVAL_REQUIRED` or `DENIED`, got `FAILED`. | `src/aegis/l5_execution/policy/rules.py`: changed `decision=PermissionDecision.SANDBOX_REQUIRED` → `decision=PermissionDecision.NEEDS_APPROVAL` on `builtin-shell-sandbox` rule. Two regression tests added. |

### 5.2 Known Technical Debt

| # | Issue | Severity | Notes |
|---|---|---|---|
| TD-01 | Ruff 281 lint issues in src + tests | LOW | Pre-existing: unused imports, import ordering (I001), unused vars (F841). All auto-fixable with `ruff --fix`. Not test-blocking. |
| TD-02 | mypy blocked by Windows Application Control policy | MEDIUM | DLL load failure blocks mypy. Run on Linux/macOS to validate strict types. |
| TD-03 | Cargo not installed → Rust FFI crates unverified | MEDIUM | Install rustup then `cargo check --workspace` in /crates. |
| TD-04 | T2SubprocessSandbox: shell builtins fail on Windows without `shell=True` | MEDIUM | `asyncio.create_subprocess_exec(["echo", "hello"])` fails on Windows — echo is a CMD builtin. Mitigated by B-L5-001 fix (shell.exec now requires approval so Stage 6 never reached in the affected test path). Needs proper fix when shell executor is used in production. |
| TD-05 | T4 Firecracker sandbox not implemented | LOW | `SandboxManager.build_context()` raises `NotImplementedError` for T4. Expected — planned for P08+. |
| TD-06 | `user_confirmed=True` does not bypass direct `NEEDS_APPROVAL` policy rules | MEDIUM | `user_confirmed` only bypasses the `force_approval_on_critical` override path. Direct NEEDS_APPROVAL rules always produce APPROVAL_REQUIRED regardless. A pre-approval token mechanism (future feature) would be needed to fully implement the confirmation flow. |

---

## 6. Architecture Decisions

### Authoritative ADR location: No separate ADR folder exists yet.
All decisions below are captured from code and 11 Prompt 01 docs. They are BINDING. Do not contradict without writing an ADR.

| ID | Decision | Constraints / Why | Depends On |
|---|---|---|---|
| ADR-P01-001 | Strict 7-layer downward-only dependencies. L1 imports no internal modules. L2 imports only from L1. L3 must import only interfaces from L1/L2, never concrete L1/L2 internals | Enforced by manual code review; no static arch-linter yet | All modules |
| ADR-P01-002 | 7-stage execution pipeline (Plan → Permission → Policy → Execute → Audit → Verify → Reflect) is L3+ ONLY | Prompt 02 does NOT authorise pipeline code even as skeleton | Prompt 03 Kernel |
| ADR-P01-003 | 9-tier memory hierarchy (T0 Working through T8 Skill) is L4 Memory ONLY | No memory code in P02 scope — persistence primitives in L2 only (SQLite/NoOp stubs) | Prompt 04 Memory |
| ADR-P01-004 | Never trust LLM output. All LLM-produced actions must traverse validation + approval gates BEFORE system modification. | No LLM integration in P02, but interfaces预留 (HealthProvider.error, ErrorContext.retry_hint) for future | Prompt 03+ |
| ADR-P01-005 | Local-first P0/P1/P2; cloud models only for P3+ with explicit routing. Secrets never leave device. | Crypto redaction active; secret:// refs; file vault; as_dict_safe() serialization | Security architecture |
| ADR-P01-006 | Rust FFI boundary: aegis_ffi_common → aegis_crypto / aegis_audit_chain / … | Python fallbacks exist; FFI optional. Python is the system of record. Rust FFI imports MUST be guarded with try/except ImportError. | crates/* |
| ADR-P01-007 | Runtime lifecycle is a strict FSM. Implicit transitions are forbidden. | RuntimeState enum + _validate_transition (via transitions in start/stop code). 6 tests verify boundary conditions. | runtime.py |
| ADR-P01-008 | Dependency graph services init via Kahn's algorithm topological sort; teardown in REVERSE order. | Partial init failure: rollback (stop/undo) only what succeeded. Verified by test_partial_initialization_rollback. | runtime._topological / start / stop |
| ADR-P01-009 | DI per-scope resolution stack circular detection; NO silent cycle-breaking; always raises. | Scope._resolving list guarded by RLock; raises ResolutionError E10202. | container.py Scope.resolve |
| ADR-P01-010 | Error codes taxonomy E{layer}{category}{seq}. ALL errors are AegisError subclass. No bare `raise Exception` across module boundaries. | 30+ error codes defined; registry built at import time; dual-symbol access | codes.py / base.py |
| ADR-P01-011 | Recovery is primitive only in P02: watchdog + max attempts + exponential backoff + give-up hook. LLM-assisted root-cause self-repair ships Prompt 08/21 only. | Supervisor `_tick` no AI paths; pure deterministic retry. supervisor.py docstring explicitly says this. | supervisor.py |
| ADR-P01-012 | Plugin permission UNKNOWN → DENY BY DEFAULT. No allowlist = no load. | PLUGIN_PERMISSION_UNKNOWN E20603 high severity | plugin_loader/loader.py |
| ADR-P01-013 | Config immutability: ImmutableConfigSnapshot frozen + dict attrs deep-copied on every access. | No user mutation of snapshot can affect subsequent reads. Verified via is-not-identity test. | loader.py _DICT_FIELDS __getattribute__ |

---

## 7. Verification Status (Exact commands, exact results)

### 7.1 Prompt 02 Baseline
```
python -m pytest tests/integration_l1l2/ --tb=no -q  →  57 passed in 1.43s
```

### 7.2 Prompt 05 Recovery — Before Fix (B-L5-001)
```
python -m pytest tests/ --tb=no -q
→ 545 collected
→ 544 passed, 1 FAILED  (test_approval_required_for_critical_without_confirm)
```

### 7.3 Prompt 05 Recovery — After Fix (B-L5-001) [DEFINITIVE]
```
python -m pytest tests/ --tb=no -q
→ 546 collected (1 new regression test added)
→ 546 passed, 0 failed
→ Warnings: ~1 (asyncio_default_fixture_loop_scope deprecation — pyproject.toml config issue, harmless)
```

### 7.4 Static Analysis (Ruff)
```
python -m ruff check src/aegis tests --select E,F,I,B
→ 281 issues found — ALL pre-existing (unused imports, import ordering)
→ 188 auto-fixable with --fix; 13 additional with --unsafe-fixes
→ None introduced by this session's changes
```

### 7.5 Type Checking (mypy)
```
python -m mypy src/aegis --ignore-missing-imports
→ BLOCKED: Windows WDAC policy DLL load failure
→ Run on Linux/macOS to validate
```

### 7.6 Package Import Check
```
python -c "import aegis; print(len(dir(aegis)), 'symbols exported')"
→ 87 symbols exported
python -c "from aegis.l5_execution.pipeline import ExecutionPipeline; print('L5 OK')"
→ L5 OK
python -c "from aegis.l5_execution.policy.rules import BUILTIN_RULES; r=next(x for x in BUILTIN_RULES if x.rule_id=='builtin-shell-sandbox'); print(r.decision)"
→ PermissionDecision.NEEDS_APPROVAL  ← Fix B-L5-001 confirmed
```

### 7.7 Rust Crates Verification
```
where.exe cargo → INFO: Could not find files
→ CARGO_NOT_FOUND: install Rust toolchain. Then: cd crates && cargo check --workspace
```

---

## 8. Repository Structure (Authoritative)

Matches Prompt 01 [04_REPOSITORY_STRUCTURE.md](file:///C:/Users/adars/Projects/AGIES/docs/04_REPOSITORY_STRUCTURE.md). Key directories:
```
C:\Users\adars\Projects\AGIES
├── docs/                           Prompt 01 foundation (11 files: 00_VISION through 10_RISKS)
│   ├── PROJECT_AEGIS_CURRENT_STATE.md   ← THIS FILE
│   ├── 11_PROMPT_02_CORE_RUNTIME.md     Implementation reference (API docs for P02)
│   └── HANDOFF_PROMPT_02_CONTINUATION.md  Next-agent handoff
├── src/aegis/
│   ├── l1_core/                    L1 Core Runtime
│   │   ├── runtime.py              CoreRuntime class (main FSM)
│   │   ├── supervisor.py           Watchdog + RestartPolicy + Recovery
│   │   ├── di/container.py         DIContainer + Scope + 5 Lifetimes + Lazy + Factory
│   │   ├── errors/                 base.py (AegisError + subclasses) + codes.py (30+ codes) + classify.py
│   │   ├── health/                 registry.py (HealthAggregator+Report) + checks.py
│   │   └── interfaces/             Service / HealthProvider / ModuleLifecycle / Pluggable / events / storage / llm / memory / exec
│   ├── l2_foundation/              L2 Foundation
│   │   ├── config/loader.py        ImmutableConfigSnapshot + layered loader
│   │   ├── telemetry/              logger.py (StructuredLogger) + context.py (CorrelationContext)
│   │   ├── event_bus/core.py       CoreEventBus (DLQ, SQLite durable, priority, typed envelopes)
│   │   ├── crypto/                 redact.py + vault.py (FileSecretVault) + Hasher
│   │   ├── scheduler/background.py BackgroundTaskManager + RetryPolicy + run_with_retry
│   │   ├── persistence/sql.py      SQLiteKVStore / SQLiteDocStore + NoOp stubs
│   │   └── plugin_loader/loader.py PluginManifest + SandboxTier + deny-by-default
│   ├── __init__.py                 Public API surface (76 symbols)
│   ├── cli.py
│   └── __main__.py
├── crates/                         Rust FFI (aegis_ffi_common / aegis_crypto / aegis_audit_chain)
├── tests/integration_l1l2/         10 test modules, 57 cases
│   ├── test_config.py (9)
│   ├── test_correlation.py (6)
│   ├── test_di.py (7)
│   ├── test_event_bus.py (9 incl. 2×2 anyio)
│   ├── test_health.py (6 incl. 2×2 anyio)
│   ├── test_logging_redaction.py (5)
│   ├── test_background_tasks.py (8 incl. 4×2 anyio)
│   ├── test_recovery.py (2 incl. 2×1 anyio)
│   └── test_runtime_lifecycle.py (6)
├── examples/runtime_lifecycle.py   End-to-end example (runs exit 0)
├── pyproject.toml                  Python build (hatchling), pytest/anyio, pytest markers, ruff config (line-length=120, target Py312), mypy strict config
├── justfile                        Task runner
├── README.md
└── Cargo.toml (workspace)          (declares member crates; exists if you see this)
```

---

## 9. Next Milestone

**Suggested NEXT MILESTONE: Prompt 07 (adaptive/personal learning) — or continue stabilization of the `reasoning` provider / Rust crates first.**

_See top banner + `AEGIS_MASTER_AUDIT.md` §5 for recommended remediation. The L5-suite hang is FIXED (STAB-01); redesign-package wiring remains._

---

## 10. STOP CONDITION (historical — Prompt 05 Recovery)

Prior Prompt 05 status (superseded by the 2026-08-07 audit):
  1. Prompt 05 bug B-L5-001 fixed (`builtin-shell-sandbox` rule `SANDBOX_REQUIRED` → `NEEDS_APPROVAL`), regression tests added.
  2. Verification commands at that time reported 546/546 passing — since superseded; the suite later
     hung at L5, which STAB-01 (2026-08-07) fixed (793 system python / 782 venv).
  3. Post-STAB-01 the full-suite green baseline is restored and current.
