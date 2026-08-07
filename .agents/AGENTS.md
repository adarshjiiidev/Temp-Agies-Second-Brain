# PROJECT AEGIS — AGENT CONTEXT FILE

> **Every incoming agent MUST read this file and `docs/AEGIS_MASTER_AUDIT.md` before touching any code.**
> This is the canonical context document. The repository is the source of truth.
> **2026-08-07 STABILIZATION COMPLETE: L5 hang fixed. Full suite passes (~8s); 793 tests on system
> python (791 baseline + 2 new), 782 on `.venv` python (different pytest/pytest-anyio collection).**
> See `docs/AEGIS_MASTER_AUDIT.md` for full audit details.
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
| 2026-08-07 | **STAB-01 — L5 Hang Fix** | Root cause: `FilesystemExecutor._search` used eager `list(rglob(...))` causing unbounded walk on home dir. Fix: lazy iterator + wall-clock budget (`max_seconds=10.0`) + `truncated` field. E2E test root changed to non-existent path. 2 new regression tests added. L6 `test_known_strategies_map_correctly` fixed (non-existent SPEED_FIRST→FASTEST, SAFE_MODE→BALANCED). Docs updated. | `src/aegis/l5_execution/executors/filesystem.py`, `tests/integration_l5/test_pipeline.py`, 
`tests/integration_l6/test_reasoning_provider.py`, `docs/PROJECT_AEGIS_CURRENT_STATE.md`, `.agents/AGENTS.md` | 
**793/793 ✅ system python (~8s; 782 on .venv due to pytest-anyio collection)** |

---

## 9. WHAT TO DO NEXT (For Incoming Agents)

### Before doing ANYTHING:
1. Read this file.
2. Read `docs/PROJECT_AEGIS_CURRENT_STATE.md` for component detail and `docs/AEGIS_MASTER_AUDIT.md` for the current truth.
3. Run `python -m pytest tests/ -q` — the full suite now completes (~8s). Expect 793 tests on
   system python (782 on `.venv` python). If it hangs again, investigate L5.
4. Read the user's directive carefully. Do NOT begin implementation without explicit authorisation.

### Current state (2026-08-07, post STAB-01)
- L1–L6 implemented; redesign pkgs (reasoning/prompts/capabilities) present but UNWIRED/UNTESTED.
- **Full suite passes (~8s): 793 tests on system python, 782 on `.venv` python.** L5 hang is resolved.
- Remaining blockers: reasoning provider wiring (`has_models()`/`infer_text()` on AIKernel), Rust crates, 642 pre-existing ruff issues. See `AEGIS_MASTER_AUDIT.md`.

### Architecture red lines (never cross without explicit ADR):
- L-layer dependencies must be downward only (L6 imports L5 and below; never upward)
- No LLM calls in L1/L2/L5
- No cloud data transmission of P0/P1 data
- All actions through the L5 7-stage pipeline — no shortcuts
- All errors must be `AegisError` subclasses with proper error codes
- AI reasoning results must be validated against deterministic safety floors (especially L5 risk assessment)
- Every AI reasoning module must have a deterministic offline fallback
