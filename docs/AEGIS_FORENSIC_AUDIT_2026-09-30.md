# AEGIS Forensic Audit — 2026-09-30

**Mode:** strictly read-only (no file, service, or state mutation).
**Method:** static import/call-graph analysis of `backend/` + `src/`, live read-only `GET`s against `http://127.0.0.1:2981`, inspection of on-disk runtime state in `~/.temporary-aegis/` and `~/ObsidianVault/`, systemd unit + journal inspection, runtime log analysis.
**Confidence legend:** `CONFIRMED` = verified first-hand this session by direct file read or live response. `SUPPORTED` = reported by a delegated read-only pass and consistent with first-hand evidence. `UNKNOWN` = not establishable without state-changing action.

---

## 1. Verified inventory (re-measured this session)

| Artifact | Count | Note |
|---|---|---|
| `backend/*.py` | 44 | top-level engine modules |
| `backend/integrations/**/*.py` | 6 | `agents/ ecc/ frontier/ multica/ voicestudio/` |
| Routes in `backend/server.py` | 115 | 69 GET, 44 POST, 2 WebSocket |
| `src/components/*.tsx` | 24 | 18 mounted via `Desktop.tsx` |
| `tests/` entries | 10 | only camera tests were ever collected (`.pytest_cache`) |
| `docs/*.md` | 42 | 6 are self-certification reports |
| `scripts/` | 7 | ingestion/seed/learn helpers |
| Orphan backend modules (0 importers) | 5 | `agent_runner`, `camera_cli`, `deepseek_harness`, `openclaw_harness`, `vision_pipeline` |
| Backend routes with no `api.ts` consumer | 63 | ~55% of API surface unreachable from UI |
| Backend execution records | 0 | `~/.temporary-aegis/executions/` is empty |

**Git:** 4 total commits, last 2026-09-14; working tree carries 63 modified + 68 untracked paths. `registries/MODEL_REGISTRY.json` lost ~15,416 lines vs HEAD — this is the **intentional 9Router teardown** (870 gateway models removed), *not* accidental data loss.

---

## 2. Headline findings

### F-01 — Failures are reported as successes (CONFIRMED, critical)
`backend/screen_intel.py:154-176` POSTs to `http://127.0.0.1:20128/v1/chat/completions`. 9Router is gone (nothing listens on 20128; no unit file; no process — re-verified). The `except` branch then returns `"success": True` with deterministic text built from window titles and OCR. Every screen-intelligence answer is fabricated prose presented as a successful vision call, and no caller can distinguish real from failed.

### F-02 — Self-certifying health surfaces (CONFIRMED, critical)
`GET /api/system/graph` hardcodes `"status": "PASS"` for 10 of 14 nodes (`server.py:1027-1033, 1036, 1039-1040`); only `frontier` is computed. The Doctor endpoint asserts literals — `chk("AEGIS Core", True, ...)`, `chk("Backend API", True, ...)` (`server.py:1104-1105`) — and `chk("Ingest Daemon", ingest_daemon.running, ...)` (`server.py:1162`) reads PASS from a boolean flag while all four poll loops are empty `pass` stubs (`ingest_daemon.py:46-60`).
**Consequence: the dashboard cannot falsify anything — a broken subsystem and a working one render identically.** This is the mechanical root cause of every doc-vs-reality gap in §4.

### F-03 — The Skills panel invents capabilities (CONFIRMED, high)
Two handlers are registered for the same path: `@app.get("/api/skills")` at `server.py:891` (real `skill_registry`) **and** at `server.py:978` (ECC fusion). FastAPI resolves the first, so the ECC endpoint is unreachable dead code. The real registry is unreadable — `Failed to parse Hermes skill manifest: Expecting value: line 1 column 1` recurs in `aegis.log` (2026-09-30 17:43, 17:47) — and the handler then injects three synthetic skills, including `multica.coord` "Sub-Agent Coordinator", which has no implementation anywhere. Users are shown capabilities the system does not have.

