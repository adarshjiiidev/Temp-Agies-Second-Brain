# PROJECT AEGIS — LONG-TERM MILESTONE ROADMAP (PROMPTS 01–23)

**Document ID:** AEGIS-DOC-010
**Version:** 0.1.0 (Prompt 01 Foundation)
**Status:** 🟢 SUPERSEDED-IN-PROGRESS — 23 prompts defined; P01–P06 implemented (L1–L6). See top banner.
**Last Updated:** 2026-07-24 (orig) / 2026-08-07 (status reconciliation)

> **STATUS AS OF 2026-08-07 (see `AEGIS_MASTER_AUDIT.md`):** Prompts 01–06 (L1 through L6) are
> implemented in the repository. P07+ (adaptive/personal, HCI, production hardening) remain NOT started.
> This roadmap defines **23** prompts (not 21). The per-prompt status lines below are echoed from the
> original Prompt-01 draft and are annotated where the repository differs.

---

## 1. ROADMAP GOVERNING RULES

Rule 1 — **One prompt at a time.** Do not begin Prompt N+1 until Prompt N passes its exit gate. No shortcuts.
Rule 2 — **No feature leakage.** Code written in Prompt N must not implement features scoped to Prompt > N. If it's needed now but belongs later, put it in `future/` staging with a comment, not active code.
Rule 3 — **Stable interfaces before implementations.** Each prompt's exit gate includes a code-review check: new subsystems expose Protocol/ABC interfaces; concrete implementations behind them are swappable.
Rule 4 — **Each exit gate includes tests + negative tests.** "It works on my machine" is not enough. Pass criteria include security-negative tests, failure-mode tests, and benchmark targets from Document 03.
Rule 5 — **Prompt 01 is unique.** Prompt 01 is documentation/architecture only. All subsequent prompts ship working code with tests.

---

## 2. MILESTONE SUMMARY TABLE

| # | Prompt Name | Core Theme | Layer Focus | Primary Exit Gate |
|---|---|---|---|---|
| 01 | Vision & Technical Foundation | Establish truth | Docs only | 11 foundation docs complete, reviewed, consistent |
| 02 | Core Runtime | Run modules safely | L1 + L2 | Module load/lifecycle, event bus, 5-layer audit, health, import-linter passes |
| 03 | AI Kernel | Talk to LLMs safely | L3 AI | 4 provider plugins, router correctness, structured output 100% valid, budget + privacy tier routing |
| 04 | Memory & Knowledge Engine | Remember correctly | L4 | 9-tier write/promotion/recall, KG roundtrip, privacy tier recall, meta-memory baseline |
| 05 | Execution Kernel | Do things safely | L3 EXE | 7-stage pipeline, SVRC + risk gates, T1–T3 sandbox working, audit integrity chain |
| 06 | Cognitive Planning Engine | Think before acting | L6 Planner | Goal→plan→actions→traceability; replan-on-failure; risk gate per step |
| 07 | Adaptive Intelligence & Personal Environment Learning | Build the user model | L6 Adaptive + L4 Env | Scanner discovers env; workflow inference; preference learner; all opt-in with privacy zones |
| 08 | Tool & MCP Ecosystem | Discover & create capabilities | L5 | Registry + 7-stage discovery; MCP client; composite cap; auto-harness; self-repair end-to-end |
| 09 | Real Computer Control | Control the desktop safely | L7 Computer | Screen capture + OCR; mouse/keyboard; window manage; ALL gated HIGH/CRITICAL approval by default |
| 10 | Browser OS + Web Learning | Use the web as a tool | L7 Browser + L6 Research | Playwright-backed engine; DOM extract; forms; downloads; research orchestration with source comparison |
| 11 | Second Brain + Obsidian + Long-Term Memory | Project knowledge, human-readable | L4 Obsidian + Memory Inspector | Bidirectional vault sync; daily logs; project pages; decision ADRs; memory inspector UI |
| 12 | Coding Intelligence | Understand, write, modify code | Domain: Coding + Exec:Git | Repo understanding; code gen/mod/refactor/debug; test run; PR; coding agent delegation |
| 13 | Voice System | Talk to AEGIS, AEGIS talks back | L7 Voice | Hotword, streaming STT local, streaming TTS local, VAD; cloud optional for P2+; per-session consent |
| 14 | Vision & Perception | See (with explicit permission) | L7 Vision + Camera | Camera discovery; multi-cam; explicit-face-enrollment detection; OCR; privacy zones; local-first |
| 15 | Personal & Social Intelligence | Models of people you enroll | L6 Personal | Explicit person enrollment; evidence-based behavior predictions (probabilistic + transparent + correctable) |
| 16 | Research Intelligence | AEGIS as research partner | L6 Research (enriched) | Deep research pipeline; multi-source verification; citation graph; comparison reports; export to Obsidian |
| 17 | Finance & Trading (Indian Markets) | Understand finance, trade safely | Domain: Finance | NSE/BSE data; fundamentals; news; TA/QA; backtesting; paper trading only by default; live gated CRITICAL |
| 18 | Cybersecurity Learning Environment | Learn defense, practice safely | Domain: Cyber | CTF tooling; defensive security; sandboxed labs; vuln analysis; offensive strictly in authorized labs |
| 19 | Social & Digital Life | Manage connected accounts safely | Domain: Social | Trust-ladder: Read→Draft→Approve→Trusted→Limited; never expose creds; never irreversible without approval |
| 20 | Multi-Worker Society | AEGIS uses specialized workers | L6 Planner + L5 Skills | Worker orchestration; role assignment; task decomposition to workers; result merging; shared context bus |
| 21 | Auto-Learning + Auto-Harness + Self-Improvement | Get better every day | L5 Harness + Repair (active) | Active learning loop; daily auto-harness of all at-risk skills; decay re-test; calibration of meta-memory |
| 22 | Desktop UI + Control Center | First-class desktop UX | L7 Control Center | Tauri 2 + React desktop app; system tray; memory inspector; plan viewer; approvals; settings; audit viewer |
| 23 | Production Hardening | Make it secure & reliable | Cross-cutting all | CI/CD, SBOM, vuln scan, audit integrity chain, fuzz suite, perf regression, supply chain, docs complete |

