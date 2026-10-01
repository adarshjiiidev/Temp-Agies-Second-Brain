# AEGIS Phased Repair TODO — seeded 2026-09-30 from the forensic audit

Source of truth: `docs/AEGIS_FORENSIC_AUDIT_2026-09-30.md` (findings F-01…F-19), `docs/AEGIS_DEFECT_REGISTER.json` (D-01…D-25), `docs/AEGIS_FEATURE_MATRIX.md` (50 features), `docs/AEGIS_ACTUAL_ARCHITECTURE.md`.
This file **supersedes the phase list in `TODO.md`**, whose Phases 1–5 and 7.1–7.3 are marked `[x]` but are demonstrably incomplete (audit §3). Do not delete `TODO.md` — it is the historical record; add a pointer to this file at its top instead.

## Governing rules

1. **No component may report a status it has not measured.** Every fix is "replace the literal with a probe, then make the probe pass." A red light is a success; a fabricated green is a defect.
2. **P0 must finish before any P1–P5 fix is accepted** — until the reporting layer is truthful, "fixed" is unfalsifiable.
3. **Delete or downgrade a fake rather than leaving it green.** Prefer removing `multica.coord` over writing a shim that pretends.
4. **Every task carries a `verify` command.** A task is `[x]` only when its verify command exits 0 on this host. No "verified visually".
5. **Never let a test write production state** (`~/.temporary-aegis/`, `~/ObsidianVault/`, `~/.config/systemd/`). That is how D-07 happened.
6. Read-only invariant while investigating: no POSTs, no restarts, no builds.

## Phase overview

| Phase | Goal | Defects | Depends on | Est. |
|---|---|---|---|---|
| **P0** | Make status reporting truthful (stop fabricating success) | D-01 D-02 D-03 D-04 D-12 D-17 | — | 1 day |
| **P1** | Privacy + governance boundary integrity | D-05 D-07 D-08 D-09 D-25 | P0 | 1–2 days |
| **P2** | Model fabric truth (finish the 9Router removal) | D-10 D-11 D-20 | P0 | 1 day |
| **P3** | Memory unification + thawing frozen stores | D-13 D-14 D-15 | P0, P1(D-12) | 2–3 days |
| **P4** | Wiring, scheduling, events, dev-mode | D-16 D-18 D-21 D-22 | P0 | 2–3 days |
| **P5** | Portability, dead code, single source of truth | D-19 D-23 D-24 | P2, P4 | 1–2 days |
| **P6** | Regenerate all documentation from code | audit §5 | P0–P5 | 1 day |

Order: **P0 → P1 → P2 → P3 → P4 → P5 → P6**; only P4 may overlap P2/P3.

## Phase P0 — Truthful reporting (blocking; do first)

**Why first:** 11 of 50 features report success while not functioning (matrix summary), and the surfaces that would reveal it are themselves literals.

- [ ] **P0.1 Stop `screen_intel` from lying** (D-01, F-01)
  - `backend/screen_intel.py:154-176`: the `except` branch returns `"success": True`. Return `{"success": False, "error": "<type>: <msg>", "degraded": true}` and keep OCR/window text under a separate `"summary"` key so partial data stays usable but honestly labelled.
  - Delete the dead `127.0.0.1:20128` POST; either call `free_router.query_free_chat()` for image+text or return `"model_analysis": "unavailable"`.
  - *verify:* `curl -s localhost:2981/api/screen/intel | python3 -c "import json,sys;d=json.load(sys.stdin);assert d.get('success') is False or d.get('model_analysis');print(d.get('error',''))"`
- [ ] **P0.2 Make `/api/system/graph` computed** (D-02, F-02)
  - Replace the 10 hardcoded `"status": "PASS"` literals (`server.py:1027-1033, 1036, 1039-1040`) with the Doctor's probes (`Path(...).exists()`, adapter `is_available()`, `governance.current_level`, store record counts).
  - Status vocabulary: `PASS` (probe true) / `DEGRADED` (works, dependency missing) / `NOT_CONFIGURED` (absent by design) / `FAIL` (probe errored). **`PASS` must never be a field's default.**
  - Keep node/edge shape stable so `SystemGraphPanel.tsx` needs no change; add `probed_at` per node.
  - *verify:* `curl -s localhost:2981/api/system/graph | python3 -c "import json,sys;s=[n['status'] for n in json.load(sys.stdin)['nodes']];print(s);assert 'NOT_CONFIGURED' in s or 'FAIL' in s"`
