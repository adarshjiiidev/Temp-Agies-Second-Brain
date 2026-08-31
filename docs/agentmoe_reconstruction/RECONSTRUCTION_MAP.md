# AGENTMOE — RECONSTRUCTION MAP
**Date:** 2026-08-29 | This is the authoritative build order.

---

## PACKAGE LOCATION

AgentMoe lives INSIDE AEGIS at: `src/aegis/agentmoe/`

It is NOT a separate repository. It extends AEGIS without replacing it.

```
src/aegis/
  agentmoe/
    __init__.py          ← public API
    core/                ← BaseTool, BaseWorker, ToolFabric, WorkerRuntime
    protocols/           ← all Protocol/ABC interfaces
    security/            ← PathGuard, SSRFGuard, InjectionGuard, AutonomyEnforcer
    observability/       ← ExecutionSpan, telemetry emitter
    tools/
      filesystem/        ← FilesystemTool (promotes l5 FilesystemExecutor)
      terminal/          ← TerminalTool (streaming, env isolation, Linux-first)
      git/               ← GitTool (promotes l5 GitExecutor)
      http/              ← HTTPTool (promotes l5 HttpExecutor + SSRF guard)
      python_exec/       ← PythonTool (promotes l5 PythonExecutor)
      browser/           ← BrowserTool (Playwright + full security)
      computer/          ← ComputerTool (Linux X11/AT-SPI)
      mcp/               ← MCPTool (full transport: stdio/HTTP/SSE)
    workers/
      base.py            ← BaseWorker ABC
      runtime.py         ← WorkerRuntime (lifecycle, budget, cancel)
      coding/            ← CodingWorker
      research/          ← ResearchWorker
      data/              ← DataWorker (PDF/CSV/Excel/Markdown)
      general/           ← GeneralWorker
    models/
      fabric.py          ← ModelFabric (task-profile → provider/model)
      pool.py            ← CredentialPool (multi-key, rotation, health)
      profiles.py        ← TaskProfile enum (CODING, RESEARCH, FAST, LOCAL, VISION, etc.)
    delegation/
      contract.py        ← ExternalAgentAdapter ABC
      spawner.py         ← WorkerSpawner (privilege inheritance, depth limits)
    swarm/
      coordinator.py     ← SwarmCoordinator
      context_bus.py     ← ContextBus (T0 Working Memory per mission)
    integration/
      aegis_bridge.py    ← L6→AgentMoe bridge (AEGIS calls AgentMoe here)
    recovery/
      retry.py           ← RetryPolicy
      checkpoint.py      ← CheckpointStore
    config/
      settings.py        ← AgentMoeConfig (typed, no hardcoding)
```

---

## INTEGRATION INVARIANT (NON-NEGOTIABLE)

```
L6 PlannerService → AgentMoe ToolFabric.invoke()
                          ↓
                  CapabilityInvoker (aegis.capabilities.invocation)
                          ↓
                  L5 ExecutionPipeline.execute(action)
                          ↓
    Permission → Risk → Policy → Executor → Sandbox → Audit → Verify
```

Every AgentMoe tool/worker that causes a side effect MUST route through
this chain. No direct subprocess.run(), no direct os.system().

---

## BUILD ORDER

### PHASE 1 — Architecture + Contracts (NO side-effecting code)
Output files:
- `src/aegis/agentmoe/__init__.py`
- `src/aegis/agentmoe/protocols/__init__.py`
- `src/aegis/agentmoe/core/tool.py`  ← BaseTool ABC
- `src/aegis/agentmoe/core/worker.py` ← BaseWorker ABC
- `src/aegis/agentmoe/core/fabric.py` ← ToolFabric interface
- `src/aegis/agentmoe/observability/span.py` ← ExecutionSpan
- `src/aegis/agentmoe/config/settings.py` ← AgentMoeConfig
- `docs/AGENTMOE_ARCHITECTURE.md`
- `docs/AGENTMOE_SECURITY_MODEL.md`
- Tests: unit contracts