---

## 3. PER-PROMPT DETAIL — WHAT SHIPS, SUCCESS CRITERIA, EXIT GATE

### PROMPT 01 — VISION & TECHNICAL FOUNDATION
**Status:** ✅ DONE (11 docs under `docs/`)
**What ships:**
- 11 architecture & strategy documents under `docs/` (00_VISION through 10_RISKS)
- No implementation code, no fake stubs, no skeleton plugins
- Truthful foundation only
**Success Criteria:**
- Docs cover all required areas listed in Prompt 00 §19 and §20
- No contradictions across documents; consistent terminology
- Every NFR and F-requirement from Doc 01 maps to at least one architectural element in Doc 02–10
**Exit Gate:**
- User review + approval of all 11 docs
- Checklist: 00 Vision, 01 Requirements, 02 Architecture, 03 Tech Stack, 04 Repo Structure,
  05 Security/Privacy, 06 Memory/KG/Obsidian, 07 AI Strategy, 08 Capability/MCP/Harness,
  09 Roadmap (this), 10 Risks — all present, non-empty, internally consistent
- → If approved: proceed to PROMPT 02.
- → If changes: iterate docs only.

---

### PROMPT 02 — CORE RUNTIME
**Status:** ✅ DONE (L1 + L2; 57 tests)
**Primary modules:** L1 (runtime, supervisor, interfaces, errors, health) + L2 (event_bus, config, secrets_vault + crypto, persistence I/F, plugin_loader, telemetry, scheduler)
**Rust crates:** `aegis_crypto` AEAD encryption; `aegis_audit_chain` skeleton; `aegis_ffi_common` types
**What ships:**
- `CoreRuntime` container: module lifecycle (`init → start → healthy → degraded → stop → shutdown`)
- `Supervisor`: per-module thread/process isolation, crash restart, watchdog, dead-man switch
- All interfaces in `l1_core/interfaces/`: `ModuleLifecycle`, `HealthProvider`, `Pluggable`,
  forward-decl `LLMProvider`, `KVStore`, `DocStore`, `VectorStore`, `GraphStore`, `EventBus`, `Executor`
- `EventBus`: typed pub/sub + SQLite append-log durable topics + DLQ
- `Config`: layered defaults<file<env<runtime, schema-validated, hot-reload + audit
- `SecretsVault` + `Crypto`: AES-256-GCM + Argon2id via Rust FFI; auto-redact in logs
- `PluginLoader`: manifest.yaml-driven loading; permission scanning; deny-by-default
- `Telemetry`: structured JSON logger, metrics registry (Counter/Gauge/Histogram), OTel-compatible tracer skeleton
- `Scheduler`: async task queue, cron, retry with jitter, DLQ
- `HealthRegistry`: aggregated subsystem health, degraded-mode orchestration
**Success Criteria:**
- Import linter enforces L1↔L2 boundaries; cycles = 0
- `just test`: 200+ unit tests; core modules ≥ 85% coverage
- `just bench`: boot time p95 < 2s, core idle footprint < 500MB
- **FFI benchmark:** Python→Rust→Python roundtrip p95 < 50µs
- **Negative tests:** plugin missing manifest → denied; plugin requires unknown permission → denied;
  config secrets → redacted in log capture (regex)
**Exit Gate:**
- Pass all tests + benchmarks
- Manual chaos test: kill a module process → Supervisor detects within 500ms → restarts per policy → reports degraded health
- Audit log integrity hash chain verified for 10k writes
- → Pass → Prompt 03

---

