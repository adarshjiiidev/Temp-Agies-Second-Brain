# TEMPORARY AEGIS — AI OS Dashboard & Second Brain

**Personal AI Operating System Dashboard** — a Vite + React 19 + TypeScript + Tailwind SPA that serves as the control plane for a complete local-first AI system.

**Live:** `http://localhost:2981` | **API:** `http://127.0.0.1:2981/api` | **AI Fabric:** Multi-Provider Free (OpenRouter + Groq)

---

## What It Is

A grayscale, sparse-signal AI OS dashboard that gives you:

- **Chat panel** — talk to Agies (the Hermes "agies" profile) directly in the dashboard
- **Vault explorer** — browse your entire Obsidian vault with tree and living constellation graph views
- **Knowledge graph** — visual graph connecting projects, agents, tools, models, and decisions
- **Skills panel** — 27 cataloged skills across OpenClaw and Hermes
- **Models panel** — multi-provider free model fabric with auto round-robin and verified fallback chain
- **Agent tabs** — 6 togglable PTY terminals (Hermes, Claude Code, Codex, DeepSeek R1, OpenClaw, Bash)
- **PC monitor** — live system stats
- **Activity feed** — system events log
- **Quick actions** — run systemd scripts (snapshot, consolidate, ingest, learn)
- **Global search** — unified search across graph + vault

---

## Architecture

```
Dashboard (Vite SPA, port 2981)
    │
    ▼
FastAPI Backend (port 8787)
    │
    ├── /api/health          → systemd service health
    ├── /api/health/full     → 17 components with status
    ├── /api/vault           → Obsidian vault tree
    ├── /api/files/tree      → vault file tree
    ├── /api/memory/search   → TF-IDF ranked memory retrieval
    ├── /api/memory/temporal → daily activity reconstruction
    ├── /api/graph           → knowledge graph
    ├── /api/skills          → cataloged skills
    ├── /api/models          → free model router & health

    ├── /api/agents          → agent registry + PTY endpoints
    ├── /api/agents/:id/pty  → WebSocket PTY for agent tabs
    ├── /api/run-script      → systemd script execution (token-gated)
    ├── /api/browser/extract → headless Chrome DOM + text extraction
    ├── /api/browser/screenshot → webpage screenshots
    ├── /api/search/unified  → graph + vault unified search
    └── /api/diagnostics/deep → full system diagnostics
```

---

## Backend Modules (27 files, 0 hardcoded paths)

All paths resolved through `backend/config.py` `AegisConfig` — no `/home/adarshjii` anywhere.

| Module | Purpose |
|--------|---------|
| `server.py` | FastAPI app, all endpoints, vault serving, WebSocket PTY, script execution |
| `config.py` | Central config — paths, ports, model IDs, project scan, agent registry resolution |
| `security.py` | Token auth (256-bit hex), path traversal guard, script/agent allowlists |
| `logger.py` | Rotating file logging (5MB × 3) + stderr |
| `agent_pty.py` | PTY session manager for agent tabs |
| `agent_runner.py` | Agent command resolution via registry |
| `agent_moe.py` | AgentMoe fabric — 8 worker roles, 9 tools, capability discovery |
| `model_router.py` | 4-tier model router with fallback chain, critic verification |
| `knowledge_graph.py` | Dynamic 58-node graph from registries + decisions |
| `memory_engine.py` | TF-IDF ranked search, temporal activity, causal decisions, experience learning, poisoning defense |
| `vision_engine.py` | Screen capture (grim), OCR (tesseract), multimodal (gemini-3.8-flash), camera killswitch |
| `computer_control.py` | wtype keyboard, wl-copy/wl-paste clipboard, app launch |
| `browser_tool.py` | Headless Chrome DOM extraction, text extraction, screenshots |
| `audio_engine.py` | Audio subsystem |
| `screen_intel.py` | Screen intelligence |
| `proactive_monitor.py` | Proactive system monitoring |
| `aegis_health.py` | Health diagnostics |
| `task_planner.py` | Task planning |
| `research_engine.py` | Research engine |
| `code_sandbox.py` | Code sandbox |
| `openclaw_harness.py` | OpenClaw integration harness |
| `deepseek_harness.py` | DeepSeek R1 harness |

---

## 9Router Model Router

4 verified models with automatic fallback:

| Tier | Model | Role |
|------|-------|------|
| Default | `gemini/gemini-3.8-flash` | Frontier multimodal vision |
| Reasoning | `gemini/gemini-3.7-flash` | Deep reasoning, math, architecture |
| Fast | `gemini/gemini-3.6-flash` | Coding, chat, low-latency agent |
| Lite | `gemini/gemini-3.5-flash-lite` | Bulk summarization, extraction |

Fallback chain: `3.8-flash → 3.7-flash → 3.6-flash → 3.5-flash-lite`

---

## Agent Tabs (6 PTY terminals)

