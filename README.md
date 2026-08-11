# AEGIS — Personal Adaptive AI Operating System

**Latest state: L1–L6 implemented; P07 in progress (WIP, uncommitted)**

AEGIS is a 7-layer adaptive AI OS for Ambient Environment orchestration + General-purpose Intelligence +
Second Brain + Secure Autonomy. See the foundation documentation in the [`docs/`](./docs/) folder for the
full architecture, security, privacy, and capability model. **For the authoritative inventory and
findings, read [`docs/AEGIS_MASTER_AUDIT.md`](./docs/AEGIS_MASTER_AUDIT.md).**

## Repository Layout

```
src/aegis/
├── l1_core/          L1: Runtime FSM, service supervisor, errors, health, DI, interfaces (protocols only)
├── l2_foundation/    L2: Event Bus, Config, Structured Logging + Correlation, Crypto/Redaction, Persistence,
│                      Plugin Loader, Background Tasks
├── l3_intelligence/  L3: AI Kernel (model router, providers, accounting, cache, structured output, scrubber, keys)
├── l4_memory/        L4: Memory & Knowledge (manager, search, context, policies, markdown loader, p07/ WIP)
├── l5_execution/     L5: 7-stage execution pipeline, permission/policy/risk, audit chain, sandbox, executors
├── l6_planning/      L6: Goal/plan decomposer, dependency graph, planner service, reflection/metrics
├── reasoning/        Redesign pkg — AI reasoning provider (wired to L6 via PlannerService; MockProvider tested)
├── prompts/          Redesign pkg — 15 versioned YAML prompt templates (used by reasoning layer)
├── capabilities/     Redesign pkg — capability registry (minimal test coverage)
├── cli.py, __init__.py, __main__.py
└── crates/           Rust: aegis_ffi_common, aegis_crypto, aegis_audit_chain (NOT verified — no Cargo on host)
tests/                814 tests (system python, 2026-08-08). Full suite passes (~15s).
examples/             Minimal runtime lifecycle demo
docs/                 00..10 foundation docs + audit/state reports
```

## Quick-Start

```powershell
# Install dependencies
pip install -e .[dev,crypto]

# Run the full suite
python -m pytest tests/ -q

# Or run per layer
python -m pytest tests/integration_l1l2/ -q      # 57 passed
python -m pytest tests/integration_l3/ -q        # 263 passed (incl. registry quality tests)
python -m pytest tests/integration_l4/ -q        # 144 passed (incl. P07 model tests)
python -m pytest tests/integration_l5/ -q        # 103 passed
python -m pytest tests/integration_l6/ -q        # ~180 passed

# Run the lifecycle example
python examples/runtime_lifecycle.py
```

## Current Status (2026-08-08)

- **L1–L6 implemented** — full vertical slice (runtime → planning → execution) is in place.
- **Full suite passes:** 814 tests on system python (~15s). `.venv` python may collect fewer L1/L2 anyio cases.
- **P07 WIP:** `l4_memory/p07/` (scanners, discovery, inference) — uncommitted; see `docs/P07_ARCHITECTURE_PLAN.md`.
- **Redesign packages:** `reasoning/` wired into `PlannerService` (MockProvider + fallback tested); `KernelReasoningProvider` uses real `AIKernel.generate()` but lacks end-to-end integration test.
- **L6 default path:** deterministic keyword heuristics; AI path activates when `reasoning_provider` is injected.
- **`ruff check`** = 717 issues (410 auto-fixable). **`mypy`** blocked on Windows WDAC. **`cargo`** not installed.
- See `docs/AEGIS_MASTER_AUDIT.md` for full findings and reconciliation history.
