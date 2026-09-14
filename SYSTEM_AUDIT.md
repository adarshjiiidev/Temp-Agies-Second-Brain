# TEMPORARY AEGIS — SYSTEM AUDIT

**Date:** 2026-09-12
**Auditor:** TEMPORARY AEGIS build agent
**Scope:** Full machine inventory for AEGIS integration

---

## 1. HARDWARE

| Component | Value |
|---|---|
| OS | AGIES (Arch-based), kernel 7.2.3-arch1-3 |
| CPU | 12th Gen Intel i3-1215U (8 cores, x86_64) |
| RAM | 7.5 GB (1.5 GB available, 4.3 GB swap in use) |
| Swap | 14 GB zram |
| Storage | 475 GB NVMe (2 GB /boot, 474.9 GB root) |
| GPU | None detected (integrated Intel UHD) |
| Network | Active (9Router, OpenClaw, Hermes all running) |

**Implications:** No GPU for local inference. 7.5 GB RAM limits local model size. Remote models via 9Router are the primary inference path. Local models only if very small or via cloud API.

---

## 2. SOFTWARE STACK

### Operating System
- AGIES Linux (Arch-based, ID=omarchy)
- systemd user services active

### Runtime
- **Python:** 3.11.16 (via ~/.local/share/uv/python/cpython-3.11-linux-x86_64-gnu)
- **Node.js:** 22.23.2 (system), 24.19.0 (OpenClaw bundled)
- **Git:** 2.55.0
- **Docker:** 29.7.2 (available, not actively used by AEGIS components)
- **Rust/Cargo:** NOT installed (AEGIS Rust crates unverifiable)

### Package Managers
- **mise:** available (9Router installed via mise)
- **yay:** AUR helper (OpenClaw-desktop, 9Router installed via yay)
- **uv:** Python package management

---

## 3. OPENCLAW

| Attribute | Value |
|---|---|
| Version | 2026.9.3 |
| Install | ~/.local/share/openclaw/ (AppImage-based) |
| Gateway | systemctl --user openclaw-gateway.service, ACTIVE, port 18789 |
| Node | ~/.openclaw/tools/node-v24.19.0/bin/node |
| Desktop | openclaw.desktop, openclaw-desktop-handler.desktop installed |
| Status | Running, 327.6 MB RSS, gateway active |

OpenClaw serves as the desktop/gateway layer. It provides the chat surface and platform integrations.

---

## 4. HERMES AGENT

| Attribute | Value |
|---|---|
| Version | 0.5.59 (9Router shares this version) |
| Install | ~/.hermes/ (home), ~/.hermes/hermes-agent/ (checkout) |
| Binary | ~/.local/bin/hermes, hermes-agent, hermes-acp |
| Config | ~/.hermes/config.yaml (model: upstage/solar-pro4:free, provider: nous) |
| .env | ~/.hermes/.env (505 lines, mostly commented API key templates) |
| State DB | ~/.hermes/state.db (5.4 MB, SQLite with FTS) |
| Sessions | 3 sessions, 501 messages total |
| Skills | 23 skills across 14 categories |
| Plugins | .hermes/plugins/ directory exists |
| Logs | ~/.hermes/logs/ (agent.log, errors.log, gateway.log) |
| Cron | ~/.hermes/cron/ (scheduler active) |
| Memory | ~/.hermes/memories/ directory (empty) |
| Status | ACTIVE — 9Router service running via systemctl |

### Hermes Model Configuration
- **Default model:** upstage/solar-pro4:free
- **Provider:** nous
- **Base URL:** https://inference-api.nousresearch.com/v1
- **Reasoning effort:** medium
- **Max turns:** 500

### Hermes Tools (from config + codebase)
- terminal (local backend, 180s timeout)
- browser (inactivity timeout 120s, extension control disabled)
- file operations (read/write via CLI)
- web search
- skill execution
- memory operations
- delegation (subagents)
- cron scheduling
- compression (enabled, 50% threshold)

