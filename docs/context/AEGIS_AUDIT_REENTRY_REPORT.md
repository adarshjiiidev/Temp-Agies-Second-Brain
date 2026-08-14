# AEGIS AUDIT RE-ENTRY — CURRENT STATE

**Role:** Senior Audit / Verification Engineer (read-only audit)
**Date:** 2026-08-14
**Mode:** READ-ONLY — no source modified, nothing committed, working tree preserved.

---

## 1. Executive Verdict

**YELLOW**

The major P07 remediation claims are **independently verified true** — not regressed: H9/H10 config extraction done, H12 double-count fixed, the L6 AI path is genuinely wired and reachable, safety isolation is intact (L5 has zero reasoning imports), P07/P07-GAP/P07.5 components exist and are tested, and P-RUST is a legitimate pure acceleration kernel (26 tests). However, this is not GREEN because: (a) there is **no full-chain integration test** (`PlannerService + KernelReasoningProvider + real AIKernel + FakeProvider`), (b) AI intent does **not** reach `mission.parsed_intent` (partial AI authority), (c) two lifecycle components (FreshnessScheduler, ProviderHealthMonitor) are **not wired**, (d) the `WorkflowAutoPromoter` docstring claims a privacy-zone check the code **never performs** (stored `_zones` unused), (e) `RiskAssessmentOutput` + `risk_assessment_v1` prompt are **dead code**, and (f) docs contradict code (`current_state.json` still says the suite hangs at L5). No P0 defects; no regressions.

---

## 2. Repository State

- **HEAD:** `54afa35` — "docs: Phase R3 complete - R3 report, AGENTS.md, RUST_PERFORMANCE_CORE.md updated"
- **Branch:** `main` (ahead of `origin/main` by 1 commit)
- **Working tree:** CLEAN — only untracked `docs/context/AEGIS_AUDIT_REENTRY_REPORT.md` (this report)
- **Uncommitted files:** none (no source modifications made)
- **Milestone per AGENTS.md:** P07.5 + P-RUST R0–R3 complete; L7 HCI not started; P-RUST R4/R5 not started

---

## 3. Test Verification (measured, not trusted)

| Suite | Command | Result |
|---|---|---|
| Python | `python -m pytest tests/ -q --tb=short` | **1060 passed, 1 skipped, 4 warnings, 21.50s** |
| Rust | `cargo +stable test --workspace` | **26 passed, 0 warnings, 0.49s** |

- Rust breakdown: `aegis_audit_chain` 1, `aegis_crypto` 9, `aegis_ffi_common` 1, `aegis_search_core` 6, `aegis_graph_core` 9.
- The 4 warnings are pydantic `protected_namespaces="model_"` collisions (`model_id`, `model_used`) — cosmetic, not functional.
- AGENTS.md's claimed baselines (1060/1060 Python, 26 Rust) **match measured reality**.

---

## 4. Hardcoding Matrix

