# PROJECT AEGIS — CORE ARCHITECTURE OVERVIEW

**Document ID:** AEGIS-DOC-003
**Version:** 0.1.0 (Prompt 01 Foundation)
**Status:** DRAFT — Architecture Phase Only
**Last Updated:** 2026-07-24

---

## 1. ARCHITECTURE GUIDING CONSTRAINTS

The architecture of AEGIS is constrained by three non-negotiable properties:

1. **Capability-Based, Not Integration-Based.** The system reasons about *what capability is needed*, not *what specific product API to call*. Hardcoded product integrations are explicitly forbidden in the core.
2. **Learnable, Not Hardcoded.** Any behavior that can be learned, discovered, or generated must not be hardcoded in the kernel. The kernel provides the learning loop; the learned artifacts live outside the kernel.
3. **Secure-by-Construction.** Security is not an afterthought layer. Every subsystem boundary is a security boundary. The Plan→Permission→Policy→Execution→Audit→Verification pipeline is woven into the architecture.

---

## 2. LAYERED ARCHITECTURE

AEGIS is organized into seven horizontal layers. Dependencies flow strictly **downward**; a layer may only import interfaces from layers below it. Cycles between layers are forbidden.

```
┌─────────────────────────────────────────────────────────────────────┐
│ L7 — HUMAN INTERFACE LAYER                                          │
│  Voice / Text / Desktop UI / Control Center / Browser Panel         │
├─────────────────────────────────────────────────────────────────────┤
│ L6 — COGNITIVE & PERSONALIZATION LAYER                              │
│  Cognitive Planner · Adaptive Intelligence · Person/Social Models   │
│  Research Intelligence · Finance/Cyber/Social Intelligence Modules  │
├─────────────────────────────────────────────────────────────────────┤
│ L5 — CAPABILITY ECOSYSTEM LAYER                                     │
│  Capability Registry · Tool Generator · MCP Runtime                 │
│  Auto-Harness · Self-Repair Engine · Skill Store                    │
├─────────────────────────────────────────────────────────────────────┤
│ L4 — MEMORY & KNOWLEDGE LAYER                                       │
│  Memory Engine (9 tiers) · Knowledge Graph · Obsidian Projection    │
│  Environment Model · Meta-Memory · Vector Store                     │
├─────────────────────────────────────────────────────────────────────┤
│ L3 — INTELLIGENCE & EXECUTION LAYER                                 │
│  AI Kernel (Router + Providers) · Execution Kernel · Sandbox        │
│  Permission Engine · Policy Engine · Audit & Verification           │
├─────────────────────────────────────────────────────────────────────┤
│ L2 — FOUNDATION SERVICES LAYER                                      │
│  Event Bus · Configuration · Telemetry · Persistence Abstraction    │
│  Plugin Loader · Encryption · Secrets Vault · Task Scheduler        │
├─────────────────────────────────────────────────────────────────────┤
│ L1 — CORE RUNTIME LAYER                                             │
│  Core Runtime Kernel · Lifecycle Manager · Supervisor · Health      │
│  Error Taxonomy · Interface Definitions · Module Container          │
└─────────────────────────────────────────────────────────────────────┘
```

### Layer Import Rules (Non-Negotiable)

| This Layer | May Import Concrete From | May Import Interfaces From |
|---|---|---|
| L7 HCI | L6 interfaces only | L6, L5, L4, L3, L2, L1 |
| L6 Cognitive | L5 interfaces only | L5, L4, L3, L2, L1 |
| L5 Capability | L4 interfaces only | L4, L3, L2, L1 |
| L4 Memory | L3 interfaces only | L3, L2, L1 |
| L3 Intelligence | L2 concrete (foundations) + L1 | L2, L1 |
| L2 Foundation | L1 concrete | L1 |
| L1 Core Runtime | Nothing internal; stdlib + external deps only | External interfaces |

---