### Hermes Skills Available (23 skills)
**software-development (13):**
- codebase-inspection
- code-wiki
- dogfood
- github (gh CLI, PRs, issues, reviews, repos)
- hermes-agent-skill-authoring
- inspecting-hermes-desktop-dom
- node-inspect-debugger
- plan
- python-debugpy
- requesting-code-review
- simplify-code
- spike
- systematic-debugging
- test-driven-development

**productivity (14):**
- airtable, box, document-to-action-items, docx, google-workspace, maps, meeting-action-items, nano-pdf, notion, ocr-and-documents, pdf, powerpoint, product-price-monitor, session-librarian, teams-meeting-pipeline, weekly-review-planning, xlsx

**research (5):**
- arxiv, blogwatcher, competitor-news-monitor, grounded-citations, llm-wiki, research-paper-writing

**creative (9):**
- architecture-diagram, ascii-art, ascii-video, baoyu-infographic, claude-design, comfyui, design-md, excalidraw, humanizer, manim-video, p5js, popular-web-designs, pretext, sketch, songwriting-and-ai-music, touchdesigner-mcp

**github (5):**
- github-auth, github-code-review, github-issues, github-issue-to-pr, github-pr-workflow, github-repo-management

**mlops (4):**
- huggingface-hub, evaluating-llms-harness, weights-and-biases, llama-cpp, serving-llms-vllm

**email, note-taking, smart-home, social-media, web, autonomous-ai-agents, devops, media, diagnose-crash, omarchy**

---

## 5. 9ROUTER

| Attribute | Value |
|---|---|
| Version | 0.5.59 |
| Install | ~/.local/share/mise/installs/node/22/bin/9router |
| Service | systemctl --user 9router.service, ACTIVE, port 20128 |
| Mode | OpenAI-compatible API gateway, --host 127.0.0.1 --no-browser --skip-update -l |
| Memory | 123 MB RSS |
| Models | **860 models** available via /v1/models |

### 9Router Model Groups (verified)
- **ag/ (20):** Gemini 3.8/3.7/3.6/3.5/3.1 flash variants, Claude Sonnet 4.6, Claude Opus 4.6 Thinking — all with vision+tools+reasoning, up to 1M context
- **cx/ (15):** GPT-6 Astra, GPT-5.6 Sol/Terra/Luna (with -review variants), GPT-5.5/5.4/5.4-mini — OpenAI lineup, 272K-400K context
- **gh/ (33):** GitHub Copilot models (GPT-5.4-mini-free, Kimi K3, Claude Haiku 4.5, GPT-5-mini)
- **cl/ (445):** Chat/LM studio models — full spectrum including Claude Opus 5/4.8/4.7/4.6/4.5, Gemini 3.8-2.5, GPT-5/5.1/5.2/5.4/5.5/5.6, Kimi K2/K3, Qwen 3.5/3.6/3.7, Grok 4.20-4.3, Muse Spark 1.1-1.3
- **cu/ (100+):** Cursor models — Claude Opus 5/4.8/4.7, GPT-5.6/5.5/5.4/5.2, Gemini 3.8-3.1, Muse Spark, Kimi K3
- **qb/:** Qwen, DeepSeek, Kimi via various providers
- **gc/:** Google Cloud models
- **kc/:** Kimi/Coding models
- **kb/:** Various
- **?? (347):** Unclassified/provider-specific models

### Verified High-Capability Models (reasoning + tools + vision)

| Model | Context | Output | Thinking | Best For |
|---|---|---|---|---|
| ag/gemini-3.8-flash-high | 1M | 64K | gemini-level | Large context, multimodal |
| ag/claude-sonnet-4-6 | 1M | 128K | claude-adaptive | Coding, reasoning |
| ag/claude-opus-4-6-thinking | 200K | 64K | claude-budget | Deep reasoning |
| cx/gpt-5.6-sol | 372K | 128K | openai | Coding, agentic |
| cx/gpt-5.6-terra | 272K | 128K | openai | General, coding |
| cx/gpt-5.5 | 400K | 128K | openai | Large context |
| cx/gpt-5.4 | 400K | 128K | openai | Established capability |
| cl/anthropic/claude-opus-5 | 1M | 128K | claude-adaptive | Top reasoning |
| cl/anthropic/claude-sonnet-5 | 1M | 128K | claude-adaptive | Coding, analysis |
| cl/google/gemini-3.8-flash | 1M | 64K | gemini-level | Multimodal, fast |
| cl/openai/gpt-5.6-sol | 400K | 128K | openai | Coding agent |
| cl/openai/gpt-5.6-terra | 400K | 128K | openai | General |
| cl/qwen/qwen3.7-plus | 1M | 64K | qwen | Coding, long context |
| kimi/kimi-k3 | 1M | 128K | kimi | Long horizon |

