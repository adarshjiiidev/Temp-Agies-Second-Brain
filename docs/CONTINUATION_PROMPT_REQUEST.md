# AEGIS — CONTINUATION PROMPT REQUEST FOR SYSTEM ARCHITECT

**From:** Audit Agent
**To:** Principal System Architect
**Reason:** Repository changed since the last handoff; audit found new uncommitted work, missing pieces, and a priority conflict. We need **you to write the next continuation prompt** for the build agent.

> 🎯 **Your deliverable: a single self-contained CONTINUATION PROMPT (or ordered step set) for the next engineer. It must treat the HARDCODING REMEDIATION as FIRST PRIORITY, then resume P07. No implementation from you.**

---

## 1. WHAT CHANGED — FULL CHANGE AUDIT (verified against git, 2026-08-08)

### 1.1 Committed — SAFE (commit `dc7eb56 "Phase 6"`, HEAD)
- STAB-01 L5-hang fix: `src/aegis/l5_execution/executors/filesystem.py` (lazy walk + `max_seconds`), `tests/integration_l5/test_pipeline.py` (+2 regression tests), `tests/integration_l6/test_reasoning_provider.py` (enum fix).
- Docs: `README.md`, `.agents/AGENTS.md`, `docs/09_ROADMAP.md`, `docs/AEGIS_MASTER_AUDIT.md`, `docs/PROJECT_AEGIS_CURRENT_STATE.md`, `docs/current_state.json`, `docs/PROMPT_FIX_L5_SUITE_HANG.md`, `docs/P07_ARCHITECTURE_PLAN.md`, `CODING_TASK_FIX_L5_HANG.md`, superseded banners.
- **Suite still green:** 793 passed (system `python`), ~7s.

### 1.2 Uncommitted — AT RISK (working tree, NOT committed, NOT in any commit)
- **Modified:** `src/aegis/l4_memory/__init__.py` (exports `PrivacyZonePolicy`), `src/aegis/l4_memory/types.py` (+`OBSERVER_DERIVED` provenance, +`APPLICATION/DEVICE/DEV_ENVIRONMENT/ACCOUNT/WORKSPACE` entities, +`RUNS_ON/DEPLOYS_THROUGH/MANAGES` relations), `src/aegis/l4_memory/policies.py` (+`PrivacyZonePolicy`).
- **Untracked package:** `src/aegis/l4_memory/p07/` (about 20 new files: `model/`, `scanners/`, `observer/`, `persistence/`, `privacy/`).
  - Imports fine. Present: `model/types.py`, `model/freshness.py`, `scanners/{base,app_scanner,project_scanner,cli_scanner,relation_scanner}.py`, `observer/{events,audit,sink}.py`, `persistence/{env_store,candidate_store}.py`, `privacy/{zones,redaction}.py`.
  - **No tests exist for any p07 module.**
  - **Missing vs its own docstring (`p07/__init__.py`): `inference/` (workflow + preference candidate) and `discovery/` (consent gate + coordinator) subpackages are ABSENT.**
- ⚠️ This whole block (1.2) can be lost by any `git clean`/`checkout`. **The continuation prompt MUST tell the engineer: do not reset/discard; preserve uncommitted work (§21 of master directive).**

---

## 2. WHAT WAS LOST / NEVER EXISTED

| Item | Status |
|---|---|
| `ARCHITECT_HANDOFF_PROMPT_07.md` | **MISSING — never written to disk** (referenced in earlier sessions; only `docs/P07_ARCHITECTURE_PLAN.md` exists). |
| p07 `inference/` subpackage | **ABSENT** (workflow inference + preference candidate generation promised by docstring + P07 plan §5.4) |
| p07 `discovery/` subpackage | **ABSENT** (opt-in consent gate + scanning coordinator promised by docstring + plan §5.2) |
| p07 tests | **NONE** (plan §8 success criteria untestable today) |
| `reasoning/` → L6 wiring | **STILL DEAD** — nothing fixed yet; `kernel_provider.py` still calls missing `AIKernel.has_models()/infer_text()`. |

---