- [ ] **P0.3 Remove Doctor literals; add a real ingest probe** (D-03, F-02)
  - Delete `chk("AEGIS Core", True, …)` / `chk("Backend API", True, …)` (`server.py:1104-1105`); probe the port and a request counter instead.
  - `ingest_daemon.running` (`server.py:1162`) is a flag, not evidence. Add `last_poll_at` / `items_ingested` counters and report `NOT_IMPLEMENTED` while all four loops are `pass` (`ingest_daemon.py:46-60`).
  - Add `NOT_IMPLEMENTED` to the Doctor vocabulary and render it in `DoctorPanel.tsx`.
  - *verify:* `curl -s localhost:2981/api/health/doctor | python3 -c "import json,sys;n=[c['name'] for c in json.load(sys.stdin)['checks'] if c['status']=='NOT_IMPLEMENTED'];print(n);assert n"`
- [ ] **P0.4 Kill fabricated skills, fix the real registry** (D-04, F-03)
  - Delete the duplicate `@app.get("/api/skills")` at `server.py:978-999` (unreachable — `:891` wins) together with the three injected demo skills.
  - Fix the root cause: `Failed to parse Hermes skill manifest: Expecting value: line 1 column 1` — make `skill_registry` skip-and-log per file instead of aborting the whole scan.
  - Return `{"skills": [...], "source": "skill_registry", "degraded": false, "unreadable": []}`.
  - *verify:* `curl -s localhost:2981/api/skills | python3 -c "import json,sys;ids=[s['id'] for s in json.load(sys.stdin)['skills']];assert 'multica.coord' not in ids;print(len(ids))"`; `grep -c '@app.get("/api/skills")' backend/server.py` must be `1`.
- [ ] **P0.5 Fix the token gate so legitimate UI writes work** (D-12, F-11)
  - `POST /api/memory/mem0/add` and `/api/sandbox/execute` are rejected now (`aegis.log` 09-29 22:14, 09-30 17:43). Choose **one** CSRF strategy for all mutating routes (double-submit cookie or `Origin`/`Sec-Fetch-Site` check) instead of a cookie scoped to `/api/chat`.
  - Keep `POST /api/chat` local-only; do not weaken it while doing this.
  - *verify:* reload the dashboard, trigger a memory add and a sandbox run, then confirm `grep -c 'bad/missing token' ~/.temporary-aegis/logs/aegis.log` did not increase.
- [ ] **P0.6 Remove the always-green frontend unit** (D-17, F-13)
  - `aegis-frontend.service` is `ExecStart=/usr/bin/true` reporting `active (exited)`, and `aegis_health.py:120` probes exactly this class of unit. Delete it (the backend already serves `dist/` via `StaticFiles`) or make it really serve the SPA.
  - Point the health check at `GET /api/health`, never at `systemctl is-active <name>` alone.
  - *verify:* `systemctl --user cat aegis-frontend.service 2>&1 | head -3` shows absent or a real `ExecStart`.
- [ ] **P0.7 Gate — P0 exit criteria**
  - [ ] `grep -rn '"PASS"' backend/server.py` matches only probe-derived expressions
  - [ ] removing a dependency flips its node/doctor row off `PASS` (test by temporarily pointing `AEGIS_VAULT_PATH` at a missing dir)
  - [ ] `scripts/audit_truthfulness.sh` runs all P0 verifies and is itself surfaced in the Doctor as "Self-audit: N checks passed"

## Phase P1 — Privacy and governance boundary integrity

**Depends on:** P0, so that "governed" becomes a measured state rather than an aspiration.