| Tab | Agent | Harness |
|-----|-------|---------|
| Hermes | Agies (Hermes 3 profile) | Hermes CLI |
| Claude | Claude Code | claude CLI |
| Codex | OpenAI Codex | codex CLI |
| DeepSeek | DeepSeek R1 | DeepSeek CLI |
| OpenClaw | OpenClaw Gateway | OpenClaw |
| Bash | Host shell | /usr/bin/bash |

---

## Vision Subsystem

- **Screen capture:** `grim` on Wayland — captures current desktop
- **OCR:** `tesseract` with `--oem 1 -l eng` — deterministic text extraction
- **Multimodal:** `gemini/gemini-3.8-flash` via 9Router — image analysis
- **Camera:** `/dev/video0` via `ffmpeg` — hard killswitch (OFF = HARD DENY, no permanent storage)

---

## Computer Control

- **Keyboard:** `wtype` — keystroke injection into focused window
- **Clipboard:** `wl-copy` / `wl-paste` — read/write system clipboard
- **App launch:** `subprocess.Popen` with risk-level gating (high/critical requires manual confirmation)

---

## Browser Subsystem

Uses system `google-chrome-stable --headless=new`:

- **DOM extraction:** `--dump-dom` → raw HTML
- **Text extraction:** HTML → clean markdown via regex parsing
- **Screenshots:** `--screenshot=path` → PNG capture

---

## Memory & Knowledge

### Cross-Agent Consolidation (`aegis_consolidate.py`)
Scans 6 sources and writes to `~/ObsidianVault/agies/`:

| Source | Files |
|--------|-------|
| Antigravity brains (3) | Transcripts, tasks, messages, walkthroughs |
| Antigravity IDE logs | IDE logs, crash logs, editor logs |
| Codex sessions | history.jsonl, session_index, goals DB, sessions/ |
| Hermes profiles | agies profile, cache, config |
| Obsidian vault | Existing vault notes |
| .temporary-aegis | Memory scaffold, scripts, config |

Output: **2,197+ .md files** organized in 4 dimensions:
- `by-agent/` — per-brain session notes, transcripts, decisions, files-built, tasks
- `by-date/` — chronological consolidation
- `by-topic/` — topic-indexed
- `raw/` — original file copies

### Full Project Ingestion (`aegis_ingest_all.py`)
Reads all 12 project repos from `~/Projects/` and produces `ALL_PROJECTS_INGESTION.md` (1.08M chars) in Hermes agies profile memories.

Each project ingested with:
- Full README
- Key config files (package.json, Cargo.toml, pyproject.toml, etc.)
- 8-20 source file samples
- Directory structure
- Git info (remotes, branches, last commit)
- Vault project notes

### Systemd Timers
| Timer | Schedule |
|-------|----------|
| `aegis-consolidate.timer` | Every 15 min + 30 sec after boot |
| `aegis-consolidate-daily.timer` | Daily at 3PM + 30 sec after boot + catch-up |
| `aegis-ingest.timer` | Daily at 4AM + 5 min after boot |
| `aegis-snapshot.timer` | Daily PC state snapshot |
| `aegis-ingest-chatgpt.timer` | Daily ChatGPT export ingest |
| `aegis-learn.timer` | Weekly pattern learning |

---

## Security

- **CORS:** Locked to localhost origins only (no wildcard)
- **Binding:** Uvicorn on `127.0.0.1` (not `0.0.0.0`)
- **Auth:** 256-bit hex API token (`X-AEGIS-Token` header) on all mutating endpoints
- **Path guard:** `safe_path()` enforces filesystem reads stay within home directory
- **Allowlists:** Scripts and agent IDs validated against allowlists
- **Token storage:** `chmod 600` on `~/.temporary-aegis/config/aegis_api_token`

---

## Systemd Services

| Service | Port | Status |
|---------|------|--------|
| `aegis-backend.service` | 8787 | ✅ active |
| `aegis-frontend.service` | 2981 | ✅ active |
| `9router.service` | 20128 | ✅ active |
| `aegis-snapshot.service` | — | ✅ active (timer) |
| `aegis-ingest-chatgpt.service` | — | ✅ active (timer) |
| `aegis-consolidate.service` | — | ✅ active (timer) |

All enabled for auto-start at boot.

---

## Projects Covered (12)

| # | Project | Stack | Files |
|---|---------|-------|-------|
| 1 | Aegis | Rust + Python AI OS | 357 |
| 2 | world-viewer | Electron + Cesium 3D | 3,869 |
| 3 | Kagazi | Next.js trading platform | 123 |
| 4 | nexo.ai | Autonomous AI agent (Groq) | 40 |
| 5 | TN-Commerce | Next.js e-commerce | 160 |
| 6 | assistant | Groq AI proxy | 26 |
| 7 | billing-dis | Electron + Next.js | 33 |
| 8 | jailbreak-autoresearch | OpenRouter research | 30 |
| 9 | Flicker | Next.js + MongoDB | 139 |
| 10 | pybackend | Daaddys AI swarm (13 agents) | 140 |
| 11 | repusense | GitHub intelligence | 11 |
| 12 | chrome-extra | Chrome extension | 6 |

---

## Knowledge Graph (58 nodes)

