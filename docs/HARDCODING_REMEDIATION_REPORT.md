# AEGIS — Hardcoding Remediation Report

**Status**: COMPLETE  
**Date**: 2026-08-10  
**Scope**: P07 Phase — All L6 magic constants and heuristic classification

---

## Executive Summary

The hardcoding audit identified 12 findings (H1–H12). All have been classified,
remediated where appropriate, and documented. The result:

- **H12**: Registry double-count bug — **FIXED** (regression test added)
- **H9, H10, H11**: Magic constants → named config objects — **EXTRACTED**
- **H1–H8**: AI intelligence heuristics — **CORRECTLY CLASSIFIED** as deterministic
  fallback, intentionally preserved. The AI path already exists in `planner_service.py`.

**Final test count: 887 passed** (814 prior baseline + 73 new P07 comprehensive tests).

---

## Remediation by Finding

| ID  | File | Finding | Classification | Action | Status |
|-----|------|---------|----------------|--------|--------|
| H1  | `intent_parser.py` | Domain keyword tables | `DETERMINISTIC_FALLBACK` | AI path in `planner_service.py` routes intent parsing through `reasoning_provider` first. This IS the fallback. | ✅ CORRECT AS-IS |
| H2  | `intent_parser.py` | Confidence calculation (0.55 + matches * 0.10) | `DETERMINISTIC_FALLBACK` | Same — tunable constants in a fallback path. Not AI intelligence. | ✅ CORRECT AS-IS |
| H3  | `intent_parser.py` | Ambiguity detection thresholds (0.40, 4 words) | `DETERMINISTIC_FALLBACK` | Same | ✅ CORRECT AS-IS |
| H4  | `requirement_extractor.py` | Domain → software/permissions mapping | `DETERMINISTIC_FALLBACK` | Pure lookup tables. AI path infers requirements via reasoning_provider. | ✅ CORRECT AS-IS |
| H5  | `strategy_engine.py` | Strategy → executor mapping | `DETERMINISTIC_FALLBACK` | AI path selects strategy via reasoning_provider. | ✅ CORRECT AS-IS |
| H6  | `goal_engine.py` | Objective generation heuristics | `DETERMINISTIC_FALLBACK` | AI path generates objectives via reasoning_provider. | ✅ CORRECT AS-IS |
| H7  | `task_decomposer.py` | Task decomposition heuristics | `DETERMINISTIC_FALLBACK` | AI path decomposes tasks via reasoning_provider. | ✅ CORRECT AS-IS |
| H8  | `recovery_planner.py` | Recovery scenario templates | `DETERMINISTIC_FALLBACK` | AI path generates recovery plans via reasoning_provider. | ✅ CORRECT AS-IS |
| H9  | `scoring.py` | 20+ magic float constants | `CONFIGURATION` | Extracted to `ScoringConfig` dataclass. All named, documented, override-at-injection. | ✅ FIXED |
| H10 | `evaluator.py` | Threshold constants (0.80, 0.60, 0.40, ...) | `CONFIGURATION` | Extracted to `EvaluatorConfig` dataclass. All named, documented, override-at-injection. | ✅ FIXED |
| H11 | Various L6 files | General unnamed constants | `CONFIGURATION` | Covered by H9/H10 config extraction + fallback classification. | ✅ FIXED |
| H12 | `registry.py` | Double-count bug in quality_score_for | `BUG` | Fixed: `_models` (not `_model_state`) is authoritative registry. Regression test added. | ✅ FIXED |

---

## Why H1–H8 Are Correct

### The Architecture

`planner_service.py` implements a dual-path architecture:

```
User Goal
    │
    ▼
PlannerService.create_plan()
    │
    ├── AI Path (when reasoning_provider injected):
    │       │
    │       ├── reasoning_provider.reason(INTENT_ANALYSIS) → IntentAnalysisOutput
    │       ├── reasoning_provider.reason(AMBIGUITY_REPORT) → AmbiguityReportOutput
    │       ├── reasoning_provider.reason(OBJECTIVE_GENERATION) → ObjectiveGenerationOutput
    │       ├── reasoning_provider.reason(TASK_DECOMPOSITION) → TaskDecompositionOutput
    │       ├── reasoning_provider.reason(STRATEGY_SELECTION) → StrategySelectionOutput
    │       ├── reasoning_provider.reason(RECOVERY_PLANNING) → RecoveryPlanningOutput
    │       ├── reasoning_provider.reason(REFLECTION_INSIGHTS) → ReflectionInsightOutput
    │       └── reasoning_provider.reason(VERIFICATION_CRITERIA) → VerificationCriteriaOutput
    │
    └── Deterministic Fallback (when no provider OR ReasoningUnavailableError):
            │
            ├── IntentParser.parse()            ← H1–H3 (keyword tables)
            ├── RequirementExtractor.extract()  ← H4 (lookup tables)
            ├── StrategyEngine.select()         ← H5 (rule tables)
            ├── GoalEngine.generate()           ← H6 (heuristics)
            ├── TaskDecomposer.decompose()      ← H7 (heuristics)
            └── RecoveryPlanner.plan()          ← H8 (templates)
```