- [ ] **P1.1 Purge test residue from the camera registry** (D-07, F-07 — highest-severity privacy item)
  - Live state to remove: `cam-2d077c85` name `TestCam2` uri `mock://uri` with `authorized: true`, `vision_enabled: true`, plus duplicate `Integrated Camera (cert run)` rows on `/dev/video0`. Locate the file with `grep -rl TestCam2 ~/.temporary-aegis` and delete only rows whose `uri` starts with `mock://` or whose name matches `cert run|TestCam`.
  - Make the killswitch durable — today it is RAM-only, so a restart re-arms capture for every authorized camera. Persist `armed: false` and require an explicit re-arm.
  - Audit-log every authorization change (route, decision, timestamp) to `~/.temporary-aegis/logs/camera_auth.log`.
  - *verify:* `curl -s localhost:2981/api/cameras | python3 -c "import json,sys;n=[c['name'] for c in json.load(sys.stdin)['cameras']];print(n);assert not any('Test' in x or 'cert' in x for x in n)"`; after a backend restart, `vision_enabled` stays false until re-armed.
- [ ] **P1.2 Stop tests writing production state** (D-25, root cause of F-07)
  - Give `camera_registry` an env seam (e.g. `AEGIS_CAMERA_REGISTRY`) and point `tests/test_camera_e2e.py` at `tmp_path`; add a session fixture that fails when a test touches `~/.temporary-aegis` or `~/ObsidianVault`.
  - Repoint or delete `tests/benchmark_models.py:41` (benchmarks the dead `:20128`, writes `docs/MODEL_FABRIC.md`).
  - Install `pytest` into the interpreter actually used and record the command in `AGENTS.md`.
  - *verify:* `grep -rn '20128' tests/` empty; the guard fixture raises when a test writes outside `tmp_path`.
- [ ] **P1.3 Make governance actually govern** (D-08, F-06)
  - Fix the inverted logic at `execution_core.py:190` and `frontier_adapter.py:95`: `if auto_approve and not authorize(...)` only seeks approval when the user already said yes. Call `authorize()` unconditionally and let the autonomy level decide.
  - Add `governance.authorize()` to the ungoverned side-effecting entry points: `agent_pty` start (`/api/pty/start`), `code_sandbox.execute`, `browser_tool` fetch/screenshot, `/api/run-script`, and the unwired `computer_control` routes before they ship.
  - Write a decision ledger (`~/.temporary-aegis/logs/governance.jsonl`: action, level, decision, ts) and expose `GET /api/governance/decisions` so the Autonomy panel shows real evidence.
  - *verify:* `grep -rn 'governance.authorize' backend/ | wc -l` ≥ 8; start a PTY session at level `readonly` and see a `DENY` in the ledger.
- [ ] **P1.4 Close the unauthenticated actuator GETs** (D-09, F-16)
  - `GET /api/browser/{extract,screenshot,dom}` (`server.py:805-815`) trigger a real headless-Chrome fetch with no token, and `security.py:47` allow-lists the whole governance family. Convert these to POST and require the token on all actuator routes.
  - Add a URL policy denying loopback/link-local ranges and every port owned by AEGIS's own fabric (2981, 1234, 8787) so the browser tool cannot probe its own system.
  - *verify:* `curl -s -o /dev/null -w '%{http_code}' 'localhost:2981/api/browser/extract?url=http://127.0.0.1:1234/'` → 401/403; with a valid token it returns a denied-host error.
- [ ] **P1.5 Voice must fail loudly** (D-05, F-04)
  - `backend/integrations/voicestudio/adapter.py:20` returns `b"fake_audio_data"` and `transcribe` returns a hardcoded sentence, both behind live POST routes.
  - Preferred: raise `NotImplementedError` → `501 {"error":"voice provider not configured"}` and render "not configured" in the UI instead of a transcript.
  - Cheapest real win (separate ticket, not a blocker): bridge the already-running voxtype daemon at `/run/user/1000/voxtype/audio.sock`.
  - *verify:* `curl -s -o /dev/null -w '%{http_code}' -X POST localhost:2981/api/voice/transcribe` → 501; `grep -rn 'fake_audio_data' backend/` empty.
- [ ] **P1.6 Gate:** registry clean + durable killswitch; ≥8 governed call sites with a visible ledger; actuator GETs denied; voice 501; test-isolation fixture green.