| ID | File | Finding | Classification | Evidence | Status | Priority |
|---|---|---|---|---|---|---|
| H1 | `l6_planning/intent/intent_parser.py:27` `_DOMAIN_KEYWORDS` | ~200 domain keywords | **DETERMINISTIC FALLBACK** | AI path active when `is_available` (planner_service.py:157); `_detect_domain` only reached in fallback | Confirmed | — |
| H2 | `intent_parser.py:76-93` internet/local/tool keywords | internet/local/tool detection | **DETERMINISTIC FALLBACK** | `_check_internet`/`_check_local_only` in fallback path only | Confirmed | — |
| H3 | `intent_parser.py:207-219` | confidence formulas `0.55+n*0.10` | **DETERMINISTIC FALLBACK** | Same module, fallback-only | Confirmed | — |
| H4 | `intent/requirement_extractor.py:36-81` | software/permission/effort maps | **DETERMINISTIC FALLBACK** | Deterministic requirement inference; policy enforcement stays L5 | Confirmed | — |
| H5 | `strategy/strategy_engine.py:20-33` `_DOMAIN_STRATEGY` | strategy selection | **DETERMINISTIC FALLBACK** | AI path calls `r.reason(STRATEGY_SELECTION)` first | Confirmed | — |
| H6 | `planning/goal_engine.py:32-96` `_DOMAIN_OBJECTIVES` | objective templates | **DETERMINISTIC FALLBACK** | AI objectives override deterministic ones in AI path (planner_service.py:270-283) | Confirmed | — |
| H7 | `decomposition/task_decomposer.py:84` `_TASK_TEMPLATES` | task templates | **DETERMINISTIC FALLBACK** | AI TaskSpecs converted via `_ai_specs_to_tasks` | Confirmed | — |
| H8 | `recovery/recovery_planner.py:55-99` | failure modes + probabilities | **DETERMINISTIC FALLBACK** | AI path calls `RECOVERY_PLANNING` prompt | Confirmed | — |
| H9 | `reasoning/scoring.py` | scoring heuristics | **CONFIGURATION** ✅ FIXED | `ScoringConfig` dataclass (scoring.py:28), all constants extracted, `default()` == pre-H9 | **FIXED** | — |
| H10 | `reasoning/evaluator.py` | evaluator thresholds | **CONFIGURATION** ✅ FIXED | `EvaluatorConfig` (evaluator.py:40) | **FIXED** | — |
| H11 | `tradeoffs.py:53-54` (0.20/0.08), `reflection_engine.py:145-154`, `planner_service.py:898` `_prob_map`, `_risk_map`, `_severity_to_blocking`, `_ai_recovery_to_plan` retry (1/3), `_seconds_to_effort_level` | assorted heuristics | **CONSTANT** | Named thresholds in tradeoffs (class attrs); reflection complexity formula `(tasks/30*0.4 + risk*0.3 + (1-conf)*0.3)`; planner helper maps | Open (P2) | P2 |
| H12 | `l3_intelligence/ai_kernel/registry.py:415-444` | `quality_score_for` double-count | **BUG** ✅ FIXED | `structural*0.35 + reliability*0.35 + long_context_bonus` — reliability counted **once**; comment documents the fix (registry.py:430-436) | **FIXED** | — |

### New findings

| ID | File | Finding | Classification | Evidence | Status | Priority |
|---|---|---|---|---|---|---|
| N1 | `inference/promotion.py:244-248` | `zone_registry` stored but **never used** in `_try_promote`; docstring:313 claims "Privacy zone check passes (if zone_registry provided)" — no such code path exists | **BROKEN CONTRACT** | grep: `_zones` appears only at 248 (assignment); no `check_path/check_node` calls | Deficit | P1 |
| N2 | `schemas.py:233` + `risk_assessment_v1.yaml` + `PromptId.RISK_ASSESSMENT` | RiskAssessmentOutput declared, prompt exists, but **not called** anywhere in `_ai_create_plan` (8 prompts used, not 9) | **DEAD CODE** | grep: no `r.reason(RISK_ASSESSMENT)` in planner | Deficit | P2 |

---

## 5. AI Architecture (actual call graph, traced)