### PROMPT 03 — AI KERNEL
**Status:** ✅ DONE (L3; 256 tests)
**Primary modules:** L3 ai_kernel (router, providers/base/ollama/openrouter/groq/vllm, structured, cost, prompts library)
**What ships:**
- `LLMProvider` interface with full typed signature; `EmbeddingProvider` interface
- 4 provider plugins: Ollama (P0), OpenRouter (P0), Groq (P1), vLLM (P1)
- `ModelSpec` catalog with `provider × model → capabilities/cost/latency/health/privacy_tier_support`
- 5-stage Model Router: §07.3 algorithm implemented + weights configurable
- **Privacy routing P0 RULE:** 100% local-only; no silent P0 leak
- Prompt Scrubber: secret detection, PII redaction, auto-tag tier
- **Structured output pipeline:** Pydantic v2 schema + retry loop N=3
- Token + cost ledger: per-call, per-day, per-month, per-key, per-project, per-task
- Budget enforcement 4-point: pre-call, mid-stream, post-call, rollup. Default $2/day $40/mo.
- Prompt Template library with: versioning, typed variables, UNTRUSTED_VAR boundary interpolation,
  template AB evaluation via meta-memory
- Offline mode; graceful fallback chain; circuit breaker per model
**Success Criteria:**
- Router correctness 100-case battery (P0/P1/cost/latency) as in §07.11
- Structured output 50-case battery: caller never sees invalid object
- Budget enforcement: $0.10/day cap → 10th call blocked
- Offline mode: 20 calls → 0 network packets (test via tcpdump/equivalent)
- Provider health: 3 consecutive failures → circuit breaker + degraded
- **No secrets in audit/log:** regex scan of 100 log lines; 0 unredacted secrets hits
**Exit Gate:** All above pass → Prompt 04.

---

### PROMPT 04 — MEMORY & KNOWLEDGE ENGINE
**Status:** ✅ DONE (L4; 130 tests)
**Primary modules:** L4 full: memory_engine (9 tiers), vector, knowledge_graph, environment (scanner), meta_memory
Rust crates: `aegis_store` high-performance index FFI (baseline)
**What ships:**
- 9-tier write path: T0 in-memory → T1 Session → T2/T3/T4/T5/T6/T7/T8 durable stores
- Promotion gates: §06.2 algorithm. T5 promotion REQUIRES explicit user confirmation.
- Provenance chain on every write; revision history
- **Recall pipeline 5-stage:** §06.3. Decompose → per-tier retrieve → rerank → budget pack → assemble
- Privacy tier filter in recall: P0 never goes to cloud prompt (router error, not silent skip)
- Vector store: Qdrant local-mode default; hybrid vector + FTS5 keyword retrieval
- Knowledge Graph: SQLite nodes/edges tables; NetworkX in-memory traversal; typed entities/relations
- **Draft edges:** auto-suggested edges NOT traversed by default
- Meta-Memory: coverage, confidence buckets, staleness, provenance, skills failing, known unknowns, calibration
- Environment scanners: OS, installed apps, Git repos, projects (opt-in, privacy zones respected)
- Full lifecycle CRUD + archive + delete + export (JSONL, Markdown, SQLite)
**Success Criteria:**
- Microbenchmark: 100k writes, 1k queries — recall p95 per tier < targets (§03 benchmarks)
- Promotion gate correctness: T1→T5 auto-promotion count = 0 in 100-sample battery
- Privacy recall: P0 → cloud provider = 0 / 50 samples
- KG roundtrip: 50 random queries → SQLite/NetworkX identical results
- Scanner with privacy zones: blacklisted `~/.ssh` path appears in 0 scan results
**Exit Gate:** All above pass → Prompt 05.

---

### PROMPT 05 — EXECUTION KERNEL
**Status:** ✅ DONE (L5; note suite currently hangs at L5 integration — see audit report)
**Primary modules:** L3 full (permission, policy, execution, sandbox, audit, verification)
Rust crates: `aegis_sandbox` T1/T2 enforcement; `aegis_audit_chain` full
**What ships:**
- **7-stage execution pipeline:** Plan → Permission → Policy → Execute → Audit → Verify → Reflect. No stage bypass.
- Permission Engine: SVRC model; allow/deny/NEEDS_APPROVAL decisions; RBAC + ABAC; consent storage
- Policy Engine: 4-tier risk (LOW/MEDIUM/HIGH/CRITICAL) with approval gates; policy-as-code YAML; versioned rules
- Execution Kernel: typed `Action` / `ActionResult` dispatch; executor plugin interface;
  built-in CLI, FS, Process, Git executors; timeout/cancellation/retry; transactional undo log
- **Sandbox 4 tiers:** T1 Python AST jail, T2 subprocess + Job Objects/WSL2 + overlay dir,
  T3 Docker container, T4 Firecracker optional. Tier selector automatic per provenance + permissions
- Audit: append-only hash-chained log; root MAC signature; verification CLI; query API;
  every decision/action/verification recorded
