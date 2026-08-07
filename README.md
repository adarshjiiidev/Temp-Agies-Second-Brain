# AEGIS — Personal Adaptive AI Operating System

**Latest state: L1–L6 implemented**
**Phase (docs): Prompt 02 was the last *declared* milestone, but the repository now contains L1–L6 + redesign packages.**

AEGIS is a 7-layer adaptive AI OS for Ambient Environment orchestration + General-purpose Intelligence +
Second Brain + Secure Autonomy. See the foundation documentation in the [`docs/`](./docs/) folder for the
full architecture, security, privacy, and capability model. **For the authoritative, current inventory and
findings, read [`docs/AEGIS_MASTER_AUDIT.md`](./docs/AEGIS_MASTER_AUDIT.md).**

## Repository Layout

```
src/aegis/
├── l1_core/          L1: Runtime FSM, service supervisor, errors, health, DI, interfaces (protocols only)
├── l2_foundation/    L2: Event Bus, Config, Structured Logging + Correlation, Crypto/Redaction, Persistence,
│                      Plugin Loader, Background Tasks
├── l3_intelligence/  L3: AI Kernel (model router, providers, accounting, cache, structured output, scrubber, keys)
├── l4_memory/        L4: Memory & Knowledge (manager, search, context, policies, markdown loader)
├── l5_execution/     L5: 7-stage execution pipeline, permission/policy/risk, audit chain, sandbox, executors
├── l6_planning/      L6: Goal/plan decomposer, dependency graph, planner service, reflection/metrics
├── reasoning/        Redesign pkg (AI reasoning provider) — PRESENT, NOT test-covered
├── prompts/          Redesign pkg (prompt library) — PRESENT, NOT test-covered
├── capabilities/     Redesign pkg (capability model) — PRESENT, NOT test-covered
├── cli.py, __init__.py, __main__.py
└── crates/           Rust: aegis_ffi_common, aegis_crypto, aegis_audit_chain (NOT verified — no Cargo on host)
tests/                791 tests collected. NOTE: the full suite HANGS at L5 integration (see audit report §3.1).
examples/             Minimal runtime lifecycle demo
docs/                   00..10 foundation docs + audit/state reports
```

## Quick-Start

```powershell
# Install dependencies
pip install -e .[dev,test]

# Run a layer you need (full suite hangs at L5 — see audit report)
python -m pytest tests/integration_l1l2/ -q      # 57 passed
python -m pytest tests/integration_l3/ -q        # 256 passed
python -m pytest tests/integration_l4/ -q        # 130 passed

# Run the lifecycle example
python examples/runtime_lifecycle.py
```

## Current Status (2026-08-07 audit)

- **L1, L2, L3, L4, L5 (partial), L6 implemented** — far beyond the documents' "L1+L2" claim.
- Full suite **does not terminate** (hangs at `test_pipeline.py::test_50_e2e_actions_all_produce_audit`).
- Measured counts: 57 (L1/L2) + 256 (L3) + 130 (L4) passing; L5/L6 not fully runnable.
- `ruff check` = 642 issues (docs previously claimed 281).
- Redesign packages (`reasoning`, `prompts`, `capabilities`) are present but **unwired/untested**.
- See `docs/AEGIS_MASTER_AUDIT.md` for full findings and reconciliation.