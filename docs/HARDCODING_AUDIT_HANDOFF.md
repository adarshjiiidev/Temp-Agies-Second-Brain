# AEGIS — HARDCODING AUDIT HANDOFF FOR SYSTEM ARCHITECT

**From:** Audit Agent (read-only code audit)
**To:** Principal System Architect
**Purpose:** This document is the COMPLETE hardcoding/architecture audit. Your task: read it, verify against the repo if you wish, and **write ONE remediation prompt (or a small set) for the next build agent** that solves all the hardcoded-intelligence problems identified here — while preserving the deterministic safety layer.

> 🎯 **Deliverable you must produce: a build prompt for the remediation of L6 pseudo-intelligence toward the AI-driven architecture, with deterministic fallback, wired to the existing (currently dead) reasoning layer. Do NOT implement code; produce the prompt/spec the engineer will follow.**

---

## 0. MISSION CONTEXT (from master directive §3–§4, §27)

> **AI decides what should happen; deterministic infrastructure guarantees what is allowed to happen.**

- Deterministic code = security, privacy, permissions, sandbox, risk, audit, lifecycle — **must stay deterministic**.
- AI code = intent interpretation, planning, decomposition, reasoning, summarization, preference adaptation, strategy generation.
- **Do NOT replace safety invariants with AI.** Do NOT replace intelligence with giant hardcoded rule tables.
- System must migrate: `hardcoded → structured abstractions → AI-assisted → AI-driven → learning` while keeping safety deterministic.

---

## 1. THE CENTRAL PROBLEM

The **entire L6 planning stack is hardcoded keyword/rule pseudo-intelligence.** There is exactly **zero** AI involvement in the live planning path. A legitimate AI path exists (`src/aegis/reasoning/`) but is **dead code** — it references a nonexistent `AIKernel` API and nothing wires it in.

Every "intelligence" decision — domain classification, requirements, strategy, objectives, task templates, failure modes, effort/risk/scores — comes from **literal tables of keywords and magic numbers**.

---

## 2. WHAT IS CORRECT AND MUST NOT CHANGE (§3/§15 deterministic by design)

These are genuine safety invariants. **Leave them as deterministic tables. Do not "AI-ify."**
- `src/aegis/l5_execution/risk/analyzer.py` — `_VERB_RISK`, `_SUBJECT_TRUST`, `_RESOURCE_SCOPE_RISK`, hard overrides.
- `src/aegis/l5_execution/permission/*` , `policy/*`, `sandbox/*`, `audit/chain.py`
- `src/aegis/l3_intelligence/ai_kernel/scrubber.py` — P0/PII regex
- `src/aegis/l2_foundation/crypto/redact.py` — secrets REDACT patterns
- `src/aegis/l4_memory/policies.py` — retention/access/merge + `PrivacyZonePolicy` (already P07-aligned; uncommitted edits are intentional, preserve them)
- `src/aegis/l3_intelligence/ai_kernel/accounting.py` — budget/cost enforcement (soft-configurable)

Also NOT a violation (configurable / standard):
- `l3_intelligence/ai_kernel/router.py`, `keys.py`, `contracts.py`, `types.py` — data/configural routing weights (documented in 07_AI_STRATEGY), keep config-driven.

---

## 2. VIOLATIONS — HARDCODED PSEUDO-INTELLIGENCE (migrate, don't pretend)

All under `src/aegis/l6_planning/`. For each: extract the decision being made, today's literal table, and what AI should eventually produce (structured output schema).

| # | File + line | Hardcoded decision | What AI should decide |
|---|---|---|---|
| H1 | `intent/intent_parser.py:27-74` `_DOMAIN_KEYWORDS` | domain classification (~200 literals) | free-text → domain, with schema `{domain, confidence, reasons}` |
| H2 | `intent_parser.py:76-93` internet/local/tool keywords | internet/local/tool detection | include in same structured output |
| H3 | `intent_parser.py:207-219` | confidence formulas `0.55+n*0.10` | AI confidence + calibration |
| H4 | `intent/requirement_extractor.py:36-88` `_DOMAIN_SOFTWARE/_PERMISSIONS/_EFFORT` | requirements inference | AI → `{software_needed, permissions_needed, effort, risk}` |
| H5 | `strategy/strategy_engine.py:20-33` `_DOMAIN_STRATEGY` | strategy selection | AI → `{strategy, rationale}` (deterministic policy override stays) |
| H6 | `planning/goal_engine.py:31-96` `_DOMAIN_OBJECTIVES` | objective templates | AI → objective breakdown |
| H7 | `decomposition/task_decomposer.py:84` `_TASK_TEMPLATES` | per-domain task templates | AI → task list w/ action_hint, risk, seconds |
| H8 | `recovery/recovery_planner.py:55-99` `_FAILURE_MODES/_FALLBACK_STRATEGIES` | failure scenarios + probabilities | AI → scenario/fallback, with deterministic escalation override |
| H9 | `reasoning/scoring.py:103-144` | heuristics `0.6/0.3/0.1`, `task/15`, log-speed | replace formulaic scoring with AI judgement OR keep tuneable weights (DECISION NEEDED) |
| H10 | `reasoning/evaluator.py:47-131` | penalties/thresholds | AI judgement (candidate) |
| H11 | `reasoning/tradeoffs.py`, `goal_engine.py:297-303`, `reflection_engine.py:145-154`, `verification/verification_planner.py:120-129`, `orchestration/planner_service.py:898` | assorted magic constants | consolidate; mark explicit |  |
| H12 | `l3_intelligence/ai_kernel/registry.py:428-436` `quality_score_for()` | quality heuristic weights `0.35/0.35` | **BUG: `reliability` used twice — double-count.** Fix now. |

