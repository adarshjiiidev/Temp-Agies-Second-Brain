# AGENTMOE — SURVIVAL AUDIT
**Date:** 2026-08-29 | **Status:** VERIFIED AGAINST ACTUAL CODE

---

## 1. FORENSIC CONCLUSION

**AgentMoe was never a separate committed package in this repository.**

`git log --diff-filter=D` returned zero results matching any
`agentmoe/`, `tools/`, `workers/`, `swarm/`, `browser/`, `computer/`,
`research/`, `coding/`, `models/`, or `delegation/` paths.

The Windows → Omarchy migration did not cause file loss of a prior AgentMoe
implementation because no such implementation was ever committed. The name
"AgentMoe" refers to a capability/tool/worker fabric that is:

- SPECIFIED in `docs/09_ROADMAP.md` (P09–P21)
- PARTIALLY SCAFFOLDED as `src/aegis/capabilities/` (P08, 2026-08-15/16)
- REFERENCED in `.agents/AGENTS.md` (design intent only)

---

## 2. SURVIVING AGENTMOE-RELEVANT CODE

### 2.1 `src/aegis/capabilities/` — P08 Foundation (✅ REAL CODE)

| File/Dir | LOC | State | Description |
|----------|-----|-------|-------------|
| `model/capability.py` | 248 | ✅ REAL | CapabilityRecord, CapabilityCategory(23 cats), TrustState, ProvenanceSource |
| `model/composition.py` | 86 | ✅ REAL | BuiltinRef, MCPToolRef, ExternalAgentRef, CompositeRef, CapabilityComposition |
| `model/health.py` | 73 | ✅ REAL | CapabilityHealth, HealthStatus |
| `model/metrics.py` | 81 | ✅ REAL | CapabilityMetrics (success/failure tracking) |
| `store/capability_store.py` | 219 | ✅ REAL | In-memory capability store with filter/search |
| `registry_v2/capability_registry.py` | 325 | ✅ REAL | SemanticCapabilityRegistry (discover/register/query/find_for_task) |
| `discovery_providers/base.py` | 78 | ✅ REAL | CapabilityDiscoveryProvider ABC |
| `discovery_providers/cli_provider.py` | 230 | ✅ REAL | CLIDiscoveryProvider (shutil.which based) |
| `discovery_providers/local_model_provider.py` | 193 | ✅ REAL | LocalModelDiscoveryProvider |
| `discovery_providers/mcp_provider.py` | 125 | ✅ REAL | MCPDiscoveryProvider |
| `discovery_providers/static_provider.py` | 185 | ✅ REAL | StaticRegistryProvider |
| `discovery_providers/plugin_provider.py` | 100 | ✅ REAL | PluginDiscoveryProvider |
| `mcp/types.py` | 98 | ✅ REAL | MCPServerRecord, MCPToolRecord, MCPTransport |
| `mcp/server_registry.py` | 181 | ✅ REAL | MCPServerRegistry (register/discover/health) |
| `mcp/tool_registry.py` | 41 | ✅ REAL | MCPToolRegistry |
| `mcp/schema_normalizer.py` | 162 | ✅ REAL | MCPSchemaNormalizer |
| `mcp/health_monitor.py` | 164 | ✅ REAL | MCPHealthMonitor (asyncio background loop) |
| `selection/schemas.py` | 98 | ✅ REAL | CapabilityConstraints/Input/Output |
| `selection/selector.py` | 281 | ✅ REAL | CapabilitySelector (filter+rank) |
| `invocation/invoker.py` | 337 | ✅ REAL | CapabilityInvoker → L5 bridge (CRITICAL) |
| `external_agents/types.py` | 112 | 🔷 TYPES ONLY | AgentType, AgentCommunication, ExternalAgentCapability |
| `discovery.py` | 174 | ✅ REAL | Discovery orchestration |
| `registry.py` | 157 | ✅ REAL | Pre-P08 env-probe CapabilityRegistry |
| `types.py` | 120 | ✅ REAL | Pre-P08 Capability, CapabilityKind, CapabilityStatus, CapabilitySet |
| **TOTAL** | **4,118** | | |

### 2.2 `src/aegis/l5_execution/` — Execution Backbone (✅ FULLY REAL)

These are the low-level execution primitives AgentMoe will invoke.

