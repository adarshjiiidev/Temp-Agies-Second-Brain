# CONTEXT ARCHITECTURE — TEMPORARY AEGIS

> **Design Principle:** Context is not a prompt. Context is a living, layered state that flows from the global to the live situation.

---

## 1. The Five-Layer Context Model

```
GLOBAL ──────────────────────────────────── Who you are, what machine you run on, what tools exist
  └── DOMAIN ─────────────────────────────── Which area of life/work is active
        └── PROJECT ──────────────────────── Which specific codebase/effort is in focus
              └── TASK ─────────────────────── What goal is being pursued RIGHT NOW
                    └── LIVE SITUATION ──────── What just happened in the last 60 seconds
```

Each layer is a distinct context scope. Each has its own persistence strategy and TTL.

---

## 2. Layer Details

### Layer 1 — GLOBAL Context
**What it represents:** The invariant identity of the system and its operator.

| Field | Value | Source |
|---|---|---|
| User | `adarshjii` | `cfg.USER` (runtime, not hardcoded) |
| Machine | Arch Linux, 6.6.137-1-lts | `platform.uname()` |
| Home | `cfg.HOME` | `Path.home()` |
| Router | 9Router at `:20128` | `cfg.ROUTER_URL` |
| Backend | AEGIS API at `:8787` | `cfg.BACKEND_PORT` |
| Frontend | AEGIS Dashboard at `:2981` | `cfg.FRONTEND_PORT` |
| Model Matrix | gemini-3.8-flash / gemini-3.7-flash / gemini-3.6-flash / gemini-3.5-lite | `cfg.MODEL_*` |
| Vault | `~/ObsidianVault` | `cfg.VAULT` |
| State Dir | `~/.temporary-aegis/` | `cfg.AEGIS_DIR` |

**Persistence:** Permanent. Set at system init. Loaded from `backend/config.py` singleton (`cfg`).

---

### Layer 2 — DOMAIN Context
**What it represents:** The broad category of work. Derived from active projects and vault structure.

Active domains in AEGIS:
- `AI_SYSTEMS` — Rust/Python Aegis core, model routing, agent fabric
- `WEB_DEV` — aegis-dashboard, repusense, world-viewer, chrome-extra
- `RESEARCH` — DeepSeek-V3 study, model eval, hermes-agent
- `PERSONAL_INTELLIGENCE` — memory, tasks, notes, obsidian vault

Domain is inferred from:
1. Which `~/Projects/` subdirectory is active (git status, recent commits)
2. The open agent (OpenClaw = AI work; OpenCode = coding; Hermes = orchestration)
3. The active vault notes pattern (via `memory_engine.py` TF-IDF scan)

**Persistence:** Session-scoped. Stored in `~/.temporary-aegis/current_domain.json`.

---

### Layer 3 — PROJECT Context
**What it represents:** A specific workspace or repository that is the current focus.

Registered projects (from `cfg.PROJECTS` — dynamic, registry-driven):
| Project | Path |
|---|---|
| `aegis-dashboard` | `~/aegis-dashboard` |
| `Aegis` | `~/Projects/Aegis` |
| `chrome-extra` | `~/Projects/chrome-extra` |
| `repusense` | `~/Projects/repusense` |
| `world-viewer` | `~/Projects/world-viewer` |
| `DeepSeek-V3` | `~/aegis-dashboard/repos/DeepSeek-V3` |
| `hermes-agent` | `~/.hermes/hermes-agent` |
| `openclaw` | `~/.openclaw/workspace` |
| `opencode` | `~/.opencode` |

Project context is held in:
- `backend/knowledge_graph.py` — 58 nodes including all 9 projects
- `~/ObsidianVault/memory/1-Projects/<name>/` — living project memory
- `backend/memory_engine.py` — TF-IDF index over vault notes

**Persistence:** Persisted in Obsidian vault (PARA structure). Refreshed on each `CONSOLIDATE` run (every 15 min via systemd timer `aegis-consolidate`).

---

### Layer 4 — TASK Context
**What it represents:** The immediate goal being worked on.

Task context is tracked via:
- **Task Planner** (`backend/task_planner.py`) — goal decomposition using `cfg.MODEL_REASONING`
- **Experience Journal** (`~/.temporary-aegis/experiences.json`) — past task outcomes, decisions, failures
- **Proactive Monitor** (`backend/proactive_monitor.py`) — detects task drift, stale branches, uncommitted work

Task state fields:
```json
{
  "task_id": "uuid",
  "goal": "string",
  "steps": ["step1", "step2", "..."],
  "status": "planning | executing | blocked | done",
  "model_used": "gemini/gemini-3.7-flash",
  "started_at": "iso8601",
  "updated_at": "iso8601"
}
```

**Persistence:** Transient (in-memory during session). Written to experiences.json on completion.

---

### Layer 5 — LIVE SITUATION Context (60-second window)
**What it represents:** The real-time sensory state of the system.

Sources:
- `backend/vision_engine.py` — Wayland screen capture (`grim`) + OCR (`tesseract`)
- `backend/vision_engine.py` — Camera frame (gated by hard killswitch — default HARD_DENY)
- `backend/computer_control.py` — Clipboard contents (`wl-paste`)
- `backend/proactive_monitor.py` — Last git diffs, test results, service health
- `backend/screen_intel.py` — Active window title, desktop context

Live situation is consumed in real-time by the chat panel and does NOT persist beyond the session. It is injected into the system prompt dynamically when the user sends a message.

---

## 3. Context Flow in AEGIS

```
[User sends message]
      │
      ▼
[ChatPanel.tsx] ── collects UI state ──────────────────────────────────►
[backend/server.py /api/chat] ◄─── injects all 5 context layers into LLM call
      │
      ├─ GLOBAL:  cfg.*  (model, router, vault)
      ├─ DOMAIN:  current_domain.json
      ├─ PROJECT: knowledge_graph nodes + vault memory notes
      ├─ TASK:    task_planner state + experiences.json
      └─ LIVE:    screen OCR + clipboard + git status (if proactive monitor enabled)
      │
      ▼
[9Router at :20128] ── routes to best model (gemini-3.8/3.7/3.6/lite)
      │
      ▼
[LLM response with full context awareness]
```

---

## 4. Context Persistence Map

| Layer | TTL | Storage | Refreshed By |
|---|---|---|---|
| GLOBAL | Permanent | `backend/config.py` | System start |
| DOMAIN | Session | `~/.temporary-aegis/current_domain.json` | Manual / proactive monitor |
| PROJECT | 15 min | `ObsidianVault/memory/1-Projects/` | `aegis-consolidate` systemd timer |
| TASK | Task lifetime | `~/.temporary-aegis/experiences.json` | On task completion |
| LIVE | 60 seconds | In-memory only | `vision_engine` + `proactive_monitor` |

---

## 5. Design Decisions

- **No global mutable state in Python** — all context is either file-backed or per-request.
- **Context is structured, not prompt-stuffed** — each layer has a defined schema.
- **Privacy by default** — camera and screen capture are gated; live context is transient.
- **GLOBAL context is from runtime** — `cfg` computes everything from `Path.home()`, never hardcoded strings.