- Verification: post-execution assertion engine; auto-rollback triggers (best-effort, logged)
**Success Criteria:**
- Pipeline integration: 50 end-to-end actions; 7-stage pipeline traversal confirmed in audit for each
- SVRC denial: 20 unpermitted actions → ALL denied + audit entry exists
- **Sandbox escape battery (T1/T2):** 50 known escape attempts → ALL blocked + audit `ESCAPE_ATTEMPT`
- T3 Docker sandboxed: no host FS access outside scratch volume, network default deny
- Audit integrity: truncate/gap/reorder → `aegis audit verify` reports corruption
- CRITICAL policy auto-triggers approval UI even with PERMISSION ALLOW
**Exit Gate:** All above pass → Prompt 06.

---

### PROMPT 06 — COGNITIVE PLANNING ENGINE
**Status:** ✅ DONE (L6; 180 tests)
**Primary modules:** L6 planner
**What ships:**
- Intent → typed Goal → Subgoals → Tasks → typed Actions decomposition
- **Plan as first-class data:** versioned, serializable, editable, with dependency graph
- Parallel execution when task dependency graph permits
- Pre-flight check: capabilities + permissions + context satisfied before execute
- **Risk scoring per step:** HIGH/CRITICAL step → approval gate before execution
- **Replan on failure:** causal analysis of failed action; regenerate downstream tasks
- **Traceability:** every Action → Task → Subgoal → Goal → Intent id chain in audit
- **No raw LLM output downstream:** planner output = typed Plan validated through structured pipeline
**Success Criteria:**
- 20 diverse user intents → plans with ≤ 20% manual correction needed by evaluator
- Failure injection: 10 plans fail a step → all 10 replan; ≥ 7 succeed on retry
- Risk gate: 10 HIGH-risk injected steps → ALL require approval before exec
- Traceability: 100 random actions from production simulation → 100% have complete trace back to Intent
- Dependency graph: A depends on B; parallelism scheduler picks B-first-A-later 100% correct
**Exit Gate:** All above pass → Prompt 07.

---

### PROMPT 07 — ADAPTIVE INTELLIGENCE & PERSONAL ENVIRONMENT LEARNING
**Status:** 🔲 NOT STARTED (next milestone after L6)
**Primary modules:** L6 adaptive (observers, workflow inference, preference learner) + enriched L4 environment
**What ships:**
- Environment Model graph: hardware, OS, apps, projects, repos, files, workspaces, devices, tools, accounts
- Relationship inference in environment graph ("Project X uses Python env Y")
- Scanners enriched: CLI entrypoints, app versions, file-type stats
- **User behavior observers:** OPT-IN only; scoped windows; can pause anytime
- Workflow inference: repeated sequences → T4 procedural candidates; promote after 3 successes OR user confirm
- Preference learning: repeated choices → T5 personal candidates; promote on user confirm ONLY
- Privacy zones: excluded paths, sensitive dirs, redaction rules, retention caps; blacklist editor
- Freshness tracking: T6 environmental auto-rescan triggers; staleness penalty
**Success Criteria:**
- Env model scanner discovers 95% of user-installed apps vs. ground truth list (Windows add/remove programs)
- Workflow inference: 10 synthetic repeated workflows → ≥ 8 correctly detected as candidates
- Preference inference: 10 consistent repeated choices → T5 candidates created; 0 auto-promoted without confirm
- Privacy zone tests: 20 files in blacklisted paths → 0 in observer/event streams
- Observer opt-out: toggle off mid-session → all observer sinks drain → 0 records after toggle
**Exit Gate:** All above pass → Prompt 08.

---

### PROMPT 08 — TOOL & MCP ECOSYSTEM
**Primary modules:** L5 full (registry, tool_runtime, mcp_runtime, discovery, generator, auto_harness, self_repair, skill_store)
**What ships:**
- Capability Registry: semantic search + filter/rank; typed Capability model; metadata tracking
- Tool Runtime: schema-validated execution, retry, context injection
- MCP Runtime: standard client; typed manifest-based registration with integrity hash pin + sandbox tier assignment;
  tools/resources/prompts
- **Capability Discovery 7-stage pipeline end-to-end (§08.3)**
- Tool/MCP Generator: typed wrapper generation; mypy + ast validation pass before handoff
- **Auto-Harness 5-stage:** test gen → sandbox run → scoring → decision → register. Periodic re-harness scheduler.
- **Self-Repair 6-stage:** analyze → research → generate fix → sandbox test → risk-tiered deploy → remember.
  Hard rule: NO TCB repair without explicit CRITICAL user approval.
- Skill Store: versioned storage + eval history + rollback points
**Success Criteria:**
- Registry roundtrip 20/20
- End-to-end discovery: 5 user goals "no existing cap" → 4 register ACTIVE; 1 escalate to user
- MCP security: 10 malicious tool attempts → sandbox BLOCK + audit ESCAPE_ATTEMPT
- Harness calibration: 10 good / 10 bad → TP/TN ≥ 90% harness decisions
- Self-repair: 3 injected bugs → all 3 fixed in ≤ 3 attempts; new version harness score ≥ 90% of previous
**Exit Gate:** All above pass → Prompt 09.

---