## 3. CORE ARCHITECTURAL DIAGRAM — END-TO-END FLOW

```
                                 USER
                                  │
                        ┌─────────▼─────────┐
                        │  MULTIMODAL HCI   │  (L7)
                        │  Text / Voice / UI│
                        └─────────┬─────────┘
                                  │ Personal Context + Intent
                        ┌─────────▼─────────┐
                        │   COGNITIVE       │  (L6)
                        │   PLANNER         │
                        │ Decompose · Risk  │
                        └─────────┬─────────┘
                                  │ Plan + Required Capabilities
                        ┌─────────▼───────────────────────┐
                        │   CAPABILITY DISCOVERY PIPELINE │  (L5)
                        │ Registry → Tools → MCP → CLI    │
                        │ → Inspect Software → Learn      │
                        └─────────┬───────────────────────┘
                                  │ Capability + Bound Context
                        ┌─────────▼─────────┐
                        │   MEMORY ENGINE   │  (L4)
                        │ Recall · Context  │
                        │ Knowledge Graph   │
                        └─────────┬─────────┘
                                  │ Structured Action Request
┌─────────────────────────────────▼───────────────────────────────────────┐
│                   AI KERNEL  ·  EXECUTION KERNEL  (L3)                  │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐                │
│  │  Model Router│   │  Permission  │   │  Sandboxed   │                │
│  │  + Providers │   │  + Policy    │   │  Executor    │                │
│  └──────────────┘   └──────┬───────┘   └──────┬───────┘                │
│                            │  GATED           │  Execute                │
│                     ┌──────▼───────┐   ┌──────▼───────┐                │
│                     │  AUDIT LOG   │   │  VERIFY      │                │
│                     └──────────────┘   └──────────────┘                │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
            ┌─────────────────────┼──────────────────────┐
    ┌───────▼───────┐     ┌───────▼───────┐     ┌────────▼──────┐
    │   COMPUTER    │     │    BROWSER    │     │    VISION     │  (External)
    │   CONTROL     │     │     OS        │     │ PERCEPTION    │
    └───────────────┘     └───────────────┘     └───────────────┘
```

---

## 4. MODULE DECOMPOSITION — BY LAYER

### L1 — CORE RUNTIME LAYER

| Module | Responsibility | Extension Point |
|---|---|---|
| `core_runtime` | Module container, lifecycle state machine (`init → start → healthy → degraded → stopping → stopped`), dead-man switch | Plugin interface |
| `supervisor` | Per-module process/thread isolation, crash detection, restart policy, watchdog | Restart strategy plugins |
| `interface_registry` | All system-wide interfaces / protocols / traits defined here; no implementations | New interface registration |
| `error_taxonomy` | Typed error hierarchy, severity codes, retry hints, classification engine | New error categories |
| `health_registry` | Aggregated subsystem health, dependency liveness, degraded-mode orchestration | Custom health checks |

### L2 — FOUNDATION SERVICES LAYER

| Module | Responsibility | Extension Point |
|---|---|---|
| `event_bus` | Typed pub/sub, durable topics (append-log), at-least-once delivery, dead-letter queue | Storage backends, delivery guarantees |
| `config` | Layered config: defaults < file < env < runtime, schema validation, hot reload, audit trail of changes | Config sources |
| `secrets_vault` | Encrypted-at-rest secret storage, never dumps to log, per-scope ACL, KMS abstraction | Encryption backends, KMS plugins |
| `crypto` | AEAD encryption, hashing, signature verification, key derivation; single audited surface | Crypto providers |
| `persistence` | Abstract KV store, document store, relational store interfaces. No concrete DB in L2. | Storage backend plugins |
| `plugin_loader` | Manifest-driven plugin loading, permission scoping, dependency resolution, hot-reload safety | Plugin formats |
| `telemetry` | Metrics (Prometheus-compatible), logs (structured JSON), traces (OTel), zero-external default | Exporters |
| `scheduler` | Async task queue, cron, retries with backoff, priority queues, dead-letter | Queue backends |