## Phase P2 — Model fabric truth (finish the 9Router removal)

**Depends on:** P0. P3 provenance and P6 docs both cite model IDs, so they wait on this.

- [ ] **P2.1 Replace the 8 dead `cl/` IDs** (D-10, F-08)
  - `backend/config.py:72-91` (`MODEL_DEFAULT`, `MODEL_REASONING`, `MODEL_FAST`, `MODEL_LITE`, `FREE_CHAT_MODELS`) → IDs that exist in `GET /api/models`. Four of the current slugs appear nowhere in the repo.
  - Add a startup assertion that every configured ID resolves through the router's candidate builder; log the offender and fall back to `auto` (never crash, never silently passthrough).
  - Fix the wasted-request bug: `free_router.py:489-495` sends an unknown ID verbatim to OpenRouter and then applies a 60 s cooldown. Validate against the candidate list **before** dispatch so role-keyed requests stop burning a guaranteed 4xx.
  - Clean the mirrored copies in `~/.hermes/.env` and `~/.gemini/config/settings.json` so external harnesses stop receiving unresolvable IDs.
  - *verify:* `grep -c 'cl/' backend/config.py` = 0; `grep -rn 'cl/z-ai' ~/.hermes/.env ~/.gemini/config/settings.json` empty; startup log contains `model id assertion: OK`.
- [ ] **P2.2 Make local providers selectable** (D-11, F-09)
  - `free_router.py:313-340` emits only `groq/` and `openrouter/` candidates although dispatch supports `lmstudio/` at `:480-483`; `/api/model-health` reports `lmstudio=detected`, `groq=standby`.
  - Include reachable local providers in `get_round_robin_candidates()` behind an env-configurable `AEGIS_LMSTUDIO_URL` (default `http://127.0.0.1:1234`).
  - Surface the missing Groq key as a Doctor row (`NOT_CONFIGURED`, naming the env var) instead of advertising multi-provider resilience with one live provider.
  - *verify:* `curl -s localhost:2981/api/model-health | jq .providers` lists lmstudio as eligible; with LM Studio serving, a chat turn logs an `lmstudio/` dispatch; Doctor shows `GROQ_API_KEY: NOT_CONFIGURED`.
- [ ] **P2.3 Retire the second router and its fabricated metrics** (D-20, F-08)
  - `model_router.py` is live at `server.py:1448`, `research_engine.py:79,173`, `task_planner.py:84`, and `VERIFIED_MODEL_PROFILES` hardcodes `avg_latency 6.85` / `reliability 1.0`.
  - Preferred: migrate the 3 call sites to `free_router` and delete the module. Any profile metric that must survive has to come from recorded request timings, and the constant must be renamed `MODEL_PROFILE_SEEDS` so the name stops implying verification.
  - *verify:* `grep -rn 'model_router' backend/*.py | grep -v '^backend/model_router.py' | wc -l` = 0.
- [ ] **P2.4 Sweep the remaining 9Router residue** (measured 2026-09-30: 14 files still match `9router|20128`)
  - Backend: `deepseek_harness.py`, `openclaw_harness.py`, `vision_engine.py`, `audio_engine.py`, `screen_intel.py`, `server.py`, `free_router.py`
  - Frontend: `src/components/ModelsPanel.tsx`, `src/components/TopBar.tsx` (rename the `9router-health` fetch + label to provider health)
  - Ops/data: `aegis_consolidate.py` (repo root — **the consolidation prompt still teaches the second brain about the dead gateway**, so the vault re-learns false architecture every run), `build_master_registries.py`, `registries/MODEL_REGISTRY.json` (`9router_url` key), `tests/benchmark_models.py`
  - Rename `GET /api/9router-health` → `GET /api/providers/health`, keeping an alias for one release; drop the `9router_health` WebSocket key (`server.py:2275`).
  - *verify:* `grep -rni '9router\|20128' backend/ src/ aegis_consolidate.py build_master_registries.py tests/ | wc -l` = 0
- [ ] **P2.5 Gate:** `/api/models` and `/api/model-health` agree with config; startup ID assertion in the log; zero 9Router hits outside `docs/` history.

<!--P3-->



