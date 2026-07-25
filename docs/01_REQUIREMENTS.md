# PROJECT AEGIS — REQUIREMENTS SPECIFICATION

**Document ID:** AEGIS-DOC-002
**Version:** 0.1.0 (Prompt 01 Foundation)
**Status:** DRAFT — Architecture Phase Only
**Last Updated:** 2026-07-24

---

## 1. INTENT

This document defines the requirements for Project AEGIS as a system. Requirements are categorized by:

- **F-SYS** Functional — System Core
- **F-AI** Functional — AI Kernel
- **F-MEM** Functional — Memory & Knowledge
- **F-EXE** Functional — Execution Kernel
- **F-PLN** Functional — Cognitive Planning
- **F-ADAPT** Functional — Adaptive Intelligence & Learning
- **F-TOOL** Functional — Tool & MCP Ecosystem
- **F-HCI** Functional — Human-Computer / Multimodal Interface
- **NFR** Non-Functional Requirements

Requirements are marked by **Target Milestone** using the Prompt 01–23 sequence. A requirement labeled **M02** means it is due by Prompt 02 (Core Runtime). Prompt 01 is documentation-only, so no functional requirement targets M01 as deliverable code.

---

## 2. FUNCTIONAL REQUIREMENTS

### 2.1 SYSTEM CORE (F-SYS)

| ID | Requirement | Milestone | Priority |
|---|---|---|---|
| F-SYS-001 | Core Runtime provides a typed plugin loader with lifecycle hooks: `init → start → run → stop → shutdown` | M02 | P0 |
| F-SYS-002 | Core Runtime provides an Event Bus supporting pub/sub, typed events, and at-least-once delivery for persistent topics | M02 | P0 |
| F-SYS-003 | Core Runtime provides Configuration Management with layered precedence: defaults < config file < env vars < runtime overrides | M02 | P0 |
| F-SYS-004 | Core Runtime provides Audit Log subsystem with structured records, integrity protection, and immutable append mode | M02 | P0 |
| F-SYS-005 | Core Runtime provides Telemetry (metrics, traces, logs) with open exporters and zero external dependencies by default | M02 | P1 |
| F-SYS-006 | All subsystems expose a standardized health check: `{ status, reason, dependencies[] }` | M02 | P1 |
| F-SYS-007 | Graceful shutdown with ordered teardown, timeout, and forced-stop fallback | M02 | P1 |
| F-SYS-008 | Error taxonomy with typed error codes, severity levels, retry hints, and user-safe message separation | M02 | P1 |
| F-SYS-009 | Versioned interfaces; breaking changes require major version bump and migration path | M02 | P0 |

### 2.2 AI KERNEL (F-AI)

| ID | Requirement | Milestone | Priority |
|---|---|---|---|
| F-AI-001 | AI Kernel exposes an abstract `LLMProvider` interface: `complete(), chat(), stream(), tokenize(), get_context_window()` | M03 | P0 |
| F-AI-002 | Provider implementations are plugins; none are hardcoded in the kernel | M03 | P0 |
| F-AI-003 | Multiple concurrent API keys per provider with rotation and health checks | M03 | P1 |
| F-AI-004 | Model Router selects provider+model based on: task type, cost cap, latency SLA, privacy sensitivity, context size, and provider health | M03 | P0 |
| F-AI-005 | Structured output enforcement (JSON schema / Pydantic) with LLM fallback + validation retries | M03 | P0 |
| F-AI-006 | Token usage accounting with per-task, per-provider, per-day cost tracking and hard-stop limits | M03 | P0 |
| F-AI-007 | Prompt template library with versioning, variables, and safe variable interpolation (no raw prompt injection via untrusted vars) | M03 | P1 |
| F-AI-008 | Offline fallback: gracefully degrade to local-only models when WAN unavailable | M03 | P2 |

### 2.3 MEMORY & KNOWLEDGE ENGINE (F-MEM)

