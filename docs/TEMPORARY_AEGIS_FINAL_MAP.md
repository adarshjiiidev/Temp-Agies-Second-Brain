# TEMPORARY AEGIS — FINAL SYSTEM MAP

> One document. Everything. Where it lives, what it does, how it connects.

---

## 1. Identity

| Field | Value |
|---|---|
| **System Name** | Temporary AEGIS |
| **Build Status** | Complete, Operational, Hardened |
| **Host** | Arch Linux 6.6.137-1-lts |
| **Operator** | `adarshjii` (resolved at runtime via `cfg.USER`) |
| **Architecture Style** | Personal AI OS — Context/Connection/Capability/Cadence |

---

## 2. Live Service Map

| Service | Port | Unit | Status |
|---|---|---|---|
| AEGIS Dashboard (Next.js) | :2981 | `aegis-frontend.service` | ✅ Active |
| AEGIS Backend (FastAPI) | :8787 | `aegis-backend.service` | ✅ Active |
| 9Router (Gemini gateway) | :20128 | external | ✅ Active |
| Consolidation timer | — | `aegis-consolidate.timer` | ✅ Active (15 min) |
| Snapshot timer | — | `aegis-snapshot.timer` | ✅ Active (daily) |
| ChatGPT ingest timer | — | `aegis-ingest-chatgpt.timer` | ✅ Active (on-demand) |

---

## 3. Directory Map

```
~/ (cfg.HOME)
├── aegis-dashboard/                  ← This repository (dashboard + backend)
│   ├── src/components/               ← UI components (18 files)
│   ├── backend/                      ← Python API (22 modules)
│   ├── registries/                   ← AGENT, TOOL, MODEL, SKILL registries
│   ├── docs/                         ← All architecture documentation (this file)
│   └── tests/                        ← End-to-end mission tests
│
├── ObsidianVault/                    ← Living knowledge base (cfg.VAULT)
│   ├── memory/
│   │   ├── 0-Inbox/                  ← Unprocessed captures
│   │   ├── 1-Projects/               ← Living project memories (9 projects)
│   │   ├── 2-Areas/                  ← Domain-level knowledge
│   │   ├── 3-Resources/              ← Reference material
│   │   └── 4-Archive/                ← Completed work
│   ├── agies/                        ← Hermes/Agies workspace notes
│   └── (root notes — excluded from graph canvas)
│
├── .temporary-aegis/                 ← AEGIS state dir (cfg.AEGIS_DIR)
│   ├── config/
│   │   └── aegis_api_token           ← 256-bit auth token (chmod 600)
│   ├── logs/
│   │   └── aegis.log                 ← Rotating backend log (5MB × 3)
│   ├── scripts/                      ← Systemd timer scripts
│   ├── pc-state/                     ← Daily system snapshots
│   ├── experiences.json              ← Task outcomes + decisions journal
│   └── SKILL_REGISTRY.json           ← 27 discovered skills
│
├── Projects/                         ← Main workspace
│   ├── Aegis/                        ← Rust/Python adaptive AI OS
│   ├── chrome-extra/                 ← Browser extension agent
│   ├── repusense/                    ← Next.js repo intelligence
│   └── world-viewer/                 ← Electron 3D spatial globe
│
├── .hermes/
│   ├── profiles/agies/               ← Hermes brain (Agies profile)
│   │   ├── memories/                 ← Hermes persistent memory
│   │   └── skills/                   ← Hermes skills
│   └── hermes-agent/                 ← Multi-agent evaluation gateway
│
├── .openclaw/workspace/              ← Claude-native workspace
├── .opencode/                        ← OpenCode ACP/MCP runtime
│   └── bin/opencode                  ← 184MB binary
│
└── aegis-dashboard/repos/
    └── DeepSeek-V3/                  ← MoE inference codebase (study)
```

---

## 4. Backend Module Map

| Module | File | Role |
|---|---|---|
| **Central Config** | `backend/config.py` | Single source of truth for all paths, ports, models |
| **API Server** | `backend/server.py` | FastAPI with CORS, auth, all endpoints (55KB) |
| **Security** | `backend/security.py` | X-AEGIS-Token, safe_path(), input validation |
| **Logger** | `backend/logger.py` | Rotating log to `~/.temporary-aegis/logs/aegis.log` |
| **Knowledge Graph** | `backend/knowledge_graph.py` | 58-node dynamic graph from registries |
| **Memory Engine** | `backend/memory_engine.py` | TF-IDF vault search, temporal memory |
| **Agent MoE** | `backend/agent_moe.py` | Tool dispatch, worker roles, capability discovery |
| **Agent PTY** | `backend/agent_pty.py` | PTY multiplexer for all interactive agents |
| **Agent Runner** | `backend/agent_runner.py` | Non-interactive agent dispatch |
| **Task Planner** | `backend/task_planner.py` | Goal decomposition (uses MODEL_REASONING) |
| **Proactive Monitor** | `backend/proactive_monitor.py` | Git drift, service health, disk checks |
| **Research Engine** | `backend/research_engine.py` | Web research + synthesis |
| **Vision Engine** | `backend/vision_engine.py` | Screen OCR (grim+tesseract), camera (gated) |
| **Computer Control** | `backend/computer_control.py` | wtype, wl-copy/paste, system actions |
| **Browser Tool** | `backend/browser_tool.py` | Headless Chrome DOM extract + screenshot |
| **Screen Intel** | `backend/screen_intel.py` | Active window, desktop context |
| **Model Router** | `backend/model_router.py` | 9Router client + model selection |
| **AEGIS Health** | `backend/aegis_health.py` | Deep diagnostics, service status |
| **Code Sandbox** | `backend/code_sandbox.py` | Safe Python execution (allowlist-restricted) |
| **Audio Engine** | `backend/audio_engine.py` | TTS/STT interface (stubs + real backends) |
| **OpenClaw Harness** | `backend/openclaw_harness.py` | Claude via OpenClaw SSE stream |
| **DeepSeek Harness** | `backend/deepseek_harness.py` | DeepSeek-V3 reasoning + thinking tokens |

