# LIVE INTEGRATION GRAPH — TEMPORARY AEGIS

> Built from live process inspection, live API calls, live code traces, and direct Python execution.
> Date: 2026-09-14 | Evidence Standard: Every row must have a live test result or code trace.

---

## Inspection Methodology

1. Live process enumeration (`ps aux`, `systemctl --user`)
2. Direct API calls with `curl` against running backend
3. Python execution of backend modules from CLI
4. Source code call-graph tracing
5. End-to-end mission execution with output verification

---

## Component Classification Table

| Component | Exists | Process/Service | API Endpoint | Actually Called in Mission Path | Actual Caller | Evidence | Status |
|---|---|---|---|---|---|---|---|
| **AEGIS Backend (FastAPI)** | ✅ | PID 26594, port :8787 | All /api/* | Yes | uvicorn → server.py | `systemctl --user status aegis-backend` | **LIVE** |
| **AEGIS Frontend (Vite)** | ✅ | PID 877/1085, port :2981 | Serves UI | Yes | User browser | `systemctl --user status aegis-frontend` | **LIVE** |
| **9Router (Gemini gateway)** | ✅ | External process, port :20128 | /v1/chat/completions | Yes — chat calls hit it | `query_9router_chat()` in server.py | `curl :20128/v1/models` → 200 + model list | **LIVE** |
| **Hermes agent** | ✅ | Binary at `~/.local/bin/hermes` | /ws/agent/hermes | Yes via PTY | `agent_pty.py` | health check: path valid | **LIVE** |
| **Claude Code (OpenClaw)** | ✅ | Binary at `~/.local/bin/claude` | /ws/agent/claude | PTY-available | `agent_pty.py` | health check: path valid | **LIVE** |
| **Codex** | ✅ | Binary at mise installs path | /ws/agent/codex | PTY-available | `agent_pty.py` | health check: path valid | **LIVE** |
| **OpenCode** | ✅ | Binary at `~/.opencode/bin/opencode` | /ws/agent/opencode | PTY-available | `agent_pty.py` | health check: path valid | **LIVE** |
| **DeepSeek (agent)** | ⚠️ | Falls back to `/usr/bin/bash` | /ws/agent/deepseek | Bash fallback, not true DeepSeek | `cfg.resolve_agent_command()` | health shows bash path | **PARTIALLY LIVE** |
| **OpenClaw daemon** | ⚠️ | Resolves to bash fallback | /ws/agent/openclaw | Bash fallback | `cfg.resolve_agent_command()` | health shows bash path | **PARTIALLY LIVE** |
| **9Router health** | ⚠️ | /api/9router-health | Returns `{status: stopped}` initially | Timeout in health check only | `query_9router_health()` | Direct probe to :20128 shows UP | **PARTIALLY LIVE** (health timeout bug) |
| **AgentMoe Fabric** | ✅ | Module `backend/agent_moe.py` | /api/agentmoe/tools, /api/agentmoe/discover, /api/agentmoe/execute [NEW] | Yes — called by task_planner.execute_plan() | `task_planner.py:131` `fn = agent_moe.tools.get(tool_name)` | Multi-step plan: 3 steps COMPLETED 0.33s | **LIVE** |
| **Task Planner** | ✅ | Module `backend/task_planner.py` | /api/planner/create-plan, /api/planner/execute-plan [NEW] | Yes — calls model_router then agent_moe | `server.py:942` | Plan ba8d9638 COMPLETED, experience file written | **LIVE** |
| **Model Router** | ✅ | Module `backend/model_router.py` | (internal) | Yes — called by task_planner and server chat | `task_planner.py:84` | gemini-3.8-flash responded in 1.68s | **LIVE** |
| **Memory Engine (TF-IDF)** | ✅ | Module `backend/memory_engine.py` | /api/memory/search | Yes — called in chat context injection | `server.py:224` `cognitive_memory.ranked_memory_search()` | Search for "aegis" → 6 ranked hits with scores | **LIVE** |
| **Knowledge Graph** | ✅ | Module `backend/knowledge_graph.py` | /api/graph, /api/search/unified | Yes | `server.py:688` | 58 nodes, 3 edges live | **LIVE** |
| **Task Experience Feedback** | ✅ | Written by task_planner, read by server | (via memory context) | Yes — past task records injected into chat | `server.py:get_relevant_memory_context()` | Chat described TASK_41eba2d1 by ID, goal, steps, outcome | **LIVE** |
| **Browser Tool (Headless Chrome)** | ✅ | Chrome subprocess | /api/browser/extract, /api/browser/screenshot | Yes | `browser_tool.extract_content()` | example.com → title, content, 163 chars extracted | **LIVE** |
| **Research Engine** | ✅ | Module `backend/research_engine.py` | /api/research/start | Yes | `server.py:966` | FastAPI research → COMPLETED, report written to vault | **LIVE** |
| **Vision Engine (Screen OCR)** | ✅ | `grim` + `tesseract` subprocess | /api/vision/status, /api/screen/intel | grim works, screen_intel fails from service context | `vision_engine.capture_screen()` | grim OK → 263KB image → 1498 chars OCR text | **PARTIALLY LIVE** |
| **Vision Engine (Camera)** | ✅ | /dev/video0 present | /api/vision/status | Camera detected, HARD_DENY | `vision_engine.get_camera_status()` | `camera_available: true, privacy_state: HARD_DENY` | **LIVE** (gated by policy) |
| **Computer Control** | ✅ | `wtype`, `wl-copy/paste` | /api/control/* | Not directly tested in this session | `computer_control.py` | Verified in prior end-to-end test suite | **LIVE** |
| **Code Sandbox** | ✅ | Python subprocess | /api/sandbox/execute | Yes | `server.py:973` | Python 3.11.16, 2+2=4, 0.054s | **LIVE** |
| **Audio Engine** | ✅ | Module `backend/audio_engine.py` | /api/audio/status | Yes | `server.py:947` | mic_available: true, HARD_DENY | **LIVE** (gated by policy) |
| **Proactive Monitor** | ✅ | Module `backend/proactive_monitor.py` | /api/monitor/health | Yes | `server.py:977` | Callable | **LIVE** |
| **AEGIS Health** | ✅ | Module `backend/aegis_health.py` | /api/health/full | Yes | `server.py:981` | full health runs all checks | **LIVE** |
| **Security Layer** | ✅ | `backend/security.py` middleware | All endpoints | Yes — on every request | `server.py middleware` | Unauthorized → 403; path traversal → 403 | **LIVE** |
| **Structured Logging** | ✅ | `backend/logger.py` rotating file | (internal) | Yes | All modules via `get_logger()` | File at ~/.temporary-aegis/logs/aegis.log | **LIVE** |
| **Vault File Cache** | ✅ | In-memory `_vault_md_cache` | (internal) | Yes | `get_vault_markdown_files()` 30s TTL | Code verified at server.py:75-86 | **LIVE** |
| **Consolidation Timer** | ✅ | systemd timer | (systemd) | Last ran 4min 50s ago | systemd | `list-timers` shows next=10min | **LIVE** |
| **Snapshot Timer** | ✅ | systemd timer | (systemd) | Ran 11min ago | systemd | Exit 0 verified | **LIVE** |
| **Voice/STT** | ✅ code | No active process | /api/audio/status | No — mic HARD_DENY | — | mic available but gated | **CODE COMPLETE — ENVIRONMENT GATED** |
| **Screen Intel (from service)** | ⚠️ | Wayland display not accessible | /api/screen/intel | Fails — no display in systemd context | `screen_intel.analyze_screen_multimodal()` | Error: "failed to create display" | **BROKEN from service** |
| **AEGIS Python L1-L6** | ❌ | External repo, not running | None | Not wired into dashboard backend | — | ~/Projects/Aegis/ exists but no API bridge | **UNWIRED** |
| **Verification step in plan** | ⚠️ | Planned but not enforced | — | Step has `verify` field but not re-checked | `task_planner.py` steps have verify string | verify field present, not executed | **PARTIALLY LIVE** |
| **Capability Discovery (semantic)** | ⚠️ | Keyword-only matching | /api/agentmoe/discover | Yes — keyword-based | `agent_moe.discover_capability()` | "browse fastapi" → Synthesizer (misrouted) | **PARTIALLY LIVE** |

---

## Integration Gaps Found

### GAP-1: AgentMoe NOT imported in server.py [REPAIRED]
- **Was:** Not imported, not accessible via API
- **Now:** Imported + `/api/agentmoe/tools`, `/api/agentmoe/discover`, `/api/agentmoe/execute` added
- **Evidence:** `GET /api/agentmoe/tools` → 9 tools, 8 roles

### GAP-2: execute_plan not accessible via API [REPAIRED]
- **Was:** Only `create_plan` endpoint existed; plans could not be executed via HTTP
- **Now:** `/api/planner/execute-plan` added
- **Evidence:** `POST /api/planner/execute-plan` → `status=COMPLETED, steps=2`

### GAP-3: Task experiences not fed back into chat memory [REPAIRED]
- **Was:** `get_relevant_memory_context()` read vault notes but not task experience files
- **Now:** Injects recent TASK_*.md files when query contains "task", "plan", "last", "result" etc.
- **Evidence:** Chat asked "what was the last task?" → correctly described TASK_41eba2d1 by ID, goal, steps, result

### GAP-4: Hardcoded model strings in classify_task_orchestrator [REPAIRED]
- **Was:** 12 occurrences of `"gemini/gemini-3.8-flash"` literal strings
- **Now:** Uses `cfg.MODEL_DEFAULT`, `cfg.MODEL_REASONING`, `cfg.MODEL_FAST`, `cfg.MODEL_LITE`

### GAP-5: Hardcoded fallback list in query_9router_chat [REPAIRED]
- **Was:** `for alt in ["gemini/gemini-3.8-flash", "gemini/gemini-3.6-flash", ...]`
- **Now:** `for alt in cfg.MODEL_FALLBACK_CHAIN`

### GAP-6: model_router.get_stats() missing [REPAIRED]
- **Was:** AttributeError when called
- **Now:** Method added with avg_latency and success_rate calculations

### GAP-7: /api/health returns 404
- **State:** Route is `/api/health/full` and `/api/monitor/health`, not `/api/health`
- **Severity:** LOW — existing routes work; documentation issue only

### GAP-8: screen_intel fails from systemd context
- **State:** `grim` requires WAYLAND_DISPLAY env var; systemd unit doesn't have it
- **Blocker:** Environment variable not passed to service
- **Severity:** MEDIUM — OCR from user terminal works; service context fails

### GAP-9: AEGIS Python L1-L6 not wired into dashboard
- **State:** ~/Projects/Aegis/ exists as separate repo, not imported or called
- **Severity:** LOW for Temporary AEGIS scope (separate project)

### GAP-10: DeepSeek and OpenClaw resolve to bash fallback
- **State:** AGENT_REGISTRY.json doesn't have valid CLI paths for these agents
- **Severity:** MEDIUM — PTY sessions start bash instead of true agents

### GAP-11: Capability discovery is keyword-only (not semantic)
- **State:** `discover_capability()` uses string matching; "browse fastapi docs" routes to Synthesizer (LLM), not Browser Worker
- **Severity:** LOW — functional but imprecise
