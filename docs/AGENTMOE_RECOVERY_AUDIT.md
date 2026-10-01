# AGENTMOE RECOVERY AUDIT — PHASE 0
**Date:** 2026-08-29 | **Status:** COMPLETE

---

## 0. EXECUTIVE SUMMARY

**The AgentMoe name does not appear anywhere in the existing AEGIS git history, source tree, or filesystem.**

This is the critical finding. "AgentMoe" was not a prior project that was lost during the Windows→Omarchy migration. It is the **name for a capability/tool/worker fabric that has not yet been fully built** — specified in the AEGIS roadmap under prompts P09–P21 and partially scaffolded as the `aegis.capabilities` package (P08, delivered 2026-08-16).

**What actually exists:**

| Component | Location | State |
|-----------|----------|-------|
| P08 Capabilities layer | `src/aegis/capabilities/` | ✅ 4,118 LOC / 33 files / 954 test LOC |
| L5 Execution Pipeline (backbone) | `src/aegis/l5_execution/` | ✅ Full 7-stage |
| L5 Executors (8 active, 3 stubs) | `src/aegis/l5_execution/executors/` | ✅ / ❌ stubs |
| Rust perf crates | `crates/` | ✅ 26 tests |
| Hermes Agent (local reference) | `/home/adarshjii/.hermes/hermes-agent/` | ✅ Full source |
| AEGIS roadmap P09–P21 | `docs/09_ROADMAP.md` | ✅ Detailed spec |

---

## 1. GIT ARCHAEOLOGY RESULTS

**Commits found:** 24 total.
**Deleted AgentMoe files:** ZERO. No files matching `agentmoe/`, `tools/`, `workers/`, `swarm/`, `browser/`, `computer/`, `research/`, `coding/`, `models/`, `delegation/` were ever committed then deleted.

**Conclusion:** AgentMoe was never a separate committed project. It was designed-but-not-yet-built execution fabric described in the AEGIS roadmap.

**Relevant recent commits:**
- `fc5ae63` Phase 8 L8 Imp — capabilities invocation, external agents, MCP health (2026-08-16)
- `02b7aa7` Phase 8 Base — MCP schema normalizer, server/tool registry
- `baa4633` Phase 8 Updates — capability model, discovery providers, store (1911 LOC)

---

## 2. SURVIVING CODE MAP

### L1–L6 + Rust: COMPLETE (see AGENTS.md for full detail)
Total: 1097 Python tests passing + 26 Rust tests passing.

### P08 Capabilities — `src/aegis/capabilities/` (FOUNDATION OF AGENTMOE)

| Subpackage | Key Classes | LOC | Status |
|-----------|-------------|-----|--------|
| `model/` | CapabilityRecord, CapabilityCategory(23), TrustState, ProvenanceSource, CapabilityComposition | 486 | ✅ |
| `store/` | CapabilityStore | 219 | ✅ |
| `registry_v2/` | SemanticCapabilityRegistry (discover/register/query/find_for_task) | 325 | ✅ |
| `discovery_providers/` | base, static, CLI, local_model, MCP, plugin | 901 | ✅ |
| `mcp/` | MCPServerRegistry, MCPToolRegistry, MCPSchemaNormalizer, MCPHealthMonitor, types | 516 | ✅ |
| `selection/` | CapabilitySelector, CapabilityConstraints/Input/Output | 379 | ✅ |
| `invocation/` | CapabilityInvoker (→L5 bridge — critical) | 337 | ✅ |
| `external_agents/` | ExternalAgentCapability, AgentType, AgentCommunication (types only) | 112 | 🔷 Types only |
| P08 tests | test_capability_model, test_capability_store_registry, test_discovery_providers, test_mcp_registry | 954 | ✅ |

**KEY INVARIANT preserved in `invocation/invoker.py`:**
> ALL side effects go through L5.
> No capability may be directly executed without passing through:
> Permission → Risk → Policy → Sandbox → Executor → Audit → Verify