### L3 — INTELLIGENCE & EXECUTION LAYER

| Module | Responsibility | Extension Point |
|---|---|---|
| `ai_kernel` | Model Router, provider abstraction, structured output enforcement, token/cost accounting, prompt template library | LLM Provider plugins |
| `permission_engine` | Subject-Verb-Resource-Context permission checks, RBAC + ABAC hybrid, allow/deny lists, consent records | Policy decision points |
| `policy_engine` | Risk scoring per action, approval gate triggers, policy-as-code, versioned policies | Policy languages |
| `execution_kernel` | Typed Action dispatcher, executor plugin router, timeout/cancellation, transaction log | Executor plugins (CLI, FS, Process, MCP, …) |
| `sandbox` | Isolated execution for generated code/tools: filesystem overlay, network ACL, cgroup/ulimit, resource limits, rollback | Sandbox backends |
| `audit` | Append-only audit trail, integrity protection, every action + decision + result recorded, query API | Audit sinks, integrity mechanisms |
| `verification` | Post-execution intent verification, assertion engine, result grading, auto-rollback triggers | Verifier plugins |

### L4 — MEMORY & KNOWLEDGE LAYER

| Module | Responsibility | Extension Point |
|---|---|---|
| `memory_engine` | 9-tier memory hierarchy, write/read path with tier routing, TTL/archival, provenance tracking | Memory tier plugins |
| `vector_store` | Embeddings storage and similarity search, hybrid retrieval, embedding model abstraction | Vector DB backends, embedding models |
| `knowledge_graph` | Typed entity/relation store, traversal queries, link prediction, subgraph extraction, diff/versioning | Graph DB backends |
| `obsidian_projection` | Bidirectional sync: structured memory ⇄ human-readable Obsidian Vault (markdown + links), conflict resolution | Vault layout strategies |
| `environment_model` | Digital environment graph (hardware/OS/apps/projects/repos/files/accounts), freshness tracking, relationship inference | Scanner plugins |
| `meta_memory` | Confidence tracking, staleness detection, provenance chain, "what I know / don't know" index, calibration | Calibration strategies |

### L5 — CAPABILITY ECOSYSTEM LAYER

| Module | Responsibility | Extension Point |
|---|---|---|
| `capability_registry` | Typed capability descriptions, semantic search, metadata (confidence, success-rate, last-tested, permissions, deps, version) | Capability formats |
| `tool_runtime` | Tool execution wrapper, schema validation, argument coercion, retry, context injection | Tool types |
| `mcp_runtime` | Standard MCP client, tool schema import, lifecycle management, connection pooling | MCP transport plugins |
| `capability_discovery` | Goal → required-capability → registry → tool → MCP → CLI → software-inspection → docs → learn pipeline | Discovery strategies |
| `tool_generator` | Generate tools / MCP wrappers from learned software models, type-check, write to sandbox | Generator strategies |
| `auto_harness` | Generated test cases, sandboxed evaluation, expected-vs-actual comparison, scoring, repair loop, registration gate | Test generators, evaluators |
| `self_repair` | Failure → root-cause analysis → research → fix generation → sandbox evaluation → versioned deploy → audit | Repair strategies |
| `skill_store` | Versioned skill definitions, evaluation history, provenance, rollback points | Skill formats |

### L6 — COGNITIVE & PERSONALIZATION LAYER

| Module | Responsibility | Extension Point |
|---|---|---|
| `cognitive_planner` | Intent → sub-goals → tasks → typed actions; dependency graph; risk scoring; replan-on-failure; traceability | Planner strategies |
| `adaptive_intelligence` | User observation, workflow inference, preference learning, environment relationship discovery | Learners |
| `personal_models` | Explicitly enrolled people models, preferences/interactions/projects, evidence-based probabilistic predictions | Model types |
| `research_intelligence` | Web research orchestration, source comparison, citation graph, summarization, information verification | Research strategies |
| `domain_modules` | Finance (Indian markets) · Cybersecurity learning · Social media — each as independent plugin module with gated capabilities | Domain plugins |