| ID | Requirement | Milestone | Priority |
|---|---|---|---|
| F-MEM-001 | Working Memory (in-context / short-horizon, bound by LLM context window, TTL) | M04 | P0 |
| F-MEM-002 | Session Memory (per session, persisted at session end, scrubbable | M04 | P0 |
| F-MEM-003 | Episodic Memory (what happened when: timestamped events with provenance | M04 | P0 |
| F-MEM-004 | Semantic Memory (facts, knowledge, embeddings, vector search) | M04 | P0 |
| F-MEM-005 | Procedural Memory (learned workflows, skill definitions) | M04 | P1 |
| F-MEM-006 | Personal Memory (preferences, styles, goals — user-validated tier) | M04 | P1 |
| F-MEM-007 | Environmental Memory (observed env facts with freshness TTL) | M07 | P1 |
| F-MEM-008 | Project Memory (scoped to repo/project, can travel with project) | M04 | P1 |
| F-MEM-009 | Skill Memory (auto-harness results: confidence, success rate, last tested, limitations) | M08 | P1 |
| F-MEM-010 | Meta-Memory: system tracks what it knows, confidence, staleness, and provenance | M04 | P0 |
| F-MEM-011 | Knowledge Graph: entities, relations, typed edges, traversal queries, link suggestions | M04 | P0 |
| F-MEM-012 | Obsidian Projection: bidirectional sync between structured knowledge and human-readable markdown vault | M11 | P1 |
| F-MEM-013 | Full memory lifecycle: write, read, update, archive, delete, export, import, TTL enforcement | M04 | P0 |
| F-MEM-014 | User-facing memory inspection UI with provenance timeline, edit, and delete | M11 | P1 |

### 2.4 EXECUTION KERNEL (F-EXE)

| ID | Requirement | Milestone | Priority |
|---|---|---|---|
| F-EXE-001 | Execution Kernel accepts typed `Action` objects; never accepts free-form text commands | M05 | P0 |
| F-EXE-002 | Permission Check pipeline runs before every action (subject, verb, resource, context) | M05 | P0 |
| F-EXE-003 | Policy Engine: deny-by-default, allowlisted capabilities, risk-scored approvals | M05 | P0 |
| F-EXE-004 | Sandbox execution for untrusted/generated code and generated tools | M05 | P0 |
| F-EXE-005 | Structured audit record for every action: who/what/where/when/result | M05 | P0 |
| F-EXE-006 | Verification step: post-execution assertion that intent was achieved | M05 | P1 |
| F-EXE-007 | Executor plugins: CLI, File System, Process, Git, Docker, MCP, Browser (each isolated behind interface) | M05 | P1 |
| F-EXE-008 | Transactional / reversible actions where possible; undo log for reversible operations | M05 | P2 |
| F-EXE-009 | Timeout, cancellation, and retry with exponential backoff and jitter | M05 | P1 |

### 2.5 COGNITIVE PLANNING ENGINE (F-PLN)

| ID | Requirement | Milestone | Priority |
|---|---|---|---|
| F-PLN-001 | Goal decomposition: user intent → sub-goals → tasks → actions | M06 | P0 |
| F-PLN-002 | Plans are first-class data: typed, versioned, serializable, editable | M06 | P0 |
| F-PLN-003 | Plan re-planning on failure with causal analysis of the failure | M06 | P0 |
| F-PLN-004 | Dependency graph between plan steps; parallel execution when independent | M06 | P1 |
| F-PLN-005 | Resource pre-check before plan execution (capabilities, tools, permissions, context) | M06 | P1 |
| F-PLN-006 | Risk scoring per plan step; high-risk steps trigger approval gate | M06 | P0 |
| F-PLN-007 | Plan traceability: every action references its plan step and original user intent | M06 | P0 |

### 2.6 ADAPTIVE INTELLIGENCE & PERSONAL ENVIRONMENT LEARNING (F-ADAPT)

| ID | Requirement | Milestone | Priority |
|---|---|---|---|
| F-ADAPT-001 | Environment Model: hardware, OS, apps, projects, repos, files, workspaces, devices, tools, accounts | M07 | P0 |
| F-ADAPT-002 | Relationship graph in environment model (e.g., "Project X uses Python env Y and repo Z") | M07 | P0 |
| F-ADAPT-003 | Software discovery: installed applications, versions, CLI entrypoints, UIs | M07 | P1 |
| F-ADAPT-004 | User behavior observation with explicit opt-in and scoped observation windows | M07 | P1 |
| F-ADAPT-005 | Workflow inference: repeated sequences → candidate procedural memory → user validation | M07 | P1 |
| F-ADAPT-006 | Preference learning: repeated choices → candidate preference memory → user validation | M07 | P1 |
| F-ADAPT-007 | Privacy zones: excluded locations, sensitive directories, redaction rules, retention caps | M07 | P0 |

### 2.7 TOOL & MCP ECOSYSTEM (F-TOOL)

| ID | Requirement | Milestone | Priority |
|---|---|---|---|
| F-TOOL-001 | Capability Registry: typed capability descriptions, metadata, confidence scores, provenance | M08 | P0 |
| F-TOOL-002 | Capability Discovery pipeline: goal → required capability → registry lookup → tool lookup → MCP lookup → CLI lookup | M08 | P0 |
| F-TOOL-003 | MCP Client: standard MCP protocol client with tool schema validation, timeout, retry | M08 | P0 |
| F-TOOL-004 | Generated Tool / Generated MCP: create new tool wrappers for learned capabilities | M08 | P1 |
| F-TOOL-005 | Sandboxed tool testing before registry (auto-harness entry point) | M08 | P0 |
| F-TOOL-006 | Versioned tool deployment with rollback and A/B evaluation | M08 | P1 |
| F-TOOL-007 | Tool confidence tracking: success rate, last tested, limitations, dependencies | M08 | P1 |

### 2.8 HUMAN-COMPUTER / MULTIMODAL INTERFACE (F-HCI)

| ID | Requirement | Milestone | Priority |
|---|---|---|---|
| F-HCI-001 | Text-based interface is the first-class interface (all capabilities reachable via text) | M02 | P0 |
| F-HCI-002 | Conversation context is bounded and explicitly managed; not an unbounded chat history | M02 | P1 |
| F-HCI-003 | Explicit approval UI for gated actions (text, then later desktop UI) | M05 | P0 |
| F-HCI-004 | Voice input / output pipeline with local-first preference, hotword, wake-word, streaming STT/TTS | M13 | P2 |
| F-HCI-005 | Desktop Control Center UI: system status, memory inspector, plan viewer, approvals, settings | M22 | P1 |
| F-HCI-006 | Computer control: screen understanding, mouse, keyboard, window management (with permission) | M09 | P1 |
| F-HCI-007 | Browser OS: full browser automation, navigation, extraction, forms, downloads (with permission) | M10 | P1 |
| F-HCI-008 | Vision / camera: OCR, object/person (explicit enrollment only), scene, change detection (explicit authorization) | M14 | P2 |

---

## 3. NON-FUNCTIONAL REQUIREMENTS (NFR)

### 3.1 SECURITY (SEC)

| ID | Requirement | Target |
|---|---|---|
| NFR-SEC-001 | **Deny-by-default.** No subsystem accesses anything outside its boundary without an explicit allowlist entry. | Permanent |
| NFR-SEC-002 | All secrets stored encrypted at rest (AES-256-GCM or better). Never plaintext on disk. Kept separate from config. | M02 |
| NFR-SEC-003 | No secrets in logs, audit trails, telemetry, or crash dumps. Automatic redaction. | M02 |
| NFR-SEC-004 | Prompt injection mitigations: structured output validation, output encoding, variable interpolation sanitization. | M03 |
| NFR-SEC-005 | Sandbox for all generated / user-supplied code: process isolation, filesystem overlay, network ACL, resource limits. | M05 |
| NFR-SEC-006 | Supply chain: pinned dependency versions, lockfiles, SBOM generation, vulnerability scanning in CI. | M23 |
| NFR-SEC-007 | Integrity protection for audit log and memory store (Merkle-tree or append-only MAC chain). | M23 |

### 3.2 PRIVACY (PRIV)

| ID | Requirement | Target |
|---|---|---|
| NFR-PRIV-001 | **Local-first principle.** Sensitive data never leaves the device unless user explicitly opts in for that specific datum. | Permanent |
| NFR-PRIV-002 | Privacy tiers for data: Local Only → E2EE Cloud → Public. All data tagged at write time. | M02 |
| NFR-PRIV-003 | Cloud model calls: user-sensitive content is automatically routed to local models when a suitable local model exists. | M03 |
| NFR-PRIV-004 | Full data portability: export all personal data to open formats (JSONL, Markdown, SQLite) without vendor lock-in. | M04 |
| NFR-PRIV-005 | Right-to-be-forgotten: atomic delete of all data associated with a user-requested scope. | M04 |
| NFR-PRIV-006 | Camera / microphone: hard kill switch (software toggle confirmed by OS-level indicator). Explicit per-session consent. | M14 |

### 3.3 RELIABILITY / AVAILABILITY (REL)

| ID | Requirement | Target |
|---|---|---|
| NFR-REL-001 | Core Runtime MTBF > 72 hours of continuous use under simulated load. | M02 |
| NFR-REL-002 | Any subsystem crash does not crash the Core Runtime; isolation via process boundary or supervised threads. | M02 |
| NFR-REL-003 | Automatic self-test on startup; degraded-mode operation when non-critical subsystems fail. | M02 |
| NFR-REL-004 | All persistence stores support backup / restore with point-in-time snapshots. | M04 |
| NFR-REL-005 | Network failures never hang the user-facing loop; bounded timeouts + offline queues. | M03 |

### 3.4 PERFORMANCE (PERF)

| ID | Requirement | Target |
|---|---|---|
| NFR-PERF-001 | Text interface response p95 < 500ms for non-AI actions. | M02 |
| NFR-PERF-002 | First-token latency p95 < 3s for cloud LLMs, < 8s for local 7B-class models. | M03 |
| NFR-PERF-003 | Memory vector search over 100k embeddings: p95 < 200ms. | M04 |
| NFR-PERF-004 | Core Runtime idle footprint < 500MB RAM on a 16GB system. | M02 |
| NFR-PERF-005 | Knowledge graph traversal (depth 3, 10k nodes): p95 < 100ms. | M04 |

### 3.5 MAINTAINABILITY / OBSERVABILITY (MAINT)

| ID | Requirement | Target |
|---|---|---|
| NFR-MAINT-001 | Every module emits structured logs (JSON), metrics (OpenTelemetry-compatible), and distributed traces. | M02 |
| NFR-MAINT-002 | Code coverage: core modules ≥ 85%, subsystems ≥ 70%, generated code excluded. | M02 |
| NFR-MAINT-003 | Dependency graph acyclic between layers (lower layers never import higher layers). | Permanent |
| NFR-MAINT-004 | Public interfaces versioned; breaking changes gated by major version. | Permanent |
| NFR-MAINT-005 | One-command reproducible dev environment + one-command test suite. | M02 |

### 3.6 EXTENSIBILITY (EXT)

| ID | Requirement | Target |
|---|---|---|
| NFR-EXT-001 | Every subsystem boundary defined by a stable interface (trait / protocol / ABC). No direct cross-subsystem imports of concrete classes. | Permanent |
| NFR-EXT-002 | Plugin manifest with capabilities, permissions, dependencies, and version. Plugin load is deny-by-default. | M02 |
| NFR-EXT-003 | Capability Registry supports runtime registration without Core Runtime restart. | M08 |
| NFR-EXT-004 | LLM provider, vector store, KG store, and execution backends all swappable via plugins. | Permanent |

---

## 4. REQUIREMENTS TRACEABILITY (SUMMARY)

| Prompt Phase | Primary Requirements Addressed |
|---|---|
| 01: Vision & Tech Foundation | This document (0/0 implemented, 100% specified) |
| 02: Core Runtime | F-SYS-*, NFR-SEC-002/003, NFR-REL-*, NFR-MAINT-*, NFR-EXT-001/002 |
| 03: AI Kernel | F-AI-*, NFR-SEC-004, NFR-REL-005, NFR-PERF-002 |
| 04: Memory & Knowledge Engine | F-MEM-*, NFR-PRIV-004/005, NFR-REL-004, NFR-PERF-003/005 |
| 05: Execution Kernel | F-EXE-*, NFR-SEC-005 |
| 06: Cognitive Planning Engine | F-PLN-* |
| 07: Adaptive Intelligence & Environment Learning | F-ADAPT-*, NFR-PRIV-001/002/003 |
| 08: Tool & MCP Ecosystem | F-TOOL-*, NFR-EXT-003 |
| 09: Real Computer Control | F-HCI-006 |
| 10: Browser OS + Web Learning | F-HCI-007 |
| 11–23 | Remaining F-HCI and domain-specific requirements per Prompt document |

---

## 5. COMPLIANCE GATE

A Prompt phase is **not complete** until:

1. All P0 requirements targeting that milestone are implemented.
2. All relevant NFRs targeting that milestone are met with evidence (tests, benchmarks, audits).
3. No P0 regression vs. prior milestone.
4. Documentation is current.

---

*End of Document 01_REQUIREMENTS.md*