```
PlannerService.create_plan (planner_service.py:128)
  ├─ if self._reasoning and self._reasoning.is_available  (line 157)
  │    └─ _ai_create_plan  (line 178)
  │         ├─ r.reason(INTENT_ANALYSIS)      → IntentAnalysisOutput      (186)
  │         ├─ r.reason(AMBIGUITY_DETECTION)  → AmbiguityReportOutput     (193)
  │         ├─ r.reason(OBJECTIVE_GENERATION) → ObjectiveGenerationOutput (211)
  │         ├─ r.reason(STRATEGY_SELECTION)   → StrategySelectionOutput   (224)
  │         ├─ r.reason(TASK_DECOMPOSITION)   → TaskDecompositionOutput   (246)
  │         ├─ r.reason(VERIFICATION_CRITERIA)→ VerificationCriteriaOutput(307)
  │         ├─ r.reason(RECOVERY_PLANNING)    → RecoveryPlanningOutput    (323)
  │         └─ r.reason(REFLECTION)           → ReflectionInsightOutput   (359)
  └─ else → _deterministic_create_plan  (line 415)  [keyword tables only here]

KernelReasoningProvider.reason (kernel_provider.py:101)
  ├─ library.get(prompt_id)  [real PromptLibrary, all 15 templates on disk]
  ├─ output_schema.model_json_schema() → rendered prompt
  ├─ builds real AIRequest(StructuredOutputRequirements, RoutingRequirements)
  └─ await kernel.generate(request)  (kernel_provider.py:188)

AIKernel.generate (kernel.py:167)
  ├─ scrub_messages → elevated privacy tier  (Phase 1)
  ├─ cache lookup (P0 bypasses cache)        (Phase 2)
  ├─ router.route (P0 NEVER_CLOUD, P1 PREFER_LOCAL) (Phase 3)
  └─ fallback chain per RouteDecision (Phase 4):
       key select → budget check → provider.chat →
       structured validation+retry → ledger → cache → metrics → AIResponse
```

- **All links exist and are reachable.** `AIKernel.has_models()/list_models()/provider_count()` (kernel.py:143-161), `generate()` (kernel.py:167), `PromptLibrary` with 15 YAML templates including all 8 used PromptIds — all verified.
- **`is_available`** duck-types `kernel._registry._models` (kernel_provider.py:96) — works against real AIKernel.
- **Provider abstraction:** Groq, OpenRouter, Ollama, vLLM, Fake all extend `BaseProvider`; `ProviderRegistry` maps provider_id→provider.

---

## 6. AI vs Fallback — PROVEN (partially)

- **Proven at L3 kernel level** (`tests/integration_l3/test_reasoning_integration.py`): real `AIKernel + FakeProvider` chain exercises `KernelReasoningProvider.reason()` — P0 rejection (`test_generate_p0_refuses_cloud` asserts cloud call_count == 0), bad-prompt-id → ReasoningUnavailableError, is_available true/false. **No network.**
- **Proven at L6 level** (`tests/integration_l6/test_ai_orchestration.py`): `PlannerService + MockReasoningProvider` — AI-available path asserts all 8 prompts called exactly once; unavailable path asserts 0 calls and deterministic fallback; garbage strategy string → BALANCED.
- **NOT proven end-to-end:** there is **no test** driving `PlannerService + KernelReasoningProvider + real AIKernel + FakeProvider` through the complete chain. L3 tests use a **stub** prompt library and call `.reason()` directly; L6 tests use `MockReasoningProvider`, not the kernel. The seam between the two proven halves is untested. This is a genuine test-coverage gap, not a code gap.

---

## 7. AI Intent → Mission — **ALIGN**

Investigation:
- `_ai_create_plan` calls `mission = self._goal_engine.create_mission(...)` (planner_service.py:261) — this **always** runs the deterministic parser; then overrides `objectives` and `strategy` via `model_copy` (line 283).
- `mission.parsed_intent` (domain/verb/confidence) remains **deterministic** — the AI `intent_out` is used only to drive downstream prompts and set objective `confidence = intent_out.confidence * 0.9`.
- Answer: (A) partially intentional — the mission contract must remain structurally valid for the deterministic pipeline; (C) AI intent influences downstream planning but **not** mission intent state; (D) deterministic parse wins; (E) not documented anywhere.

**Recommendation: ALIGN.** Map AI intent into `mission.parsed_intent` (`domain`, `confidence`, `requires_internet`, `requires_local_only`) when the AI path is used, while keeping structural fields deterministic — so the AI is genuinely authoritative when available, and the fallback behavior stays identical. This is a P1.

---

## 8. P07 Status

All subpackages exist: `discovery/`, `inference/`, `model/`, `observer/`, `persistence/`, `privacy/`, `scanners/` (verified tree).