### L7 — HUMAN INTERFACE LAYER

| Module | Responsibility | Extension Point |
|---|---|---|
| `text_interface` | First-class text UI, conversation context manager, approval prompts, status streaming | Text frontends (CLI, REPL, web chat) |
| `control_center` | Desktop UI: status dashboard, memory inspector, plan viewer, approval panel, settings, audit viewer | UI widgets |
| `voice_system` | Hotword, streaming STT, streaming TTS, voice activity detection, local-first preference | STT/TTS providers |
| `computer_control` | Screen capture, OCR, mouse, keyboard, window manager, accessibility APIs | Automation backends |
| `browser_os` | Full browser automation, navigation, extraction, forms, uploads/downloads, cookie isolation | Browser engines |
| `vision_perception` | Camera discovery, multi-camera, explicit-face-enrollment detection, OCR, scene, change/anomaly/event detection, privacy zones | Perception models |

---

## 5. MODULE DEPENDENCY GRAPH

The following is a **directed, acyclic graph** of module-to-module dependencies. Arrows read as "depends on (interfaces of)". Cycles are forbidden.

```
L1:
  core_runtime → [stdlib, external deps only]
  supervisor → core_runtime
  interface_registry → core_runtime
  error_taxonomy → core_runtime
  health_registry → core_runtime, supervisor

L2:
  event_bus → core_runtime, interface_registry, persistence (I/F), error_taxonomy
  config → core_runtime, interface_registry, crypto (I/F)
  secrets_vault → core_runtime, crypto, persistence (I/F)
  crypto → core_runtime, interface_registry
  persistence → core_runtime, interface_registry  (interfaces only, no concrete backends in L2)
  plugin_loader → core_runtime, interface_registry, config, crypto
  telemetry → core_runtime, config, persistence (I/F)
  scheduler → core_runtime, event_bus, telemetry, error_taxonomy

L3:
  ai_kernel → core_runtime, config, secrets_vault, telemetry, event_bus, plugin_loader, persistence (I/F)
  permission_engine → core_runtime, config, persistence (I/F), event_bus
  policy_engine → permission_engine, ai_kernel (I/F), event_bus, persistence (I/F)
  execution_kernel → core_runtime, permission_engine, policy_engine, audit, scheduler, telemetry, plugin_loader
  sandbox → core_runtime, config, crypto, telemetry, persistence (I/F)
  audit → core_runtime, crypto, persistence (I/F), event_bus
  verification → ai_kernel (I/F), execution_kernel (I/F), audit, telemetry

L4:
  memory_engine → core_runtime, ai_kernel (I/F), persistence (I/F), crypto, event_bus, telemetry, meta_memory
  vector_store → ai_kernel (I/F) [embeddings], persistence (I/F), telemetry
  knowledge_graph → persistence (I/F), ai_kernel (I/F), telemetry, event_bus
  obsidian_projection → memory_engine, knowledge_graph, vector_store, file_system (I/F from L3 exec)
  environment_model → persistence (I/F), knowledge_graph, execution_kernel (I/F for scanners), telemetry
  meta_memory → memory_engine, knowledge_graph, ai_kernel (I/F), audit

L5:
  capability_registry → knowledge_graph, persistence (I/F), vector_store, telemetry, event_bus
  tool_runtime → execution_kernel (I/F), sandbox (I/F), permission_engine, audit, telemetry
  mcp_runtime → tool_runtime, plugin_loader, secrets_vault, telemetry
  capability_discovery → capability_registry, tool_runtime, mcp_runtime, ai_kernel (I/F),
                          memory_engine, environment_model, research_intelligence (I/F from L6)
  tool_generator → ai_kernel, capability_discovery, sandbox, auto_harness (I/F), telemetry
  auto_harness → tool_generator, sandbox, ai_kernel, verification, capability_registry, audit
  self_repair → audit, auto_harness, ai_kernel, memory_engine, capability_registry, tool_generator, telemetry
  skill_store → persistence (I/F), capability_registry, auto_harness, audit, vector_store

L6:
  cognitive_planner → ai_kernel, memory_engine, knowledge_graph, capability_discovery,
                      permission_engine, policy_engine, execution_kernel (I/F), audit
  adaptive_intelligence → environment_model, memory_engine, ai_kernel, event_bus, audit
  personal_models → knowledge_graph, memory_engine, ai_kernel, adaptive_intelligence
  research_intelligence → ai_kernel, memory_engine, browser_os (I/F), knowledge_graph, telemetry
  domain_modules → cognitive_planner, research_intelligence, capability_registry,
                   execution_kernel (I/F), policy_engine, audit

L7:
  text_interface → cognitive_planner, adaptive_intelligence, policy_engine, audit, telemetry
  control_center → text_interface (I/F), memory_engine, knowledge_graph, cognitive_planner,
                   audit, capability_registry, health_registry
  voice_system → text_interface, ai_kernel (I/F for STT/TTS), secrets_vault, telemetry
  computer_control → execution_kernel (I/F), sandbox, policy_engine, audit, ai_kernel (I/F for vision)
  browser_os → execution_kernel (I/F), sandbox, policy_engine, audit, ai_kernel (I/F), research_intelligence
  vision_perception → computer_control (I/F), ai_kernel (I/F), sandbox, policy_engine, audit, secrets_vault
```

