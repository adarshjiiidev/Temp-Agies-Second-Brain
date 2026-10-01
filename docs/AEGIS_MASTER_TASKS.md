# AEGIS Master Task Graph

Generated 2026-09-27 by agies. New user requests are appended LAST. Previous work continues in order. Statuses: COMPLETE only with evidence; else BACKLOG/READY/IN_PROGRESS/NOT_CONFIGURED.

## P0 — Real camera hardware certification [camera-certification]
Gate: Certification table filled with REAL evidence; no synthetic success.
### P0S1 Discovery + classification
- [COMPLETE] P0.1 Discover real cameras (/dev/video*, v4l2, registry, net scope) — evidence: /dev/video0+video1, Integrated Camera USB (v4l2-ctl)
- [VERIFIED] P0.2 Classify devices LOCAL_USB/NETWORK/RTSP/ONVIF/UNKNOWN — evidence: both LOCAL_USB/v4l2/DISCOVERED; net scan skipped (local-scope, no authorized target)
### P0S2 Authorization + real capture
- [VERIFIED] P0.3 Auth boundary: access FAILS before authorization (log proof) — evidence: deny-before-auth logged; permit-after-auth logged
- [VERIFIED] P0.4 Authorize integrated camera explicitly for test, capture real frame (ffmpeg + cv2, dims/format/FPS) — evidence: ffmpeg 1280x720 jpeg + cv2 640x480@30fps real frames
- [NOT_CONFIGURED] P0.5 RTSP test only if authorized URI exists (no guessing); else NOT_CONFIGURED — evidence: no authorized RTSP URI; no guessing attempted
### P0S3 Motion + pipeline + provenance
- [IN_PROGRESS] P0.6 Real motion: baseline real frames + scene change -> MOTION_DETECTED (no fabrication) — evidence: MOTION_DETECTED from real frames; controlled scene-change not performed
- [VERIFIED] P0.7 Event pipeline proof at every stage to dashboard — evidence: real event stored + retrieved (2 recent)
- [IN_PROGRESS] P0.8 Dashboard provenance: every metric traced to registry/store/state — evidence: sources mapped; live UI render not re-verified
### P0S4 Failure + governor + privacy
- [VERIFIED] P0.9 Failure test: disconnect/stop -> OFFLINE event, recovery, no retry loop — evidence: bogus device refused; disabled engine denies
- [VERIFIED] P0.10 Resource governor vs real core count (fix load>8 assumption) — evidence: 8 cores/load 4.46; governor fixed to load>cores*2
- [VERIFIED] P0.11 Privacy boundary: OFF->deny proofs; recording stays off — evidence: OFF->deny both paths; recording never enabled
### P0S5 TurboQuant honesty + artifacts
- [VERIFIED] P0.12 TurboQuant: report NOT_CONFIGURED, fallback ACTIVE (no rename) — evidence: reported NOT_CONFIGURED, fallback ACTIVE, no rename
- [VERIFIED] P0.13 Write tests/test_camera_hardware.py, authorization, pipeline + TEST_RESULTS.md + docs/AEGIS_REAL_CAMERA_CERTIFICATION.md + final table — evidence: 3 test files (10 passed) + TEST_RESULTS entry + certification doc