---

## 3. WHAT DOES NOT EXIST YET (THE AGENTMOE FABRIC)

| Component | Roadmap Ref | Status |
|-----------|------------|--------|
| BaseTool ABC (identity, schema, risk, permissions, timeout, audit, dry-run) | P08→P09 | ❌ |
| BaseWorker ABC (spawn, delegate, collect, budget, cancel, checkpoint) | P21 | ❌ |
| ToolFabric (registry, resolve, invoke, audit all) | P08 | ❌ |
| FilesystemTool (full: path guard, privacy zones, workspace roots) | P09 | ❌ |
| TerminalTool (streaming, env isolation, Linux-first, timeout/cancel) | P09 | ❌ |
| GitTool (full ops from L5 GitExecutor + dangerous op authorization) | P09 | ❌ |
| BrowserTool (Playwright, SSRF guard, session isolation, DOM extract) | P10 | ❌ |
| ComputerTool (Linux/X11/AT-SPI, keyboard/mouse/screenshot) | P09 | ❌ |
| HTTPTool (promote from L5 + SSRF rules + domain policies) | P09 | ❌ |
| MCPTool (full transport via existing aegis.capabilities.mcp) | P08 | 🔷 Stub |
| PythonTool (promote from L5 + sandbox tier selection) | P09 | ❌ |
| CodingWorker (inspect→plan→edit→test→repair) | P12 | ❌ |
| ResearchWorker (search→fetch→extract→synthesize→cite) | P10 | ❌ |
| DataWorker (PDF, CSV, Excel, Markdown, JSON) | P10+ | ❌ |
| Model Fabric (task-driven: CODING→coding model, RESEARCH→reasoning model) | P08+ | 🔷 L3 exists, no selector |
| Credential Pool (multi-key, rotation, health, rate-limit, cooldown) | P08+ | 🔷 Resolver exists, no pool |
| WorkerRuntime (spawn, delegate, budget inheritance, privilege inheritance) | P21 | ❌ |
| SwarmCoordinator (delegate, collect, vote, cancel, max depth/workers) | P21 | ❌ |
| Shared Context Bus (T0 Working Memory scoped per mission) | P21 | ❌ |
| ExternalAgentAdapter (real implementation with sandbox/trust) | P08 | 🔷 Types only |
| Autonomy Level L0–L5 enforcement | Cross-cutting | ❌ |
| PathGuard / SSRFGuard / InjectionGuard / BudgetGuard | P09 | ❌ |
| ExecutionSpan observability (exec_id, worker_id, mission_id, parent_id) | Cross-cutting | ❌ |
| RetryPolicy with backoff + alternate provider/model/tool | Cross-cutting | ❌ |
| CheckpointStore backed by L4 memory | Cross-cutting | ❌ |

---

## 4. REFERENCE IMPLEMENTATIONS

### 4.1 Hermes Agent — `/home/adarshjii/.hermes/hermes-agent/`
Production-grade AI agent framework. Full source available.

**Extractable concepts (STUDY → EXTRACT → ADAPT → TEST → INTEGRATE):**

| File | Size | Pattern to Extract | Destination |
|------|------|--------------------|-------------|
| `agent/tool_guardrails.py` | 43k | Idempotent/mutating classification, loop detect | `agentmoe/security/tool_classifier.py` |
| `tools/computer_use/tool.py` | Large | Linux X11/AT-SPI computer control contract | `agentmoe/tools/computer/backend.py` |
| `tools/computer_use/backend.py` | — | ActionResult/CaptureResult/UIElement protocol | `agentmoe/tools/computer/types.py` |
| `tools/browser_tool.py` | Large | Multi-backend browser + session isolation pattern | `agentmoe/tools/browser/tool.py` |
| `tools/code_execution_tool.py` | Large | UDS-RPC sandboxed Python, streaming, file RPC | `agentmoe/tools/python_exec/executor.py` |
| `tools/budget_config.py` | — | Per-tool/turn budget tracking | `agentmoe/runtime/budget.py` |
| `tools/checkpoint_manager.py` | — | Checkpoint/recovery contract | `agentmoe/runtime/checkpoint.py` |
| `agent/terminal_env_provider.py` | 9k | Environment detection + isolation | Extend `aegis.l4_memory.p07` |
| `tools/delegate_tool.py` | — | Task delegation contract | `agentmoe/delegation/contract.py` |
| `acp_adapter/` | — | External agent protocol adapter pattern | `agentmoe/integration/adapters/base.py` |

