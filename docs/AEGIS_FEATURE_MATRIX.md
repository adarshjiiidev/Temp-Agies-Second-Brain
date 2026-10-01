# AEGIS Feature Wiring Matrix — 2026-09-30

Stage-by-stage truth for every advertised capability. A feature is only *real* when every applicable stage is ✅ **and** produces real data.

**Legend** — `C` code exists · `I` imported · `R` HTTP/WS route · `U` UI consumer · `P` persists · `S` scheduled job · `T` test coverage · `D` produced **real** output this week
`✅` verified · `⚠️` partial · `❌` absent · `🚫` **fabricates success** · `n/a` not applicable
Verdicts: **REAL** · **PARTIAL** · **UNWIRED** · **DEAD** · **FALSE** (reports success while not functioning)

| # | Feature | C | I | R | U | P | S | T | D | Verdict | Decisive evidence |
|---|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|---|---|
| 1 | Chat (LLM, `auto`) | ✅ | ✅ | ✅ | ✅ | ✅ | n/a | ❌ | ✅ | **REAL** | `server.py:2233` → `free_router.query_free_chat`; 429-failover proven in `aegis.log` |
| 2 | Free model fabric (round-robin) | ✅ | ✅ | ✅ | ✅ | ⚠️ | n/a | ❌ | ✅ | **REAL** | `GET /api/models` returns 14 live IDs; cooldowns held in RAM only |
| 3 | Role-based routing (`MODEL_FAST`, `_REASONING`…) | ✅ | ✅ | ⚠️ | ❌ | ❌ | n/a | ❌ | ❌ | **FALSE** | IDs are 9Router `cl/` slugs; unknown → sent verbatim → 4xx → cooldown (`config.py:72-91`, `free_router.py:489-495`) |
| 4 | LM Studio local inference | ✅ | ✅ | ✅ | ✅ | ❌ | n/a | ❌ | ❌ | **UNWIRED** | `query_lmstudio` reachable by ID prefix but `get_round_robin_candidates()` never emits `lmstudio/` |
| 5 | Groq tier | ✅ | ✅ | ⚠️ | ⚠️ | ❌ | n/a | ❌ | ❌ | **UNWIRED** | `providers.groq = "standby"`; no `GROQ_API_KEY` resolvable |
| 6 | Cactus Needle tier | ✅ | ✅ | ⚠️ | ❌ | ❌ | n/a | ❌ | ❌ | **UNWIRED** | `cactus_needle: "installable"`; module not importable |
| 7 | Tasks (`/api/tasks`) | ✅ | ✅ | ✅ | ✅ | ⚠️ | n/a | ❌ | ❌ | **PARTIAL** | live list returns `[]`; `~/.temporary-aegis/executions/` empty |
| 8 | Executions + trace API | ✅ | ✅ | ✅ | ❌ | ⚠️ | n/a | ❌ | ❌ | **UNWIRED** | 4 routes, no `api.ts` consumer; 0 records |
| 9 | Frontier execution (ReAct/AgentTeam) | ✅ | ✅ | ✅ | ⚠️ | ✅ | n/a | ❌ | ⚠️ | **PARTIAL** | `.venv` present; `frontier_runs/` holds only 2 `context-*.md` (Sep 27); never dispatched |
| 10 | Multica executor | 🚫 | ✅ | ⚠️ | ⚠️ | ❌ | n/a | ❌ | ❌ | **FALSE** | `assign_task()`→`"ASSIGNED"`, `monitor_task()`→`progress:100,"COMPLETED"` (`adapter.py:56-63`) |
| 11 | ECC skill fusion | ⚠️ | ✅ | 🚫 | 🚫 | ❌ | n/a | ❌ | ❌ | **FALSE** | duplicate `/api/skills` (891, 978); handler injects 3 synthetic skills; Hermes manifest unparseable |
| 12 | Skills panel | ✅ | ✅ | ✅ | ✅ | ⚠️ | n/a | ❌ | 🚫 | **FALSE** | shows `multica.coord`, which does not exist |
| 13 | Voice ASR | 🚫 | ✅ | ✅ | ✅ | ❌ | n/a | ❌ | ❌ | **FALSE** | `b"fake_audio_data"` + canned transcript (`voicestudio/adapter.py:20`) |
| 14 | Voice TTS | 🚫 | ✅ | ✅ | ✅ | ❌ | n/a | ❌ | ❌ | **FALSE** | same adapter; `/api/voice/status` honestly reports `available:false` |
| 15 | Real ASR daemon (voxtype) | n/a | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ | **UNWIRED** | `voxtype.service` active with Unix socket; 0 repo references |
| 16 | Camera registry + authorization | ✅ | ✅ | ✅ | ✅ | ✅ | n/a | ✅ | 🚫 | **PARTIAL / contaminated** | `TestCam2 mock://uri authorized:true vision_enabled:true` live in `GET /api/cameras` |
| 17 | Real capture (`/dev/video0`) | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | n/a | ✅ | ❌ | **PARTIAL** | real cv2/ffmpeg code; runtime `camera_enabled:false, HARD_DENY` (killswitch correctly holds) |
| 18 | Vision analysis of frames | ✅ | ⚠️ | ⚠️ | ❌ | ❌ | n/a | ⚠️ | ❌ | **UNWIRED** | `vision_engine.analyze_image_with_model` has 0 callers; `vision_pipeline` import-broken + orphaned |
| 19 | Network camera discovery | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | n/a | ❌ | ❌ | **PARTIAL** | real `nmap -p 554 --open` (`camera_registry.py:95`) but `nmap` is not installed |
| 20 | Screen intelligence | ✅ | ✅ | ✅ | ⚠️ | ❌ | n/a | ❌ | 🚫 | **FALSE** | dead `:20128` call; `except` returns `"success": True` (`screen_intel.py:154-176`) |