| Component | LOC | State |
|-----------|-----|-------|
| `pipeline.py` | 547 | ✅ REAL — 7-stage pipeline |
| `types.py` | 368 | ✅ REAL — Action, ActionKind, ActionResult, RiskLevel, SandboxTier |
| `contracts.py` | 309 | ✅ REAL — ExecutorManifest, SandboxContext |
| `permission/` | ~600 | ✅ REAL — PermissionEngine, SVRC, store |
| `risk/analyzer.py` | 281 | ✅ REAL — RiskAnalyzer (4-tier) |
| `policy/` | ~300 | ✅ REAL — PolicyEngine, rules |
| `audit/chain.py` | 296 | ✅ REAL — Hash-chain AuditChain |
| `sandbox/` | ~400 | ✅ REAL — T1 AST jail, T2 subprocess, T3 Docker |
| `rollback.py` | ~150 | ✅ REAL — RollbackEngine |
| `verify.py` | ~120 | ✅ REAL — PostExecVerifier |
| **executors/filesystem.py** | 334 | ✅ REAL — FS_READ/WRITE/APPEND/COPY/MOVE/DELETE/MKDIR/HASH/SEARCH/WATCH |
| **executors/git.py** | 217 | ✅ REAL — GIT_STATUS/DIFF/LOG/COMMIT/CHECKOUT/CLONE/PULL/PUSH/FETCH/BRANCH |
| **executors/shell.py** | 132 | ✅ REAL — SHELL_EXEC (T2 only, no shell=True) |
| **executors/http.py** | 218 | ✅ REAL — HTTP_GET/POST/PUT/DELETE/HEAD |
| **executors/python_exec.py** | 150 | ✅ REAL — PYTHON_EXEC (T1 AST jail or T2) |
| **executors/docker.py** | 240 | ✅ REAL — DOCKER_RUN/BUILD/PULL |
| **executors/obsidian.py** | 271 | ✅ REAL — OBSIDIAN_READ/WRITE/SEARCH |
| **executors/mcp.py** | 172 | 🔷 STUB — MCP_INVOKE stub (transport not implemented) |
| **executors/browser.py** | 25 | ❌ STUB — BROWSER_NAVIGATE/READ/FILL/CLICK/DOWNLOAD |
| **executors/desktop.py** | 22 | ❌ STUB — DESKTOP_SCREENSHOT/MOUSE/KEYBOARD/WINDOW |
| **executors/vscode.py** | 22 | ❌ STUB — VSCODE_READ/SEARCH/DIAGNOSTICS/TASK |
| **executors/base.py** | 131 | ✅ REAL — StubExecutor, ExecutorHealth |

### 2.3 `src/aegis/l3_intelligence/` — Model Fabric (✅ FULLY REAL)

| Component | LOC | State |
|-----------|-----|-------|
| `ai_kernel/kernel.py` | 662 | ✅ REAL — AIKernel facade (inference orchestrator) |
| `ai_kernel/router.py` | 383 | ✅ REAL — ModelRouter (capability-based routing) |
| `ai_kernel/registry.py` | 451 | ✅ REAL — ModelRegistry (quality scoring, dedup) |
| `ai_kernel/credentials.py` | 342 | ✅ REAL — CredentialResolver (env:/file:/aegis-keyring: schemes) |
| `ai_kernel/health.py` | ~200 | ✅ REAL — ProviderHealthMonitor (asyncio loop) |
| `ai_kernel/cache.py` | 447 | ✅ REAL — ResponseCache |
| `ai_kernel/accounting.py` | 330 | ✅ REAL — CostAccountant |
| `ai_kernel/streaming.py` | 357 | ✅ REAL — StreamingResponseProcessor |
| `ai_kernel/keys.py` | 336 | ✅ REAL — KeyManager |
| `providers/ollama.py` | 309 | ✅ REAL — Ollama (discovery, health, generate) |
| `providers/groq.py` | ~200 | ✅ REAL — Groq provider |
| `providers/openrouter.py` | ~200 | ✅ REAL — OpenRouter provider |
| `providers/vllm.py` | ~150 | ✅ REAL — vLLM provider |

**Missing from L3:**
- No multi-key credential pool (rotation, health-per-key, cooldown)
- No task-profile → provider/model mapping (CODING→coding model etc.)

