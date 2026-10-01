# CONNECTION ARCHITECTURE — TEMPORARY AEGIS

> **Design Principle:** Every component must be wired to every other component that it logically needs. No islands. No orphans.

---

## 1. System Topology

```
┌────────────────────────────────────────────────────────────────────────────┐
│                        AEGIS DASHBOARD  (:2981)                            │
│  Next.js / TypeScript UI                                                   │
│  ChatPanel  AgentTabs  ObsidianGraph  VaultExplorer  ModelsPanel  PCMonitor│
└───────────────────────────────┬────────────────────────────────────────────┘
                                │ HTTP + WebSocket (:8787)
                                ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                        AEGIS BACKEND  (:8787)                              │
│  FastAPI  •  CORS: localhost only  •  Auth: X-AEGIS-Token  •  127.0.0.1   │
│                                                                            │
│  server.py ──────── config.py (cfg) ─── AegisConfig singleton             │
│       │                                                                    │
│       ├── knowledge_graph.py   (Relational graph & unified search)         │
│       ├── memory_engine.py     (TF-IDF ranked vault search & memory)       │
│       ├── agent_moe.py         (Capability fabric, 9 tools, 8 roles)       │
│       ├── agent_pty.py         (PTY multiplexer, persistent agent sessions)│
│       ├── agent_runner.py      (Universal CLI agent harness runner)        │
│       ├── agent_supervisor.py  (Agent lifecycle & heartbeat monitoring)   │
│       ├── governance.py        (Deterministic capability & tool gating)    │
│       ├── task_planner.py      (Long-horizon goal decomposition)           │
│       ├── proactive_monitor.py (Git drift, health, resource telemetry)     │
│       ├── research_engine.py   (Web research & vault synthesis)            │
│       ├── vision_engine.py     (Screen OCR & camera frame capture)         │
│       ├── camera_registry.py   (Camera discovery vs auth state machine)    │
│       ├── vision_pipeline.py   (Local event detection & retention)         │
│       ├── computer_control.py  (Keyboard simulation & clipboard sync)      │
│       ├── browser_tool.py      (Headless Chrome DOM & screenshot)          │
│       ├── screen_intel.py      (Active window & desktop telemetry)         │
│       ├── linux_intelligence.py(Host hardware, kernel & resource intel)    │
│       ├── project_intelligence.py (Workspace git & tree analyzer)          │
│       ├── skill_registry.py    (Dynamic Hermes & Aegis skill discovery)    │
│       ├── turboquant_store.py  (Vector storage for memory/research)        │
│       ├── context_router.py    (Multi-layer context assembly)              │
│       ├── aegis_health.py      (System diagnostics & health checks)        │
│       ├── security.py          (Token auth, safe_path, rate limits)        │
│       ├── code_sandbox.py      (Safe Python/subprocess sandbox)            │
│       ├── audio_engine.py      (Audio status & microphone killswitch)      │
│       ├── model_router.py      (Dynamic model selection & fallback)        │
│       └── logger.py            (Structured rotating logs → ~/.temporary-aegis/logs/)
└───────────────────────────────┬────────────────────────────────────────────┘
                                │
          ┌─────────────────────┼────────────────────────┐
          ▼                     ▼                        ▼
┌──────────────────┐  ┌──────────────────┐   ┌───────────────────────────────┐
│  9Router (:20128)│  │  OpenClaw (SSE)  │   │  DeepSeek-V3 (local API)      │
│  Model Gateway   │  │  Claude-native   │   │  MoE reasoning                │
│  Free pool + fallback  ~/.openclaw/    │   │  repos/DeepSeek-V3            │
│  matrix: nex/glm/gemma workspace/      │   └───────────────────────────────┘
└──────────────────┘  └──────────────────┘
          │
          ├── OpenCode PTY  (~/.opencode/bin/opencode)
          ├── Hermes PTY    (~/.local/bin/hermes --profile agies)
          ├── Codex PTY     (~/.local/share/mise/installs/codex)
          ├── Claude Code   (~/.local/share/mise/installs/claude)
          └── Bash PTY      (/usr/bin/bash)
```