---

## 5. Frontend Component Map

| Component | File | Role |
|---|---|---|
| **Chat Panel** | `ChatPanel.tsx` | Main AI conversation + streaming (19KB) |
| **Agent Tabs** | `AgentTabs.tsx` | Multi-agent PTY switcher |
| **Agent Tab** | `AgentTab.tsx` | Single agent PTY terminal |
| **Obsidian Graph** | `ObsidianGraph.tsx` | Knowledge graph visualization (16KB) |
| **Vault Explorer** | `VaultExplorer.tsx` | Vault file browser + note viewer |
| **Models Panel** | `ModelsPanel.tsx` | 9Router model matrix + health |
| **PC Monitor** | `PCMonitor.tsx` | System diagnostics + proactive checks |
| **Skills Panel** | `SkillsPanel.tsx` | Skill registry browser |
| **Tools Panel** | `ToolsPanel.tsx` | Tool registry browser |
| **Note Viewer** | `NoteViewer.tsx` | Markdown rendering for vault notes |
| **Global Search** | `GlobalSearchModal.tsx` | Unified cross-system search |
| **Quick Actions** | `QuickActions.tsx` | Browser, scripts, one-click tools |
| **Codex Modal** | `CodexModal.tsx` | Codex direct interaction panel |
| **Desktop** | `Desktop.tsx` | OS-like desktop shell |
| **Dock** | `Dock.tsx` | Panel navigation dock |
| **Top Bar** | `TopBar.tsx` | Status bar + quick health |
| **Panel** | `Panel.tsx` | Resizable panel container |
| **Activity Feed** | `ActivityFeed.tsx` | Live system event stream |

---

## 6. Registry Map

| Registry | File | Contents |
|---|---|---|
| Agent Registry | `registries/AGENT_REGISTRY.json` | Agent IDs, CLI paths, capabilities |
| Tool Registry | `registries/TOOL_REGISTRY.json` | Tool IDs, implementations, constraints |
| Model Registry | `registries/MODEL_REGISTRY.json` | Model IDs, providers, capabilities |
| Skill Registry | `~/.temporary-aegis/SKILL_REGISTRY.json` | 27 skills with tool requirements |

---

## 7. API Endpoint Map (Key Endpoints)

| Endpoint | Method | Auth Required | Purpose |
|---|---|---|---|
| `/api/health` | GET | No | Quick health ping |
| `/api/chat` | POST | Yes | Main AI chat (SSE stream) |
| `/api/memory/search` | GET | No | TF-IDF vault search |
| `/api/memory/temporal` | GET | No | Time-based memory query |
| `/api/knowledge-graph` | GET | No | 58-node graph data |
| `/api/search/unified` | GET | No | Cross-system search |
| `/api/models` | GET | No | 9Router model list |
| `/api/vault` | GET | No | Vault file tree |
| `/api/files/read` | GET | No | Read vault note |
| `/api/agent/pty/start` | POST | Yes | Start PTY session |
| `/api/agent/pty/input` | POST | Yes | Send to agent |
| `/api/agent/pty/output` | GET | No | Stream agent output |
| `/api/diagnostics/deep` | GET | No | Full system diagnostics |
| `/api/skills` | GET | No | Skill registry |
| `/api/tools` | GET | No | Tool registry |
| `/api/run-script` | POST | Yes | Execute system script |
| `/api/browser/extract` | POST | Yes | Headless browse + DOM |
| `/api/browser/screenshot` | POST | Yes | Webpage screenshot |
| `/api/vision/screen` | GET | Yes | Screen OCR |
| `/api/control/clipboard` | POST | Yes | Clipboard read/write |

Auth: `X-AEGIS-Token: <token>` header. Token in `~/.temporary-aegis/config/aegis_api_token` (chmod 600).

---

## 8. Security Map

| Threat | Mitigation | Status |
|---|---|---|
| Unauthorized API mutation | X-AEGIS-Token on all POST/PUT/DELETE | ✅ Active |
| CORS exploitation | Explicit localhost-only origins | ✅ Active |
| Network exposure | Backend bound to 127.0.0.1 only | ✅ Active |
| Path traversal | `safe_path()` — must start with `cfg.HOME` | ✅ Active |
| Command injection | Subprocess allowlist + shell=False where possible | ✅ Active |
| Camera surveillance | HARD_DENY default; no persistent video | ✅ Active |
| Token leakage | Token at chmod 600; never logged | ✅ Active |

---

## 9. Architecture Principle Summary

| Principle | How It's Applied |
|---|---|
| **One config to rule all** | `cfg = AegisConfig()` singleton, computed from `Path.home()` |
| **Registry-driven** | Agents, tools, models, skills all come from JSON registries |
| **No orphan islands** | Every component wired to `cfg`, `logger`, and appropriate APIs |
| **Context is layered** | GLOBAL → DOMAIN → PROJECT → TASK → LIVE |
| **Cadence is autonomous** | systemd timers run independent of user interaction |
| **Security is default** | No wildcard CORS, no `0.0.0.0`, no plaintext tokens |
| **Privacy is hard-coded** | Camera: HARD_DENY. Screen: ephemeral only. |
| **Capabilities grow via registry** | New tools → add to registry → graph auto-discovers |