| 21 | Browser tool (extract/DOM/shot) | ✅ | ✅ | ✅ | ❌ | ⚠️ | n/a | ❌ | ✅ | **PARTIAL** | headless Chrome works; unauthenticated GETs; scheme-only URL validation |
| 22 | Code sandbox | ✅ | ✅ | ✅ | ❌ | ❌ | n/a | ⚠️ | ❌ | **BROKEN today** | `Rejected request to /api/sandbox/execute — bad/missing token` (`aegis.log` 09-30 17:43) |
| 23 | Computer control | ✅ | ✅ | ⚠️ | ❌ | ❌ | n/a | ❌ | ❌ | **UNWIRED** | `type_text` / `press_key` / `launch_application` have no route or caller |
| 24 | Governance / autonomy levels | ✅ | ✅ | ⚠️ | ✅ | ✅ | n/a | ❌ | ⚠️ | **PARTIAL** | `authorize()` only from `agent_moe` + `cloudroom_bridge`; 2 calls gated on `auto_approve`; PTY/sandbox/browser/scripts ungoverned |
| 25 | PTY terminal multiplexer | ✅ | ✅ | ✅ | ✅ | ❌ | n/a | ❌ | ✅ | **PARTIAL** | real xterm sessions; in-RAM dict, no respawn across restarts |
| 26 | `agent_runner` harness registry | ✅ | ❌ | ❌ | ❌ | ❌ | n/a | ❌ | ❌ | **DEAD** | 0 importers; self-referential registry → `exit(1)` |
| 27 | Agent MoE tools | ✅ | ✅ | ✅ | ❌ | ❌ | n/a | ❌ | ❌ | **UNWIRED** | 3 routes + the only governance-aware tools; no UI consumer |
| 28 | Supervisor | ✅ | ✅ | ✅ | ✅ | ⚠️ | ❌ | ❌ | ❌ | **PARTIAL** | `/api/supervisor/*` consumed by `api.ts` but no respawn loop behind it |
| 29 | Memory — TurboQuant | ✅ | ✅ | ✅ | ⚠️ | ✅ | n/a | ❌ | 🚫 | **PARTIAL / frozen** | 237 recs, 29 sources, newest 09-27 13:15; contains `cert_test`, `test_doc_1` |
| 30 | Memory — mem0 | ✅ | ✅ | ✅ | ✅ | ✅ | n/a | ❌ | 🚫 | **PARTIAL / frozen** | 61 recs newest 09-27 12:45; UI writes 403-blocked; chat writes swallowed by bare `except` |
| 31 | Memory — CognitiveMemory (TF-IDF) | ✅ | ✅ | ✅ | ⚠️ | ❌ | n/a | ❌ | ❌ | **PARTIAL** | `/api/memory/search` reads only this store; `?q=camera` → `[]` |
| 32 | Memory — Knowledge graph | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | **REAL** | learn job wrote 119 nodes / 211 edges; `/api/knowledge/rebuild` callable from `SpatialMemoryCanvas` |
| 33 | Obsidian vault (human corpus) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | **REAL** | 2,351 notes; real agent transcripts under `agies/by-agent/` |
| 34 | Cross-agent shared retrieval | ⚠️ | ✅ | ✅ | ⚠️ | ⚠️ | n/a | ❌ | ❌ | **PARTIAL** | 4 stores, 3 read endpoints, no canonical path; one agent's write is another's blind spot |
| 35 | Universal ingestion (10 sources) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | **REAL / partial** | frontier sessions redacted → vault confirmed; ChatGPT + projects jobs succeed |
| 36 | Ingest daemon (live polling) | 🚫 | ✅ | ⚠️ | ❌ | ❌ | ✅ | ❌ | ❌ | **FALSE** | 4 `# Stub / pass` loops (`ingest_daemon.py:46-60`) yet doctor reports PASS via `.running` |
| 37 | Consolidation | ✅ | ✅ | n/a | n/a | ✅ | ⚠️ | ❌ | ✅ | **REAL / over-scheduled** | double timer ⇒ ~96 runs/day rewriting the vault |
| 38 | Learn-patterns + snapshots | ✅ | ✅ | n/a | n/a | ✅ | ✅ | ❌ | ✅ | **REAL** | journals succeed; `aegis-learn-loop.timer` shipped disabled |
| 39 | Vault Explorer + Constellation graph | ✅ | ✅ | ✅ | ✅ | n/a | n/a | ❌ | ✅ | **REAL** | `/api/obsidian-graph` + `ObsidianGraph.tsx` mounted in `Desktop.tsx` |
| 40 | Spatial Memory Canvas | ✅ | ✅ | ✅ | ✅ | ⚠️ | n/a | ❌ | ⚠️ | **PARTIAL** | `TODO.md` 6.1 still `[ ]`: cards not fully vault-grounded |