### F-04 — Voice path returns canned data (CONFIRMED, high)
`backend/integrations/voicestudio/adapter.py:20` returns the literal `b"fake_audio_data"`; the transcribe path returns a hardcoded transcript. Both are reachable through live POST routes. `GET /api/voice/status` correctly answers `{"available": false}`, but the write endpoints still accept audio and return fabricated text. Meanwhile a working local ASR daemon (`voxtype.service`, active, Unix socket) has **zero** references in this repo — the real capability exists and is unwired.

### F-05 — Multica reports success it did not perform (CONFIRMED, high)
`backend/integrations/multica/adapter.py:56-63`: `assign_task()` returns `status="ASSIGNED"` with no network call; `monitor_task()` returns `{"progress": 100, "status": "COMPLETED"}` unconditionally. `execution_core.dispatch()` blocks any non-`frontier` target (`execution_core.py:186-189`), so the fake is not currently reachable via the task path — but the stub remains registered as an executor and importable.

### F-06 — Governance is narrower than documented (CONFIRMED, high)
One singleton exists (`governance = governance_engine`, `governance.py:125-126`) and the method is `authorize()` — **`check_permission` does not exist**. Verified callers: `agent_moe.py:57,71,84`, `cloudroom_bridge.py:139-142`, plus two *conditional* calls — `execution_core.py:190` and `frontier_adapter.py:95`, both written `if auto_approve and not governance.authorize(...)`, so authorization is skipped when `auto_approve` is false.
**Not governed at all:** `agent_pty` terminal sessions, `code_sandbox`, `browser_tool`, `computer_control`, `/api/run-script`, camera and vision routes. The UI autonomy toggle (`TopBar.tsx` → `POST /api/governance/level`) therefore changes a value most actuators never read.

### F-07 — Camera state contains test residue promoted to policy (CONFIRMED, high)
Live `GET /api/cameras` returns `cam-2d077c85` = `"TestCam2"`, `uri: "mock://uri"`, `"authorized": true`, `"vision_enabled": true`, plus repeated `"Integrated Camera (cert run)"` rows bound to `/dev/video0`, all `authorized: true`. These originated from `tests/test_camera_e2e.py` writing the real registry. The privacy killswitch (`GET /api/vision/status` → `"camera_enabled": false, "privacy_state": "HARD_DENY"`) is RAM-only, so durable per-camera grants outlive it: one toggle re-arms `/dev/video0` with no per-camera consent or audit.

### F-08 — Model routing: two incompatible ID namespaces (CONFIRMED, high)
`backend/config.py:72-91` still hardcodes eight **9Router-era `cl/` IDs** (`cl/z-ai/glm-5.2:free`, `cl/nex-agi/nex-n2.5-pro:free`, `cl/poolside/laguna-s-2.1:free`, …) as `MODEL_DEFAULT`, `MODEL_REASONING`, `MODEL_FAST`, `MODEL_LITE` and `FREE_CHAT_MODELS`. The live fabric exposes 14 IDs under `openrouter/`, `groq/`, `cactus/`. **Zero of the eight resolve.** Four slugs (`glm-5.2`, `nex-n2.5-pro`, `nex-n2.5-mini`, `inclusionai/ling-3.0-flash-vl`) exist nowhere in the codebase.
In `query_free_chat` (`free_router.py:431-501`) an unknown prefixed ID falls to the `else` branch and is sent **verbatim** to OpenRouter as `model: "cl/z-ai/glm-5.2:free"` → guaranteed 4xx → 60 s cooldown → fall through to round-robin. Every role-based selection therefore costs one wasted failing request before the system recovers; role routing is effectively decorative.