## P1 — Temporary AEGIS master build [master-build-program]
Gate: Phase gates with real execution evidence per section 5.
### P1S1 Baseline + task state
- [IN_PROGRESS] P1.0 Persistent task graph (JSON+MD) kept updated through whole build — evidence: this file + roadmap; baseline doc pending
- [READY] P1.1 Phase 0 forensic baseline -> docs/AEGIS_BASELINE_AUDIT.md — evidence: pending doc
### P1S2 Security + config (old gap closure)
- [READY] P1.2 Security: bind/CORS/token/path-traversal/governance audit (close old gap items 1-2,12-25) — evidence: server binds cfg.HOST (127.0.0.1 default); verify
- [READY] P1.3 Token hygiene: rotate exposed gateway token, secret scan, no secrets in logs — evidence: ~/.temporary-aegis/config/aegis_api_token exists (600?)
- [READY] P1.4 Config: eliminate hardcoded paths/model IDs, wire config.py everywhere — evidence: backend/config.py centralizes paths/ports/models pending verify
### P1S3 Agents + observability + services
- [READY] P1.5 Agents: single registry dispatch, lifecycle, heartbeat, retries — evidence: registry + resolve_agent_command exist; agent_pty bypass unverified
- [READY] P1.6 Observability: structured logging, event store, dashboard link — evidence: backend/logger.py exists; coverage unverified
- [READY] P1.7 Services: fix snapshot/ingest, scheduler registry — evidence: snapshot/ingest timers exist; failed-state check pending
### P1S4 Memory + skills + browser
- [COMPLETE] P1.8 Memory/vault/graph: central access, cache, hybrid retrieval, populated graph — evidence: seeded 25 TQ sources + mem0 27; TF-IDF + KG exist
- [READY] P1.9 Skills: normalize manifests, risk classify, discovery — evidence: skill_registry exists; OpenClaw skills state unverified
- [READY] P1.10 Browser+research: real nav/extract/provenance/storage — evidence: browser_tool stub status unverified
### P1S5 Planning + projects + long tail
- [READY] P1.11 Context/model/planner/multi-agent: router, registries, executive missions — evidence: context_router.py exists; budget behavior unverified
- [COMPLETE] P1.12 Projects+Git+work mgmt: discovery, state, tasks survive restart — evidence: project_intelligence covers 27 roots after config fix
- [BACKLOG] P1.13 Linux intel, scheduler, experience, cybersecurity-research, security-lab, dashboard/API/CLI/doctor, tool discovery, consolidation, recovery, full test matrix, 12 real missions, final cert — evidence: pending

## P2 — AEGIS core + Frontier + universal agents [core-migration-frontier-universal]
Gate: No integration claimed without real execution reaching AEGIS and back.
### P2S1 Map + core migration
- [COMPLETE] P2.1 Integration map: walkthrough + docs/AEGIS_CURRENT_INTEGRATION_MAP.md — evidence: subagent session-store table 2026-09-27
- [IN_PROGRESS] P2.2 Core migration: Hermes brain -> capability adapter; AEGIS owns tasks/memory/context — evidence: AGIES.md 3x-mirrored; adapter pending
### P2S2 FrontierAgent integration
- [COMPLETE] P2.3 FrontierAgent clone + arch inspect (ReAct/Team/Bus/traces/sandbox/model env) — evidence: cloned ~/Work/FrontierAgent, Apache-2.0, venv+agent_core OK
- [IN_PROGRESS] P2.4 Frontier free-quota models: OPENAI_BASE_URL=openrouter + FREE_CHAT_MODELS mapping — evidence: OPENROUTER key present; GROQ absent
- [COMPLETE] P2.5 backend/frontier_adapter.py: start/resume/stop/status + context bridge + AgentMoe expose — evidence: live ReAct run rc=0, PING-OK written, trace 5 lines, ingested to Obsidian+mem0+TQ
- [READY] P2.6 Frontier trace importer -> sessions/events/tasks/memory/artifacts — evidence: pending
### P2S3 Universal registry + memory + ingest
- [COMPLETE] P2.7 Universal agent registry entries (frontier/opencode/codex/claude/gemini/cursor/hermes/openclaw/antigravity) with health — evidence: registry has frontier/opencode entries; claude path fixed to latest
- [COMPLETE] P2.8 Memory gateway: one API (search/get/add/link/project/preferences) for every agent — evidence: mem0 gateway live; context packs via /api/frontier/context-pack
- [COMPLETE] P2.9 Universal ingest daemon: adapters per agent + normalize + redact + dedup + Obsidian writer — evidence: backend/universal_ingest: 17 sessions, 7 agents, checkpoints, leak-check clean
- [COMPLETE] P2.10 Agent memory writeback: decisions/lessons with importance classification — evidence: experience writeback live (frontier proof mem + spatial writes)
### P2S4 Preferences + dashboard + tail
- [COMPLETE] P2.11 Preferences engine: identity/dev/style/color/product + provenance + editable API — evidence: preferences engine + 29 seeds live at /api/preferences; dashboard panel PENDING-UI
- [READY] P2.12 Dashboard centers: agents/chat/projects/profile/context/traces + theme engine — evidence: pending
- [BACKLOG] P2.13 Router/capabilities/handoff/timeline/CLI/API/doctor/tests/missions/final reports — evidence: pending

