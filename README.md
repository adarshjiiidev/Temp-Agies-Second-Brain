# AEGIS — Personal Adaptive AI Operating System

**Phase: Prompt 02 — Core Runtime Implementation (L1 + L2 Foundation only).**

AEGIS is a 7-layer adaptive AI OS for Ambient Environment orchestration + General-purpose Intelligence +
Second Brain + Secure Autonomy. See the Prompt 01 documentation in the [`docs/`](./docs/) folder for the
full architecture, security, privacy, and capability model.

## Repository Layout

```
src/aegis/
├── l1_core/          L1: Runtime FSM, service supervisor, errors, health, DI, interfaces (protocols only)
├── l2_foundation/    L2: Event Bus, Config, Structured Logging + Correlation, Crypto/Redaction, Persistence,
│                      Plugin Loader (skeleton), Background Tasks
└── crates/           Rust: aegis_ffi_common, aegis_crypto (PyO3 bindings), aegis_audit_chain (skeletons)
tests/                Prompt 02 deterministic test suite (no network)
examples/             Minimal runtime lifecycle demo (no future subsystems)
docs/                 Prompt 01 architecture documentation (00..10).md
```

## Quick-Start (Prompt 02)

```powershell
# Install dependencies
pip install -e .[dev,test]

# Run all tests
just test
# Or via pytest: pytest -n0 tests/integration_l1l2/ -v

# Run the lifecycle example
python examples/runtime_lifecycle.py
```

## Scope of this milestone

Everything in Prompt 02 is explicitly **L1 Core + L2 Foundation only**. Layers L3–L7 (AI Kernel, Memory,
Agents, Browser, Vision, UI, etc.) are intentionally not implemented in this milestone. They will be
activated in later Prompts per the 23-Prompt canonical roadmap in [`docs/09_ROADMAP.md`](./docs/09_ROADMAP.md).