- 17 projects (scanned from `~/Projects/` + dashboard + agent dirs)
- 8 agents (from `AGENT_REGISTRY.json`)
- 10 tools (from `TOOL_REGISTRY.json`)
- 20 models (from `MODEL_REGISTRY.json`)
- 3 decisions (from `DECISIONS.md`)

---

## Skills (27 cataloged)

From `~/.openclaw/plugin-skills/` and `~/.hermes/profiles/agies/skills/`:

OpenClaw plugins: 1password, blogwatcher, blucli, camsnap, coding-agent, eightctl, gifgrep, gog, goplaces, himalaya, mcporter, model-usage, nano-pdf, openai-whisper, openai-whisper-api, openhue, oracle, ordercli, sag, sherpa-onnx-tts, songsee, sonoscli, spotify-player, summarize, trello, xurl

Hermes agies skills: 18 skills in the agies profile

---

## Test Suite

`tests/test_end_to_end_missions.py` — 5 multimodal missions:

- **Mission A:** Complex Goal Planning & Experience Learning → PASS
- **Mission B:** Screen Understanding & Visual Grounding → PASS
- **Mission C:** Camera Subsystem & Privacy Filtering → PASS
- **Mission D:** Autonomous Research & Knowledge Synthesis → PASS
- **Mission E:** Context Reconstruction → PASS

**5/5 PASS (100% SUCCESS)**

---

## Stack

- **Frontend:** Vite + React 19 + TypeScript + Tailwind CSS 4
- **Backend:** FastAPI + Uvicorn
- **Model Gateway:** 9Router (OpenAI-compatible, 870 models)
- **AI Profiles:** Hermes agies (solar-pro4:free via Nous)
- **OS:** Arch Linux + Wayland + Hyprland + Omarchy

---

## Quick Start

```bash
# Start all services
cd /home/adarshjii/aegis-dashboard
bash start.sh

# Or individually:
systemctl --user start aegis-backend
systemctl --user start aegis-frontend
systemctl --user start 9router

# Dashboard: http://localhost:2981
# API docs:   http://127.0.0.1:8787/docs
```

---

## Repo Structure

```
aegis-dashboard/
├── src/
│   ├── App.tsx
│   ├── main.tsx
│   ├── styles/globals.css
│   ├── components/
│   │   ├── AgentTab.tsx        # xterm.js PTY terminal
│   │   ├── AgentTabs.tsx       # 6-agent multiplexer
│   │   ├── ChatPanel.tsx       # Agies chat interface
│   │   ├── ModelsPanel.tsx     # model router display
│   │   ├── VaultExplorer.tsx   # Obsidian vault tree
│   │   ├── ObsidianGraph.tsx   # knowledge graph viz
│   │   ├── SkillsPanel.tsx     # 27 skills catalog
│   │   ├── ToolsPanel.tsx      # tool inventory
│   │   ├── Desktop.tsx         # main desktop layout
│   │   ├── Dock.tsx            # panel launcher dock
│   │   ├── PCMonitor.tsx       # live system stats
│   │   ├── ActivityFeed.tsx    # event log
│   │   ├── GlobalSearchModal.tsx
│   │   ├── QuickActions.tsx    # script execution buttons
│   │   ├── CodexModal.tsx
│   │   ├── NoteViewer.tsx
│   │   └── TopBar.tsx
│   └── lib/
│       ├── api.ts     # API client (8787)
│       └── store.tsx  # OS state management
├── backend/
│   ├── server.py         # FastAPI — all endpoints
│   ├── config.py         # Central config (no hardcoded paths)
│   ├── security.py       # Token auth + path guard + allowlists
│   ├── logger.py         # Rotating file logging
│   ├── agent_pty.py      # PTY session manager
│   ├── agent_runner.py   # Agent command resolution
│   ├── agent_moe.py      # AgentMoe fabric
│   ├── model_router.py   # 4-tier model router
│   ├── knowledge_graph.py # 58-node dynamic graph
│   ├── memory_engine.py  # TF-IDF ranked memory
│   ├── vision_engine.py  # Screen/OCR/camera/multimodal
│   ├── computer_control.py # wtype + clipboard
│   ├── browser_tool.py   # Headless Chrome
│   ├── audio_engine.py
│   ├── screen_intel.py
│   ├── proactive_monitor.py
│   ├── aegis_health.py
│   ├── task_planner.py
│   ├── research_engine.py
│   ├── code_sandbox.py
│   ├── openclaw_harness.py
│   └── deepseek_harness.py
├── docs/                 # 20+ architecture docs
├── registries/
│   ├── AGENT_REGISTRY.json
│   ├── MODEL_REGISTRY.json
│   ├── SKILL_REGISTRY.json
│   └── TOOL_REGISTRY.json
├── tests/
│   └── test_end_to_end_missions.py
├── start.sh              # Boot script
├── vite.config.ts        # Port 2981
└── package.json
```

---

## Remote

`git@github.com:adarshjiiidev/Temp-Agies-Second-Brain.git`

This repo is pushed to the `Temp-Agies-Second-Brain` remote as the `master` branch.