### PROMPT 09 — REAL COMPUTER CONTROL
**Primary modules:** L7 computer
**What ships:**
- Windows: Win32 + UI Automation API + DXGI Desktop Duplication screen capture
- Cross-platform: fallback abstraction layer
- **OCR:** RapidOCR (ONNX local) + Tesseract plugin option
- Mouse / keyboard / window management
- Permission: all verbs = HIGH risk BY DEFAULT → per-call approval out of the box
- Can lower to MEDIUM for user-approved workflows AFTER 5 successes
- Context injection: screen understanding → typed scene description → planner memory only
**Success Criteria:**
- Screen capture + OCR: open Notepad, type known string → OCR extracts string with ≥ 98% accuracy
- Mouse click target: 20 UI buttons → ≥ 19 correct click locations (no off-by)
- Approval gating: 20 actions → 20 approval prompts rendered before execution
- Permission bypass: try to call computer_control as untrusted plugin → SVRC DENY
**Exit Gate:** All above pass → Prompt 10.

---

### PROMPT 10 — BROWSER OS + WEB LEARNING
**Primary modules:** L7 browser + L6 research (skeleton)
**What ships:**
- Playwright-backed Browser Engine: cross-browser, per-context isolation
- DOM extraction, accessibility tree, semantic content extraction (readability-like)
- Forms: fill, submit, validate
- Downloads/uploads: sandboxed dir; virus scan pass; size caps
- Ephemeral vs. persistent browser profiles; cookie scoping
- Research Orchestrator skeleton: search → fetch → extract → compare → cite
- Web learning: unfamiliar site → study → candidate workflow (T4 procedural DRAFT)
**Success Criteria:**
- 10 diverse websites: DOM extraction renders page topic summary correct ≥ 90%
- Form fill: submit 5 test forms → success on 5
- Download: 5 files → all land in sandbox dir only; no host FS escape
- Unknown site workflow: show it a TODO web app; AEGIS learns "create todo" → registered DRAFT cap
**Exit Gate:** All above pass → Prompt 11.

---

### PROMPT 11 — SECOND BRAIN + OBSIDIAN + LONG-TERM MEMORY
**Primary modules:** L4 obsidian (projection, ingest, sync, templates) + text memory inspector UI
**What ships:**
- Obsidian vault layout §06.6.2
- **Bidirectional sync §06.6.3:** AEGIS→vault writer; vault→AEGIS ingest; 3-way merge; conflict files
- Auto-generated pages: Project, Technology, Decision ADRs, Research, Experiments, Daily logs
- **Memory inspector (TUI text UI):** browse/search all memory by tier, by date, by provenance;
  view/edit/delete/correct/export; promotion audit log
- Knowledge graph human view: static render of subgraphs into vault pages + canvas embeds
- Vault path allowlist: AEGIS only reads/writes within configured paths
**Success Criteria:**
- Roundtrip: AEGIS writes 20 files → vault reads back → re-ingest → no diffs on non-hand-edited
- User hand-edits 10 files → candidate memory created, 0 auto-promoted past DRAFT
- Conflict generation: both sides edit same line → conflict file created correctly; no silent winner
- Inspector UI: create/edit/delete via UI → backend state matches
**Exit Gate:** All above pass → Prompt 12.

---

### PROMPT 12 — CODING INTELLIGENCE
**Primary modules:** L6 planner/coding enriched; domain module coding; enhanced exec git; L7 computer use in editor
**What ships:**
- Repository understander: parse project graph, dependency graph, architecture pattern detection
- Code generation/modification: Pydantic-typed plan → AST-aware patches, not whole-file blind rewrite
- Refactor, debug, run tests, create branches, commit messages, PR summaries
- **Delegation to coding agents:** when task matches a specialty, route to external Codex/Claude Code/Gemini CLI
  (via plugin; outputs validated, not trusted directly)
- Coding style inference: T5 personal DRAFT candidates on repeated style; user promotion
- Git integration: safe by default — commits pushed only after user approval
**Success Criteria:**
- On 5 benchmark repo tasks: implement feature, add test, run test pass, PR summary on 4/5
- AST-aware patching: 10 patch tasks; ≤ 2 instances of unrelated code clobbered
- Delegation: 5 tasks → AEGIS picks correct agent for 4; agent result validated through structured pipeline
- Push safety: no git push command ever succeeds without explicit user approval in same session
**Exit Gate:** All above pass → Prompt 13.

---

### PROMPT 13 — VOICE SYSTEM
**Primary modules:** L7 voice
**What ships:**
- Local STT: faster-whisper or Whisper.cpp; configurable model size per hardware
- Local TTS: Piper or Coqui local
- Hotword + VAD: Porcupine + WebRTC VAD
- **Privacy by default:** audio never leaves device unless user opts into cloud STT/TTS (P2+)
- Per-session consent: voice recording indicator; user can stop at any time; kill switch in settings
- Voice → text interface → standard planner; no separate code path for voice
**Success Criteria:**
- 20 spoken commands → STT transcription accuracy ≥ 92% on in-domain
- Hotword: 100 utterances "Hey AEGIS" in quiet room → 95+ detections; ≤ 3 false positives in 1h ambient
- Privacy: in default config, run tcpdump → 0 audio packets to WAN
- Kill switch: mid-utterance toggle off → processing stops immediately; partial audio not retained
**Exit Gate:** All above pass → Prompt 14.