---

## 3. THE DEAD AI PATH (why it's unused — you must rewire it)

`src/aegis/reasoning/`:
- `kernel_provider.py:83` calls `self._kernel.has_models()` — **doesn't exist** on `LISKernel`.
- `kernel_provider.py:122` calls `self._kernel.infer_text()` — **doesn't exist**.
- `kernel_provider.py:110` `output_schema.model_json_schema()` → validates via L3 `structured.py` — good pattern to keep.
- No L6 module imports `reasoning/` at all — the planned injection `PlannerService(reasoning_provider=provider)` is described in docstrings only.

**Action for you:** reconcile `AIKernel`'s real interface (see `l3_intelligence/ai_kernel/kernel.py` in repo) with what `reasoning/kernel_provider.py` needs, then define the migration so `reasoning/` becomes the ONE place L6 calls for AI. Keep a deterministic fallback for offline.

---

## 4. ARCHITECTURE TARGET (what the migration prompt should produce)

```text
Input (user goal)
   ▼
PARSING LAYER:
   IntentParser:
     - PRIMARY: AI interpretation → structured Intent (schema)
     - FALLBACK (offline/denied): keyword heuristic, EXPLICITLY flagged "fallback" (keep as disaster backup, not the main path)
   ▼
REQUIREMENTS LAYER:                 (H4)
   - AI → software/permission/effort; deterministic policy still enforces
   ▼
GOAL/OBJECTIVE LAYER: (H6-H7)
   - AI → objectives + tasks (structured TaskPlan schema)
   ▼
STRATEGY LAYER: (H5, deterministic-policy priority unchanged)
   ▼
SCORING + DECISION: (H9-H11) — AI judgment (candidate) OR weighted-score (DECISION NEEDED)
   ▼
PLANNING RESULT → Execution (L5) — safety deterministic throughout
```

**Provider-Neutral requirement:** all AI through the `reasoning/` provider → the L3 AIKernel abstraction. Local: Ollama/LM Studio/vLLM. Remote: OpenRouter/Groq. Offline → deterministic fallback. No hardcoded provider routing.

---

## 5. OFFICE/PRIVACY HARD INVARIANTS *never* AI-driven (unchanged)

- **P0/P1 data is never returned to cloud LLM.**  `L4` memory + L3 scrubber handle tier filter. The AI layer must receive scrubbed context ONLY. (Keep `policies.py` access/`scrubber.py`.)
- **Notice: keep every pre-upload redaction/consent gate deterministic.**

---

## 6. DELIVERABLE SPEC — what YOUR prompt to the engineer must contain

1. **File path scope** — which files to change / which to create (`src/aegis/reasoning/*` wiring; L6 modules; any new schemas in `reasoning/schemas.py`).
2. **The structured output schemas** for each step (H1–H10) as Pydantic models, so the engineer has exact targets.
3. **The fallback strategy**: how each AI step degrades offline (keep deterministic output shape; mark `"source":"fallback"` / `"model":null` in provenance).
4. **Wire the reasoning provider** into `PlannerService` / `GoalEngine` (clear `reasoning/` dead-interface fix: align `kernel.infer` signature + `has_models`).
5. **Regression tests** to add (tests/integration_l6) — fake provider, offline fallback, privacy zero-leak.
6. **Determinate keep-list** (do NOT rewrite the §G list above).
7. **Acceptance criteria**: full suite passes (793 sys / 782 venv) for baseline; NO upward deps; all new AI outputs validated by L3 schema; fallback proven offline; existing tests updated NOT removed.
8. **DO-NOT** boundary recap (directive §5, §27).

---

## 7. CONTRACT MANUAL for the engineer's prompt (verbatim, reused)

```
DETERMINISTIC KEEP  →  privacy, security, permissions, sandbox, audit, retention, execution/state machine
AI / LEARNED        →  similar semantic classification, decomposition, strategy synthesis, reasoning
NEVER               →  AI overriding consent/allowed;  hardcoded keyword tables as "the intelligence"
```

---

## 8. A REQUIRED ADDITIONAL ITEM — the registry double-count bug

**SPEC (must include a fix):** `registry.quality_score_for` at `src/aegis/l3_intelligence/ai_kernel/registry.py:415`:
```
score = structural*0.35 + reliability*0.35 + long_context_bonus + reliability      # reliability counted twice
```
Correct form: `structural*0.35 + reliability*0.35 + long_context_bonus`, clamp/normalize. Confirm with a unit test.

---

## 9. WHICH TESTS EXIST TODAY — don't break (already verified)

- Full suite **793 passed** (system `python`, pytest 8.3.3) / **782** (`.venv`, pytest-anyio — 11 fewer L1/L2 params).
- layer counts: L3=256, L4=130, L5=103, L6=256... L6 units cover IntentParser/GoalEngine/scoring/decomposer/etc.
- New AI wiring must keep exact keyword fallback tests intact (they'll be the "fallback" path tests now).

---

## 10. FINAL ASK (canned response to architect)

> ⚠️ "READ everything. Re-verify a few files in the repo. Then produce a single, self-contained **BUILD-ONLY remediation prompt** (or group of steps) that makes L6's planning go through the `reasoning/` AI provider with an explicitly-marked deterministic fallback, wires the dead provider to the real `AIKernel` API, fixes the registry double-count, keeps every safety module deterministic, and adds regression tests — without breaking the 793/782 suite. Present stage-ordered steps and exact success criteria. **No implementation now.**"
---
*Audit Agent — handoff complete. This file documents the state I trust for you to plan against.*