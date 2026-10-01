# CADENCE ARCHITECTURE — TEMPORARY AEGIS

> **Design Principle:** AEGIS runs on rhythms — not only when you call it. Automation, consolidation, and proactive awareness happen on a cadence, independent of user interaction.

---

## 1. The Four Cadences

```
IMMEDIATE    — 0ms     — Direct user requests, live tool calls
REACTIVE     — <5s     — Proactive monitor responses, git event detection
CONSOLIDATION— 15 min  — Memory rebuild, project sync, vault update
SNAPSHOT     — Daily   — Full system state capture, experience archival
```

---

## 2. Systemd Timer Architecture

All background cadences are managed as `systemd --user` units. They run independently of the frontend or user interaction.

### Timer: `aegis-consolidate` (Every 15 Minutes & Daily 3PM)

**Unit files:**
- `~/.config/systemd/user/aegis-consolidate.timer` (15-minute rhythm)
- `~/.config/systemd/user/aegis-consolidate-daily.timer` (Daily 3:00 PM deep run)
- `~/.config/systemd/user/aegis-consolidate-shutdown.service` (Triggered on shutdown target)
**Service & Exec:** `~/.config/systemd/user/aegis-consolidate.service` running `aegis-dashboard/aegis_consolidate.py` via Python venv  

**What it does on each tick:**
1. Scans multi-agent sessions: Antigravity IDE (`~/.gemini/antigravity-ide/brain`, `~/.config/Antigravity IDE/logs`), Codex, Claude, Hermes (`~/.hermes/profiles/agies`), and Temporary AEGIS (`~/.temporary-aegis`).
2. Consolidates structured knowledge into `ObsidianVault/agies/` (topic notes, living project memory, decision logs).
3. Redacts sensitive tokens (`sk-*`, `ghp_*`) deterministically before writing notes.
4. Updates living memory notes per project in `ObsidianVault/memory/1-Projects/<name>/LIVING_MEMORY.md`.
5. Rebuilds TF-IDF index cache in `backend/memory_engine.py`.
6. Refreshes knowledge graph nodes from registries and writes consolidation log.

**Why 15 minutes:** Balances real-time cross-agent awareness with low CPU/disk footprint.

---

### Timer: `aegis-snapshot` (Daily)

**Unit file:** `~/.config/systemd/user/aegis-snapshot.timer`  
**Script:** `~/.temporary-aegis/scripts/aegis-snapshot.sh`

**What it does daily:**
1. Records full system state to `~/.temporary-aegis/pc-state/YYYY-MM-DD.md`
2. Captures: running services, installed packages, disk usage, model status, git branch states per project
3. Summarizes active tasks from `experiences.json`
4. Archives completed tasks older than 7 days

**Output format (each daily snapshot):**
```markdown
# AEGIS System Snapshot — 2026-09-13

## Services
- aegis-backend: active (running) since ...
- aegis-frontend: active (running) since ...
- 9router: active

## Projects
- aegis-dashboard: branch main, 3 uncommitted changes
- Aegis: branch feature/rust-core, clean
...

## Experience Journal
- Tasks completed this week: 12
- Decisions logged: 3
```

---

### Timer: `aegis-ingest-chatgpt` (On Demand / Daily)

**Unit file:** `~/.config/systemd/user/aegis-ingest-chatgpt.timer`  
**Script:** `~/.temporary-aegis/scripts/aegis-ingest-chatgpt.sh`

**What it does:**
- Scans `~/Downloads/` for ChatGPT export zip files
- If found: extracts and converts conversations to vault notes in `ObsidianVault/memory/imports/chatgpt/`
- If not found: exits cleanly with code 0 (no error; export is optional)

**Status:** Fixed (previously failed silently with non-zero exit when no export was present).

---

## 3. Service Cadence (Always-On)

| Service | Cadence | Port | Restart Policy |
|---|---|---|---|
| `aegis-backend` | Always-on | :8787 | `on-failure` |
| `aegis-frontend` | Always-on | :2981 | `on-failure` |

Both are `systemctl --user` units. They auto-restart on crash and are verified healthy via `/api/health`.

---

## 4. Proactive Monitor — Reactive Cadence

**File:** `backend/proactive_monitor.py`  
**Trigger:** Called by `/api/proactive/check` (frontend polls or on-demand)

The proactive monitor runs lightweight checks without blocking:

| Check | Method | Cadence |
|---|---|---|
| Git uncommitted changes | `git status --short` (timeout 10s) | On demand |
| Stale branch detection | `git log --since=7days --oneline` | On demand |
| Failed test detection | Scan for `pytest.log` or `test_results.json` | On demand |
| Service health | `systemctl --user is-active <service>` | On demand |
| Disk space warning | `df -h cfg.HOME` | On demand |
| Memory usage | `free -m` | On demand |

Results are surfaced in:
- `PCMonitor.tsx` component in the dashboard
- `GET /api/diagnostics/deep` response body

---

## 5. Memory Consolidation Cadence

Memory is rebuilt on two cadences:

### Vault Index (15-min, via `aegis-consolidate`)
- `memory_engine.py` maintains a TF-IDF index JSON at `~/.temporary-aegis/vault_index.json`
- On cache miss (index older than 30 min), it auto-rebuilds from all `.md` files in `cfg.VAULT`
- The 30-second in-memory cache (`_vault_cache`) reduces disk I/O between consolidation ticks

### Experience Journal (On task completion)
- `task_planner.py` appends to `~/.temporary-aegis/experiences.json` after each completed task
- Format: `{task_id, goal, steps, outcome, model_used, duration, timestamp}`
- The snapshot timer archives old entries daily

---

## 6. Context Refresh Cadence

| Context Layer | Auto-Refresh | How |
|---|---|---|
| GLOBAL | Never (stable) | `cfg` loaded at process start |
| DOMAIN | Session-change | `current_domain.json` written on agent switch |
| PROJECT | 15 min | `aegis-consolidate` timer |
| TASK | On task events | `task_planner.py` on start/complete/fail |
| LIVE | 60s TTL | `vision_engine` / `proactive_monitor` on each chat |

---

## 7. Knowledge Graph Refresh Cadence

| Trigger | Action |
|---|---|
| Cold start | Graph built from registries + project scan |
| `/api/knowledge-graph` GET request | Served from in-process cache |
| `aegis-consolidate` tick | Rebuilds node list from filesystem + registries |
| Registry file change | Next request auto-picks up new nodes |

The graph is never stale by more than 15 minutes in steady state.

---

## 8. Cadence Design Decisions

- **No polling from frontend** — The frontend never polls the backend on a timer. All background work happens in systemd timers. The frontend fetches on user action or explicit panel open.
- **Timeout-bounded** — All subprocess calls in proactive monitor, memory engine, and git operations use explicit `timeout=` values. No background job can block the API.
- **Exit 0 on no-op** — All timer scripts exit cleanly when nothing to do. `aegis-ingest-chatgpt.sh` and `aegis-snapshot.sh` are both fixed to not error when conditions aren't met.
- **Log everything** — All timer and service output goes to `~/.temporary-aegis/logs/` (rotating, 5MB × 3 files). Never to stdout-only.

---

## 9. Cadence Monitoring

You can inspect all cadences live:

```bash
# Check timer status
systemctl --user list-timers

# Check service status  
systemctl --user status aegis-backend aegis-frontend

# Tail live logs
tail -f ~/.temporary-aegis/logs/aegis.log

# Inspect consolidation output
ls -lh ~/.temporary-aegis/pc-state/
cat ~/.temporary-aegis/logs/consolidate.log | tail -50
```