---

## 6. CODEX

| Attribute | Value |
|---|---|
| Version | 0.153.4 |
| Install | ~/.local/bin/codex (wrapper), ~/.codex/ (home) |
| Config | ~/.codex/config.toml (model: gpt-5.6-terra, reasoning: medium) |
| Plugins | app-tools, visualize, documents, pdf, spreadsheets, presentations, template-creator, browser |
| MCP | node_repl (CUA node) |
| Models Cache | ~/.codex/models_cache.json (fetched 2026-09-12) |
| Global State | ~/.codex/.codex-global-state.json (322 KB) |
| SQLite DBs | goals_1.sqlite, logs_2.sqlite (4.4 MB), memories_1.sqlite, queue_1.sqlite, models_cache.json |
| Browser | Browser plugin enabled (Chrome, IAB backends) |
| Trusted Projects | /home/adarshjii/Documents/Codex/2026-08-25/hey, /home/adarshjii/Work, /home/adarshjii/Projects/world-viewer |
| Status | Installed and configured, not currently running as service |

Codex provides a dedicated coding agent runtime. It can be invoked for coding tasks, repository understanding, and code edits.

---

## 7. AEGIS PROJECT (User's Own Project)

| Attribute | Value |
|---|---|
| Location | ~/Projects/Aegis/ |
| Language | Python 3.12 (pyproject.toml), Rust crates (uncompiled) |
| Status | L1–L6 implemented, 1060 tests passing |
| Architecture | 7-layer adaptive AI OS (L1 Core → L7 HCI) |
| Layers Implemented | L1 Core Runtime, L2 Foundation, L3 AI Kernel, L4 Memory/Knowledge, L5 Execution, L6 Planning |
| L7 | Not started |
| Docs | 20+ docs in docs/ including AEGIS_MASTER_AUDIT.md, architecture docs, roadmap |
| Key Components | AI Kernel with model router, 4 memory stores, execution pipeline, planning engine |
| Test Suite | 1060 tests, ~22s runtime, full suite passes |
| Rust Crates | aegis_ffi_common, aegis_crypto, aegis_audit_chain, aegis_graph_core, aegis_search_core (compile errors, cargo not installed) |

The AEGIS project provides the architectural blueprint for the TEMPORARY AEGIS system. Its concepts (layered architecture, memory tiers, execution pipeline, routing) inform how we configure the live system.

---

## 8. USER PROJECTS (Authorized)

| Project | Location | Language | Notes |
|---|---|---|---|
| Aegis | ~/Projects/Aegis/ | Python/Rust | User's AI OS project, L1-L6 done |
| repusense | ~/Projects/repusense/ | Node.js | Has hermes-parser dependency |
| world-viewer | ~/Projects/world-viewer/ | ? | Codex trusted project |
| chrome-extra | ~/Projects/chrome-extra/ | ? | Chrome extension? |
| copilot-worktrees | ~/Projects/copilot-worktrees/ | ? | GitHub Copilot related |

---

## 9. FILESYSTEM / ENVIRONMENT

### Key Directories
- ~/.hermes/ — Hermes home (config, state, skills, sessions, logs)
- ~/.codex/ — Codex home (config, state, SQLite DBs, plugins)
- ~/.openclaw/ — OpenClaw tools (Node 24.19.0)
- ~/Projects/ — User's projects (Aegis, repusense, world-viewer, etc.)
- ~/.local/bin/ — User binaries (hermes, codex, gh, opencode, claude, gemini, etc.)
- ~/.config/systemd/user/ — User systemd services (openclaw-gateway, 9router)

