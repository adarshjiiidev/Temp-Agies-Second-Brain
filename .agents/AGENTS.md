# PROJECT AEGIS — AGENT CONTEXT FILE

> **Every incoming agent MUST read this file and `docs/AEGIS_MASTER_AUDIT.md` before touching any code.**
> This is the canonical context document. The repository is the source of truth.
> **2026-08-11 P07.5 COMPLETE: Provider-agnostic LLM inference infrastructure hardened.**
> **2026-08-12 P-RUST PHASE R0+R1 COMPLETE: Rust Performance Core audit + crate repairs — FULLY VERIFIED.**
> `cargo +stable test --workspace` → 11 Rust tests pass. `aegis_crypto` bugs fixed. 0 warnings.
> **Full suite: 1060 Python tests + 11 Rust tests. 0 regressions. 0 warnings.**
> See `docs/architecture/RUST_PERFORMANCE_CORE.md` and `docs/adr/ADR-0001-rust-performance-core.md`.
> This file tells you WHERE you are, WHAT is done, and WHAT to do next.

---

## 0. MANDATORY RULES FOR ALL AGENTS

1. **Never commit unless explicitly told to.**
2. **Never start the next Prompt milestone unless the user says so explicitly.**
3. **Never modify code outside the authorised scope of the current directive.**
4. **Never trust conversation history — always re-audit from actual code.**
5. **Update this file at the end of every completed task.** (See §7 for format.)
6. **The repository is the single source of truth.** Docs are secondary.

---

## 1. WHAT IS AEGIS?

**AEGIS** = Adaptive Executive Governance & Intelligence System

A **personal, local-first AI operating system** — not a chatbot, not an API wrapper.
Architecture: 7 strict downward-only dependency layers (L1 → L7). Nothing jumps layers.

```
L7  HCI / UI               🔲 Not started
L6  Planning / Agents      ✅ Implemented
L5  Execution Engine       ✅ Implemented (hang fixed 2026-08-07; full suite now passes)
L4  Memory & Knowledge     ✅ Implemented
L3  AI Kernel              ✅ Implemented
L2  Foundation             ✅ Implemented
L1  Core Runtime           ✅ Implemented

🔷 Redesign pkgs (reasoning/ prompts/ capabilities) exist on disk — PRESENT but UNWIRED/UNTESTED.
✅ 2026-08-07 stabilization: full test suite completes — 793 pass on system python (782 on `.venv` python), ~8s.
```

---

## 2. MILESTONE STATUS

| Prompt | Scope | Status | Tests | Last Action |
|--------|-------|--------|-------|-------------|
| P01 | Architecture docs (11 files) | ✅ DONE | N/A | — |
| P02 | L1 Core Runtime + L2 Foundation | ✅ DONE | 57/57 | 15 bugs fixed |
| P03 | L3 AI Kernel | ✅ DONE | 131/131 | — |
| P04 | L4 Memory & Knowledge | ✅ DONE | 238/238 | — |
| P05 | L5 Execution Engine | ✅ DONE | 546/546 (at the time) | Bug B-L5-001 fixed |
| P06 | L6 Planning / Agents | ✅ DONE | 726/726 (at the time) | 180 L6 tests added; 2 bugs fixed (intent domain, cycle detection) |
| REDESIGN | AI-Native Architectural Overhaul | 🔷 PLAN PRODUCED | — | Migration plan produced |
| P07 | P07 Hardcoding Remediation + Env Model | ✅ DONE | 887/887 | H12 bug fix, H9/H10 ScoringConfig/EvaluatorConfig, kernel_provider rewrite, 73 new P07 comprehensive tests, 7 P07 persistence bugs fixed |
| P07-GAP | P07 Gap Remediation (4 architectural gaps) | ✅ DONE | 1007/1007 | Provider abstraction, WorkflowAutoPromoter, FreshnessScheduler, PrivacyZoneService; 120 new tests |
| P07.5 | LLM Provider & Inference Infrastructure | ✅ DONE | 1060/1060 | Ollama discovery, ProviderHealthMonitor, CredentialResolver, CredentialProvisioner ABC, AIKernel.has_models/list_models/provider_count; 53 new tests; 0 regressions |
| P-RUST R0+R1 | Rust Performance Core — Audit + Crate Repairs | ✅ DONE | 1060 Python + 11 Rust | Phase R0: full L1–L7 migration map, ADR-0001. Phase R1: 6 compile errors fixed in `aegis_crypto`, `rand` dep added to `aegis_ffi_common`, `tempfile` dev-dep added to `aegis_audit_chain`, `rust-toolchain.toml` updated to `stable`. **cargo verified**: `cargo +stable test --workspace` → 11/11 pass, 0 warnings. |