## 3. PRIORITY ORDER (CONFIRMED BY PROJECT DIRECTOR)

> **1. HARDCODING REMEDIATION = FIRST PRIORITY. Then P07 continuation.**

### 3.1 P0 — Hardcoding remediation (see `docs/HARDCODING_AUDIT_HANDOFF.md` for full list)
- H1–H12: all L6 keyword/rule tables → AI-driven with deterministic fallback.
- Fix `registry.quality_score_for` double-count bug (`registry.py:428-436`, reliability counted twice).
- Rewire `src/aegis/reasoning/` into the real `AIKernel` interface; wire `reasoning_provider` into `PlannerService`/`GoalEngine`.
- Deterministic keep-list: risk/permission/sandbox/audit/scrubber/redact/policies MUST NOT change.

### 3.2 P1 — P07 continuation
- Build the missing `inference/` + `discovery/` subpackages to match the `p07/__init__.py` docstring + `docs/P07_ARCHITECTURE_PLAN.md` §5.
- Add tests for all existing p07 modules + the P07 success criteria (§8 of the plan: 95% app discovery, ≥8/10 workflows, candidate-only preference, zero leak, zero-after-shutdown).
- Wire scanners to `MemoryManager`/`KnowledgeGraph` via `persistence/env_store.py`.

---

## 4. REQUIRED CONTENT OF YOUR CONTINUATION PROMPT

1. **Warn block:** repository has uncommitted work — never `git clean`/`checkout`/`reset`/`discard` (master directive §21). Preserve `l4_memory` edits + `p07/`.
2. **Stage 0 (verification):** run full suite (expect 793 sys / 782 venv); confirm imports of `aegis.l4_memory.p07.*`.
3. **Stage 1 (P0 hardcoding):** reference `docs/HARDCODING_AUDIT_HANDOFF.md`; implement in this exact order:
   1. Fix registry double-count bug + unit test.
   2. Reconcile `AIKernel` interface vs `reasoning/kernel_provider.py`; make provider work.
   3. Migrate L6 modules (H1–H10) to call `reasoning` provider with deterministic fallback; keep existing keyword code as explicit `"source=fallback"` path.
   4. Keep deterministic modules untouched (list them).
4. **Stage 2 (P1 P07):** complete `inference/` + `discovery/`, add tests, wire storage.
5. **Stage 3 (close):** re-run suite; update `.agents/AGENTS.md`, roadmap, current_state; report A–O (directive §26).
6. **Success criteria:** suite green; zero upward deps; AI outputs schema-validated via L3; offline fallback proven; no privacy-leak regressions; all p07 success criteria testable + passing.

---

## 5. KNOWN GOOD FACTS FOR YOUR PLANNING (verified today)

- `python` (system, 3.12, pytest 8.3.3): **793 passed, ~7s**.
- `.venv` (pytest 9.1.1 + pytest-anyio): **782 passed** (11 fewer L1/L2 anyio params).
- Layer counts: L3=256, L4=130, L5=103, L6=256 (approx; L6 is the hardcoding target).
- `import aegis.l4_memory.p07.*` all OK (model, scanners, observer, persistence, privacy).
- L5 risk/permission/sandbox = deterministic safety (correct as-is).

---

## 6. CANNED ASK

> ⚠️ "READ this doc + `docs/HARDCODING_AUDIT_HANDOFF.md` + `docs/P07_ARCHITECTURE_PLAN.md`. Verify the repo (git status, run tests). Then produce ONE self-contained **CONTINUATION PROMPT** for the next engineer with: (1) preserve-uncommitted-work warning, (2) Stage 0 verify, (3) **Stage 1 HARDCODING REMEDIATION FIRST** (registry bug, dead `reasoning/` wiring, L6 H1–H10 with deterministic fallback), (4) Stage 2 P07 continuation (missing `inference/`+`discovery/`, tests, wiring), (5) Stage 3 close-out + A–O report. Include exact files, schemas, success criteria, and DO-NOT list. **No implementation by you now.**"

---
*Audit Agent — handoff complete. P0 = hardcoding; P1 = P07. Nothing committed is at risk; uncommitted work must be preserved.*
