# PROJECT AEGIS — REPOSITORY STRUCTURE PROPOSAL

**Document ID:** AEGIS-DOC-005
**Version:** 0.1.0 (Prompt 01 Foundation)
**Status:** DRAFT — Architecture Phase Only
**Last Updated:** 2026-07-24

---

## 1. LAYOUT PRINCIPLES

The repository layout directly mirrors the 7-layer architecture from [02_ARCHITECTURE.md](02_ARCHITECTURE.md). Layout rules are enforced by CI and import lints:

1. **One directory per module.** Every module in the dependency graph has a corresponding directory. No "kitchen sink" modules.
2. **Layer directories group modules.** Top-level directories `l1_core/`, `l2_foundation/`, `l3_intelligence/`, `l4_memory/`, `l5_capability/`, `l6_cognitive/`, `l7_hci/` enforce the layer boundary.
3. **No cross-layer imports above.** `l3_intelligence/` never imports from `l4_memory/` or higher. Lint rule.
4. **Plugins live outside layers.** `plugins/` directory hosts all implementations. Layers define interfaces only.
5. **Interfaces first, implementations second.** Each module has a `interfaces.py` (or `.rs`) file that defines the protocol. Concrete classes live in `plugins/` or a dedicated `impl/` subdirectory marked as internal.
6. **Tests live adjacent.** Each module has a `tests/` subdirectory. This keeps tests close to the code without polluting production imports.
7. **Runtime data lives outside the source tree.** All data — memory, audit logs, secrets vault, vector DB, KG DB, Obsidian vault — lives under `$AEGIS_DATA_DIR` (default: `~/.aegis/`), never under the source repo.

---

## 2. FULL REPOSITORY TREE