> **2026-08-07 STAB-01: L5 hang fixed — full suite now completes (~8s).**
> Count is interpreter-dependent: system `python` = 793 (791 baseline + 2 new regression tests);
> `.venv` python = 782 (venv has pytest 9 / pytest-anyio which collect 11 fewer L1/L2
> anyio-backend-parametrized cases). Either count is green; both were measured passing.
> See `docs/AEGIS_MASTER_AUDIT.md`.
> Run layers individually: `python -m pytest tests/integration_l1l2/ -q` etc.

---

## 3. REPOSITORY STRUCTURE

```
AGIES/
├── src/aegis/
│   ├── l1_core/              Runtime FSM, DI, Errors, Health, Supervisor
│   ├── l2_foundation/        Config, Logging, EventBus, Crypto, Scheduler, Persistence, PluginLoader
│   ├── l3_intelligence/      ModelRouter, ProviderRegistry, Accounting, Cache, StructuredOutput, Scrubber, Keys
│   ├── l4_memory/            MemoryManager, SearchEngine, ContextBuilder, Policies, Markdown loader
│   ├── l5_execution/         Pipeline, Permission, Policy, Risk, Audit, Sandbox, Executors, Rollback, Verify
│   └── l6_planning/          GoalEngine, TaskDecomposer, DependencyGraph, DecisionEngine, PlannerService,
│                             ReflectionEngine, VerificationPlanner, RecoveryPlanner, Metrics
│                             (11 subpackages: intent, planning, decomposition, reasoning, orchestration,
│                              strategy, reflection, state, verification, recovery, metrics)
│   ├── reasoning/            Redesign (AI reasoning provider) — UNWIRED/UNTESTED
│   ├── prompts/              Redesign (prompt library) — UNWIRED/UNTESTED
│   ├── capabilities/         Redesign (capability model) — UNWIRED/UNTESTED
├── tests/
│   ├── integration_l1l2/     57 tests
│   ├── integration_l3/       256 tests
│   ├── integration_l4/       130 tests
│   ├── integration_l5/       103 tests (hang fixed 2026-08-07)
│   └── integration_l6/       180 tests
├── docs/
│   ├── PROJECT_AEGIS_CURRENT_STATE.md   ← Full state (see top banner — partially out of date)
│   ├── AEGIS_MASTER_AUDIT.md            ← ✅ CURRENT truth (2026-08-07)
│   ├── 00_VISION.md through 10_RISKS.md ← Architecture foundation (P01 deliverables)
│   └── 09_ROADMAP.md                    ← 23-prompt roadmap
├── crates/                   Rust FFI (aegis_ffi_common, aegis_crypto, aegis_audit_chain) — UNVERIFIED (no cargo)
├── examples/                 runtime_lifecycle.py (L1/L2 demo, exits 0)
└── .agents/AGENTS.md         ← THIS FILE
```

---

## 4. L5 EXECUTION ENGINE — KEY ARCHITECTURE

The 7-stage pipeline (every action flows through ALL stages in order):

```
Stage 1  Permission Engine   SVRC deny-by-default check
Stage 2  Risk Analyzer       LOW / MEDIUM / HIGH / CRITICAL (weighted factors)
Stage 3  Policy Engine       ALLOW / DENY / NEEDS_APPROVAL / SANDBOX_REQUIRED
Stage 4  Executor Registry   Route to executor plugin
Stage 5  Sandbox Manager     Build SandboxContext (T1-T3 active, T4 stub)
Stage 6  Executor            Run action (with dry-run support)
Stage 7  Audit + Verify      Hash-chain audit + post-exec assertions
```

**Critical invariants (enforced in pipeline.py):**
- No stage may be skipped
- Every stage produces an audit entry before the next stage begins
- `CRITICAL` risk without `user_confirmed` → `ApprovalRequiredError`
- `SandboxEscapeError` → ESCAPE_ATTEMPT audit entry, then re-raise