| Item | Status |
|---|---|
| Consent deny-by-default | COMPLETE (`ConsentGate`; coordinator blocks when no consent — coordinator.py:137) |
| Privacy zones before persistence | COMPLETE (`ZoneRegistry` gate in coordinator before `env_store` persist) |
| P0 exclusion / zero-leak | COMPLETE (`test_p0_path_never_reaches_store`, `test_privacy_zero_leak`) |
| T5 candidate safety | COMPLETE (promotion.py:346 blocks `kind=="preference"`; tests at 673, 890) |
| Workflow promotion (T4, threshold 3, cooldown, provenance) | PARTIAL — logic COMPLETE, but **zone check claimed in docstring not implemented** (N1) |
| Observer shutdown | COMPLETE (`test_*shutdown*`, zero-leftover invariants) |
| Freshness (FreshnessScheduler) | **PARTIAL** — implemented+tested, but **not wired** into ScanningCoordinator (no import) |
| Scanner discovery (app/project/cli/relation) | COMPLETE |
| Windows registry provider | COMPLETE (`WindowsRegistryProvider`, winreg) |
| Linux/macOS | **PARTIAL** — `PathToolProvider` cross-platform; **XDG provider deferred** (providers.py:6 "in future"); 1 test skipped non-Windows |
| Persistence integration | COMPLETE (env_store, candidate_store; 7 bugs previously fixed) |
| Coordinator integration | COMPLETE (consent + zones + scanners + store) |
| ProviderHealthMonitor lifecycle | **DEFERRED** — implemented+tested at L3, **not wired** into AEGIS lifecycle (no callers outside health.py/__init__.py/tests) |
| Reasoning → P07 | **DEFERRED** — no P07 module calls reasoning/ (correct for now; P07 is deterministic) |

---

## 9. P07.5 Provider Architecture

| Capability | Status | Evidence |
|---|---|---|
| Multiple keys per provider | COMPLETE | `KeyManager` per-provider key lists (keys.py:98) |
| Configurable key pools | COMPLETE | `EnvironmentProvisioner` registers `{P}_API_KEY_1..20` as a pool |
| Automatic rotation | COMPLETE | 4 strategies: ROUND_ROBIN, LRU, LRF, HEALTH_AWARE (keys.py:205-212) |
| Cooldown on failed keys | COMPLETE | `mark_failure` → rate-limit (30s), auth (permanent), quota (86400s) |
| Rate-limit handling | COMPLETE | `FailureCategory.RATE_LIMITED` → `rate_limited_until` |
| Provider health scoring | COMPLETE | `ProviderHealthMonitor` threshold-gated DOWN (failure_threshold=3), UNKNOWN-safe |
| Fallback between providers | COMPLETE | kernel.py fallback chain (router decisions, provider_not_found/key_unavailable/budget_denied continue) |
| Local-first routing | COMPLETE | P0 NEVER_CLOUD (router.py:16,169-173), P1 PREFER_LOCAL (router.py:245-271) with audit flag |
| Free-tier / offline | PARTIAL | Local providers cost 0; `is_available` gating; offline → deterministic fallback |
| Credentials outside source code | COMPLETE | `vault_ref` only `env:`/`file:` schemes; raw secrets never stored/logged; keyring hook stubbed |
| Browser account/key automation | **SAFELY PROHIBITED** | `BrowserProvisioner` raises NotImplementedError (credentials.py:337); explicit no-CAPTCHA/no-account-creation contract |

---

## 10. P-RUST

- **R0** COMPLETE (audit + ADR-0001 + migration map). **R1** COMPLETE (crate repairs, `cargo +stable test` 11→pass). **R2** COMPLETE (crypto stays Python; B1–B6). **R3** COMPLETE (`aegis_search_core` + `aegis_graph_core`, 26 tests total — re-measured passing).
- Rust classification: **GOOD — pure acceleration kernel.** No FFI, no I/O in inner loops, u32 indices, POD structs; no business-logic duplication, no policy bypass, no upward deps. Verified: `crates/` has only the 5 kernels + bench; PyO3 absent from `src/` (single docstring mention).
- **R4 readiness: READY.** Recommendation stands: profile real L5 `FilesystemExecutor` under P07 app-scanning workload; implement `aegis_scanner_core` only if >5s at realistic scope.
- **R5 readiness: NOT STARTED.** No PyO3 wiring exists; Rust kernels remain unconnected to Python. This is explicitly future work (AGENTS.md §9).