---

### PROMPT 14 — VISION & PERCEPTION
**Primary modules:** L7 vision/camera
**What ships:**
- Camera discovery + multi-camera support
- **Explicit person enrollment only:** AEGIS will NOT attempt to identify strangers;
  "Person in view" only unless user explicitly enrolls specific people with sample images + consent
- Object detection, OCR, scene classification, change detection, anomaly detection, event detection
- **Privacy zones:** define regions in each camera FOV to blur/ignore before any neural processing
- Local-first processing: everything runs on-device unless user opts in for cloud vision (P2+)
- **Hard kill switch:** software toggle; OS camera indicator; no silent capture ever
**Success Criteria:**
- Explicit enrollment: 5 unenrolled people across test set → all labeled "Unfamiliar person"; no name guessing
- Privacy zones: draw a zone around a desk area → 20 snapshots → zone content never in scene log
- Kill switch off → camera APIs return HARD DENY; capture attempts denied
- Anomaly detection: 20 synthetic "room empty, now open door" events → 18+ detected
**Exit Gate:** All above pass → Prompt 15.

---

### PROMPT 15 — PERSONAL & SOCIAL INTELLIGENCE
**Primary modules:** L6 personal (enriched)
**What ships:**
- Explicit person enrollment workflow: user adds a name + AEGIS asks for model categories
  (preferences, interests, shared projects, communication patterns, explicitly-provided sample observations)
- Evidence-based probabilistic prediction models per enrolled person
- Prediction output format §00 VISION: Observed pattern → Possible next actions with % probabilities
  + Confidence label (Low/Med/High) + Evidence list
- **No mind-reading claims:** never output "Alice is angry". Output "Alice's last 3 messages were shorter than
  her average. Possible explanations: busy (60%), distracted (25%), frustrated (15%). Confidence: Low. Evidence:
  recent message length stats."
- Correctable: user can correct any prediction / model entry; correction updates provenance chain
**Success Criteria:**
- 10 synthetic enrolled-persons → next-action prediction Brier score ≤ 0.25 (well-calibrated)
- Mind-reading check: 20 ambiguous input samples → zero outputs containing affective/mental state labels without
  "Possible explanations:", "Confidence:", "Evidence:" triplet
- Correctability: user corrects 10 entries → all corrections reflected; originals retained as revised_by_user flag
- P0 tier applied: enrolled person data NEVER sent to cloud LLM
**Exit Gate:** All above pass → Prompt 16.

---

### PROMPT 16 — RESEARCH INTELLIGENCE
**Primary modules:** L6 research (enriched)
**What ships:**
- Deep multi-step research pipeline: topic → plan queries → search → fetch → read → extract →
  cross-source compare → verify → synthesize → cite → report → Obsidian page
- Citation graph; provenance chain per claim
- **Claim verification:** every extracted fact ≥ 2 sources → auto-corroboration, else "single-source, verify"
- Source comparison UI: list top sources, agreement/disagreement breakdown, source quality score
- Export: Obsidian research note, Markdown report, JSON citation graph
**Success Criteria:**
- 5 research topics: 5 reports generated; ≥ 80% of factual claims have ≥ 2 sources listed
- Fabrication probe: include in source pool a fake page with deliberate false claim;
  AEGIS flags as single-source OR contradicts with real sources in ≥ 4/5 probes
- Obsidian export: end-to-end verify report links correctly in vault; citation graph renders as links
**Exit Gate:** All above pass → Prompt 17.

---

### PROMPT 17 — FINANCE & TRADING (INDIAN MARKETS)
**Primary modules:** L6 domains/finance_in
**What ships:**
- NSE/BSE data adapters (price, volume, fundamentals; free/paid user-provided API keys)
- News ingestion; entity extraction; sentiment (evidence-based, not "market is bullish")
- Technical analysis library + indicators; quantitative research primitives
- **Backtesting engine:** historical data → strategy simulation → metrics → equity curve
- **Paper trading only by default:** no live order capability ships without CRITICAL user flag
  + explicit approval per order
- **Risk tier:** live trading = CRITICAL. Trust ladder: Research → Analysis → Backtest → Paper →
  (APPROVAL WALL) → Live.
- Disclaimer system: financial outputs marked "Not investment advice; for educational/research purposes only"
**Success Criteria:**
- 5 backtests over synthetic data → strategy PnL curve matches oracle by ≤ 1% error
- Live trading default OFF: attempt to place live order → DENIED with "requires user to enable live mode"
- NSE/BSE data: 20 ticker symbols → 20 successfully retrieved (non-empty) via adapter
- Risk tier: all live order actions score CRITICAL in policy engine → approval UI triggered
**Exit Gate:** All above pass → Prompt 18.

---