```
AGIES/
├── docs/                               # PROMPT 01 DOCUMENTATION (already exists)
│   ├── 00_VISION.md
│   ├── 01_REQUIREMENTS.md
│   ├── 02_ARCHITECTURE.md
│   ├── 03_TECH_STACK.md
│   ├── 04_REPOSITORY_STRUCTURE.md
│   ├── 05_SECURITY_PRIVACY.md
│   ├── 06_MEMORY_KNOWLEDGE.md
│   ├── 07_AI_STRATEGY.md
│   ├── 08_CAPABILITY_DISCOVERY.md
│   ├── 09_ROADMAP.md
│   └── 10_RISKS.md
│
├── crates/                             # RUST KERNEL (perf/security hotspots)
│   ├── Cargo.toml                      # Rust workspace manifest
│   ├── aegis_sandbox/                  # T1/T2 sandbox enforcement (FFI to Python)
│   ├── aegis_crypto/                   # AEAD encryption, integrity, key derivation (FFI)
│   ├── aegis_audit_chain/              # Append-only audit log MAC chain (FFI)
│   ├── aegis_store/                    # High-performance KV / vector / graph index (FFI)
│   └── aegis_ffi_common/               # Shared PyO3 types, error codes, IDL
│
├── src/                                # PYTHON SOURCE TREE
│   └── aegis/
│       ├── __init__.py
│       ├── __main__.py                 # Entrypoint: `python -m aegis`
│       ├── cli.py                      # Typer-based CLI (M02)
│       │
│       ├── l1_core/                    # LAYER 1 — CORE RUNTIME
│       │   ├── __init__.py
│       │   ├── runtime.py              # CoreRuntime: module container + lifecycle FSM
│       │   ├── supervisor.py           # Crash detection, restart policy, watchdog
│       │   ├── interfaces/             # ALL system interfaces (Protocol / ABC)
│       │   │   ├── __init__.py
│       │   │   ├── base.py             # ModuleLifecycle, HealthProvider, Pluggable
│       │   │   ├── llm.py              # LLMProvider, EmbeddingProvider (forward decl to l3)
│       │   │   ├── storage.py          # KVStore, DocStore, VectorStore, GraphStore
│       │   │   ├── exec.py             # Executor, Action, ActionResult (forward to l3)
│       │   │   ├── memory.py           # MemoryStore (forward to l4)
│       │   │   └── events.py           # EventBus, Event, Subscriber (forward to l2)
│       │   ├── errors/                 # Typed error taxonomy
│       │   │   ├── __init__.py
│       │   │   ├── base.py             # AegisError (Severity, RetryHint, UserSafeMsg)
│       │   │   ├── codes.py            # Error code registry
│       │   │   └── classify.py         # Error classifier
│       │   ├── health/
│       │   │   ├── __init__.py
│       │   │   ├── registry.py         # HealthAggregator, HealthReport
│       │   │   └── checks.py           # Standard health checks
│       │   └── tests/
│       │
│       ├── l2_foundation/              # LAYER 2 — FOUNDATION SERVICES
│       │   ├── __init__.py
│       │   ├── event_bus/
│       │   │   ├── __init__.py
│       │   │   ├── bus.py              # InProcessEventBus + SQLite append-log
│       │   │   ├── topics.py           # Standard topic registry
│       │   │   ├── types.py            # Typed event definitions
│       │   │   └── tests/
│       │   ├── config/
│       │   │   ├── __init__.py
│       │   │   ├── loader.py           # Layered config: defaults < file < env < runtime
│       │   │   ├── schema.py           # Pydantic config schemas
│       │   │   ├── hot_reload.py       # Hot reload + change audit
│       │   │   └── tests/
│       │   ├── crypto/
│       │   │   ├── __init__.py
│       │   │   ├── vault.py            # SecretsVault: encrypted-at-rest secrets
│       │   │   ├── redact.py           # Automatic log/trace redaction
│       │   │   ├── ffi.py              # Bridge to Rust aegis_crypto
│       │   │   └── tests/
│       │   ├── persistence/            # INTERFACES + DEFAULT IMPLS (SQLite plugin default)
│       │   │   ├── __init__.py
│       │   │   ├── kv.py               # KVStore impl (SQLite)
│       │   │   ├── doc.py              # DocStore impl (SQLite JSONB + FTS5)
│       │   │   ├── vector.py           # VectorStore impl (Qdrant local-mode wrapper)
│       │   │   ├── graph.py            # GraphStore impl (SQLite edge tables)
│       │   │   ├── migrations/         # Alembic-style SQL migrations (versioned)
│       │   │   └── tests/
│       │   ├── plugin_loader/
│       │   │   ├── __init__.py
│       │   │   ├── manifest.py         # manifest.yaml schema validation
│       │   │   ├── loader.py           # Manifest-driven dynamic load
│       │   │   ├── registry.py         # Loaded plugin registry
│       │   │   └── tests/
│       │   ├── telemetry/
│       │   │   ├── __init__.py
│       │   │   ├── logger.py           # Structured JSON logger, redacted
│       │   │   ├── metrics.py          # Counter, Gauge, Histogram with Prometheus export
│       │   │   ├── tracer.py           # OTel-compatible tracer (no vendor by default)
│       │   │   └── tests/
│       │   └── scheduler/
│       │       ├── __init__.py
│       │       ├── queue.py            # Async task queue + priority
│       │       ├── cron.py             # Cron schedules
│       │       ├── retry.py            # Retry with backoff/jitter
│       │       └── tests/
│       │
│       ├── l3_intelligence/            # LAYER 3 — AI KERNEL + EXECUTION
│       │   ├── __init__.py
│       │   ├── ai_kernel/
│       │   │   ├── __init__.py
│       │   │   ├── router.py           # ModelRouter: cost/latency/privacy/context routing
│       │   │   ├── providers/          # Provider plugin skeletons (concrete impls in plugins/)
│       │   │   │   ├── base.py
│       │   │   │   ├── ollama.py
│       │   │   │   ├── openrouter.py
│       │   │   │   ├── groq.py
│       │   │   │   └── vllm.py
│       │   │   ├── structured.py       # Pydantic v2 structured output + retry loop
│       │   │   ├── cost.py             # Token/cost accounting, hard-stop limits
│       │   │   ├── prompts/            # Versioned prompt templates
│       │   │   │   ├── library.py
│       │   │   │   └── registry.py
│       │   │   └── tests/
│       │   ├── permission/
│       │   │   ├── __init__.py
│       │   │   ├── engine.py           # SVRC permission engine
│       │   │   ├── rbac.py             # Role definitions
│       │   │   ├── abac.py             # Attribute-based policies
│       │   │   ├── consent.py           # User consent records
│       │   │   └── tests/
│       │   ├── policy/
│       │   │   ├── __init__.py
│       │   │   ├── engine.py           # Policy-as-code, risk scoring
│       │   │   ├── approval.py         # Approval gate router
│       │   │   ├── rules.py            # Built-in policy rules (versioned)
│       │   │   └── tests/
│       │   ├── execution/
│       │   │   ├── __init__.py
│       │   │   ├── kernel.py           # ExecutionKernel: typed Action dispatcher
│       │   │   ├── action.py           # Action / ActionResult typed models
│       │   │   ├── executor_plugins/   # Executor interface + built-in (CLI, FS, Process, Git…)
│       │   │   │   ├── base.py
│       │   │   │   ├── cli.py
│       │   │   │   ├── fs.py
│       │   │   │   ├── process.py
│       │   │   │   └── git.py
│       │   │   ├── tx_log.py           # Transactional undo log
│       │   │   └── tests/
│       │   ├── sandbox/
│       │   │   ├── __init__.py
│       │   │   ├── tier1_ast.py        # Python AST-limited evaluator
│       │   │   ├── tier2_subproc.py    # Subprocess + resource limits (Job Objects/WSL2)
│       │   │   ├── tier3_docker.py     # Docker container backend
│       │   │   ├── manager.py          # Tier selector + orchestrator
│       │   │   ├── ffi.py              # Bridge to Rust aegis_sandbox
│       │   │   └── tests/
│       │   ├── audit/
│       │   │   ├── __init__.py
│       │   │   ├── logger.py           # Append-only AuditLogger
│       │   │   ├── integrity.py        # MAC chain (Rust FFI)
│       │   │   ├── query.py            # Audit query API
│       │   │   └── tests/
│       │   └── verification/
│       │       ├── __init__.py
│       │       ├── verifier.py         # Post-execution assertion engine
│       │       ├── assertions.py       # Built-in assertion library
│       │       └── tests/
│       │
│       ├── l4_memory/                  # LAYER 4 — MEMORY + KNOWLEDGE
│       │   ├── __init__.py
│       │   ├── memory_engine/
│       │   │   ├── __init__.py
│       │   │   ├── engine.py           # 9-tier memory router
│       │   │   ├── tiers/              # Each memory tier as submodule
│       │   │   │   ├── working.py
│       │   │   │   ├── session.py
│       │   │   │   ├── episodic.py
│       │   │   │   ├── semantic.py
│       │   │   │   ├── procedural.py
│       │   │   │   ├── personal.py
│       │   │   │   ├── environmental.py
│       │   │   │   ├── project.py
│       │   │   │   └── skill.py
│       │   │   ├── provenance.py       # Provenance tracking for every memory write
│       │   │   ├── ttl.py              # TTL + archival policy
│       │   │   ├── lifecycle.py        # Write/Read/Update/Archive/Delete/Export/Import
│       │   │   └── tests/
│       │   ├── vector/
│       │   │   ├── __init__.py
│       │   │   ├── store.py            # VectorStore: Qdrant-backed (default impl)
│       │   │   ├── hybrid.py           # Hybrid retrieval: vector + keyword (FTS5)
│       │   │   ├── embeddings.py       # Embedding model router
│       │   │   └── tests/
│       │   ├── knowledge_graph/
│       │   │   ├── __init__.py
│       │   │   ├── store.py            # GraphStore: SQLite edge + NetworkX traversal
│       │   │   ├── types.py            # Entity, Relation, Edge typed models
│       │   │   ├── traversal.py        # Query DSL, subgraph extraction, path queries
│       │   │   ├── linker.py           # Link suggestion / auto-linking
│       │   │   └── tests/
│       │   ├── obsidian/
│       │   │   ├── __init__.py
│       │   │   ├── projection.py       # Structured memory → Obsidian vault writer
│       │   │   ├── ingest.py           # Obsidian vault → structured memory reader
│       │   │   ├── sync.py             # Bidirectional sync + conflict resolution
│       │   │   ├── templates/          # Note templates (project, research, daily, decision…)
│       │   │   └── tests/
│       │   ├── environment/
│       │   │   ├── __init__.py
│       │   │   ├── model.py            # Environment graph model
│       │   │   ├── scanners/           # Scanner plugins: hardware/os/apps/repos/files
│       │   │   │   ├── base.py
│       │   │   │   ├── os.py
│       │   │   │   ├── apps.py
│       │   │   │   ├── repos.py
│       │   │   │   └── projects.py
│       │   │   ├── freshness.py        # Freshness tracking + re-scan triggers
│       │   │   └── tests/
│       │   └── meta_memory/
│       │       ├── __init__.py
│       │       ├── index.py            # "What I know / don't know" index
│       │       ├── calibration.py      # Confidence calibration
│       │       ├── staleness.py        # Staleness detection + refresh triggers
│       │       └── tests/
│       │
│       ├── l5_capability/              # LAYER 5 — CAPABILITY ECOSYSTEM
│       │   ├── __init__.py
│       │   ├── registry/
│       │   │   ├── __init__.py
│       │   │   ├── capability.py       # Capability typed model + metadata
│       │   │   ├── store.py            # CapabilityRegistry: semantic search + KG-backed
│       │   │   ├── metadata.py         # Confidence/success-rate/version tracking
│       │   │   └── tests/
│       │   ├── tool_runtime/
│       │   │   ├── __init__.py
│       │   │   ├── wrapper.py          # Tool execution wrapper (schema, retry, coercion)
│       │   │   ├── context.py          # Context injection policy
│       │   │   └── tests/
│       │   ├── mcp_runtime/
│       │   │   ├── __init__.py
│       │   │   ├── client.py           # Standard MCP client
│       │   │   ├── schema.py           # Tool schema import / validation
│       │   │   ├── lifecycle.py        # Connection pooling, health
│       │   │   └── tests/
│       │   ├── discovery/
│       │   │   ├── __init__.py
│       │   │   ├── pipeline.py         # Goal → capability → tool → MCP → CLI → learn
│       │   │   ├── goal_decompose.py   # Goal-to-capability mapping
│       │   │   ├── software_inspect.py # Software discovery + familiarization
│       │   │   └── tests/
│       │   ├── generator/
│       │   │   ├── __init__.py
│       │   │   ├── tool_gen.py         # Tool / MCP wrapper code generator
│       │   │   ├── type_check.py       # Generated code type-check pass
│       │   │   └── tests/
│       │   ├── auto_harness/
│       │   │   ├── __init__.py
│       │   │   ├── harness.py          # Harness runner
│       │   │   ├── test_gen.py         # Test case generator
│       │   │   ├── scorer.py           # Expected vs actual scorer
│       │   │   ├── repair.py           # Repair loop
│       │   │   └── tests/
│       │   ├── self_repair/
│       │   │   ├── __init__.py
│       │   │   ├── analyzer.py         # Failure root cause analysis
│       │   │   ├── fix_gen.py          # Fix generator
│       │   │   ├── deploy.py           # Versioned deploy + rollback policy
│       │   │   └── tests/
│       │   └── skill_store/
│       │       ├── __init__.py
│       │       ├── skill.py            # Skill typed model
│       │       ├── store.py            # Versioned storage, eval history, rollback points
│       │       └── tests/
│       │
│       ├── l6_cognitive/               # LAYER 6 — COGNITIVE + PERSONALIZATION
│       │   ├── __init__.py
│       │   ├── planner/
│       │   │   ├── __init__.py
│       │   │   ├── cognitive.py        # CognitivePlanner: intent→subgoals→tasks→actions
│       │   │   ├── plan.py             # Plan typed model (versioned, serializable)
│       │   │   ├── risk.py             # Per-step risk scoring
│       │   │   ├── replan.py           # On-failure replan with causal analysis
│       │   │   ├── trace.py            # Traceability: action ← step ← task ← goal ← intent
│       │   │   └── tests/
│       │   ├── adaptive/
│       │   │   ├── __init__.py
│       │   │   ├── observers.py        # User behavior observers (opt-in)
│       │   │   ├── workflow.py         # Workflow inference engine
│       │   │   ├── preference.py       # Preference learner
│       │   │   └── tests/
│       │   ├── personal/
│       │   │   ├── __init__.py
│       │   │   ├── models.py           # Explicitly enrolled person models
│       │   │   ├── predict.py          # Evidence-based probabilistic predictions
│       │   │   └── tests/
│       │   ├── research/
│       │   │   ├── __init__.py
│       │   │   ├── orchestrator.py     # Research pipeline orchestrator
│       │   │   ├── sources.py          # Source comparison + verification
│       │   │   ├── citations.py        # Citation graph
│       │   │   └── tests/
│       │   └── domains/                # DOMAIN MODULES (Finance, Cyber, Social) — plugins
│       │       ├── __init__.py
│       │       ├── finance_in/         # Indian markets (NSE/BSE)
│       │       ├── cybersecurity/      # Defensive + CTF labs
│       │       └── social/             # Social media trust ladder
│       │
│       └── l7_hci/                     # LAYER 7 — HUMAN INTERFACE
│           ├── __init__.py
│           ├── text/
│           │   ├── __init__.py
│           │   ├── interface.py        # First-class text interface core
│           │   ├── context.py          # Bounded conversation context manager
│           │   ├── approval.py         # Text-mode approval prompts
│           │   ├── streaming.py        # Status streaming
│           │   ├── tui.py              # Textual TUI (M02)
│           │   └── tests/
│           ├── control_center/         # M22: Tauri 2 + React desktop UI
│           │   ├── backend.py          # Python sidecar IPC handler
│           │   └── frontend/           # React/TS source (separate build; NOT part of core)
│           ├── voice/                  # M13
│           │   ├── __init__.py
│           │   ├── stt.py
│           │   ├── tts.py
│           │   ├── hotword.py
│           │   └── vad.py
│           ├── computer/               # M09
│           │   ├── __init__.py
│           │   ├── screen.py
│           │   ├── input.py
│           │   ├── windows.py
│           │   ├── ocr.py
│           │   └── backends/
│           │       ├── win32.py
│           │       └── accessibility.py
│           ├── browser/                # M10
│           │   ├── __init__.py
│           │   ├── engine.py
│           │   ├── extract.py
│           │   ├── forms.py
│           │   └── profiles.py
│           └── vision/                 # M14
│               ├── __init__.py
│               ├── camera.py
│               ├── perception.py
│               ├── privacy_zones.py
│               └── models/
│
├── plugins/                            # EXTERNAL / OPTIONAL PLUGINS
│   ├── llm_providers/                  # Extra LLM providers beyond the 4 built-in
│   ├── storage_backends/               # Alternative backends (Postgres, Neo4j, Redis…)
│   ├── executors/                      # Extra executors (Docker, WSL, SSH remote…)
│   ├── mcp_servers/                    # Bundled optional MCP servers shipped with AEGIS
│   └── domains/                        # Extra domain modules (beyond finance/cyber/social)
│
├── tests/                              # CROSS-MODULE INTEGRATION TESTS
│   ├── conftest.py
│   ├── fixtures/
│   ├── integration_l1l2/
│   ├── integration_l123/
│   ├── integration_full_stack/
│   ├── security/                       # Security tests: sandbox escape, prompt injection, etc.
│   └── benchmarks/
│
├── data/                               # .gitignore'd — local dev data, NEVER committed
│   └── .gitkeep
│
├── supabase/                           # SUPABASE MIGRATIONS (if cloud sync is enabled)
│   └── migrations/
│
├── examples/
│   └── config.example.yaml
│
├── scripts/                            # Dev scripts (one-off utilities, NOT part of runtime)
│   ├── bootstrap_dev_env.py
│   ├── migrate_storage.py
│   └── export_memory.py
│
├── justfile                            # Task runner: `just test`, `just lint`, etc.
├── pyproject.toml                      # Python project: uv/ruff/mypy/pytest config
├── uv.lock                             # Pinned Python dependencies
├── .python-version                     # Required Python (3.12+)
├── Cargo.toml                          # Rust workspace root (also in crates/ but root for convenience)
├── Cargo.lock                          # Pinned Rust dependencies
├── rust-toolchain.toml                 # Required Rust toolchain
├── .gitignore
├── .editorconfig
├── LICENSE.txt
└── README.md
```