**Policy decision semantics:**
- `ALLOW` → proceed
- `SANDBOX_REQUIRED` → proceed but enforce sandbox tier
- `NEEDS_APPROVAL` → raise `ApprovalRequiredError` → pipeline returns `APPROVAL_REQUIRED`
- `DENY` → raise `PolicyViolationError` → pipeline returns `DENIED`

**Important design note (TD-06):**
`user_confirmed=True` on an `Action` does NOT bypass direct `NEEDS_APPROVAL` policy rules.
It only bypasses the `force_approval_on_critical` override (which elevates ALLOW→NEEDS_APPROVAL
for CRITICAL risk when user hasn't confirmed). Direct NEEDS_APPROVAL rules always block.

---

## 5. KNOWN BUGS & FIXES

### Fixed Bugs (audit trail)

| ID | Layer | Description | Fix Location |
|----|-------|-------------|--------------|
| B1–B15 | L1/L2 | Core Runtime contract mismatches (15 bugs) | See docs/PROJECT_AEGIS_CURRENT_STATE.md §5 |
| **B-L5-001** | L5 | `builtin-shell-sandbox` policy rule used `SANDBOX_REQUIRED` instead of `NEEDS_APPROVAL`. Shell exec at HIGH risk reached T2SubprocessSandbox, which failed on Windows (echo is a shell builtin without `shell=True`). Test expected `APPROVAL_REQUIRED`, got `FAILED`. | `src/aegis/l5_execution/policy/rules.py` — changed decision to `NEEDS_APPROVAL`. Two regression tests added in `tests/integration_l5/test_pipeline.py`. |

### Active Technical Debt

| ID | Severity | Description |
|----|----------|-------------|
| TD-01 | LOW | 642 ruff lint issues (pre-existing: unused imports, import ordering). `ruff --fix` resolves most. |
| TD-02 | MEDIUM | mypy blocked by Windows WDAC policy (DLL load failure). Run on Linux/macOS. |
| TD-03 | MEDIUM | Rust FFI crates unverified — cargo not installed. `cd crates && cargo check --workspace` when available. |
| TD-04 | MEDIUM | `T2SubprocessSandbox`: shell builtins fail on Windows without `shell=True`. Mitigated by B-L5-001 (shell.exec now requires approval so executor is never reached in tests). |
| TD-05 | LOW | T4 Firecracker sandbox raises `NotImplementedError`. Planned P08+. |
| TD-06 | MEDIUM | `user_confirmed=True` does not bypass direct `NEEDS_APPROVAL` rules. Needs approval token mechanism (future). |

---

## 6. ENVIRONMENT NOTES (Windows-Specific)

- **Python**: 3.12.3, path: `C:\Users\adars\AppData\Local\Programs\Python\Python312\python.exe`
- **pytest**: `python -m pytest tests/ --tb=short -q`
- **venv**: `.venv/` in project root (activate: `.venv\Scripts\activate`)
- **mypy**: BLOCKED by Windows WDAC — do not waste time on it
- **cargo**: not installed — do not attempt Rust builds
- **Shell builtins**: `echo`, `dir` etc. are CMD builtins, not executables. `asyncio.create_subprocess_exec` will fail for them without `shell=True`
- **Never use `cd` in commands** — always set `Cwd` explicitly

---

## 7. HOW TO UPDATE THIS FILE

After completing any task, add a row to the **Session Log** table below.

**Format:**
```
| DATE | PROMPT/TASK | WHAT CHANGED | FILES TOUCHED | TEST RESULT |
```

Append to the bottom of §8. Then update §2 (milestone status) if a prompt milestone completed.

---

## 8. SESSION LOG

| Date | Prompt / Task | What Changed | Files Touched | Tests |
|------|---------------|--------------|---------------|-------|
| 2026-08-02 | **P01** | Architecture docs, ADRs, 21-prompt roadmap written | `docs/00_VISION.md` → `docs/10_RISKS.md`, `docs/09_ROADMAP.md` | N/A |
| 2026-08-02 | **P02** | L1 Core Runtime + L2 Foundation implemented. 15 bugs (B1–B15) fixed. | `src/aegis/l1_core/`, `src/aegis/l2_foundation/`, `tests/integration_l1l2/`, `examples/` | 57/57 ✅ |
| 2026-08-02 | **P03** | L3 AI Kernel: model router, provider registry, accounting, cache, structured output, scrubber, key manager. | `src/aegis/l3_intelligence/`, `tests/integration_l3/` | 131/131 ✅ |
| 2026-08-02 | **P04** | L4 Memory & Knowledge: MemoryManager (T0–T8), SearchEngine, ContextBuilder, Policies, Markdown loader, P0 privacy invariant. | `src/aegis/l4_memory/`, `tests/integration_l4/` | 238/238 ✅ |
| 2026-08-02 | **P05** | L5 Execution Engine: 7-stage pipeline, PermissionEngine, PolicyEngine, RiskAnalyzer, AuditChain, SandboxManager, 10 executors, RollbackEngine, PostExecVerifier. | `src/aegis/l5_execution/`, `tests/integration_l5/` | 545/545 ✅ (before fix) |
| 2026-08-02 | **P05 Recovery** (B-L5-001) | Fixed `builtin-shell-sandbox` policy rule: `SANDBOX_REQUIRED` → `NEEDS_APPROVAL`. Added 2 regression tests. Removed 30 spurious asyncio marks from L4 sync tests. Updated `PROJECT_AEGIS_CURRENT_STATE.md`. | `src/aegis/l5_execution/policy/rules.py`, `tests/integration_l5/test_pipeline.py`, `tests/integration_l4/test_policies.py`, `tests/integration_l4/test_privacy_p0.py`, `docs/PROJECT_AEGIS_CURRENT_STATE.md`, `.agents/AGENTS.md` | **546/546 ✅** |
| 2026-08-04 | **P06** | L6 Planning Engine: GoalEngine, TaskDecomposer, DependencyGraph, DecisionEngine, ScoringEngine, PlannerService, ReflectionEngine, VerificationPlanner, RecoveryPlanner, IntentParser, AmbiguityDetector, RequirementExtractor. 11 subpackages. Fixed syntax bug in ambiguity_detector.py (f-string !r in generator). Fixed 2 test failures (browser domain keyword, cycle detection). | `src/aegis/l6_planning/` (all 11 subpackages), `tests/integration_l6/` (180 tests), `src/aegis/l1_core/errors/codes.py` (L6 error codes) | **726/726 ✅** |
| 2026-08-04 | **Architectural Redesign Directive** | Full repo audit performed. Migration plan produced: 27 files require redesign, 3 new component directories to create (prompts/, reasoning/, capabilities/). 6 migration phases (A–F). Awaiting user approval before implementation. | `.agents/AGENTS.md` (this file), `docs/PROJECT_AEGIS_CURRENT_STATE.md` | 726/726 ✅ (no code changes) |
| 2026-08-07 | **Master Audit (read-only)** | Verified live ground truth: 791 tests collected; 57+256+130 pass (L1–L4); full suite **HANGS** at L5; ruff=642; cargo absent; L1–L6 + redesign pkgs present; L6/redesign unwired. Corrected docs: `AEGIS_MASTER_AUDIT.md` (new), `README.md`, `current_state.json`, `PROJECT_AEGIS_CURRENT_STATE.md` banner, `AGENTS.md`, roadmap status. | `docs/AEGIS_MASTER_AUDIT.md`, `README.md`, `docs/current_state.json`, `docs/PROJECT_AEGIS_CURRENT_STATE.md`, `.agents/AGENTS.md`, `docs/09_ROADMAP.md` | 57 L1/L2 + 256 L3 + 130 L4 ✅; L5 HANGS ⚠️ |
| 2026-08-07 | **STAB-01 — L5 Hang Fix** | Root cause: `FilesystemExecutor._search` used eager `list(rglob(...))` causing unbounded walk on home dir. Fix: lazy iterator + wall-clock budget (`max_seconds=10.0`) + `truncated` field. E2E test root changed to non-existent path. 2 new regression tests added. L6 `test_known_strategies_map_correctly` fixed (non-existent SPEED_FIRST→FASTEST, SAFE_MODE→BALANCED). Docs updated. | `src/aegis/l5_execution/executors/filesystem.py`, `tests/integration_l5/test_pipeline.py`, `tests/integration_l6/test_reasoning_provider.py`, `docs/PROJECT_AEGIS_CURRENT_STATE.md`, `.agents/AGENTS.md` | **793/793 ✅ system python (~8s; 782 on .venv due to pytest-anyio collection)** |
| 2026-08-10 | **P07 Phase 1 — Hardcoding Remediation** | H12 Registry double-count bug fixed. `kernel_provider.py` rewritten to use real `AIKernel.generate()` API. H9: `scoring.py` magic constants → `ScoringConfig`. H10: `evaluator.py` thresholds → `EvaluatorConfig`. H1–H8 classified as `DETERMINISTIC_FALLBACK` (correct). `HARDCODING_REMEDIATION_REPORT.md` produced. | `src/aegis/l3_intelligence/ai_kernel/registry.py`, `src/aegis/reasoning/kernel_provider.py`, `src/aegis/l6_planning/reasoning/scoring.py`, `src/aegis/l6_planning/reasoning/evaluator.py`, `tests/integration_l3/test_registry_quality_score.py`, `docs/HARDCODING_REMEDIATION_REPORT.md` | **814/814 ✅** |
| 2026-08-10 | **P07 Phase 2 — Comprehensive P07 Tests + Persistence Bug Fixes** | 73 new comprehensive P07 tests added covering observer, audit, sink, consent gate, privacy zones, workflow/preference inferencer (8/10 criterion), scanning coordinator, app scanner (95% criterion), candidate store, env store, and shutdown zero-leftover invariants. Fixed 7 bugs in `env_store.py` (wrong KG method names) and `candidate_store.py` (invalid SearchQuery kwarg, PENDING_REVIEW invisible to search, wrong promote call, T5 policy gate). | `tests/integration_l4/test_p07_comprehensive.py` (NEW), `src/aegis/l4_memory/p07/persistence/env_store.py`, `src/aegis/l4_memory/p07/persistence/candidate_store.py`, `docs/HARDCODING_REMEDIATION_REPORT.md` | **887/887 ✅ (~17s)** |
| 2026-08-11 | **P07-GAP — Gap Remediation (4 gaps)** | GAP #1: `ApplicationDiscoveryProvider` abstraction + `PathToolProvider`/`WindowsRegistryProvider`/`CompositeProvider`; `app_scanner.py` refactored to use DI. GAP #2: `WorkflowSuccessTracker` + `WorkflowAutoPromoter` (threshold=3, T5 never auto-promotes, cooldown, provenance). GAP #3: `FreshnessScheduler` (asyncio, shutdown-safe, failure-tolerant, no L2 dep). GAP #4: `PrivacyZoneService` (add/remove/update/list/check/export/import, boundary-safe path normalization, atomic import, P0 invariant). 120 new tests added. 0 regressions. | `src/aegis/l4_memory/p07/scanners/providers.py` (NEW), `app_scanner.py`, `scanners/__init__.py`, `inference/promotion.py` (NEW), `inference/__init__.py`, `model/scheduler.py` (NEW), `model/__init__.py`, `privacy/service.py` (NEW), `privacy/__init__.py`, `tests/integration_l4/test_p07_gaps.py` (NEW), `docs/P07_ARCHITECTURE_PLAN.md`, `docs/PROJECT_AEGIS_CURRENT_STATE.md`, `.agents/AGENTS.md` | **1007/1007 ✅ (~10s)** |
| 2026-08-11 | **P07.5 — LLM Provider & Inference Infrastructure** | `BaseProvider.health_check()` + `discover_models()` (default UNKNOWN/static). `OllamaProvider` overrides: `GET /api/version` (health), `GET /api/tags` (discovery), fallback to static list on error. `ProviderHealthMonitor` (asyncio background loop, threshold-gated DOWN marking, UNKNOWN-safe). `CredentialResolver` (env:/file:/aegis-keyring: schemes). `CredentialProvisioner` ABC + `ManualProvisioner` + `EnvironmentProvisioner` + `BrowserProvisioner` (NotImplementedError stub). `AIKernel.has_models()` + `list_models()` + `provider_count()`. `ProviderRegistry.register_force()`. 53 new tests (credential security + L6→L3 integration). 0 regressions. | `providers/base.py`, `providers/ollama.py`, `ai_kernel/health.py` (NEW), `ai_kernel/credentials.py` (NEW), `ai_kernel/kernel.py`, `ai_kernel/__init__.py`, `tests/integration_l3/test_credential_security.py` (NEW), `tests/integration_l3/test_reasoning_integration.py` (NEW), `docs/P07_5_ARCHITECTURE.md` (NEW), `.agents/AGENTS.md` | **1060/1060 ✅ (~22s)** |
| 2026-08-12 | **P-RUST R0+R1 — Rust Performance Core Audit + Crate Repairs (VERIFIED)** | Phase R0: Complete L1–L7 component audit. Every component classified (KEEP_PYTHON/RUST_CANDIDATE/RUST_CORE/DO_NOT_MIGRATE). Full migration map written. `ADR-0001-rust-performance-core.md` written. Phase R1: Fixed 6 compile errors in `aegis_crypto/src/lib.rs` (KeyInit trait ambiguity, AeadCore/OsRng unused imports, base64 import, const hex table, array indexing, AES-GCM double-encrypt, missing closing paren, hmac return type). Added `rand = "0.8"` to `aegis_ffi_common/Cargo.toml`. Added `tempfile = "3"` dev-dep to `aegis_audit_chain/Cargo.toml`. Updated `rust-toolchain.toml` to `stable` (was `1.75.0`, causing rustup download errors). Fixed `unused_must_use` warning in audit chain test. **Fully verified**: `cargo +stable test --workspace` → 11/11 Rust tests pass, 0 warnings. Python 1060/1060. | `crates/aegis_ffi_common/Cargo.toml`, `crates/aegis_crypto/src/lib.rs`, `crates/aegis_audit_chain/src/lib.rs`, `crates/aegis_audit_chain/Cargo.toml`, `rust-toolchain.toml`, `Cargo.toml` (rust-version 1.75→1.80), `docs/architecture/RUST_PERFORMANCE_CORE.md` (NEW), `docs/adr/ADR-0001-rust-performance-core.md` (NEW), `.agents/AGENTS.md`, `docs/PROJECT_AEGIS_CURRENT_STATE.md` | **11 Rust ✅ + 1060 Python ✅ — 0 warnings** |

---

## 9. WHAT TO DO NEXT (For Incoming Agents)

### Before doing ANYTHING:
1. Read this file.
2. Read `docs/PROJECT_AEGIS_CURRENT_STATE.md` for component detail and `docs/AEGIS_MASTER_AUDIT.md` for the current truth.
3. Read `docs/P07_5_ARCHITECTURE.md` for the complete P07.5 implementation record.
4. Read `docs/P07_ARCHITECTURE_PLAN.md §10` for P07 gap remediation details.
5. Read `docs/HARDCODING_REMEDIATION_REPORT.md` for P07 hardcoding audit results.
6. Run `python -m pytest tests/ -q` — expect **1060 tests** on system python (~22s). If it hangs, investigate L5.
7. Read the user's directive carefully. Do NOT begin implementation without explicit authorisation.

### Current state (2026-08-12, post P-RUST R0+R1 — FULLY VERIFIED)
- L1–L6 implemented; redesign pkgs (reasoning/prompts/capabilities) present — `KernelReasoningProvider` wired and tested.
- **Python: 1060 tests pass (~23s).** L5 hang resolved. 0 regressions.
- **Rust: 11 tests pass (`cargo +stable test --workspace`).** 0 errors, 0 warnings.
  - `aegis_ffi_common`: 1 test (UUID v4 version bits)
  - `aegis_crypto`: 9 tests (SHA-256, HMAC, AES-GCM roundtrip, base64, hex)
  - `aegis_audit_chain`: 1 test (append + verify + tamper detection)
- P07 environment model: inference, discovery, persistence, scanners, observer, consent gate, privacy zones — all implemented and tested.
- **P07.5 complete:** OllamaProvider health/discovery, ProviderHealthMonitor, CredentialResolver/Provisioner, AIKernel introspection.
- **P-RUST R0+R1 complete + verified:** Full L1–L7 audit, ADR-0001, RUST_PERFORMANCE_CORE.md, all three Rust crates compile clean and all tests pass.
- **`cargo` is now installed** (rustup stable, 1.87.0). `rust-toolchain.toml` pinned to `stable`.
- Remaining: Phase R2 benchmarks (measure Python vs Rust latency), then R3 new crates (`aegis_search_core`, `aegis_graph_core`). Also: 642 pre-existing ruff issues, ProviderHealthMonitor not yet wired into AEGIS lifecycle.

### Architecture red lines (never cross without explicit ADR):
- L-layer dependencies must be downward only (L6 imports L5 and below; never upward)
- No LLM calls in L1/L2/L5
- No cloud data transmission of P0/P1 data
- All actions through the L5 7-stage pipeline — no shortcuts
- All errors must be `AegisError` subclasses with proper error codes
- AI reasoning results must be validated against deterministic safety floors (especially L5 risk assessment)
- Every AI reasoning module must have a deterministic offline fallback