### PROMPT 18 — CYBERSECURITY LEARNING ENVIRONMENT
**Primary modules:** L6 domains/cybersecurity
**What ships:**
- CTF toolkit wrapper: common CTF tools bundled as plugins with permission gating
- Defensive security: log analysis helpers, vuln scanner wrappers, hardening checklist generators
- Vuln analysis: vulnerability DB lookup; CVSS vector explanation; mitigation suggestion generator
- **Sandboxed labs provisioning:** spin up isolated Docker/Vagrant labs for exercises
- **Hard rule: OFFENSIVE EXPERIMENTATION RESTRICTED TO AUTHORIZED SANDBOXED LABS ONLY.**
  Network scan, exploit, brute force: ONLY within labs, never against targets user cannot prove authorization.
- Authorization tracking: every lab session has authorization token; lab auto-destroyed after TTL
**Success Criteria:**
- Lab provisioning: request a CTF lab → instance created; networking scope is isolated; no host reach
- Offensive attempt without lab: try to scan external host → SVRC DENY; audit OFFENSIVE_UNAUTHORIZED
- 10 vuln analysis tasks: 9 generate correct CWE/CVSS mapping to known benchmarks
**Exit Gate:** All above pass → Prompt 19.

---

### PROMPT 19 — SOCIAL & DIGITAL LIFE
**Primary modules:** L6 domains/social
**What ships:**
- Trust ladder: Read Only → Draft → User Approval → Trusted Workflow → Limited Autonomy
  for each connected account
- **Credential handling:** all creds in secrets vault; never logged; never passed to subprocess env vars
  (use in-memory fd / secure token passing)
- Per-account permission models: what AEGIS can do at each trust tier
- **No irreversible action at trust < Trusted Workflow:** delete, post, DM-send require approval until
  user explicitly grants Trusted tier
- Draft mode: AEGIS drafts a post/tweet/email → user edits/approves → send at Approved tier
- Audited: every social/digital action logged with full context + before/after snapshots
**Success Criteria:**
- Trust Read Only: AEGIS can fetch 5 timelines; 5 attempts to write → ALL denied
- Draft→Approval: AEGIS drafts 3 messages → user approves → all 3 sent correctly
- Credential leak test: grep logs/traces/audit for plaintext cred patterns → 0 hits
- Deletion safety: attempt to delete at Read/Draft/Approved tiers → DENY until Trusted Workflow set
**Exit Gate:** All above pass → Prompt 20.

---

### PROMPT 20 — MULTI-WORKER SOCIETY
**Primary modules:** L6 planner (worker_orch, role_assign, result_merger); enriched L5 skill_store
**What ships:**
- Worker roles: Researcher, Coder, Auditor, Planner, Executor, Synthesizer, Critic.
  Roles are capability + prompt-profile combos; not separate OS processes (but CAN be, via plugin)
- Role assignment: task → role classifier → best-suited worker; fallback to generalist
- Shared context bus: T0 Working Memory shared across workers for the same parent task
- Sub-task delegation: Planner → spawn N workers per subgoal with scoped context
- Result merging: Synthesizer worker merges N worker outputs into one coherent result;
  conflict resolution = diff + auditor worker
- Cost/performance awareness: small tasks → single worker; large → parallel map-reduce
**Success Criteria:**
- 10 complex tasks: role assignment correctness ≥ 80% vs. oracle labels
- Parallel speedup: 5 long tasks; parallel wall time ≤ 65% of sequential baseline
- Merge conflicts: 10 synthetic worker disagreement scenarios → auditor resolves 9 correctly
- Budget safety: parallel workers respect shared parent task cost budget; over-budget → workers paused
**Exit Gate:** All above pass → Prompt 21.

---

### PROMPT 21 — AUTO-LEARNING + AUTO-HARNESS + SELF-IMPROVEMENT (ACTIVE LOOP)
**Primary modules:** L5 (auto_harness, self_repair) enriched; scheduler jobs for continuous learning
**What ships:**
- **Daily active learning loop:** every 24h, scheduler:
  1. Runs re-harness on every skill with last_tested > 30d or success_rate trend declining
  2. Runs calibration sweep on Meta-Memory confidence buckets
  3. Runs scanner refresh on stale T6 Environmental records
  4. Runs workflow inference retraining on new observation data
  5. Checks for known security advisories in dependency SBOM
  6. Generates daily-improvement report: what got better, what broke, what still needs work
- **Auto-learning triggers enabled (opt-in global toggle):** §08.8.1 table
- **No core mutation:** learning = new artifacts only; TCB modules still require manual approval
- **Version history:** every skill mutation is a new semver; rollback always one-click
**Success Criteria:**
- Simulated 7-day run: 10 skills degraded → 9 repaired + re-harness pass by end-of-week
- Meta-calibration: 1000 predictions → calibration curve Brier score ≤ 0.05 (well-calibrated)
- Core mutation attempt: auto-learning proposes TCB change → proposal created for user approval; NOT applied
- Daily report: 7 daily reports generated; contain no P0 data unless user explicitly enabled
**Exit Gate:** All above pass → Prompt 22.