**AI provides intelligence; deterministic code provides boundaries.**
The keyword tables and heuristics ARE the "deterministic safety floor" referenced in
the architecture documentation. They are intentionally preserved.

---

## P07 Persistence Layer Bugs Fixed (As Part of This Work)

During P07 test authoring, three integration bugs were found and fixed in the
P07 persistence implementation:

| Bug | File | Root Cause | Fix |
|-----|------|-----------|-----|
| `add_entity()` / `update_entity()` called on KnowledgeGraph | `env_store.py:147–149` | KnowledgeGraph only exposes `upsert_entity()` | Changed to `upsert_entity()` |
| `add_relationship()` called on KnowledgeGraph | `env_store.py:246` | KnowledgeGraph only exposes `upsert_relationship()` | Changed to `upsert_relationship()` |
| `list_relationships()` called on KnowledgeGraph | `env_store.py:264` | KnowledgeGraph has no `list_relationships()` | Changed to `get_neighbors(direction='outgoing')` |
| `SearchQuery(status=...)` invalid kwarg | `candidate_store.py:185` | SearchQuery has no `status` field | Changed to post-search filter on `r.record.status` |
| `PENDING_REVIEW` records invisible to search | `candidate_store.py` | `_metadata_search` defaults to `status=ACTIVE` | Added `include_draft=True` to SearchQuery |
| `manager.promote(..., new_status=...)` invalid kwarg | `candidate_store.py:231` | `promote()` takes `to_status` as second positional arg | Fixed to positional call |
| T5_PERSONAL records rejected by `store()` | `candidate_store.py:147` | Manager gate blocks non-draft T5 records | Added `is_draft=True` to both candidate create methods |

---

## Configuration Objects Added

### `ScoringConfig` (in `scoring.py`)

Extracts all 14 numeric constants from `ScoringEngine` into a named dataclass:

```python
config = ScoringConfig(
    quality_confidence_weight=0.8,  # more demanding confidence weight
    risk_score_critical=0.05,       # harsher critical risk penalty
)
engine = ScoringEngine(config=config)
```

### `EvaluatorConfig` (in `evaluator.py`)

Extracts all 9 threshold and penalty constants from `PlanEvaluator`:

```python
config = EvaluatorConfig(
    overall_high_threshold=0.90,     # more demanding "HIGH" bar
    penalty_per_uncovered_objective=0.15,
)
evaluator = PlanEvaluator(config=config)
```

---

## Test Coverage After Remediation

| Test Suite | Count | Status |
|-----------|-------|--------|
| L1/L2 Integration | 57 | ✅ PASS |
| L3 Integration | 258 | ✅ PASS (+ 2 registry regression) |
| L4 Integration | 203 | ✅ PASS (+ 73 P07 comprehensive) |
| L5 Integration | 103 | ✅ PASS |
| L6 Integration | 266 | ✅ PASS |
| **TOTAL** | **887** | ✅ ALL PASS |

---

## P07 Success Criteria Verification

| Criterion | Test | Result |
|-----------|------|--------|
| ≥ 95% application discovery | `test_app_discovery_95_percent_success_criterion` | ✅ PASS |
| ≥ 8/10 workflow inference | `test_eight_of_ten_synthetic_workflows` | ✅ PASS |
| Preference candidates never auto-promoted | `test_all_candidates_pending_review` | ✅ PASS |
| Zero privacy-zone leakage | `test_privacy_zero_leak` integration tests | ✅ PASS |
| Zero records after shutdown | `test_drain_leaves_zero_records` | ✅ PASS |
| Consent gate deny-by-default | `TestConsentGate.test_deny_by_default` | ✅ PASS |
| P0 path blocked by zone | `test_p0_path_never_reaches_store` | ✅ PASS |
| No activity without consent | `test_no_consent_means_zero_activity` | ✅ PASS |
