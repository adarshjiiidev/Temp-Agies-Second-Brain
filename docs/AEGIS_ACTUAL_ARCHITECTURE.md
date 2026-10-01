# AEGIS Actual Architecture (as-built, post-9Router) — 2026-09-30

Describes the system **as it runs today**, not as designed. Every arrow was traced through code or observed in a live response/journal. Companion docs: `AEGIS_FORENSIC_AUDIT_2026-09-30.md` (findings F-01…F-19), `AEGIS_FEATURE_MATRIX.md` (50 features × 8 stages), `AEGIS_DEFECT_REGISTER.json` (machine-readable), `../../AEGIS_PHASED_TODO.md` (repair plan).

## 1. Process & port topology (measured)

| Process | Supervisor | Bind / IPC | Reality |
|---|---|---|---|
| FastAPI backend (`backend/server.py`) | `aegis-backend.service` | `127.0.0.1:2981`, `AEGIS_BACKEND_PORT=2981` | **healthy**; unit `Description=` still claims 8787 |
| Built SPA | same process | served by `StaticFiles` mount, `API_BASE='/api'` | healthy; `dist/` rebuilt 2026-09-30 13:43 |
| Vite dev server | manual | `port: 2981`, proxies `/api`+`/ws` → `127.0.0.1:8787` | **broken**: collides with backend and proxies to a dead port |
| LM Studio | external | `127.0.0.1:1234` (`free_router.py:415`) | `detected`, but unreachable from chat routing |
| 9Router gateway | — | `127.0.0.1:20128` | **gone** — no socket, no unit, no process; still called by `screen_intel.py` |
| voxtype ASR daemon | `voxtype.service` | `/run/user/1000/voxtype/audio.sock` | active; **zero** repo references |
| Batch jobs | 4 user timers | `~/.temporary-aegis/*` | all succeed; consolidate fires ~96×/day |

Nothing listens on 3000/8000 (`config.py:45-48`) or 5000 (`voicestudio/adapter.py:12`) or 8080 (`multica/adapter.py:27`) — those defaults are aspirational.

## 2. Request path that actually works (the golden path)

```
Browser (SPA, 18 panels)
  └─ fetch /api/…  ──► SecurityMiddleware (token/CSRF gate, security.py)
       └─ POST /api/chat  (needs cookie from GET /api/chat/session, local-only)
            └─ free_router.query_free_chat(model="auto")
                 ├─ get_round_robin_candidates()  → groq/* then openrouter/*
                 ├─ dispatch by ID prefix: groq/ | openrouter/ | lmstudio/ | cactus/
                 ├─ 4xx/429 → mark cooldown 60 s → next candidate   ← observed live in aegis.log
                 └─ parse both `content` and `reasoning_content`
            └─ response streamed to ChatPanel
            └─ (fire-and-forget) mem0_engine.add(...)  ← inside try/except Exception: pass
```

This path is **real** and is why the product feels functional. Its two hidden defects: role-keyed requests first waste one guaranteed-fail call (F-08), and the memory write after every turn can fail silently (F-10/F-11).

## 3. Model fabric — two incompatible namespaces

| Layer | ID namespace | Count | Status |
|---|---|---|---|
| `config.py` role keys + `FREE_CHAT_MODELS` | `cl/…` (9Router-era) | 8 distinct | **resolves to nothing**; falls through to raw passthrough |
| `free_router` runtime pool | `openrouter/…`, `groq/…`, `cactus/…` | 14 (`/api/models`) | live; 11 report available (`/api/model-health`) |
| `registries/MODEL_REGISTRY.json` | mixed + `9router_url` | 3 KB (was 15,416 lines) | post-teardown; keeps advertising a dead gateway |
| `model_router.VERIFIED_MODEL_PROFILES` | bare slugs | — | fabricated latency/reliability constants; still live-called by `research_engine`, `task_planner`, `server.py:1448` |

Effective provider count today is **one** (OpenRouter): Groq is `standby` (no key), Cactus is `installable`, LM Studio is `detected` but never auto-selected. `cl/` IDs are also mirrored into `~/.hermes/.env` and `~/.gemini/config/settings.json`, so external harnesses have been handed the same unresolvable IDs.

## 4. Memory architecture — 5 corpora, 3 read endpoints, no canonical store

```
write paths
  chat turn ──► mem0_engine.add()  ─┐ (silent-fail)
  UI POST /api/memory/mem0/add ─────┤ 403 today (token gate)
  scripts/seed_agies_knowledge.py ──┼─► turboquant_store.json (237) / mem0_store.json (61)   ← both frozen at 2026-09-27
  aegis-universal-ingest (10 src) ──► ObsidianVault/agies/**  (2,351 .md)                     ← live, real
  aegis-learn-patterns ─────────────► knowledge_graph.json (119 nodes / 211 edges)            ← live
  aegis-consolidate (~96×/day) ─────► ObsidianVault (rewrites)                                ← live, over-scheduled

read paths
  /api/turboquant/search   → TurboQuantStore      (vector-ish, JSON scan)
  /api/memory/mem0/search  → mem0_engine          (entity+category)
  /api/memory/search       → CognitiveMemoryEngine (TF-IDF, in-process)
  /api/graph, /api/obsidian-graph → knowledge_graph / vault wikilinks
```