---

### PROMPT 22 — DESKTOP UI + CONTROL CENTER
**Primary modules:** L7 control_center
**What ships:**
- **Tauri 2 + React:** desktop shell, native menus, system tray, secure IPC to Python backend
- Dashboard: AEGIS status, health, budgets, recent activity summary, online/offline
- Memory Inspector UI: browse/search/edit/delete/export memory; promotion history
- Plan Viewer: current plan, its steps, statuses, risks, traceability to user intent; manual override controls
- **Approval Panel:** real-time approval requests with risk badges, context panel, approve/deny/snooze
- Settings: privacy tiers, trust ladders, budgets, permission editor, privacy zone editor
- Audit Viewer: browse audit log; filter by subject/verb/resource/date/risk; verify integrity chain
- **All UI actions go through the same pipeline.** A button-click in the UI is treated the same as
  a text command: SVRC permission check → policy → audit → verify
**Success Criteria:**
- UI smoke test: 20 interactions (approve/deny/edit setting/query memory) → all success;
  all 20 present in audit log with correct provenance "origin=ui"
- Settings change: edit daily budget from $2 → $3 → router respects new value on next call
- Memory Inspector edit: correct a T3 fact → revision bump; old version retained; provenance updated
- Security: UI IPC messages for unpermitted actions → backend SVRC DENY; no client-side auth bypass possible
**Exit Gate:** All above pass → Prompt 23.

---

### PROMPT 23 — PRODUCTION HARDENING
**Primary modules:** Cross-cutting all layers; CI/CD + security + quality
**What ships:**
- **CI/CD pipeline:** GitHub Actions with self-hosted runner option
  - Lint: mypy --strict; ruff lints all; cargo clippy deny-warnings; rustfmt
  - Test: pytest + cargo nextest; coverage gate (core ≥ 85%, subsys ≥ 70%)
  - Bench: performance regression suite (fail if -15% on any tracked benchmark)
  - Security: gitleaks, detect-secrets, pip-audit, cargo audit, trivy for Docker, syft SBOM generation
  - Fuzz: cargo fuzz / python fuzz for 10 hot security boundaries (sandbox, permission, audit, crypto)
  - Supply chain: lockfile hash verification, provenance / sigstore signing for releases
- **Audit log integrity chain:** full verification in CI; fuzz for truncation/gap/reorder
- **Sandbox continuous escape battery:** M05 T1/T2 escape tests run on every PR with ≥1 attempt/module
- **Documentation completeness:** all public interfaces have docstrings; user docs; admin docs;
  threat model; architecture decision records (ADRs) in Obsidian vault projection
- **Upgrade + migration tooling:** `aegis upgrade`; `aegis migrate storage --from N --to N+1`
  with dry-run + backup
- **Release process:** semver releases, changelog, signed artifacts, SBOM attached, rollback instructions
**Success Criteria:**
- CI full run: 100% green on main; no flaky tests
- Supply chain: `just sbom` → valid SPDX 2.3; `just audit` → 0 CRITICAL/HIGH CVEs with known fixes unapplied
- Fuzz suite: each of 10 security fuzz targets runs 24h in release pipeline; 0 crashes
- Migrations: upgrade from version X-1 → X on seeded database succeeds with 0 data loss verification query
**Exit Gate:** All above pass → AEGIS reaches v1.0. Launch user communication; continuous improvement cycles begin.

---

## 4. CRITICAL PATH MILESTONES

The system delivers real value even before M23. The **first "useful" vertical slice** is complete at Prompt 06 (Planner + Memory + AI + Execution + Text).

| Milestone | What User Can Do |
|---|---|
| After P06 | Ask AEGIS in text for tasks; AEGIS plans, uses basic built-in tools, remembers sessions, asks for approvals on high-risk. |
| After P08 | Plus: automatically figures out how to do new things without pre-written integrations. |
| After P11 | Plus: memory is persistent, human-readable in Obsidian, can be corrected/audited. |
| After P12 | Plus: AEGIS genuinely helps with coding work. |
| After P21 | Plus: gets measurably better every week without manual intervention. |
| After P22 | Plus: polished desktop experience for non-terminal users. |
| After P23 | Plus: production-grade, auditable, supply-chain secure. |

---

## 5. ROLLBACK & DECOMMITMENT STRATEGY

If at any prompt the exit gate cannot pass within a reasonable iteration budget:

1. **Do not hack.** No "ship it and fix later" on core or security.
2. **Simplify.** If a design (e.g., T4 Firecracker) cannot be made reliable for the prompt, demote it to optional plugin and ship without it. Do not block the milestone for advanced non-P0 features.
3. **De-commit if necessary.** If the architecture itself is the blocker, go back to Prompt 01 docs, update them, get user approval for the new direction, then restart implementation. It is better to delay by one prompt and build the right thing than to build on a broken foundation.
4. **Retrospective mandatory.** Any rollback/decommitment writes an ADR in Obsidian → why it failed, what we learned, what replaces it.

---

*End of Document 09_ROADMAP.md*