### F-09 — "Multi-provider" is currently single-provider (CONFIRMED, medium)
`GET /api/model-health` → `providers: {openrouter: online, groq: standby, cactus_needle: installable, lmstudio: detected}`, `available_models: 11`. `get_round_robin_candidates()` (`free_router.py:313-340`) only emits `groq/` and `openrouter/` IDs, so `lmstudio/` and `cactus/` are dispatchable (`free_router.py:480-483`) but **never selected**; `query_lmstudio` is unreachable from chat. With `GROQ_API_KEY` unset all traffic funnels through OpenRouter — real resilience today is 11 model IDs behind one provider, not three providers. Failover itself works: `Rate limited (HTTP 429)` → next candidate, `No choices in completion` → next candidate (`aegis.log` 2026-09-27 13:14).

### F-10 — Four memory stores, three read paths, two frozen (CONFIRMED, high)
| Store | Records | Read endpoint | Newest |
|---|---|---|---|
| `turboquant_store.json` | 237 (29 distinct `source_id`) | `/api/turboquant/search` | 2026-09-27 13:15 |
| `memory/mem0_store.json` | 61 | `/api/memory/mem0/search`, `/all` | 2026-09-27 12:45 |
| `CognitiveMemoryEngine` (TF-IDF) | in-process | `/api/memory/search` (`server.py:775-779`) | — |
| `memory/knowledge_graph.json` | dict | `/api/graph` | — |

Plus Obsidian (2,351 `.md`) as a fifth, markdown-only corpus. Two stores have not accepted a write in three days while `consolidate` rewrites the vault ~96×/day (F-13). `turboquant` carries test residue as knowledge: `source_id: "cert_test"` → `"This is a certification test for turboquant storage."`, plus `"test_doc_1"`. Chat writes to mem0 inside `try/except Exception: pass`, so failures are invisible.

### F-11 — Memory writes from the UI are blocked by the token gate (CONFIRMED, high)
`aegis.log`: `Rejected request to /api/memory/mem0/add — bad/missing token` + `Security reject 403` (2026-09-29 22:14, twice) and `Rejected request to /api/sandbox/execute — bad/missing token` (2026-09-30 17:43). The session cookie is minted only by `GET /api/chat/session` and documented as usable "only for POST /api/chat", yet other POST routes demand it. A live break hit today; it also explains part of F-10.

### F-12 — Dev mode cannot work (CONFIRMED, medium)
`vite.config.ts:13-22` sets the dev server to `port: 2981` — the same port the systemd backend occupies — while proxying `/api` → `http://127.0.0.1:8787` and `/ws` → `ws://127.0.0.1:8787`. Port 8787 is a pre-teardown default with nothing listening. `npm run dev` therefore either fails to bind or serves a dashboard whose every API call is refused. The stale `8787` also survives in `src/lib/api.ts:3`. Production is unaffected because the built SPA is served by the backend's `StaticFiles` mount using the relative `API_BASE = '/api'` (`api.ts:326`).

### F-13 — Consolidation runs ~96×/day instead of daily (SUPPORTED, medium)
`aegis-consolidate.timer` and `aegis-consolidate-daily.timer` both target the same service with identical `OnUnitActiveSec=15min` + `OnBootSec=30sec`, sharing `LastTriggerUSec` and `NextElapse`; the `-daily` unit's own `OnCalendar 15:00` is subsumed by its own 15-minute clause. Journals confirm all four scheduled jobs **succeed** — `aegis-ingest` ("Projects ingested: 13", wrote a 1,285,779-char file), `aegis-consolidate` ("Brains consolidated: 5, Living project memories: 9"), `aegis-learn` ("Graph supplement written: 119 nodes, 211 edges"), `aegis-snapshot` — zero tracebacks. The batch tier is healthy but rewrites the vault continuously. Also: `aegis-ingest` is enabled as a *service* **and** a timer (double boot run), `aegis-learn-loop.timer` ships disabled-but-present, and `aegis-frontend.service` is `ExecStart=/usr/bin/true` yet reports `active (exited)`, which any `is-active` probe reads as green.