| 41 | System graph panel | 🚫 | ✅ | ✅ | ✅ | n/a | n/a | ❌ | 🚫 | **FALSE** | 10 of 14 nodes hardcoded `"PASS"` (`server.py:1027-1040`) |
| 42 | Doctor / health | ✅ | ✅ | ✅ | ✅ | n/a | n/a | ❌ | 🚫 | **FALSE** | `chk("AEGIS Core", True)`, `chk("Backend API", True)` literals (`server.py:1104-1105`) |
| 43 | Events / WebSocket layer | ⚠️ | ✅ | ✅ | ⚠️ | ❌ | n/a | ❌ | ⚠️ | **PARTIAL** | 2 of ~7 message types emitted; `initial_data` computed-then-discarded; `subscribe_*` dead at both ends |
| 44 | PC telemetry monitor | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | **REAL** | `pc_update` broadcast + 30 s polling fallback (`store.tsx:218`) |
| 45 | Preferences / personal context | ✅ | ✅ | ✅ | ⚠️ | ✅ | n/a | ❌ | ✅ | **PARTIAL** | 5 route groups, no `api.ts` coverage; hardcodes `/home/adarshjii` (`preferences.py:214`) |
| 46 | Research engine / lab | ✅ | ✅ | ✅ | ❌ | ✅ | n/a | ❌ | ❌ | **UNWIRED** | `/api/research/start`, `/api/lab/*` have no UI; engine calls the stale `model_router` |
| 47 | Cloudroom bridge | ✅ | ✅ | ✅ | ✅ | ⚠️ | n/a | ❌ | ❌ | **UNWIRED** | only caller of the level-based command guard; no consumer exercises it |
| 48 | Proactive monitor | ✅ | ✅ | ✅ | ❌ | ⚠️ | ❌ | ❌ | ❌ | **UNWIRED** | route only; never scheduled |
| 49 | Frontend service supervision | 🚫 | n/a | n/a | n/a | n/a | ✅ | n/a | 🚫 | **FALSE** | `aegis-frontend.service` = `ExecStart=/usr/bin/true`, reports `active (exited)` |
| 50 | Dev server (`npm run dev`) | ❌ | n/a | n/a | n/a | n/a | n/a | n/a | ❌ | **BROKEN** | binds 2981 (the backend's port) while proxying `/api`+`/ws` to dead `:8787` (`vite.config.ts:13-22`) |

## Summary distribution (50 features)

| Verdict | Count | Rows |
|---|---|---|
| REAL | 9 | 1, 2, 32, 33, 35, 37, 38, 39, 44 |
| PARTIAL | 16 | 7, 9, 16, 17, 19, 21, 24, 25, 28, 29, 30, 31, 34, 40, 43, 45 |
| UNWIRED | 11 | 4, 5, 6, 8, 15, 18, 23, 27, 46, 47, 48 |
| **FALSE** (reports success while not functioning) | **11** | 3, 10, 11, 12, 13, 14, 20, 36, 41, 42, 49 |
| DEAD | 1 | 26 |
| BROKEN | 2 | 22, 50 |

Four REAL features carry a runtime caveat that must not be lost when they are "fixed": consolidation is **over-scheduled** (row 37), both vector stores are **frozen** (29, 30), the camera registry is **contaminated** with test residue (16), and the ingestion tier succeeds while its live-polling half is empty (35 vs 36).

**The number that matters most: 11 of 50 audited features actively fabricate or misreport success**, and that failure is invisible from the dashboard because its status fields are literals rather than probes — see `docs/AEGIS_FORENSIC_AUDIT_2026-09-30.md` §F-02. Fixing the *reporting layer* (Phase P0) is therefore a prerequisite to fixing the features: without it, every later "fixed" claim is unfalsifiable.