---

## 3. BOUNDARY RULES — ENFORCED MECHANISMS

| Rule | Mechanism |
|---|---|
| Higher layer never imports concrete class from lower layer | Import lint: `ruff` custom rule + mypy plugin; CI fails on forbidden imports |
| Layers 1–7: dependencies flow downward | `import-linter` contract files; explicit allowlist per layer pair |
| `l1_core/interfaces/` is the ONLY allowed cross-module direct import | All other module-to-module calls use interface injection or Event Bus |
| Plugins never import concrete classes from each other | Plugin-to-plugin goes through interfaces + Event Bus only |
| Secrets never appear in code | `detect-secrets` pre-commit hook + CI scan; `aegis.crypto.redact` |
| Memory data never committed | `data/` + `~/.aegis/` gitignored; integration tests use ephemeral temp dirs |
| No hardcoded provider API keys in repo | Pre-commit hook + `gitleaks`; tests use fixture `os.environ["TEST_DUMMY_KEY"]` |

---

## 4. MILESTONE-BY-MILESTONE FILES ACTIVATED

| Prompt | New directories/modules written in that prompt |
|---|---|
| 01 (this phase) | docs/ only |
| 02 Core Runtime | `src/aegis/l1_core/`, `src/aegis/l2_foundation/`, `crates/*` skeleton, `pyproject.toml`, `justfile`, tests/l1l2 |
| 03 AI Kernel | `src/aegis/l3_intelligence/ai_kernel/` |
| 04 Memory Engine | `src/aegis/l4_memory/` |
| 05 Execution Kernel | `src/aegis/l3_intelligence/{permission,policy,execution,sandbox,audit,verification}/` |
| 06 Cognitive Planning Engine | `src/aegis/l6_cognitive/planner/` |
| 07 Adaptive Intelligence | `src/aegis/l6_cognitive/{adaptive,personal}/`, `l4_memory/environment/` |
| 08 Tool & MCP Ecosystem | `src/aegis/l5_capability/` |
| 09 Real Computer Control | `src/aegis/l7_hci/computer/` |
| 10 Browser OS | `src/aegis/l7_hci/browser/` + `l6_cognitive/research/` |
| 11 Second Brain + Obsidian | `src/aegis/l4_memory/obsidian/` + memory inspector UI in text |
| 12 Coding Intelligence | `plugins/executors/git.py` enhanced + codex/claude/gemini CLI wrappers |
| 13 Voice System | `src/aegis/l7_hci/voice/` |
| 14 Vision & Perception | `src/aegis/l7_hci/vision/` |
| 15 Personal & Social | `l6_cognitive/personal/` enriched |
| 16 Research | `l6_cognitive/research/` enriched |
| 17 Finance | `l6_cognitive/domains/finance_in/` |
| 18 Cybersecurity | `l6_cognitive/domains/cybersecurity/` |
| 19 Social Media | `l6_cognitive/domains/social/` |
| 20 Multi-Worker Society | `l6_cognitive/planner/worker_orch.py` |
| 21 Auto-Learning | `l5_capability/auto_harness/` + `self_repair/` enriched with active learning |
| 22 Desktop UI | `l7_hci/control_center/` + Tauri frontend |
| 23 Production Hardening | CI/CD, SBOM, vuln scanning, audit log integrity, fuzz suite |

---

## 5. COMMITMENT TO NO LEAKAGE

Principle P2 (Clean Boundaries) is enforced at the repository level:

- **Prompt 02 code cannot mention the word "Ollama"** — the provider interface exists; the concrete Ollama plugin ships in Prompt 03.
- **Prompt 03 code cannot import Obsidian** — that is L4; it writes in Prompt 04/11.
- **Prompt 04 code cannot call a shell command** — Execution Kernel is Prompt 05.

Any file that violates the boundary is either moved to a later prompt's `future/` staging directory or reverted. No exceptions. The roadmap is deliberate; skipping phase boundaries is how systems become unmaintainable monoliths.

---

*End of Document 04_REPOSITORY_STRUCTURE.md*