**What NOT to copy:**
- Hermes display/UI (KawaiiSpinner, cute messages, display.py)
- Hermes billing/account system (billing_view.py, account_usage.py)
- Hermes ACP protocol internals
- node_modules/, .git directories
- Anthropic-specific adapters (extract generic patterns only)
- Hermes authentication system

### 4.2 gods-eye-view-main.zip
Geospatial/CCTV intelligence viewer. **Entirely irrelevant to AgentMoe.** Ignore.

---

## 5. CAPABILITY EXTRACTION DECISIONS

| Capability | Source | Adaptation Required | Security Impact | Decision |
|-----------|---------|--------------------|-----------------|----|
| Tool idempotent/mutating classification | Hermes `tool_guardrails.py` | Map to AgentMoe RiskLevel enum | HIGH | ✅ EXTRACT |
| Loop/stall detection per tool | Hermes `tool_guardrails.py` | Add to worker runtime | HIGH | ✅ EXTRACT |
| ComputerUseBackend protocol | Hermes `computer_use/backend.py` | Keep protocol, adapt for Linux AT-SPI | CRITICAL | ✅ EXTRACT PROTOCOL |
| Browser multi-backend abstraction | Hermes `browser_tool.py` | Strip Hermes internals, keep isolation | HIGH | ✅ EXTRACT PATTERN |
| UDS-RPC sandboxed code exec | Hermes `code_execution_tool.py` | Adapt to AEGIS L5 sandbox tiers | CRITICAL | ✅ EXTRACT PATTERN |
| Task delegation contract | Hermes `delegate_tool.py` | Adapt to AEGIS permission inheritance | HIGH | ✅ EXTRACT PATTERN |
| Budget tracking per tool | Hermes `budget_config.py` | Integrate with L3 CostAccountant | MEDIUM | ✅ EXTRACT |
| Checkpoint/recovery | Hermes `checkpoint_manager.py` | Back by L4 memory store | LOW | ✅ EXTRACT |
| ACP adapter pattern | Hermes `acp_adapter/` | ExternalAgentAdapter base class | MEDIUM | ✅ EXTRACT PATTERN |

---

## 6. SECURITY MODEL (PRE-DEFINED)

Privacy tiers (aligned with AEGIS P0 invariant):
- **P0** — Prohibited/private. Never leaves device. Never in tool input/output logs.
- **P1** — Sensitive. Local execution only. No cloud tools.
- **P2** — Normal. Standard policy applies.
- **P3** — Low-risk. Read-only or reversible operations.

Risk levels (aligned with existing L5 RiskLevel):
- **CRITICAL** — Requires explicit user approval. Desktop control, system-level ops, destructive ops.
- **HIGH** — Requires policy authorization. Shell exec, file delete, network requests.
- **MEDIUM** — Standard sandbox. File reads, local code execution.
- **LOW** — Minimal restriction. Dry-run, read-only, idempotent.

Autonomy levels:
- **L0** — Observe only. No side effects.
- **L1** — Suggest only. No execution.
- **L2** — Execute LOW-risk actions.
- **L3** — Execute approved workflows (saved permission grants).
- **L4** — Autonomous bounded execution (budget + scope limits enforced).
- **L5** — System-level autonomy. **DISABLED BY DEFAULT. Requires explicit user activation.**

---

## 7. INTEGRATION BOUNDARY

