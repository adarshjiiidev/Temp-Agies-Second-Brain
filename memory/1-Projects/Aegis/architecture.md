# AEGIS Architecture

**Related:** [[Aegis]] project page, [[AEGIS_DOCS/02_ARCHITECTURE]]

---

## Layer Architecture

Aegis uses a 7-layer architecture with strict downward dependencies. Each layer can only import from layers below it.

```
L7 — Human Interface (not started)
L6 — Cognitive & Personalization
L5 — Capability Ecosystem
L4 — Memory & Knowledge
L3 — Intelligence & Execution
L2 — Foundation Services
L1 — Core Runtime
```

## Layer Details

### L1 — Core Runtime
**Status:** ✅ Complete

- **Runtime FSM:** CREATED → INIT → START → RUN → STOP → STOPPED
- **DI Container:** 5 lifetimes (SINGLETON, SCOPED, TRANSIENT, FACTORY, LAZY)
- **Error Hierarchy:** Typed errors with severity/retry/code

### L2 — Foundation
**Status:** ✅ Complete

- Event bus for cross-service communication
- Config management
- Structured logging with correlation
- Crypto vault (encryption, redaction)
- Plugin loading system
- Background task scheduling

### L3 — AI Kernel
**Status:** ✅ Complete

**Core:**
- `kernel.py` — Top-level orchestrator (scrub→cache→route→infer)
- `router.py` — 5-stage model router (hard→quality→SLA→score→budget)
- `registry.py` — Model registry with 10-stage filter_candidates()
- `accounting.py` — Cost accountant with 4-point budget enforcement
- `cache.py` — Response cache with LRU/TTL
- `structured.py` — JSON extraction + Pydantic validation + retry loop
- `scrubber.py` — PII/secret detector → auto P0 elevation
- `metrics.py` — Rolling counters, p50/p95 latency

**Providers (6 adapters):**
- fake — Deterministic test provider (no network)
- ollama — Ollama local adapter (httpx)
- openrouter — OpenRouter cloud adapter (httpx + SSE)
- groq — Groq cloud adapter (httpx + SSE)
- vllm — vLLM self-hosted adapter (httpx + SSE)

### L4 — Memory & Knowledge
**Status:** ✅ Complete

- `store.py` — 3 memory stores (episodic, semantic, working)
- `graph.py` — Knowledge graph for relationship tracking
- `context.py` — Context assembly from multiple sources
- `search.py` — Full-text search + semantic search
- `policies.py` — Retention, privacy, verification policies
- `markdown.py` — Markdown loader
- `p07/` — WIP: scanners, discovery, inference

### L5 — Execution
**Status:** ✅ Complete

- `pipeline.py` — 7-stage: Plan→Permission→Policy→Execution→Audit→Verification
- `permission.py` — Permission engine
- `policy.py` — Policy engine
- `audit_chain.py` — Full traceability
- `sandbox/` — 4-tier sandbox by provenance
- `executors/` — Different action type executors

### L6 — Planning
**Status:** ✅ Implemented

- `planning_engine.py` — Planning engine
- `goal_decomposer.py` — Goal decomposition
- `planner_service.py` — Planner service with multiple strategies
- `dependency_graph.py` — Task dependency tracking
- `reflection.py` — Reflection and improvement
- `metrics.py` — Planning metrics

**Strategy:** Deterministic keyword heuristics (default). AI path activates when `reasoning_provider` is injected.

---

## Redesign Packages (Present but Untested)

### reasoning/
- `kernel_provider.py` — Calls `kernel.has_models()` and `kernel.infer_text()` which DON'T EXIST on AIKernel
- `mock_provider.py` — Test provider
- **Status:** Dead/untested. Only L3 ai_kernel works.

### prompts/
- 15 versioned YAML prompt templates
- **Status:** Present, not wired

### capabilities/
- Capability registry
- **Status:** Present, minimal test coverage

---

## Security Model

From [[AEGIS_DOCS/05_SECURITY]]:

**Critical Risks Identified:**
1. LLM hallucination → incorrect actions (Critical)
2. Prompt injection via ingested data (Critical)
3. Sandbox escape → host compromise (Critical)
4. P0 data routed to cloud (Critical)
5. Self-repair mutates TCB (High)
6. Generated code supply chain attack (High)

**Key Mitigations:**
- P0 never cloud (router hard rule)
- Structured output validation (never raw text to executor)
- Post-execution verification
- 4-tier sandbox by provenance
- TCB protection (lint denies write by non-human code path)

---

*See also: [[Aegis]], [[AEGIS_DOCS]]*