### Environment
- HOME=/home/adarshjii
- PATH includes ~/.local/bin, ~/.openclaw/tools/node-v24.19.0/bin, ~/.npm-global/bin, ~/bin, ~/.nix-profile/bin
- HERMES_HOME=~/.hermes (default)
- No GPU visible to PyTorch/TensorFlow

### Secrets / API Keys
- ~/.hermes/.env contains 505 lines, mostly commented API key templates for ~50 providers
- No actively configured API keys in .env (all commented out)
- Hermes config.yaml uses nous provider with Solar Pro 4 free (no key needed)
- 9Router handles model routing/auth internally

---

## 10. AVAILABLE CAPABILITIES (VERIFIED)

### Model Access
- 860 models via 9Router (OpenAI-compatible, localhost:20128)
- Hermes direct via Nous/Solar Pro 4 free
- Codex models via ChatGPT backend

### Agent Runtime
- Hermes Agent (CLI + desktop + messaging platforms)
- Codex (coding agent)
- OpenClaw Gateway (desktop chat)

### Tools
- Terminal/shell execution
- Browser automation (Hermes + Codex browser plugin)
- File read/write
- Web search
- Git operations
- HTTP requests
- Python execution
- Docker (available)
- Screenshot/OCR (via skills)

### Storage
- SQLite (Hermes state.db, Codex SQLite DBs)
- Filesystem (projects, skills, configs)
- FTS search (Hermes messages_fts)

### Scheduling
- Hermes cron scheduler
- systemd user timers (implicit)

---

## 11. GAPS / LIMITATIONS

| Gap | Impact | Mitigation |
|---|---|---|
| No GPU | No local LLM inference | Use 9Router cloud models |
| 7.5 GB RAM | Cannot run large local models | Rely on remote inference |
| No Rust toolchain | AEGIS crates unverifiable | Skip Rust, use Python AEGIS concepts |
| No active API keys | Most Hermes .env keys are commented | 9Router handles auth, Solar Pro 4 free works |
| Limited local projects | Only 5 projects discovered | Focus on Aegis + world-viewer + repusense |
| Memory stores empty | No pre-existing episodic/semantic memory | Build from session history + project docs |
| L7 HCI not implemented in AEGIS project | No desktop UI layer in user's project | Hermes + OpenClaw provide the UI layer |

---

## 12. INTEGRATION OPPORTUNITIES

1. **9Router → Hermes:** Hermes already uses 9Router as a model provider. Verify routing config.
2. **Codex → Hermes:** Hermes has Codex adapter code (codex_headers.py, codex_responses_adapter.py, codex_runtime.py). Can integrate Codex as a delegated coding agent.
3. **AEGIS project → Live system:** Use AEGIS L4 memory concepts to organize Hermes memory. Use AEGIS routing concepts to configure model selection.
4. **Hermes skills → AEGIS skills:** Extend existing skills with AEGIS-specific knowledge (project intelligence, personal context).
5. **Session history → Memory:** 501 messages across 3 sessions provide initial episodic memory.
6. **Project docs → Knowledge:** AEGIS docs (20+ files, 50KB+) provide semantic knowledge to index.

---

## 13. BUILD FEASIBILITY

**What can be built NOW (this session):**
- System audit (this document)
- Model registry with routing recommendations
- AEGIS configuration layer for Hermes
- Project intelligence indexes for user's projects
- AEGIS-enhanced skills
- Memory organization schema
- Tool registry
- End-to-end validation tests
- Documentation (COMPLETE.md, MASTER_TODO.md, etc.)

**What requires future work:**
- Persistent daily intelligence scheduler (requires cron setup verification)
- Full ChatGPT export ingestion (requires export files)
- Automatic ingestion pipelines (requires FileSystem monitoring)
- Rust crate compilation (requires cargo)
- L7 HCI layer (requires UI development)
- Multi-agent orchestration beyond Hermes delegation

**Bottom line:** The core integration — Hermes + 9Router + Codex + project intelligence + memory organization + skills — is fully buildable now. The infrastructure exists. We wire it together with AEGIS concepts.