Key invariants:
1. L1 → L2 → L3 → L4 → L5 → L6 → L7: no reverse imports of concrete classes.
2. All cross-module communication within a layer uses the Event Bus or typed interface injection. No direct cross-module method calls except through defined interfaces.
3. No module in L3–L7 ever directly imports a **concrete** backend (DB, provider, browser). It imports interfaces only.

---

## 6. CROSS-CUTTING CONCERNS — INTEGRATION POINTS

The following architectural "pipes" connect every layer. They are not modules themselves; they are mandatory usage patterns.

### 6.1 EVENT BUS TOPOLOGY

All significant state changes and actions emit typed events to the Event Bus. Example topics:

- `core.runtime.health` — subsystem health transitions
- `core.action.planned` / `approved` / `executing` / `succeeded` / `failed` / `verified`
- `memory.written` / `read` / `archived` / `deleted`
- `kg.entity.created` / `linked` / `unlinked`
- `ai.completion.requested` / `succeeded` / `failed` (token counts, cost, latency)
- `capability.registered` / `tested` / `deprecated`
- `audit.record` — every action and decision (also written to audit store)
- `user.interaction` — HCI-level events, approval responses

Pattern: Subscriber modules declare which topics they consume; Event Bus enforces permission on publish.

### 6.2 PERMISSION MODEL — INTEGRATION POINT

Before **any** side-effect, the calling module MUST:

1. Construct a `PermissionRequest` (subject, verb, resource, context, justification).
2. Call `permission_engine.evaluate(request)`.
3. Enforce the returned decision: `ALLOW` / `DENY` / `NEEDS_APPROVAL`.
4. If `NEEDS_APPROVAL`: route to approval UI; wait; re-check.
5. Record the permission decision + action result in the audit log.

No bypass. No "trusted internal" path. Not even for the Core Runtime itself.

### 6.3 PLUGIN MANIFEST CONTRACT

Every plugin / provider / executor / domain module ships a `manifest.yaml`:

```yaml
manifest_version: 1
id: com.aegis.executor.powershell
name: PowerShell Executor
version: 0.1.0
interface: aegis.executor.cli@1
provides:
  - capability: execute.powershell
    verbs: [run, read_only_run]
requires:
  permissions:
    - resource: os.process
      verbs: [create, read]
    - resource: fs.cwd
      verbs: [read]
  dependencies:
    - com.aegis.core.secrets_vault@^1
    - com.aegis.core.sandbox@^1
privacy_tier: local_only
risk: medium
```