### 2.4 `src/aegis/l4_memory/` — Memory (✅ FULLY REAL)
MemoryManager (T0-T8), SearchEngine (FTS5), KnowledgeGraph, PrivacyZoneService.
These are the persistence backend for AgentMoe context/artifacts/results.

### 2.5 `src/aegis/l1_core/`, `l2_foundation/`, `l6_planning/` — ✅ FULLY REAL
All layers L1–L6 are complete. 1097 Python tests + 26 Rust tests passing.

---

## 3. SURVIVING TESTS

| Suite | Files | LOC | Coverage |
|-------|-------|-----|---------|
| `tests/integration_p08/` | 4 | 954 | CapabilityModel, Store/Registry, DiscoveryProviders, MCPRegistry |
| `tests/integration_l5/` | 5 | ~1,200 | Full pipeline, permission, audit, policy, sandboxes |
| `tests/integration_l3/` | 9 | ~3,000 | Kernel, router, registry, credentials, providers |
| `tests/integration_l4/` | 12 | ~4,000 | Memory, store, graph, search, P07 |
| `tests/integration_l1l2/` | 6 | ~800 | Runtime, config, events |
| `tests/integration_l6/` | 7 | ~2,500 | Planning, orchestration |

**No AgentMoe tool/worker/swarm tests exist yet.**

---

## 4. SURVIVING DOCUMENTATION

| File | State | Relevance |
|------|-------|-----------|
| `.agents/AGENTS.md` | ✅ Current | Milestone status, architecture, session log |
| `docs/09_ROADMAP.md` | ✅ Current | P09–P21 spec (computer control, browser, research, coding, swarm) |
| `docs/AGENTMOE_RECOVERY_AUDIT.md` | ✅ Created | Phase 0 audit |
| `docs/AEGIS_MASTER_AUDIT.md` | ✅ Current | System-wide audit |
| `docs/adr/ADR-0001-rust-performance-core.md` | ✅ Real | Rust migration decisions |
| `docs/architecture/RUST_PERFORMANCE_CORE.md` | ✅ Real | Rust crate architecture |
| `docs/benchmarks/R3_BENCHMARK_REPORT.md` | ✅ Real | Search: 17-24× faster; DAG: 8-280× faster |

---

## 5. REFERENCE MATERIAL AVAILABLE

| Source | Location | Size | Type |
|--------|----------|------|------|
| Hermes Agent | `/home/adarshjii/.hermes/hermes-agent/` | ~4MB Python | Full agent runtime |
| gods-eye-view | `/home/adarshjii/Downloads/gods-eye-view-main.zip` | ~50MB | Geospatial viewer (IRRELEVANT) |

---

## 6. WHAT DOES NOT EXIST (AGENTMOE TO BUILD)

**Nothing in the following list has been implemented yet:**

- BaseTool ABC (identity/schema/risk/permissions/timeout/audit contract)
- BaseWorker ABC (spawn/delegate/collect/budget/cancel/checkpoint)
- ToolFabric (unified tool registry + invoke + audit)
- AgentMoe session / lifecycle manager
- FilesystemTool (high-level, path-guarded, privacy-zone-aware)
- TerminalTool (streaming, env isolation, timeout/cancel, Linux-first)
- BrowserTool (Playwright, SSRF guard, session isolation)
- ComputerTool (Linux/X11/AT-SPI)
- ResearchWorker (search→fetch→extract→synthesize→cite)
- CodingWorker (inspect→plan→edit→test→repair)
- DataWorker (PDF/CSV/Excel/Markdown/JSON)
- CredentialPool (multi-key, rotation, health, rate-limit)
- ModelFabric selector (task profile → provider/model)
- WorkerRuntime (spawn, privilege inheritance, depth limits)
- SwarmCoordinator (delegate, collect, vote, limits)
- ContextBus (T0 working memory scoped per mission)
- ExternalAgentAdapter (real implementation)
- AutonomyEnforcer (L0–L5 levels)
- PathGuard / SSRFGuard / InjectionGuard / BudgetGuard
- ExecutionSpan observability
- RetryPolicy + exponential backoff
- CheckpointStore
- MCP full transport (stdio/HTTP/SSE)
- Any AgentMoe integration/E2E tests
- Any AgentMoe security adversarial tests
