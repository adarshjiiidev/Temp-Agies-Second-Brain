# AEGIS LIVE SYSTEM MAP (Phase 0 Baseline)

Generated: 2026-09-30 · Method: direct filesystem + systemd + `/proc` + live HTTP probes.
Rule applied: a component counts as REAL only if a producer → consumer path exists at runtime.

Status vocabulary: **REAL** · **PARTIAL** · **BROKEN** · **MOCK** · **DEAD** · **NOT_CONFIGURED**

## 1. Host capability inventory (verified)

| Capability | Binary / Device | State | Consequence |
|---|---|---|---|
| Camera capture | `/dev/video0`, `/dev/video1` | PRESENT | Real capture possible |
| Microphone | `/dev/snd/pcmC0D0c` | PRESENT | Real ASR possible |
| Video tooling | `/usr/bin/ffmpeg`, `/usr/bin/v4l2-ctl` | PRESENT | v4l2 + ffmpeg paths valid |
| OCR | `tesseract` | **MISSING** | OCR features cannot be REAL |
| LAN scan | `nmap` | **MISSING** | Camera LAN discovery cannot run |
| Browser engine | `google-chrome*`, `chromium*` | **MISSING** | `browser_tool.CHROME_BIN is None` → browser features dead |
| Wayland input | `wtype`, `wl-copy`, `wl-paste`, `grim`, `slurp` | PRESENT | Computer control CAN be real |
| X11 input | `xdotool` | MISSING | Wayland path is the only valid one |
| Sandboxing | `/usr/bin/bwrap`, `/usr/bin/systemd-run` | PRESENT | Real isolation available (vs blacklist filtering) |
| Rust toolchain | `cargo`, `rustc` | PRESENT | Rust fabric possible |
| Python env | `~/.hermes/hermes-agent/venv` (pytest, fastapi) | PRESENT | Canonical runtime + test env |
| Pkg managers | `uv`, `poetry`, `bun`, `docker`, `podman` | **MISSING** | No container isolation; `npm` via mise only |
| Agent CLIs | `hermes`, `codex`, `claude`, `opencode` | PRESENT | 4 real workers |
| Agent CLIs | `deepseek`, `openclaw`, `frontier`(PATH) | **MISSING** | Registry `installed:true` for deepseek/openclaw = FALSE |
| Frontier | `~/Work/FrontierAgent` + `.venv` (module `apodex`) | PRESENT | Registry `installed:false` = FALSE |
| ASR daemon | `voxtype.service` (Parakeet, `/run/user/1000/voxtype/audio.sock`) | RUNNING | Real ASR exists, zero repo references |
| Model gateway | 9Router `:20128` | **REMOVED BY OWNER (intentional)** | Residue must be purged, not restored |
| Local model srv | LM Studio `:1234` | DETECTED | Dispatchable but never selected |

## 2. Runtime processes and ports

| Port | Process | Evidence |
|---|---|---|
| 2981 | `aegis-backend.service` → venv python `backend/server.py` | `Environment=AEGIS_BACKEND_PORT=2981` |
| 1234 | LM Studio | probed |
| 18789 | `openclaw-gateway.service` | systemd |
| 20128 | 9Router | **nothing listening (removal confirmed)** |

The UI is served by the backend's own `StaticFiles` mount (`backend/server.py:2322`) on **2981**.
`aegis-frontend.service` = `ExecStart=/usr/bin/true` → reports `active (exited)`, serves nothing.
`vite.config.ts` dev server also claims **2981** (collides with the backend) and proxies `/api` + `/ws`
to **8787**, where nothing listens → dev mode cannot function.

## 3. Subsystem status matrix (pre-repair)