---

## 11. Dependency Audit (L1→L7)

- Programmatic AST scan of all `aegis` imports: **0 genuine upward/circular violations.**
- The only 2 flagged edges are `l6_planning → aegis.reasoning` — but `reasoning/` is a redesign package that itself imports **only** L1 (interfaces) + L3 (contracts/types), so the actual direction is L6→reasoning→L3 (downward). Not a violation.
- `prompts/` and `capabilities/` import only themselves.
- No hidden service locators; no direct provider calls bypassing L3; L6 accesses L5 types only (not internals); P07 never bypasses consent/zones; Rust doesn't call Python policy.

**Dependency verdict: PASS** (strict downward layering intact).

---

## 12. Safety Audit — **PASS**

- L5 has **zero imports** from `reasoning/`, `l3_intelligence`, `prompts`, `capabilities` (verified per-file). Risk/permission/policy/sandbox/audit are purely deterministic.
- `risk/analyzer.py` keeps `_VERB_RISK`/`_SUBJECT_TRUST`/`_RESOURCE_SCOPE_RISK` tables + overrides — never AI.
- P0 routing: `AIRouterPrivacyViolationError` raised when no local model (router.py:169-173); cloud call never made (test asserts call_count == 0).
- L2 crypto/redact, L3 scrubber, L4 policies unchanged.

**Verdict: PASS** — AI recommends/plans; deterministic infrastructure enforces.

---

## 13. Test Quality

