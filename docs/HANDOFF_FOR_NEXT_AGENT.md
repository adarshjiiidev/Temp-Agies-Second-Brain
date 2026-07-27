# HANDOFF FOR NEXT CODING AGENT — PROJECT AEGIS

**Handoff Date:** 2026-07-27  
**Current State:** Prompts 01, 02, 03 are 100% COMPLETE and VERIFIED.  
**Next Prompt:** Prompt 04 — L4 Memory Layer (episodic, semantic, working memory).

---

## 1. QUICK START & VERIFICATION

Run the full verified test suite:
```bash
pytest tests/integration_l1l2 tests/integration_l3
```
**Expected:** 313 passed, 0 failed, 3 warnings (Pydantic namespace — harmless).

---

## 2. COMPLETED MILESTONES

| Prompt | Milestone | Status | Tests |
|--------|-----------|--------|-------|
| P01 | Strategy & Architecture Docs | ✅ DONE | N/A |
| P02 | L1 Core + L2 Foundation Runtime | ✅ DONE | 57 passed |
| P03 | L3 AI Kernel (Router, Providers, Budget, Keys) | ✅ DONE | 256 passed |

---

## 3. REPOSITORY ARCHITECTURE

### Layering Rules (enforced by import-linter)
- **L1** (`aegis.l1_core`) → no imports from L2+
- **L2** (`aegis.l2_foundation`) → imports L1 only
- **L3** (`aegis.l3_intelligence`) → imports L1 + L2, NOT L4+
- Future L4+ layers follow the same downward-only rule

### L3 AI Kernel Component Map

```
ai_kernel/
├── types.py          Enums: PrivacyTier (P0-P3), DeploymentKind, TaskType, QualityTier
├── contracts.py      Pydantic models: AIRequest, AIResponse, RoutingRequirements
├── registry.py       ModelRegistry + 10-stage filter_candidates()
├── keys.py           KeyManager: rotation strategies, cooldown, vault refs
├── accounting.py     CostAccountant: 4-point budget enforcement
├── cache.py          ResponseCache: LRU/TTL, P0 never cached
├── pipeline.py       PromptPipeline stage runner
├── streaming.py      StreamEvent + StreamEventEmitter
├── conversation.py   In-memory conversation history
├── structured.py     JSON extraction + Pydantic validation + retry loop
├── scrubber.py       §4.1 secret/PII detector → privacy tier auto-elevation  ← NEW P03
├── metrics.py        AIMetricsRegistry: rolling counters, p50/p95 latency     ← NEW P03
├── router.py         5-stage model router (hard→quality→SLA→score→budget)    ← NEW P03
├── kernel.py         AIKernel: top-level orchestrator (scrub→cache→route→infer) ← NEW P03
└── providers/
    ├── base.py       BaseProvider + ProviderRegistry
    ├── fake.py       Deterministic test provider (no network)                  ← NEW P03
    ├── ollama.py     Ollama local adapter (httpx)                              ← NEW P03
    ├── openrouter.py OpenRouter cloud adapter (httpx + SSE)                   ← NEW P03
    ├── groq.py       Groq cloud adapter (httpx + SSE)                         ← NEW P03
    └── vllm.py       vLLM self-hosted adapter (httpx + SSE)                   ← NEW P03
```

---

## 4. CRITICAL INVARIANTS (DO NOT BREAK)

### Privacy P0 NEVER CLOUD
- Any request with `privacy_tier=P0` (or any message containing API keys/PEM keys) **must never route to a non-local provider**.
- Test: `tests/integration_l3/test_router.py::test_p0_always_local_or_error` (25 cases)
- Test: `tests/integration_l3/test_kernel.py::test_p0_never_routes_to_cloud` (20 cases)
- Violation raises `AIRouterPrivacyViolationError` — never silently allowed.

### Budget NEVER Bypassed
- `CostAccountant.check_budgets()` runs BEFORE every inference call.
- `CostAccountant.record_spend()` runs AFTER every successful call.
- Local models ($0) always pass budget checks.

### Structured Output Invariant
- `StructuredOutputProcessor` either returns a **valid typed object** or raises `AIStructuredRetriesExhaustedError`.
- An invalid object MUST NEVER be silently returned to callers.
- Test: `test_structured.py` (50 randomized cases).

---

## 5. PROMPT 04 — WHAT COMES NEXT

Per `docs/08_MEMORY_STRATEGY.md`:

### L4 Memory Layer
1. **Episodic Memory** — timestamped conversation/event log, SQLite backend
2. **Semantic Memory** — vector-indexed knowledge store, FAISS or similar
3. **Working Memory** — short-lived scratchpad for reasoning state
4. **Memory Router** — query routing across memory types

### CoreRuntime integration (Prompt 04)
- `CoreRuntime` in `l1_core/runtime/` should bootstrap the kernel and memory layer
- `BaseService` pattern from L2 applies to memory services

### Key constraint for Prompt 04
- **No L4 imports from L3** — memory is L4, kernel is L3; L4 can call L3 (not vice-versa)
- Memory storage must respect privacy tiers — P0 conversations NEVER stored remotely

---

## 6. DEVELOPMENT WORKFLOW

```bash
# Run all tests
pytest tests/integration_l1l2 tests/integration_l3 -q

# Run just L3 tests
pytest tests/integration_l3 -q

# Single test module
pytest tests/integration_l3/test_kernel.py -v

# Import sanity check
python -c "from aegis.l3_intelligence.ai_kernel import AIKernel, Router, ModelRegistry; print('OK')"
```

---

## 7. KEY FILES TO READ FIRST

1. `docs/07_AI_STRATEGY.md` — routing algorithm spec (5 stages, privacy rules)
2. `docs/08_MEMORY_STRATEGY.md` — Prompt 04 target
3. `src/aegis/l3_intelligence/ai_kernel/contracts.py` — AIRequest/AIResponse schema
4. `src/aegis/l3_intelligence/ai_kernel/types.py` — PrivacyTier, QualityTier enums
5. `src/aegis/l3_intelligence/ai_kernel/kernel.py` — orchestration entry point