| Component | Location | Entrypoint | Callers | State/Storage | UI | Governance | Status |
|---|---|---|---|---|---|---|---|
| Chat | `server.py:2233` | `/api/chat` | ChatPanel | mem0 write | yes | cookie | **REAL** (OpenRouter-only) |
| Model router (roles) | `model_router.py` | chat + planner | 4 call sites | none | ModelsPanel | none | **PARTIAL** — IDs use removed 9Router `cl/` ns, so each call 400s then round-robins |
| Free router | `free_router.py` | all LLM calls | server, harnesses | cooldowns in RAM | yes | none | **REAL**, 1 effective provider (no `GROQ_API_KEY`); `lmstudio/` never selected |
| Camera registry | `camera_registry.py` | `/api/cameras` | CamerasPanel | `config/cameras.json` | yes | partial | **CONTAMINATED** — 3/3 rows test residue; `mock://uri` authorized:true |
| Camera events | `camera_event_store.py` | vision loop | none | `vision_events.json` | no | none | **PARTIAL** — `evt-test` pollution; no WS producer |
| Vision model | `vision_engine.analyze_image_with_model` | none | **none** | none | no | none | **DEAD** (zero callers) |
| Vision pipeline | `vision_pipeline.py` | none | **none**; import-broken | none | no | none | **DEAD** |
| Screen intel | `screen_intel.py:158` | GET `/api/screen*` | UI | none | yes | **none — GET unauthenticated** | **BROKEN+MOCK** — posts to dead `:20128`; except-path returns `success: True` |
| Voice | `audio_engine.py` | `/api/voice/status` | VoicePanel | none | yes | none | **MOCK** — `fake_audio_data` + hardcoded transcript; real voxtype unwired |
| Browser | `browser_tool.py` | GET `/api/browser/*` | UI | temp files | yes | **none — GET unauthenticated** | **BROKEN** — no chrome; scheme-only URL validation permits localhost/RFC1918 SSRF |
| Computer control | `computer_control.py` | agent_moe tools | agent_moe | none | no | bypassed | **PARTIAL** — `type_text`/`press_key`/`launch_application` skip governance |
| Sandbox | `code_sandbox.py` | `/api/sandbox/execute` | UI | tmpdir | yes | cookie only | **PARTIAL** — substring blacklist is not isolation; `bwrap`/`systemd-run` unused |
| Agent PTY | `agent_pty.py` | `/ws/agent/{name}` | AgentTab xterm | **RAM dict only** | yes | none | **PARTIAL** — nothing survives restart; no watchdog/respawn |
| deepseek / openclaw | `agent_runner.py` | PTY launch | SessionManager | none | yes | none | **BROKEN** — registry cmd `python3 -m backend.agent_runner --agent <same>` = self-recursion |
| Frontier | `frontier_adapter.py` | `/api/frontier/*` | UI | `~/.temporary-aegis/frontier_runs` | yes | cookie | **PARTIAL** — registry cmd `python -m apodex -p <task> --mode react\|agent_team` unrenderable; `installed:false` wrong |
| Governance | `governance.py` | `/api/governance/*` | **only 3 agent_moe tools** | `config/governance.json` | yes | — | **PARTIAL** — autonomy_level 1; browser/camera/computer/sandbox/exec unwired |
| Memory (4 impls) | `memory_engine`, `mem0_engine`, `turboquant_store`, `knowledge_graph` | 6+ routes | chat, UI | JSON files | yes | none | **PARTIAL** — no canonical read path; `turboquant_store` is keyword search branded semantic |
| Ingestion | `universal_ingest`, `aegis_ingest_all`, `aegis_consolidate` | timers | none | vault md | indirect | none | **REAL** (jobs succeed) but vault rewritten ~96x/day |
| Event bus | `broadcast()` `server.py:328` | `/ws` | `src/lib/api.ts` | none | partial | none | **STUB** — 2 of ~7 message types produced; peripherals emit nothing |
| Scheduler | systemd user timers | none | none | journal | no UI | none | **DUPLICATED** — see section 4 |
| Tests | `tests/` | pytest (venv only) | none | **writes production state** | no | none | **POLLUTING** — camera tests write prod `cameras.json`/`vision_events.json` |

## 4. Scheduler reality

| Unit | Schedule | Verdict |
|---|---|---|
| `aegis-consolidate.timer` | `OnUnitActiveSec=15min` + `OnBootSec=30s` | Duplicate co-timer |
| `aegis-consolidate-daily.timer` | same service; `OnCalendar=15:00` **and** `OnUnitActiveSec=15min` | **REDUNDANT** — daily clause subsumed; ~96 vault rewrites/day |
| `aegis-ingest.service` + `.timer` | both in `default.target.wants` | Runs at boot **twice** + daily 04:00 |
| `aegis-learn.timer` | Mon 04:00 | REAL (journal: 19 projects, 119 nodes, 211 edges) |
| `aegis-learn-loop.timer` | `*:0/30` | **DEAD** — on disk, `disabled`, absent from `timers.target.wants` |
| `aegis-snapshot.timer` | boot + daily | REAL (`memory/pc-state/2026-09-30.md`) |
| `aegis-backend.service` | `After=… 9router.service`; `Description=…port 8787` | **STALE** — unit absent; real port 2981 |
| `aegis-frontend.service` | `ExecStart=/usr/bin/true` | **FAKE** |
| `aegis-consolidate-shutdown.*` | referenced by nothing | DEAD |

Journal verdicts: ingest OK, consolidate OK, learn OK, snapshot OK — batch/memory tier healthy;
the rot is concentrated in peripherals, actuators, realtime and state truthfulness.

## 5. Data-location reality

Runtime state lives outside the repo in `~/.temporary-aegis/` (`cfg.AEGIS_DIR`); knowledge lives in
`~/ObsidianVault/` (2,351 markdown files). Observed contamination at baseline: `cameras.json` holds
test rows (`TestCam2` / `mock://uri` authorized+vision_enabled, two `Integrated Camera (cert run)`),
`vision_events.json` holds duplicated `evt-test` rows, and vault notes still describe the removed
9Router gateway as live (written by `aegis_consolidate.py` seed text).