- **unit-only:** most L6 modules (intent, goal, strategy, decomposition, recovery, verification, reflection).
- **mocked (integration-shaped, mock provider):** `test_ai_orchestration.py` — PlannerService + MockReasoningProvider, call-count assertions (good — proves fallback isn't silently primary).
- **integration (real kernel, no network):** `test_reasoning_integration.py` — KernelReasoningProvider + real AIKernel + FakeProvider; `test_kernel.py`, `test_credential_security.py` — real kernel.
- **real production-chain integration:** **MISSING** — the full `PlannerService + KernelReasoningProvider + AIKernel + FakeProvider` chain is never tested together (the seam gap).
- **benchmark-only:** `benches/bench_r3.py`, `bench_rust` Criterion benches — isolated kernels, not end-to-end.
- **Invalid AI output behavior:** only partially covered — garbage strategy string tested (→BALANCED); structured-output retry/exhaustion covered in kernel tests; no PlannerService test for kernel returning non-JSON (falls to deterministic).
- **P0 routing / privacy boundaries / shutdown:** well covered (P07 tests: `test_p0_path_never_reaches_store`, `test_privacy_zero_leak`, shutdown invariants; L3: `test_generate_p0_refuses_cloud`).

---

## 14. Architectural Profits

1. Provider-neutral AI kernel (`kernel.generate(AIRequest)` contract; 5 providers behind abstraction).
2. Deterministic safety boundary — L5 isolation verified programmatically (zero imports).
3. AI/fallback separation with call-count-proven behavior.
4. Privacy-first ingestion (zones/consent before every store write).
5. Structured AI outputs (strict Pydantic schemas, JSON-schema injected into prompts).
6. Configurable heuristics (ScoringConfig/EvaluatorConfig).
7. Multi-key pools + rotation + cooldown + health (complete key-management subsystem).
8. Local-first routing with hard P0 floor.
9. Rust as pure acceleration kernels (3× threshold discipline, no premature migration).
10. Strict downward-only layering (programmatically verified).

---

## 15. Architectural Deficits

| Rank | Deficit |
|---|---|
| **P1** | No full-chain integration test (PlannerService+KernelReasoningProvider+AIKernel+FakeProvider) |
| **P1** | AI intent does not reach `mission.parsed_intent` (partial AI authority) |
| **P1** | `WorkflowAutoPromoter` docstring promises privacy-zone check; `_zones` stored but never consulted |
| **P2** | FreshnessScheduler not wired into ScanningCoordinator |
| **P2** | ProviderHealthMonitor not wired into AEGIS lifecycle |
| **P2** | H11 residual constants (tradeoffs/reflection/planner maps) not config-extracted |
| **P2** | `RiskAssessmentOutput` + `risk_assessment_v1` prompt dead (never called) |
| **P2** | Docs contradict code: `current_state.json` stale ("hangs at L5"); AGENTS.md §3 still labels `reasoning/` "UNWIRED/UNTESTED" while §9 says wired — internal contradiction |
| **P3** | Linux/XDG discovery provider deferred; 642 pre-existing ruff issues; mypy blocked by Windows WDAC; R5 PyO3 unwired |

---

## 16. Prioritized Remediation

**P0:** none.

**P1**
1. Add an integration test: `PlannerService + KernelReasoningProvider + real AIKernel + FakeProvider` (real `PromptLibrary` or fixture templates), asserting both AI-available (8 prompts executed, AI-derived tasks/strategy reach result) and AI-unavailable/invalid-output (deterministic fallback).
2. ALIGN AI intent into `mission.parsed_intent` (domain/confidence/requires_internet/requires_local_only) in the AI path.
3. Implement the actual privacy-zone check in `WorkflowAutoPromoter._try_promote` (or remove the claim), and add a test that a zoned workflow key is not promoted.

**P2**
4. Wire FreshnessScheduler into ScanningCoordinator; wire ProviderHealthMonitor into the AEGIS lifecycle.
5. Extract H11 residual constants (TradeoffConfig; ReflectionConfig; planner map helpers).
6. Either wire `RISK_ASSESSMENT` into the AI pipeline or delete it (avoid dead schema).
7. Update stale docs (`current_state.json`, AGENTS.md §3).

**P3**
8. XDG discovery provider; R4 real-load profiling of FilesystemExecutor; R5 PyO3 wiring; ruff cleanup; mypy on non-Windows.

---

## 17. Recommended NEXT ENGINEERING TASK

**Exactly one:** Implement the **L6→L3 real-chain integration test** (P1 #1) — a new `tests/integration_l6/test_ai_real_chain.py` that constructs `PlannerService` with a `KernelReasoningProvider` over a real `AIKernel` + `FakeProvider` (no network), verifying: AI path executes all 8 prompts through the kernel and AI outputs reach the PlanningResult; provider-unavailable falls back deterministically with zero kernel calls; kernel returning invalid JSON safely degrades to the deterministic plan. This is the highest-value single step because it closes the one verified gap in the otherwise-proven AI architecture and guards the seam between the two halves already under test.

---

## 18. FINAL VERDICT

**YELLOW**

The repository is materially better than the previous audit — every major remediation claim held up under independent re-verification: H9/H10 config objects exist and are consumed, H12 is fixed with an explanatory comment, the L6 AI path is real and reachable through the real AIKernel, safety isolation is provably intact, and P-RUST R0–R3 is a legitimate pure-kernel effort with 26 passing tests. No regressions were found and no critical defect exists. But GREEN is withheld because the evidence also surfaced real gaps: the full AI chain is never tested end-to-end, AI intent never becomes authoritative mission state, a documented privacy-zone guard in `WorkflowAutoPromoter` is absent from the code, two lifecycle services are implemented-but-unwired, one schema+prompt pair is dead, and documentation still contradicts code. These are all fixable without architectural change, which is why the verdict is YELLOW rather than RED.

---

*Read-only audit. No source modified, nothing committed, working tree preserved. Only untracked file: `docs/context/AEGIS_AUDIT_REENTRY_REPORT.md` (this report).*
