# repusense

**AEGIS Dashboard — AI OS control plane & second brain.**

Vite + React 19 + TypeScript + Tailwind CSS 4 frontend (port 2981) + FastAPI backend (port 8787) + 9Router model gateway (port 20128). A grayscale, sparse-signal AI OS dashboard that gives you chat with Agies, vault explorer, knowledge graph, agent PTY tabs, PC monitor, and system automation — all locally.

**Live:** `http://localhost:2981` | **API:** `http://127.0.0.1:8787` | **9Router:** `http://127.0.0.1:20128`

---

## What It Is

The AEGIS Dashboard is the web control plane for a complete local-first AI system. It's the front-end for the AEGIS personal AI operating system — giving you a unified interface to chat with your AI agent, browse your Obsidian vault, visualize your knowledge graph, manage AI models, run agent terminals, monitor your PC, and execute system automation scripts.

The `app/` directory contains an older Next.js scaffold that is NOT used — the actual frontend is a Vite + React SPA in `src/`.

---

## Dashboard UI

The dashboard gives you:

- **Chat panel** — talk to Agies (the Hermes "agies" profile) directly in the dashboard
- **Vault explorer** — browse your entire Obsidian vault with a tree view
- **Knowledge graph** — visual graph of 58 nodes connecting projects, agents, tools, models, and decisions
- **Skills panel** — 27 cataloged skills across OpenClaw and Hermes
- **Models panel** — 4-tier model router with verified fallback chain
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
    ├── /api/graph           → 58-node knowledge graph
    ├── /api/skills          → 27 cataloged skills
    ├── /api/models          → model router + 9Router proxy
    ├── /api/agents          → agent registry + PTY endpoints
    ├── /api/agents/:id/pty  → WebSocket PTY for agent tabs
    ├── /api/run-script      → systemd script execution (token-gated)
    ├── /api/browser/extract → headless Chrome DOM + text extraction
    ├── /api/browser/screenshot → webpage screenshots
    ├── /api/search/unified  → graph + vault unified search
    └── /api/diagnostics/deep → full system diagnostics
```

The backend also proxies the 9Router model router (`~/.9router/router.py` on port 20128) for model selection and inference across OpenAI, Anthropic, DeepSeek, Ollama, and other providers.

---

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Frontend | Vite + React + TypeScript | 19.x |
| Styling | Tailwind CSS | 4.x |
| Backend | FastAPI + Uvicorn | Python 3.11+ |
| WebSocket | FastAPI WebSockets | — |
| Browser | Playwright (headless) | — |
| Model Routing | 9Router | latest |
| Database | Obsidian vault (Markdown) | — |
| Auth | API token (header-based) | — |

---

## Backend Modules (27)

The backend at `backend/` provides a complete AI OS substrate:

### Agent System
- `agent_runner.py` — agent lifecycle, config, task dispatch
- `agent_moe.py` — mixture-of-experts agent orchestration
- `agent_pty.py` — PTY terminal management for agent tabs
- `task_planner.py` — task decomposition and planning

### Model Routing
- `model_router.py` — 4-tier model selection (S/A/B/C) with fallback
- `deepseek_harness.py` — DeepSeek API integration
- `openclaw_harness.py` — OpenClaw API integration

### Memory & Knowledge
- `memory_engine.py` — TF-IDF search, temporal reconstruction, memory CRUD
- `knowledge_graph.py` — graph extraction, traversal, DAG validation, sink detection

### Intelligence
- `research_engine.py` — web research pipeline (FactChecker, InsightFinder, ConnectDots)
- `screen_intel.py` — screen capture and visual analysis
- `vision_engine.py` — vision model integration for image understanding

### System Control
- `browser_tool.py` — headless Chrome DOM extraction and screenshots
- `computer_control.py` — system command execution and automation
- `code_sandbox.py` — isolated code execution sandboxes
- `audio_engine.py` — audio/TTS pipeline

### Infrastructure
- `server.py` — FastAPI application, 30+ endpoints, WebSocket support
- `config.py` — environment configuration, 9Router proxy settings
- `security.py` — token auth, path traversal protection, command allowlisting
- `logger.py` — structured logging
- `aegis_health.py` — systemd service health monitoring (17 components)

### Background Services
- `proactive_monitor.py` — monitoring and alerting loop

---

## Development

```bash
cd repusense

# Frontend
npm run dev       # Vite dev server on port 2981

# Backend
python -m uvicorn backend.server:app --reload --port 8787

# Both
npm run dev & python -m uvicorn backend.server:app --reload --port 8787
```

---

## Testing

```bash
cd repusense

# Run all tests
python -m pytest tests/ -v

# Quick smoke test
python tests/test_end_to_end_missions.py
```

**5/5 tests passing** as of last verification.

---

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
# API token for dashboard auth (generate a random string)
DASHBOARD_API_TOKEN=your-secret-token-here

# 9Router settings
NINE_ROUTER_PORT=20128
NINE_ROUTER_PATH=~/.9router/router.py

# CORS
CORS_ORIGINS=http://localhost:2981
```

---

## Keystone Integration

This dashboard integrates with Keystone (the local AI inference stack) when available:

- **Model fallback chain:** If a cloud provider is unavailable, models fall back through Keystone's local model pool
- **Local inference:** Ollama-hosted models can handle chat, classification, and small code tasks locally
- **Cost optimization:** Routine tasks route to local models; complex tasks escalate to cloud

---

## Current State

**Production active.** All 3 services running, 5/5 tests passing, 27 backend modules functional, 58-node knowledge graph, 27 cataloged skills, 4-tier model router with fallback, 6 agent PTY tabs, full vision/computer control/browser subsystems.

The `app/` directory contains leftover Next.js scaffold (unused — the real frontend is the Vite SPA in `src/`).