### F-14 — Half the API has no UI consumer; the typed client is bypassed (CONFIRMED, medium)
63 of 115 routes are absent from `src/lib/api.ts` (whole groups: `/api/executions*`, `/api/planner/*`, `/api/agentmoe/*`, `/api/browser/*`, `/api/preferences*`, `/api/lab/*`, `/api/memory/search`, `/api/turboquant/search`, `/api/research/start`, `/api/sandbox/execute`, `/api/screen/intel`, `/api/capabilities`). Separately, **zero** of the 24 components import `apiClient`; panels call `fetch` directly (`AgentTabs.tsx`, `AgentTab.tsx`, `HomePanel.tsx`, `SpatialMemoryCanvas.tsx`, plus `/api/cameras` and `/api/local-model/*` at `api.ts:625-690`), so the 48 typed helpers and their interfaces are largely dead code. Features exist server-side but are invisible in the product.

### F-15 — The event layer is a stub (SUPPORTED, medium)
`broadcast()` fires only two message types — `pc_update` (`server.py:710`) and `script_result` (`server.py:919`). On `/ws` connect the server computes and discards a full `initial_data` payload on every connection (`server.py:2263-2275`); inbound `subscribe_pc` / `subscribe_scripts` / `ping` reply with fixed acks and do nothing else; camera, vision, voice, memory and execution events emit nothing, so no panel can observe them. Key `"9router_health"` persists in that payload (`server.py:2275`) though its value is free-router health.

### F-16 — Unauthenticated actuator GETs (SUPPORTED, high)
`GET /api/browser/extract|screenshot|dom` (`server.py:805-815`) drive headless Chrome with only scheme-level URL validation in `browser_tool.py`, and `security.py:47` allow-lists `/api/governance`-family paths; verified `200` without a token. On a host also running LM Studio at `127.0.0.1:1234` and a voice socket at `/run/user/1000/voxtype/audio.sock`, this is a reachable SSRF/read primitive. Path filtering also over-blocks legitimate content: `Path traversal blocked: /usr/share/omarchy/default/agents/skills/diagnose-crash/SKILL.md` (`aegis.log` 2026-09-27 13:06).

### F-17 — Orphaned and unwired code (CONFIRMED, medium)
`agent_runner`, `camera_cli`, `deepseek_harness`, `openclaw_harness`, `vision_pipeline` each have 0 inbound imports. `vision_pipeline` is additionally import-broken; `vision_engine.analyze_image_with_model` — the only real vision-model call in the repo — has no callers, so `/dev/video0` frames are never actually sent to a model. `model_router.py` is still live (`server.py:1448`, `research_engine.py:79,173`, `task_planner.py:84`) alongside `free_router`, contradicting "one model router"; its `VERIFIED_MODEL_PROFILES` carries hardcoded latency/reliability constants (e.g. `avg_latency` `6.85`, `reliability` `1.0`) presented as measured truth but never computed. `tests/benchmark_models.py:41` still benchmarks port 20128 and writes `docs/MODEL_FABRIC.md`, so re-running it now would emit a fabricated benchmark.

### F-18 — Hardcoded machine specifics (CONFIRMED, low)
Absolute paths: `preferences.py:214`, `server.py:1149`, `server.py:1173` (`/home/adarshjii/.hermes/hermes-agent/venv/bin/python`), `server.py:1185` (`/home/adarshjii/Work/FrontierAgent/.venv`). Ports: `free_router.py:415` (`1234`), `audio_engine.py:128` (`localhost:2981`), `config.py:45-48` (`3000`/`8000`). The runtime dir `~/.temporary-aegis/` is itself a git repo with one commit holding an older parallel copy of the system (`dashboard_server.py`, `build_model_registry.py`, `MODEL_REGISTRY.json`, `AGIES.md`) — a second source of truth that has silently diverged.

## 3. 9Router removal status (the user's own change) — ~85% complete

Runtime removal is **genuine and clean**: nothing listens on 20128, no `9router.service` unit exists, no process runs, `/api/model-health` is free-router-backed, and the free fabric answers. Residue that still misleads, all verified:

| # | Residue | Location | Consequence |
|---|---|---|---|
| 1 | Live POST to `127.0.0.1:20128` | `screen_intel.py:158` | dead call every use; error masked as success (F-01) |
| 2 | 8 × `cl/` model IDs | `config.py:72-91` | guaranteed 4xx + cooldown per role selection (F-08) |
| 3 | `9router_url` / `9router_models_count` keys | `registries/MODEL_REGISTRY.json:3-4` | registry advertises a dead gateway |
| 4 | `/api/9router-health` route | `server.py:907` | answers `200` with free-router data under a 9Router name |
| 5 | `"9router_health"` wire key | `server.py:2275` | WS contract still names the removed system |
| 6 | 2 orphan harnesses | `deepseek_harness.py:114`, `openclaw_harness.py:100` | dead `query_9router()` implementations |
| 7 | docstrings/labels | `vision_engine.py:215`, `audio_engine.py:84`, `ModelsPanel.tsx:187,260`, `TopBar.tsx:108`, `server.py:5,2149`, `aegis_consolidate.py` (10 sites: 330,337,390,405,421,426,487,503,507,596-614) | docs/UI/consolidated memory still describe 9Router architecture |
| 8 | benchmark targets dead port | `tests/benchmark_models.py:41,106-109` | would publish a false `MODEL_FABRIC.md` |
| 9 | unit metadata | `aegis-backend.service` lists `9router.service` in `After=`; `Description=` says port 8787 while `Environment=AEGIS_BACKEND_PORT=2981` | stale ops metadata |

`TODO.md` Phase 1 (1.1–1.4) is marked `[x]`; 1.1 and 1.2 are demonstrably not done. The vault also holds a **correct historical record** — `~/ObsidianVault/memory/3-Resources/model-providers/9Router.md` — which should be annotated "decommissioned 2026-09", not deleted; and `aegis_consolidate.py` still embeds 9Router prose as *seed project knowledge*, which is why the second brain keeps re-learning a gateway that no longer exists.

## 4. What is genuinely healthy (verified, must not be regressed)

- **Free model fabric + failover.** 11 live models, correct cooldown/failover behaviour in the journal; round-robin and dual `content`/`reasoning` parsing work.
- **Scheduled memory/ingestion tier.** All four timers execute successfully with real output volume (13 projects, 1.28 MB ingestion file, 5 brains + 9 project memories consolidated, 119 nodes/211 edges learned, daily PC-state snapshots).
- **Obsidian corpus.** 2,351 notes, actively written, real agent session content under `agies/by-agent/<agent>/<uuid>/` (transcripts, decisions, tasks, files-built) — not template filler.
- **UI shell.** All 18 panels mount and consume live endpoints; `GET /api/health` reports `{"status":"ok","port":2981}`; every `api.ts` call resolves against a real route (no 404s found — an earlier double-prefix suspicion was disproved live: `/api/cameras` → 200).
- **Privacy killswitches do hold at runtime.** `GET /api/vision/status` reports `camera_enabled: false`, `privacy_state: "HARD_DENY"`; `GET /api/voice/status` reports `available: false`.
- **PTY terminal multiplexer.** Real `agent_pty` + xterm.js sessions with working start/stop/restart routes (but see F-19: in-RAM session dict, no respawn).
- **Vision toolchain primitives.** Real OpenCV/ffmpeg capture code and a real `nmap`-based network-camera discovery routine exist (though `nmap` is absent on this host, so that path fails at runtime).

### F-19 — Agent sessions are not durable (SUPPORTED, medium)
`agent_pty` keeps sessions in an in-memory dict with no supervisor respawn loop; `agent_runner.py` (which would register `deepseek`/`openclaw`) is orphaned and its registry lookup is self-referential, so it would `exit(1)`. `agent_supervisor` exposes routes but nothing restarts a dead agent after a backend reload.

## 5. Documentation vs implementation

42 markdown reports in `docs/`, six of them self-certifications. Delegated read-only pass over the six certifications + `README.md` + `AGIES.md` + `TODO.md` produced 25 claim checks; representative contradictions:

| Claim | Verdict | Evidence |
|---|---|---|
| "L5 enforced: all dispatch paths call `authorize()`" | CONTRADICTED | only `agent_moe` + `cloudroom_bridge`; two calls gated on `auto_approve` (F-06) |
| "ECC FUSED, skills served via `/api/skills`" | CONTRADICTED | duplicate route shadowed; 3 demo skills injected (F-03) |
| "one model router — `free_router`, no secondary brains" | CONTRADICTED | `model_router.py` live in 3 call sites + registry keys (F-8, F-17) |
| "ingest daemon started at startup; ingestion active" | CONTRADICTED | 4 empty poll loops; doctor PASSes on `.running` (F-02) |
| "Multica ADAPTER READY registered in dispatch" | CONTRADICTED | stub returns `ASSIGNED`→`COMPLETED` 100 (F-05) |
| "GET `/api/system/graph` = live capability graph" | CONTRADICTED | 10 hardcoded `"PASS"` literals (F-02) |
| "VoiceStudio boundary; `/api/voice/*` active" | CONTRADICTED | `b"fake_audio_data"` + canned transcript (F-04) |
| "25 TurboQuant sources, mem0 total 27" / "27 skills" / "27 modules, 0 hardcoded paths" | CONTRADICTED | 237 records / 61 records / `SKILL_REGISTRY.json` `total_skills: 22` / 44 modules / 4 hardcoded paths (F-10, F-18) |
| "port 8787", "`aegis-frontend.service` ✅ active", OCR via `tesseract` | CONTRADICTED | `2981`; `ExecStart=/usr/bin/true`; no tesseract binary |
| "camera_registry is a stub, no scanning" (forensic doc) vs "network cams via nmap RTSP:554" (vision doc) | docs contradict each other | real `nmap -p 554 --open` exists in `camera_registry.py:95`; `nmap` absent on host |

**Task-file truth (measured, not inferred):** `AEGIS_MASTER_TASKS.json` (7 phases, 57 status-bearing leaves), `AEGIS_CERTIFICATION_TASKS.json` (24 items, `claimed_status: COMPLETE ×24` vs `actual_status` VERIFIED 18 / PARTIALLY_VERIFIED 2 / NOT_CONFIGURED 3 / NOT_IMPLEMENTED 1), `AEGIS_VISION_TURBOQUANT_TASKS.json` (7 items: 6 VERIFIED, 1 NOT_CONFIGURED). **None of the three contains any `done` key or checkbox literal** — the "all complete" impression comes from prose, not state. Checkboxes exist only in `TODO.md`: 16 `[x]`, 4 `[ ]`.

**Subsystems present in code but absent from every doc:** `org_cameras.py`, `research_lab.py`, `spatial_mode.py`, `preferences.py`, `cloudroom_bridge.py`, `universal_ingest/`, `camera_cli.py`, `openrouter_chat.py`, plus route groups `/api/org-cameras/*`, `/api/lab/*`, `/api/cloudroom/*`, `/api/preferences*` and the LM-Studio `/api/local-model/*` proxy.

### Audit-integrity note
Two delegated read-only passes were aborted on token limits and re-run; findings from them are marked `SUPPORTED`, not `CONFIRMED`. One delegated citation was **false** and has been removed from this report: `backend/ide_adapters.py` does not exist (the hardcoded venv probe is `server.py:1149,1173`). Two of my own intermediate suspicions were also disproved by direct testing and are recorded as non-defects: the "`/api/api/...` double-prefix" bug (bare `fetch` bypasses `API_BASE`) and the "two governance singletons" hypothesis (`governance = governance_engine`, one object).

## 6. Remediation

Priorities, verification commands, and acceptance criteria live in **`AEGIS_PHASED_TODO.md`** (repo root); machine-readable register in **`docs/AEGIS_DEFECT_REGISTER.json`**. The organising rule for that plan: **no component may report a status it has not measured** — every fix is expressed as "replace the literal with a probe, then make the probe pass."