Consequence: a question answered by one engine can return `[]` from another (`?q=camera` → `/api/memory/search` = `[]` while Obsidian holds camera notes). There is no read-through cache, no shared ID scheme, no tombstones, and no write-ack path — so "the second brain remembers X" is only true relative to a chosen engine. `~/.temporary-aegis/` also contains a **parallel legacy implementation** (`dashboard_server.py`, `build_model_registry.py`, its own `MODEL_REGISTRY.json`, its own `.git` with one commit) that nothing imports but a maintainer could easily edit by mistake.

## 5. Execution architecture

`execution_core` is the single lifecycle owner (BACKLOG→…→DONE, JSON-per-task under `~/.temporary-aegis/executions/`) and is correctly wired to both `/api/tasks*` and `/api/executions*`. `dispatch()` allows **only** `frontier`; every other target is set `BLOCKED` with an explicit no-subprocess reason — a good design. But: the executions directory is **empty**, so no task has ever been dispatched end-to-end; the frontier path has produced only 2 context packs (Sep 27); governance is consulted only when `auto_approve` is true (F-06); and Multica's "adapter" fabricates `ASSIGNED`/`COMPLETED` (F-05).

Two registries of executors exist (`/api/agents/registry`, `/api/system/graph`) and they disagree with `/api/ide-adapters` about what is installed.

## 6. Peripheral / actuator tier

| Actuator | Real primitive present? | Governing gate | Reachable from UI |
|---|---|---|---|
| PTY agent terminals | ✅ `agent_pty` + xterm.js | ❌ none | ✅ (`AgentTab.tsx` start/stop/restart) |
| Shell scripts | ✅ `subprocess` | ❌ none | ✅ `/api/run-script` |
| Code sandbox | ✅ | ❌ none | ⚠️ blocked by token gate (F-11) |
| Browser (headless Chrome) | ✅ | ❌ scheme check only | ❌ (unauth GETs though — F-16) |
| Camera capture | ✅ OpenCV/ffmpeg | RAM-only killswitch + **test-contaminated** durable registry | ⚠️ |
| Voice ASR/TTS | 🚫 canned bytes/text | n/a | ✅ (returns fabricated text) |
| Computer control (keys/apps) | ✅ in module | ❌ | ❌ no route |
| `agent_moe` fs/terminal tools | ✅ | ✅ **the only governed tools** | ❌ no UI |

The pattern is inverted from what the docs describe: the subsystems with real capabilities are ungoverned, and the governed ones have no user-facing path.

## 7. Observability — why drift accumulated

Three surfaces present health, and all three are partly literal:

1. `GET /api/system/graph` — 10 of 14 nodes are hardcoded `"PASS"` literals (`server.py:1027-1040`).
2. `GET /api/health/doctor` — mixed: real probes (`Path(...).exists()`, `whisper_ok`, `systemctl --user is-active`) **and** literals (`chk("AEGIS Core", True, …)`, `chk("Backend API", True, …)`), plus `ingest_daemon.running` which is a flag, not an activity measure.
3. `aegis-frontend.service` — `ExecStart=/usr/bin/true`, so `is-active` returns `active` forever, and `aegis_health.py:120` probes exactly that kind of unit.

Any monitor wired to these surfaces therefore cannot distinguish working from broken. The journal, by contrast, **is** trustworthy: the only reliable signals in this audit came from `journalctl --user -u aegis-*` and `~/.temporary-aegis/logs/aegis.log` (which recorded the 429 failovers, the 403 rejections, and the recurring `Failed to parse Hermes skill manifest`). Repair phase P0 restores trust in the surfaces before any feature is declared fixed.

## 8. Trustworthy vs untrustworthy claims (quick reference for maintainers)

**Trust** the journal, `GET /api/health`, `GET /api/models`, `GET /api/model-health`, `GET /api/vision/status`, `GET /api/voice/status`, `GET /api/ide-adapters`, the on-disk vault, and the four timers' exit codes.

**Do not trust** `/api/system/graph` node statuses, doctor's Core/Backend/Ingest rows, `/api/skills` contents, `/api/9router-health`'s name, screen-intel `"success"`, Multica task states, voice transcripts, `model_router` latency/reliability constants, `docs/MODEL_FABRIC.md`, `TODO.md` phase checkmarks, or the `claimed_status` field in any `docs/AEGIS_*_TASKS.json` (measured: all 24 certification items claim `COMPLETE` while `actual_status` says otherwise for 6).

## 9. Minimum honest architecture after repair

The end state that the phased plan aims for is deliberately smaller than the documented one: **1 provider fabric with 3 real backends (OpenRouter + Groq + LM Studio), 4 memory stores exposed behind 1 read endpoint with per-store provenance, 1 execution path (Frontier) with a real Multica client or none at all, and every status field computed by a probe that can fail.** Removing or downgrading a fake is preferred over leaving it green — the audit's central lesson is that a fabricated green costs more than a red.