---

## 2. Connection Map — All Wired Links

### Frontend → Backend API Calls

| Frontend Component | API Endpoint | Method / Protocol | Purpose |
|---|---|---|---|
| `ChatPanel.tsx` | `/api/chat` | POST (JSON / SSE) | Main AI chat with model selection & context injection |
| `ChatPanel.tsx` | `/api/memory/search` | GET | TF-IDF ranked vault search |
| `ChatPanel.tsx` | `/api/chat/session` | GET | Establishes authenticated chat session |
| `AgentTabs.tsx` | `/ws/agent/{name}` | WebSocket | Interactive PTY streaming I/O with resize & ANSI support |
| `AgentTabs.tsx` | `/api/agents` | GET | Discovers registered agents from AGENT_REGISTRY |
| `AgentTabs.tsx` | `/api/agent/{name}/start` | POST | Explicitly spawns agent process |
| `AgentTabs.tsx` | `/api/agent/{name}/stop` | POST | Terminates agent process |
| `AgentTabs.tsx` | `/api/agent/{name}/restart`| POST | Restarts agent process |
| `AgentTabs.tsx` | `/api/agent/{name}/status` | GET | Queries running/idle status |
| `ObsidianGraph.tsx` | `/api/obsidian-graph` | GET | Live Obsidian vault link graph (MOCs, projects, areas) |
| `GlobalSearchModal.tsx`| `/api/graph` | GET | Structured Knowledge Graph nodes & edges |
| `VaultExplorer.tsx` | `/api/vault` | GET | Vault hierarchy tree |
| `VaultExplorer.tsx` | `/api/file/{path}` | GET | Reads full markdown vault note |
| `ModelsPanel.tsx` | `/api/models` | GET | 9Router model catalog and tier definitions |
| `PCMonitor.tsx` | `/api/pc-state` | GET / WS (`/ws`) | Live host CPU, RAM, disk, process list, port bindings |
| `PCMonitor.tsx` | `/api/diagnostics/deep` | GET | Deep subsystem diagnostic report across all 16 domains |
| `SkillsPanel.tsx` | `/api/skills` | GET | Dynamic skill registry (Hermes + Aegis skills) |
| `ToolsPanel.tsx` | `/api/tools` | GET | Universal tool registry from TOOL_REGISTRY.json |
| `GlobalSearchModal.tsx`| `/api/search/unified` | GET | Relational search across graph nodes + vault notes |
| `TopBar.tsx` | `/api/health` | GET | Fast ping health verification |
| `TopBar.tsx` | `/api/health/full` | GET | Full composite service health |
| `QuickActions.tsx` | `/api/run-script` | POST | Executes allowlisted system maintenance scripts |
| `QuickActions.tsx` | `/api/browser/extract` | GET / POST | Headless Chrome DOM text extraction |
| `QuickActions.tsx` | `/api/browser/screenshot` | GET / POST | Headless Chrome full-page screenshot |
| `QuickActions.tsx` | `/api/vision/status` | GET | Integrated camera hardware status & hard deny check |
| `QuickActions.tsx` | `/api/audio/status` | GET | Microphone device status & policy gate check |
| `QuickActions.tsx` | `/api/screen/intel` | GET | Active desktop window & screen OCR intelligence |
| `QuickActions.tsx` | `/api/intelligence` | GET | God Mode host telemetry + project summary |

### Backend → External Services

| Module | Service | Protocol | Authentication |
|---|---|---|---|
| `model_router.py` | 9Router (:20128) | HTTP/SSE | Bearer token |
| `openclaw_harness.py` | OpenClaw daemon | SSE stream | openclaw.json token |
| `deepseek_harness.py` | DeepSeek local API | HTTP | Local (no auth) |
| `vision_engine.py` | `/dev/video0` (camera) | v4l2 | Hard killswitch |
| `vision_engine.py` | `grim` (Wayland) | subprocess | Wayland socket |
| `vision_engine.py` | `tesseract` (OCR) | subprocess | None |
| `computer_control.py` | `wtype` (keyboard) | subprocess | None |
| `computer_control.py` | `wl-copy/wl-paste` | subprocess | Wayland socket |
| `browser_tool.py` | Chrome headless | subprocess | None |
| `research_engine.py` | Web (via curl/requests) | HTTPS | None |
| `agent_pty.py` | Agent binaries | PTY | Binary paths from cfg |

