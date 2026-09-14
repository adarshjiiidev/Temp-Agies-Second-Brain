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
│       ├── knowledge_graph.py  (58 nodes, registry-driven)                 │
│       ├── memory_engine.py    (TF-IDF ranked vault search)                │
│       ├── agent_moe.py        (capability fabric, tool dispatch)           │
│       ├── agent_pty.py        (PTY multiplexer, 5+ agents)                │
│       ├── agent_runner.py     (non-interactive agent dispatch)             │
│       ├── task_planner.py     (goal decomposition)                        │
│       ├── proactive_monitor.py (project health, drift detection)           │
│       ├── research_engine.py  (web research, synthesis)                   │
│       ├── vision_engine.py    (screen OCR, camera)                        │
│       ├── computer_control.py (keyboard, clipboard, system actions)       │
│       ├── browser_tool.py     (headless Chrome DOM + screenshot)           │
│       ├── screen_intel.py     (active window, desktop context)            │
│       ├── aegis_health.py     (diagnostics, service health)               │
│       ├── security.py         (token auth, path guards)                   │
│       ├── code_sandbox.py     (safe Python execution)                     │
│       ├── audio_engine.py     (TTS/STT stubs)                             │
│       ├── deepseek_harness.py (DeepSeek-V3 reasoning interface)           │
│       ├── openclaw_harness.py (OpenClaw SSE streaming)                    │
│       ├── model_router.py     (model selection + fallback)                │
│       └── logger.py           (rotating logs → ~/.temporary-aegis/logs/)  │
└───────────────────────────────┬────────────────────────────────────────────┘
                                │
          ┌─────────────────────┼────────────────────────┐
          ▼                     ▼                        ▼
┌──────────────────┐  ┌──────────────────┐   ┌───────────────────────────────┐
│  9Router (:20128)│  │  OpenClaw (SSE)  │   │  DeepSeek-V3 (local API)      │
│  Gemini gateway  │  │  Claude-native   │   │  MoE reasoning                │
│  Model matrix:   │  │  OpenClaw harness│   │  deepseek_harness.py          │
│  • gemini-3.8-f  │  │  ~/.openclaw/    │   └───────────────────────────────┘
│  • gemini-3.7-f  │  │  workspace/      │
│  • gemini-3.6-f  │  └──────────────────┘
│  • gemini-3.5-l  │
└──────────────────┘
          │
          ├── OpenCode PTY  (~/.opencode/bin/opencode)
          ├── Hermes PTY    (~/.hermes/profiles/agies/)
          ├── Codex PTY     (openai-codex via PATH)
          └── Bash PTY      (/usr/bin/bash --login)
```

---

## 2. Connection Map — All Wired Links

### Frontend → Backend API Calls

| Frontend Component | API Endpoint | Method | Purpose |
|---|---|---|---|
| `ChatPanel.tsx` | `/api/chat` | POST | Main AI chat (streams SSE) |
| `ChatPanel.tsx` | `/api/memory/search` | GET | TF-IDF vault search |
| `AgentTabs.tsx` | `/api/agent/pty/start` | POST | Start PTY session |
| `AgentTabs.tsx` | `/api/agent/pty/input` | POST | Send input to agent |
| `AgentTabs.tsx` | `/api/agent/pty/output` | GET (SSE) | Stream agent output |
| `ObsidianGraph.tsx` | `/api/knowledge-graph` | GET | 58-node dynamic graph |
| `VaultExplorer.tsx` | `/api/vault` | GET | Vault file tree |
| `VaultExplorer.tsx` | `/api/files/read` | GET | Read vault note |
| `ModelsPanel.tsx` | `/api/models` | GET | 9Router model list |
| `PCMonitor.tsx` | `/api/diagnostics/deep` | GET | System health |
| `SkillsPanel.tsx` | `/api/skills` | GET | Skill registry |
| `ToolsPanel.tsx` | `/api/tools` | GET | Tool registry |
| `GlobalSearchModal.tsx` | `/api/search/unified` | GET | Cross-system search |
| `TopBar.tsx` | `/api/health` | GET | Quick health ping |
| `QuickActions.tsx` | `/api/run-script` | POST | Execute system script |
| `QuickActions.tsx` | `/api/browser/extract` | POST | Browse URL |
| `QuickActions.tsx` | `/api/browser/screenshot` | POST | Capture webpage |

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
