# [[[Aegis]]]

**Status:** Active Development
**Priority:** High
**Type:** Personal AI Project
**Last Updated:** 2026-09-12

---

## Overview

Aegis is a 7-layer Personal Adaptive AI Operating System — the user's primary AI project and the architectural inspiration for TEMPORARY AEGIS. Implements L1-L6 with 1060 tests passing.

**Location:** [[Projects/Aegis]]
**Repository:** /home/adarshjii/Projects/Aegis

---

## Architecture

See [[Aegis Architecture]] for full details.

### Layer Summary

| Layer | Status | Key Components |
|---|---|---|
| L1 Core Runtime | ✅ Complete | FSM lifecycle, DI container (5 lifetimes), typed errors |
| L2 Foundation | ✅ Complete | Event bus, config, logging, crypto vault, plugin loader |
| L3 AI Kernel | ✅ Complete | Model router (5-stage), 6 provider adapters, budget accounting, PII scrubber |
| L4 Memory/Knowledge | ✅ Complete | 3 stores, knowledge graph, context assembly, search |
| L5 Execution | ✅ Complete | 7-stage pipeline, permission/policy engines, 4-tier sandbox, audit chain |
| L6 Planning | ✅ Implemented | Goal decomposer, planner service, dependency graph, reflection |
| L7 HCI | ❌ Not Started | — |

### Key Design Principles

1. **Capability-Based, Not Integration-Based** — Reason about capabilities, not specific products
2. **Learnable, Not Hardcoded** — Kernel provides learning loop; artifacts live outside
3. **Secure-by-Construction** — Every subsystem boundary is a security boundary

### Privacy Invariant

**P0 data NEVER routes to cloud.** Secrets/PII detected by scrubber → auto-elevated to P0 → only local models. Violation raises `AIRouterPrivacyViolationError`.

---

## Current State

### Tests
- **1060 tests passing** (~22s runtime)
- Full suite passes since STAB-01 fix (2026-08-07)

### Quality
- Ruff: 642 issues (pre-existing, 410 auto-fixable)
- Mypy: Blocked on Windows WDAC (not relevant to Linux)
- Cargo: Not installed — Rust crates unverifiable

### Uncommitted Changes (2026-09-12)
- `.agents/AGENTS.md` — modified
- `src/aegis/agentmoe/security/autonomy.py` — modified
- `src/aegis/agentmoe/security/budget_guard.py` — modified
- `src/aegis/agentmoe/workers/runtime.py` — modified
- `tests/agentmoe/security/test_security_guards.py` — modified

### Recent Focus
**AgentMOE security autonomy and budget guard improvements.** Security guard tests being actively modified.

---

## Technology Stack

### Python Dependencies
- pydantic>=2.6,<3
- pydantic-settings>=2.1,<3
- PyYAML>=6.0.0
- aiosqlite>=0.20.0
- structlog>=24.0.0
- httpx>=0.27.0

### Dev Dependencies
- pytest>=8.0, pytest-asyncio>=0.23, pytest-cov>=4.1
- hypothesis>=6.90, ruff>=0.3.0, mypy>=1.8
- types-PyYAML

### Build
- hatchling build system
- uv recommended package manager

---

## Key Documentation

| Document | Description |
|---|---|
| [[AEGIS_DOCS/00_VISION]] | Project vision and guiding principles |
| [[AEGIS_DOCS/02_ARCHITECTURE]] | Layer architecture, component maps |
| [[AEGIS_DOCS/05_SECURITY]] | Security model, privacy boundaries, risk register |
| [[AEGIS_DOCS/06_MEMORY]] | Memory and knowledge architecture |
| [[AEGIS_DOCS/09_ROADMAP]] | 23-prompt milestone roadmap |
| [[AEGIS_DOCS/AEGIS_MASTER_AUDIT]] | Master audit report (authoritative) |
| [[AEGIS_DOCS/P07_ARCHITECTURE]] | P07 memory scanner architecture |

---

## Relationship to TEMPORARY AEGIS

Aegis is the **architectural blueprint** for TEMPORARY AEGIS:

- AEGIS L4 memory concepts → TEMPORARY AEGIS memory schema
- AEGIS L3 routing concepts → Model routing configuration
- AEGIS L5 execution pipeline → Security/authorization model
- AEGIS risk register → Security review basis

**Code is NOT directly reused** — TEMPORARY AEGIS uses existing tools (Hermes, Codex, 9Router) rather than importing Aegis. However, AEGIS documentation and architectural decisions inform configuration and design choices.

---

## Known Issues

1. **Rust crate compile errors** — missing deps (rand/tempfile), syntax errors in aegis_crypto. Cargo not installed.
2. **Redesign packages untested** — `reasoning/`, `prompts/`, `capabilities/` present but untested/UNWIRED
3. **Ruff lint** — 642 pre-existing issues, not blocking

---

## NextSteps

- Continue AgentMOE security work (uncommitted changes)
- Potentially fix Rust crate issues (requires cargo installation)
- Consider wiring redesign packages (reasoning → L3 integration)
- Run full test suite after security changes committed

---

*See also: [[Project Intelligence]], [[Aegis Architecture]], [[AEGIS_DOCS]]*