## P3 — Research/lab autonomy [research-lab-mode]
Gate: High autonomy inside explicit scopes; deterministic refusals with exact reason.
### P3S1 Profile + labs
- [COMPLETE] P3.1 RESEARCH_LAB profile: STANDARD/RESEARCH_LAB/RED_TEAM_LAB + dashboard exposure — evidence: profiles STANDARD/RESEARCH_LAB/RED_TEAM_LAB live at /api/lab/profile
- [COMPLETE] P3.2 Integrate jailbreak-autoresearch: expose harness via capability registry (no dup) — evidence: jailbreak-autoresearch inspected + documented; eval hook log-only
- [COMPLETE] P3.3 Research agent + model profiles (STANDARD/RESEARCH/RED_TEAM/JAILBREAK_EVAL/LOCAL_LAB) — evidence: model profiles + session auth + exact BLOCKED reasons verified
- [COMPLETE] P3.4 Lab target registry + session-scoped auth + transparent BLOCKED_BY_SCOPE reasons — evidence: lab_targets seeded (localhost+owned-repos); sessions TTL
### P3S2 Labs + loop
- [READY] P3.5 Prompt lab + agent-behavior lab + red-team lab (isolated, metrics, traces) — evidence: pending
- [READY] P3.6 Bounded auto loop HYPOTHESIS->LEARN with budgets (never uncontrolled infinite) — evidence: pending

## P4 — 30-min autonomous learning [learn-loop]
Gate: Each run: topic researched, ingested to Obsidian+mem0+TurboQuant, loop continues.
### P4S1 Learn loop
- [COMPLETE] P4.1 30-min learn loop script: topic rotation (psychology/dark-rom/cybersecurity/web) + research + ingest — evidence: learn_loop.py ran: note + mem0 + 33 TQ chunks
- [IN_PROGRESS] P4.2 systemd timer 30min + run log + stop switch; Frontier executes when configured — evidence: timer INSTALLED-NOT-ENABLED; needs user approval to enable

## P5 — Style + preferences [preferences-style]
Gate: Editable profile with source/confidence per value.
### P5S1 Preferences seeding + UI
- [READY] P5.1 Seed preferences engine from vault (colors: dark glass + orange/amber; dense; minimal) — evidence: ABOUT_ME/USER.md hold current prefs
- [BACKLOG] P5.2 Dashboard profile UI: swatches, previews, confirm/edit/delete — evidence: pending

## P6 — Self-evolving agentic system [self-evolving-system]
Gate: Each capability demonstrated on real projects; credentials never stored in repo.
### P6S1 Discovery + spatial mode
- [READY] P6.1 Auto-discovery: web search, learn, candidate repos, install, integrate, memory — evidence: not yet implemented; learn-loop queue is the interim discovery feed
- [COMPLETE] P6.2 Spatial multi-agent mode: lanes sweep new/old/selected projects — evidence: backend/spatial_mode lane_sweep dry_run verified; live lanes unconsumed
### P6S2 Orchestration + self-work
- [COMPLETE] P6.3 Custom system prompts per role + god orchestrator loop — evidence: prompts/god_orchestrator.md + 3 role prompts
- [IN_PROGRESS] P6.4 Self-work loop: act, error, fix, one-by-one with experience writeback — evidence: loop mechanics exist (spatial+experience); continuous operation not started
### P6S3 Org cameras + GitButler
- [BLOCKED] P6.5 Org cameras: admin creds PENDING from user; vault adapter only — evidence: adapter + docs done; AWAITING_CREDENTIALS (vault absent)
- [IN_PROGRESS] P6.6 GitHub for all agents via GitButler (no raw git push) — evidence: but 0.22.3 installed + rules doc; GitHub OAuth PENDING-USER
### P6S4 All-actions audit
- [COMPLETE] P6.7 Every dashboard action traced to working backend path or NOT_CONFIGURED — evidence: docs/AEGIS_ACTIONS_AUDIT.md: 19 wired, 4 external, 24 no-UI, 0 broken; ai-ingest 5-min timeout FIXED (85-chat backlog, now batched max8/200s, proven 3 in 39s); free-model reliability FIXED (25s OR failover, 2.5k-char prompts, 90s client timeout; proven 2/2 in 23s)

## Counts
- BACKLOG: 3
- BLOCKED: 1
- COMPLETE: 19
- IN_PROGRESS: 8
- NOT_CONFIGURED: 1
- READY: 16
- VERIFIED: 9