### PHASE 2 — Security Guards
Output files:
- `src/aegis/agentmoe/security/path_guard.py`
- `src/aegis/agentmoe/security/ssrf_guard.py`
- `src/aegis/agentmoe/security/injection_guard.py`
- `src/aegis/agentmoe/security/budget_guard.py`
- `src/aegis/agentmoe/security/autonomy.py`
- Tests: `tests/agentmoe/security/` (path traversal, SSRF, injection adversarial)

### PHASE 3 — Core Runtime
Output files:
- `src/aegis/agentmoe/core/fabric.py` (real implementation)
- `src/aegis/agentmoe/workers/runtime.py`
- `src/aegis/agentmoe/recovery/retry.py`
- `src/aegis/agentmoe/recovery/checkpoint.py`
- Tests: unit + lifecycle + cancellation + shutdown

### PHASE 4 — Filesystem + Terminal + Git Tools
Output files:
- `src/aegis/agentmoe/tools/filesystem/tool.py`
- `src/aegis/agentmoe/tools/terminal/tool.py`
- `src/aegis/agentmoe/tools/git/tool.py`
- Tests: integration + security adversarial (path traversal, injection)

### PHASE 5 — HTTP + Python + MCP Tools
Output files:
- `src/aegis/agentmoe/tools/http/tool.py`
- `src/aegis/agentmoe/tools/python_exec/tool.py`
- `src/aegis/agentmoe/tools/mcp/tool.py` (real stdio/HTTP/SSE transport)
- Tests: SSRF, injection, MCP security

### PHASE 6 — Worker Runtime + BaseWorker
Output files:
- `src/aegis/agentmoe/workers/base.py`
- `src/aegis/agentmoe/workers/general/worker.py`
- `src/aegis/agentmoe/delegation/spawner.py`
- Tests: delegation, budget, privilege inheritance

### PHASE 7 — Model Fabric + Credential Pool
Output files:
- `src/aegis/agentmoe/models/profiles.py`
- `src/aegis/agentmoe/models/fabric.py`
- `src/aegis/agentmoe/models/pool.py`
- Tests: pool rotation, health, rate-limit, fallback

### PHASE 8 — Browser + Computer Tools
Output files:
- `src/aegis/agentmoe/tools/browser/tool.py`
- `src/aegis/agentmoe/tools/computer/tool.py`
- `src/aegis/agentmoe/tools/computer/backend.py`
- Tests: auth gate, SSRF, download restriction

### PHASE 9 — CodingWorker + ResearchWorker
Output files:
- `src/aegis/agentmoe/workers/coding/worker.py`
- `src/aegis/agentmoe/workers/research/worker.py`
- Tests: E2E worker tests (mocked tools)

### PHASE 10 — Swarm
Output files:
- `src/aegis/agentmoe/swarm/coordinator.py`
- `src/aegis/agentmoe/swarm/context_bus.py`
- Tests: privilege escalation, budget exhaustion, depth limits

### PHASE 11 — External Agent Adapters
Output files:
- `src/aegis/agentmoe/delegation/contract.py`
- `src/aegis/agentmoe/integration/aegis_bridge.py`
- Tests: trust state, sandbox, malicious adapter

### PHASE 12 — Security Hardening
- Full adversarial test suite
- `tests/agentmoe/security/`

### PHASE 13 — Performance Benchmarks
- Profile tool dispatch, worker startup, delegation overhead
- Evaluate existing Rust crates (`aegis_search_core`, `aegis_graph_core`) for AgentMoe
- `docs/AGENTMOE_PERFORMANCE_BENCHMARKS.md`

### PHASE 14 — AEGIS Integration + E2E
- Wire L6 PlannerService → AgentMoe ToolFabric
- E2E mission tests
- `docs/AGENTMOE_AEGIS_INTEGRATION.md`
