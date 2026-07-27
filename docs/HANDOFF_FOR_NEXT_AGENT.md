# HANDOFF FOR NEXT CODING AGENT — PROJECT AEGIS

**Handoff Date:** 2026-07-27  
**Current State:** Prompt 01 (Docs) & Prompt 02 (Core Runtime & Foundation) are 100% COMPLETE and VERIFIED. Prompt 03 (AI Kernel) is IN PROGRESS with ~120KB of untracked code.  
**Primary Goal for Next Agent:** Complete and verify Prompt 03 (AI Kernel).

---

## 1. QUICK START & ENVIRONMENT RECONNAISSANCE

Before doing anything, run the verified test suite to confirm L1/L2 core stability:
```bash
pytest tests/integration_l1l2
```
*Expected Result:* 46 passed in ~3s.

Check the untracked L3 files:
```bash
git status
```
You will see `src/aegis/l3_intelligence/` as untracked.

---

## 2. KEY REPOSITORY ARCHITECTURE & RULES

1. **Rule of Architectural Truth:** The repository code is the ultimate source of truth. Trust verified test output over comments or READMEs.
2. **Layering Constraints:** Downward-only imports are strictly enforced via import-linter in `pyproject.toml`.
   * L1 (`l1_core`) CANNOT import L2+.
   * L2 (`l2_foundation`) CANNOT import L3+.
   * L3 (`l3_intelligence`) CAN import L1 protocols and L2 telemetry/crypto, but NOT L4+.
3. **No Mocks in L1/L2 Integration:** L1/L2 integration tests use real `aiosqlite` databases in temporary directories managed by `temp_data_dir` fixture in `tests/conftest.py`.

---

## 3. UNTRACKED L3 CODE STRUCTURE (`src/aegis/l3_intelligence/ai_kernel/`)

The following files exist in `src/aegis/l3_intelligence/ai_kernel/` but have no tests and are untracked:

1. `types.py`: PrivacyTier (P0/P1/P2/P3), DeploymentKind, TaskType.
2. `registry.py`: ModelMetadata & 10-stage candidate filter pipeline (`filter_candidates()`).
3. `keys.py`: KeyManager for API key rotation, cooldown, rate-limiting, vault references.
4. `accounting.py`: CostAccountant for 4-point budget enforcement ($2.00/day default).
5. `contracts.py`: AIRequest, AIResponse, RoutingRequirements, StructuredOutputRequirements.
6. `pipeline.py`: PromptPipeline stage execution engine.
7. `cache.py`: ResponseCache LRU & TTL store (P0 items strictly excluded from caching).
8. `streaming.py`: StreamEvent & StreamEventEmitter async chunk stream handler.
9. `conversation.py`: In-memory Conversation history manager.
10. `structured.py`: Markdown fence JSON extractor & Pydantic output validator.
11. `providers/base.py`: ProviderRegistry & BaseProvider abstraction.

---

## 4. IMMEDIATE ACTION ITEMS FOR NEXT AGENT

1. **Step 1: Test Untracked L3 Primitives**
   Create integration tests in `tests/integration_l3/` testing:
   * Candidate filtering pipeline in `registry.py` (verify P0 local-only, capability matching, etc.).
   * Budget enforcement in `accounting.py` ($0.10 limit blocks 10th call).
   * Key selection & rotation in `keys.py`.
   * Response caching in `cache.py` (verify P0 items raise error or are ignored).
   * Structured output parsing in `structured.py`.

2. **Step 2: Implement Missing Prompt 03 Components**
   * **Router (`router.py`):** Implement the 5-stage router scoring algorithm per 07_AI_STRATEGY §07.3.
   * **Provider Adapters (`providers/`):** Implement concrete provider classes for `ollama.py`, `openrouter.py`, `groq.py`, and `vllm.py`.
   * **Kernel Facade (`kernel.py`):** Create the primary `AIKernel` orchestrator unifying Router, Accounting, Providers, Caching, and Structured Output.
   * **Public Exports:** Add L3 exports to `src/aegis/__init__.py`.

3. **Step 3: Verify Prompt 03 Exit Gate**
   Refer to `docs/09_ROADMAP.md` §3 (Prompt 03 Exit Gate):
   * 100-case router battery (P0 local routing, cost, latency).
   * 50-case structured output battery (100% valid Pydantic instances).
   * 0 unredacted secrets in log capture.
   * Budget enforcement blocking calls when daily cap reached.