```
L6 PlannerService
    │
    │ produces ExecutionStep objects
    ▼
AgentMoe ToolFabric.invoke(capability_id, args, context)
    │
    │ ALWAYS goes through CapabilityInvoker (P08)
    ▼
L5 ExecutionPipeline.execute(action)
    │
    Stage 1: PermissionEngine (SVRC deny-by-default)
    Stage 2: RiskAnalyzer
    Stage 3: PolicyEngine
    Stage 4: ExecutorRegistry → BaseExecutor
    Stage 5: SandboxManager
    Stage 6: Executor.execute()
    Stage 7: AuditChain + PostExecVerifier
    │
    ▼
ActionResult (audit trail, rollback info, verification result)
    │
    ▼
L4 Memory (store result, update knowledge graph, update metrics)
```

**HARD RULE:** AgentMoe tools NEVER call `subprocess.run()`, `os.system()`, or any OS primitive directly. Every side-effecting action goes through `CapabilityInvoker` → L5 pipeline.

---

## 8. PHASED RECONSTRUCTION PLAN

| Phase | Scope | Prerequisites | Acceptance |
|-------|-------|--------------|------------|
| **PHASE 1** | Architecture + security docs, BaseTool/BaseWorker ABCs | Phase 0 audit ✅ | User approves architecture |
| **PHASE 2** | Protocols/contracts (all ABCs, enums, spans, budget) | Phase 1 approved | Type-check passes |
| **PHASE 3** | Core runtime (ToolFabric, guards, autonomy, observability) | Phase 2 | Unit tests pass |
| **PHASE 4** | Filesystem + Terminal + Git tools | Phase 3 | Integration + security tests |
| **PHASE 5** | HTTP + Python + MCP tools | Phase 3 | Integration + security tests |
| **PHASE 6** | Worker runtime (spawn, delegate, budget, checkpoint) | Phases 4+5 | Delegation tests |
| **PHASE 7** | Model fabric + credential pool | Phase 6 | Pool rotation + health tests |
| **PHASE 8** | Browser + Computer tools | Phase 6 | Auth gate tests |
| **PHASE 9** | CodingWorker + ResearchWorker | Phases 7+8 | E2E worker tests |
| **PHASE 10** | Swarm/delegation | Phase 9 | Privilege escalation tests |
| **PHASE 11** | Security hardening + adversarial tests | Phase 10 | All security tests pass |
| **PHASE 12** | Performance benchmarks + Rust candidates | Phase 11 | Benchmark report |
| **PHASE 13** | Real AEGIS integration + E2E mission tests | Phase 12 | Full mission tests pass |

---

## 9. PHASE 0 COMPLETION REPORT

### Implemented
- Complete recovery audit

### Recovered  
- P08 Capabilities layer: 4,118 LOC (foundation of AgentMoe)
- L5 Execution Pipeline: the backbone
- L3 AI Kernel: the model fabric
- Hermes Agent: reference implementation library
- AEGIS roadmap P09–P21: detailed spec

### NOT copied
- No Hermes code copied
- gods-eye-view ZIP: ignored (irrelevant)
- No code changed in AEGIS source

### Files created
- `docs/AGENTMOE_RECOVERY_AUDIT.md` (this file)

### Test results
- No tests run (no implementation changes made)

### Security implications
- CapabilityInvoker already enforces L5 pipeline routing — critical invariant identified and preserved
- No credentials found in codebase

### Performance implications
- None (no code written)

### Remaining gaps
- All AgentMoe implementation (Phases 1–13)

### Documentation updated
- `docs/AGENTMOE_RECOVERY_AUDIT.md` created

### Recommended next phase
**PHASE 1 — Architecture Reconciliation**
Produce `docs/AGENTMOE_ARCHITECTURE.md` + `docs/AGENTMOE_SECURITY_MODEL.md`.
Define `BaseTool` and `BaseWorker` ABCs.
**Do not write implementation code until user approves Phase 1.**