### Backend → Filesystem

| Module | Path | Operation |
|---|---|---|
| `memory_engine.py` | `cfg.VAULT` | Read (TF-IDF index) |
| `knowledge_graph.py` | `cfg.REGISTRIES_DIR` | Read (AGENT/TOOL/MODEL registry) |
| `knowledge_graph.py` | `cfg.PROJECTS` | Read (project scan) |
| `proactive_monitor.py` | `cfg.PROJECTS` | Read (git log, test status) |
| `task_planner.py` | `cfg.EXPERIENCES_FILE` | Read+Write |
| `logger.py` | `cfg.LOGS_DIR` | Write (rotating log) |
| `security.py` | `cfg.CONFIG_DIR/aegis_api_token` | Read (token validation) |
| `aegis_health.py` | `cfg.AEGIS_DIR` | Read (service status) |

---

## 3. Security Connection Boundaries

All connections are governed by these rules:

```
┌─────────────────────────────────────────────────────────┐
│                  SECURITY PERIMETER                      │
│                                                          │
│  FRONTEND (browser) ──HTTP──► BACKEND (:8787)           │
│                 X-AEGIS-Token required on mutations       │
│                 CORS: localhost origins ONLY              │
│                 Bind: 127.0.0.1 ONLY                     │
│                                                          │
│  BACKEND ──────────────────► 9Router (:20128)           │
│                               localhost only              │
│                                                          │
│  BACKEND ──────────────────► Filesystem                 │
│                               safe_path() guard          │
│                               must start with cfg.HOME   │
│                                                          │
│  BACKEND ──────────────────► Camera                     │
│                               HARD_DENY by default        │
│                               Must explicitly enable      │
│                                                          │
│  BACKEND ──────────────────► Subprocess                 │
│                               allowlist-checked commands  │
│                               timeout-bounded             │
└─────────────────────────────────────────────────────────┘
```

---

## 4. Data Flow Through the System

### Chat Message Flow
```
User types message in ChatPanel
    → POST /api/chat (with X-AEGIS-Token)
    → server.py injects:
        - GLOBAL context (cfg.*)
        - PROJECT context (knowledge_graph nodes)
        - TASK context (task_planner state)
        - LIVE context (optional: screen OCR, clipboard)
    → model_router.py selects model from 9Router
    → SSE stream back to frontend
    → Response displayed with citations
```

### Memory Search Flow
```
User searches vault
    → GET /api/memory/search?q=<query>
    → memory_engine.py runs TF-IDF over all .md in VAULT
    → Returns ranked results: path, score, snippet
    → Frontend shows in search modal
```

### Agent PTY Flow
```
User selects agent in AgentTabs
    → POST /api/agent/pty/start {agent_id}
    → agent_pty.py: cfg.resolve_agent_command(agent_id)
    → Spawns PTY subprocess with cfg.get_agent_env()
    → SSE stream from /api/agent/pty/output
    → User interacts via /api/agent/pty/input
```

---

## 5. Systemd Service Connections

| Service | Unit | Port/Resource | Depends On |
|---|---|---|---|
| `aegis-frontend` | user systemd | :2981 | — |
| `aegis-backend` | user systemd | :8787 | — |
| `aegis-consolidate` | systemd timer (15 min) | vault, projects | aegis-backend |
| `aegis-snapshot` | systemd timer (daily) | ~/.temporary-aegis/pc-state/ | — |
| `aegis-ingest-chatgpt` | systemd timer | ~/Downloads/ (optional) | — |