The Plugin Loader validates the manifest against the permission engine before loading.

---

## 7. KEY EXTENSION POINTS FOR FUTURE ADAPTIVE INTELLIGENCE

The architecture must anticipate the following future capabilities even though **none are implemented in Prompt 01**. Each has a dedicated extension point defined in the interface registry.

| Future Capability | Extension Point Location | Interface |
|---|---|---|
| Discovering unknown software | L5 capability_discovery + L4 environment_model | `SoftwareScanner`, `WorkflowLearner` |
| Creating new MCPs/tools at runtime | L5 tool_generator + auto_harness | `ToolGenerator`, `HarnessEvaluator` |
| Learning user workflows over time | L6 adaptive_intelligence | `WorkflowInference`, `PreferenceLearner` |
| Auto-harness evaluating every new skill | L5 auto_harness | `TestCaseGenerator`, `OutcomeScorer`, `RepairPolicy` |
| Self-repair of failing modules/tools | L5 self_repair | `FailureAnalyzer`, `FixGenerator`, `DeployPolicy` |
| Multi-worker society (M20) | L6 cognitive_planner + L5 skill_store | `WorkerOrchestrator`, `RoleAssigner`, `ResultMerger` |
| Vision perception with privacy zones | L7 vision_perception | `CameraProvider`, `PerceptionModel`, `PrivacyZoneEngine` |
| Social media trust ladder | L6 domain_modules | `TrustLadderPolicy`, `ApprovalRouter` |
| Finance paper-to-live gating | L6 domain_modules | `RiskTier`, `ApprovalMatrix`, `BacktestEngine` |

---

## 8. THE NON-NEGOTIABLE EXECUTION PIPELINE

Every side-effecting action in AEGIS passes through this seven-stage pipeline. If any stage fails, the entire action is rejected and audited as failed.

```
  STAGE 1          STAGE 2       STAGE 3       STAGE 4       STAGE 5        STAGE 6       STAGE 7
┌──────────┐     ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌──────────┐
│   PLAN   │────▶│PERMISSION│─▶│ POLICY   │─▶│ EXECUTE  │─▶│  AUDIT    │─▶│ VERIFY   │─▶│ REFLECT  │
│ (Typed   │     │  Engine  │  │  Engine  │  │ (Sandbox)│  │  (Append) │  │ (Intent) │  │ (Memory) │
│  Action) │     │  SVRC    │  │  Risk    │  │  Kernel  │  │  Only     │  │ Assert   │  │ + Learn  │
└──────────┘     └──────────┘  └──────────┘  └──────────┘  └───────────┘  └──────────┘  └──────────┘
     │                │              │             │              │              │              │
     │ ALLOW? ────────┘              │             │              │              │              │
     │  └─── DENY → HALT ────────────┘             │              │              │              │
     │                APPROVAL GATE ───────────────┘              │              │              │
     │                                        RESULT ─────────────┘              │              │
     │                                             RESULT ───────────────────────┘              │
     │                                                          RESULT + LESSONS ───────────────┘
```

- **Stage 1 Plan:** All inputs validated. Output is a typed Action object, never free-form text.
- **Stage 2 Permission:** SVRC check. No exceptions.
- **Stage 3 Policy:** Risk score computed. Approval gated if required.
- **Stage 4 Execute:** Sandboxed if untrusted/generated; executor plugin dispatched.
- **Stage 5 Audit:** Immutable append. Must succeed before result is returned.
- **Stage 6 Verify:** Did the action actually achieve the stated intent? If not → rollback/retry.
- **Stage 7 Reflect:** Write to memory, update meta-memory confidence, optionally trigger learning loop.

---

*End of Document 02_ARCHITECTURE.md*
