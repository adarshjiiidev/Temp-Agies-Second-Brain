# TEMPORARY AEGIS — COMPLETE BUILD DOCUMENTATION

**Build Date:** 2026-09-12
**Build Sessions:** 2
**Status:** COMPLETE — Foundation + Skills + Cron + Knowledge

---

## What Was Built

### Session 1: Foundation
- System audit (hardware, software, services, projects)
- Model registry (860 models → 15 curated, routing table)
- Tool registry (20 tools, 7 categories)
- Skill registry (10 skills)
- Personal context (user profile, preferences, environment)
- Second brain (PARA structure, 3 MOCs, 4 project notes, area/resource notes, daily log)
- AEGIS project knowledge ingested (vision, arch, requirements, risks, audit)
- agies profile created (/home/adarshjii/.hermes/profiles/agies/)
- Gateway multiplex config updated
- AEGIS_CONFIG.md (8-section config)
- MEMORY_SCHEMA.md (11-tier memory system)

### Session 2: Skills + Cron + Full PC Knowledge
- **Karpathy skill** — Andrej Karpathy's LLM/AI knowledge (15 principles, practical guide, project knowledge)
- **Matt Wolfe skill** — AI tool discovery, automation philosophy, evaluation framework
- **Agent MoE skill** — 12-expert Mixture of Experts architecture for computer skills
- **12 expert definitions** — FS, Shell, Git, Docker, SysAdmin, Network, Dev, Browser, Desktop, DB, Cloud, Security
- **3 systemd timers (cron)** — snapshot (daily 02:00), ChatGPT ingest (daily 03:00), pattern learning (weekly Mon 04:00)
- **3 automation scripts** — aegis-snapshot.sh, aegis-ingest-chatgpt.sh, aegis-learn-patterns.sh
- **First PC snapshot** — 2026-09-12.md (308 lines, complete machine state)
- **PC knowledge document** — full machine model for agies (16 sections)
- **ChatGPT ingestion tracking** — JSON config with privacy filters, classification, storage rules
- **agies memory expansion** — USER.md, MEMORY.md, AEGIS_PROJECT_KNOWLEDGE.md, PC_KNOWLEDGE.md, CRONTAB_SETUP.md
- **Skill INDEX.md** — all 16 skills documented
- **Updated SKILL_REGISTRY.json** — all 16 skills with full metadata

---

## Architecture

```
TEMPORARY AEGIS
├── Registries (JSON)
│   ├── MODEL_REGISTRY.json — 860 models, 15 curated, 10 task routing rules
│   ├── TOOL_REGISTRY.json — 20 tools, 7 categories, schemas, permissions, risk
│   ├── SKILL_REGISTRY.json — 16 skills (4 agies + 12 MoE experts), full metadata
│   └── PERSONAL_CONTEXT.json — user profile, projects, environment, preferences
│
├── Configuration
│   ├── AEGIS_CONFIG.md — routing, privacy, memory, skills, tools, security, multi-agent, automation
│   ├── MEMORY_SCHEMA.md — 11-tier memory system with schemas
│   └── PC_TRAINING.md — PC learning pipeline design
│
├── Second Brain (PARA + CODE)
│   ├── 0-Inbox/ — raw capture, triage README
│   ├── 1-Projects/ — Aegis, repusense, world-viewer, chrome-extra
│   ├── 2-Areas/ — development, personal (+ usage-patterns from cron)
│   ├── 3-Resources/ — 9Router, routing-strategy, memory-systems
│   ├── 4-Archives/ — README
│   ├── MOCs/ — AI-Development, System-Architecture, Personal-Knowledge
│   ├── logs/ — 2026-09-12.md, session reports
│   ├── pc-state/ — daily snapshots (2026-09-12.md)
│   ├── knowledge_graph.json — entity relationships
│   ├── chatgpt_ingestion_tracking.json — ChatGPT pipeline config
│   └── MEMORY_SYSTEM_SUMMARY.md, INGESTION_PIPELINE.md
│
├── agies Profile (/home/adarshjii/.hermes/profiles/agies/)
│   ├── config.yaml — high reasoning, 300s timeout, 2 CPU/8GB/100GB, show_reasoning
│   ├── .env — AEGIS paths, project dirs, 9Router URL
│   ├── SOUL.md — personality: direct, authoritative, efficient
│   ├── IDENTITY.md — role: god PC user
│   ├── PROFILE_INFO.md — human-readable doc
│   ├── memories/
│   │   ├── USER.md — Adarsh Jii profile
│   │   ├── MEMORY.md — AEGIS summary
│   │   ├── AEGIS_PROJECT_KNOWLEDGE.md — full AEGIS docs (vision, arch, risks, audit)
│   │   ├── PC_KNOWLEDGE.md — complete machine model (16 sections)
│   │   └── CRONTAB_SETUP.md — systemd timer documentation
│   └── skills/
│       ├── INDEX.md — all 16 skills
│       ├── aegis/ — AEGIS integration skill
│       ├── karpathy/ — Karpathy LLM/AI knowledge (15 principles)
│       ├── matt-wolfe/ — AI tools/automation knowledge
│       ├── agent-moe/ — MoE orchestration + 12 expert definitions
│       └── (inherited Hermes skills: omarchy, software-development, research, etc.)
│
├── Systemd Timers (cron)
│   ├── aegis-snapshot.timer — daily 02:00 → snapshot script
│   ├── aegis-ingest-chatgpt.timer — daily 03:00 → ChatGPT ingest script
│   └── aegis-learn.timer — weekly Mon 04:00 → pattern learning script
│
└── Scripts
    ├── aegis-snapshot.sh — full PC state capture
    ├── aegis-ingest-chatgpt.sh — ChatGPT export extraction + classification
    └── aegis-learn-patterns.sh — shell history + git + file edit analysis
```

---

## Model Stack

| Role | Model | Provider | Why |
|------|-------|----------|-----|
| Default | upstage/solar-pro4:free | nous | Hermes default, free, good all-rounder |
| Reasoning | openai/o3-mini | openai | Strong reasoning, good cost |
| Coding | openai/codex-mini | openai-codex | Codex for coding tasks |
| Browser/agent | openai/gpt-5.5 | openai-codex | Strong tool use |
| Local/private | llama3.2:3b, qwen2.5:7b | ollama | Privacy, offline |
| Research | openai/o1 | openai | Deep research synthesis |
| Fast/cheap | openrouter/deepseek-chat | openrouter | Quick, low cost |

Full routing table: MODEL_REGISTRY.json → routing → task_routing (10 task types mapped)

---

## Skills

### agies-Specific Skills (4)

| Skill | What It Does |
|-------|-------------|
| aegis | AEGIS integration — registries, memory, routing, knowledge access |
| karpathy | Andrej Karpathy's LLM/AI engineering knowledge — 15 principles, how LLMs work, tool use, RLVR, Software 3.0, vibe coding, agent building, practical usage guide |
| matt-wolfe | Matt Wolfe's AI tool discovery, automation philosophy, evaluation framework — FutureTools approach, tool stacking, human-in-loop, cost tracking |
| agent-moe | Mixture of Experts multi-agent orchestration — 12 expert definitions, routing logic, dispatch, aggregation, verification |

### Agent MoE Experts (12)

| Expert | Domain | Tools |
|--------|--------|-------|
| FS Expert | Filesystem — files, dirs, search, permissions, storage | file, terminal, search |
| Shell Expert | Shell/terminal — commands, scripting, processes, pipes | terminal, file, code_execution |
| Git Expert | Version control — commits, branches, history, merges | terminal, file |
| Docker Expert | Containers — images, Compose, networking, volumes | terminal |
| SysAdmin Expert | System admin — services, packages, users, logs, monitoring | terminal, file |
| Network Expert | Networking — interfaces, firewall, DNS, ports, connectivity | terminal |
| Dev Expert | Development — code, testing, debugging, building | terminal, file, code_execution, browser |
| Browser Expert | Web/browser — navigation, extraction, forms, screenshots | browser, web, terminal |
| Desktop Expert | Desktop/UI — windows, screenshots, clipboard, display | terminal, browser, vision |
| DB Expert | Databases — SQL, NoSQL, schemas, migrations, backups | terminal, file |
| Cloud Expert | APIs/cloud — REST, auth, rate limits, webhooks | web, terminal, file |
| Security Expert | Security — scanning, auditing, hardening, secrets detection | terminal, file, search |

### Inherited Hermes Skills

omarchy, software-development (codebase-inspection, code-wiki, systematic-debugging, spike), research, productivity, github, apple, creative, devops, email, media, note-taking, social-media, web, autonomous-ai-agents

**Total: 16 skills available to agies**

---

## Cron Infrastructure

### 3 Automated Jobs

| Timer | Schedule | Script | Output |
|-------|----------|--------|--------|
| aegis-snapshot | Daily 02:00 | aegis-snapshot.sh | pc-state/YYYY-MM-DD.md (full machine state) |
| aegis-ingest-chatgpt | Daily 03:00 | aegis-ingest-chatgpt.sh | Inbox notes → project/preference/lesson notes |
| aegis-learn | Weekly Mon 04:00 | aegis-learn-patterns.sh | 2-Areas/personal/usage-patterns.md |

### First Snapshot Completed
- 2026-09-12.md — 308 lines, 18KB
- Captured: system, hardware, memory, top processes, network, listening ports, 27 services, Docker state, packages, Python, Node, Git projects, recent file changes, Omarchy config

### ChatGPT Ingestion Ready
- Script handles: ZIP extraction, conversation parsing, privacy redaction (API keys, tokens, passwords, secrets)
- Classification: project / preference / lesson / general
- Storage: project notes → 1-Projects/<project>/, preferences → 2-Areas/personal/, lessons → 3-Resources/, general → 0-Inbox/chatgpt/
- User action needed: Export from ChatGPT → place ZIP in ~/Downloads/

---

## PC Knowledge (what agies knows about the machine)

### Hardware
- CPU: 12th Gen Intel i3-1215U (4C/8T)
- RAM: 7.5 GiB + 14 GiB swap (zram)
- Storage: 476.9G NVMe (18% used)
- Network: WiFi 192.168.31.206/24

### Software
- OS: AGIES (Omarchy 4.0.3) — Arch-based
- Kernel: 7.2.3-arch1-3
- Python 3.11.16, Node 24.19.0, Git 2.55.0, Docker 29.7.2
- Hermes 0.27.0+, 9Router, OpenClaw, llama-server, LM Studio

### Running Services (27 user systemd units)
- AI: 9router (20128), openclaw-gateway (18789), aegis-snapshot, aegis-ingest-chatgpt, aegis-learn
- Desktop: Hyprland, quickshell, Chrome (3 extensions), pipewire, gnome-keyring
- System: dbus, accessibility, Bluetooth, Fcitx5, sleep lock, crash watch

### Listening Ports
- 40565: llama-server (local LLM)
- 20128: 9router
- 40375: hermes agies
- 45787: hermes default
- 41343: LM Studio
- 18789: OpenClaw
- 631: CUPS printing
- 53: DNS resolver

### Projects
- Aegis (L1-L6 implemented, 791 tests, suite hangs)
- chrome-extra (Chrome extension, built)
- repusense (Next.js web app, early)
- world-viewer (Electron desktop app, built)

### Memory State
- 5.9G RAM used, 5.5G swap used — memory pressure from Chrome + Hermes + agents

---

## Privacy & Security

### Privacy Filtering
- .env, *.pem, *.key, id_rsa, id_ed25519, credentials*, secrets*, password* — excluded from ingestion
- ChatGPT ingest: redacts API keys, GitHub tokens, passwords, secrets, tokens
- No secrets stored in any AEGIS file

### Sudo
- Passwordless sudo configured for adarshjii
- agies can run privileged commands without password prompt

### Security Boundaries (from AEGIS requirements)
- No permission engine yet (AEGIS L3 — not built in TEMPORARY AEGIS)
- No policy engine yet (AEGIS L3 — not built)
- No sandbox yet (AEGIS L5 — not built)
- Audit: Hermes state.db provides session audit, but no AEGIS-specific audit chain

---

## What's Ready to Use

### Start agies
```bash
cd /home/adarshjii/.hermes/profiles/agies && hermes run
```

### agies can now:
1. **Answer questions about your PC** — read PC_KNOWLEDGE.md or latest snapshot
2. **Route tasks to experts** — use Agent MoE skill for complex multi-domain tasks
3. **Recommend models** — consult MODEL_REGISTRY.json routing table
4. **Search your memory** — PARA structure, MOCs, project notes, daily logs
5. **Apply Karpathy principles** — when working with LLMs, tool use, verification
6. **Evaluate AI tools** — Matt Wolfe framework for tool selection
7. **Run cron jobs manually** — `systemctl --user start aegis-snapshot`
8. **Ingest ChatGPT history** — place export in Downloads/, timer handles rest

### Example queries agies can answer:
- "What's running on my machine right now?"
- "Which model should I use for debugging?"
- "How do I use LLMs effectively?" (Karpathy skill)
- "What AI tools exist for X?" (Matt Wolfe skill)
- "Audit my system security" (Agent MoE: Security + SysAdmin + Network experts)
- "What did I work on yesterday?" (check pc-state snapshot + git log)
- "Search my memory for how I solved X" (search_files across memory/)
- "Show me my project status" (read project notes + git status)

---

## Known Limitations

1. **agies not yet run** — profile created, skills loaded, but no live session tested
2. **No semantic search** — keyword/file search only, no vector embeddings
3. **No automated ChatGPT ingestion yet** — timer ready, but no export ZIP placed
4. **No experience memory** — task experiences not yet recorded
5. **No workflow learning** — patterns detected weekly by cron, but not yet acted upon
6. **AEGIS project incomplete** — L1-L6 done, L7 not started, test suite hangs, redesign pkgs broken
7. **No permission/policy/sandbox** — these are AEGIS L3/L5 requirements, not in TEMPORARY AEGIS
8. **Model routing not exercised** — registry built, but no actual model selections made
9. **Agent MoE not tested** — architecture designed, experts defined, but not spawned in live session

---

## Migration Path to Real AEGIS

TEMPORARY AEGIS uses existing infrastructure (Hermes + 9Router + OpenClaw + Codex). Real AEGIS (in /home/adarshjii/Projects/Aegis/) is a from-scratch Python implementation.

| TEMPORARY AEGIS | Real AEGIS Equivalent |
|-----------------|----------------------|
| Hermes runtime | AEGIS L1 Core Runtime |
| MODEL_REGISTRY.json | AEGIS L3 AI Kernel model router |
| TOOL_REGISTRY.json | AEGIS L5 capability registry |
| SKILL_REGISTRY.json | AEGIS L5 skill store |
| Second brain (markdown) | AEGIS L4 memory engine + Obsidian projection |
| knowledge_graph.json | AEGIS L4 knowledge graph |
| agies profile | AEGIS L7 text interface |
| Systemd timers | AEGIS L2 scheduler |
| Agent MoE | AEGIS L6 cognitive planner + L5 capability discovery |

---

## Build Stats

| Metric | Value |
|--------|-------|
| Total files created | 60+ |
| Total size | ~300KB |
| Skills | 16 (4 agies + 12 MoE experts) |
| Models curated | 15 from 860 discovered |
| Tools registered | 20 |
| PC snapshots | 1 (daily cron will add more) |
| Systemd timers | 3 active |
| agies profile size | ~500KB (state.db + assets) |

---

## Build Session 2 Checklist

- [x] Karpathy skill — created with 15 principles + practical guide
- [x] Matt Wolfe skill — created with tool philosophy + evaluation framework
- [x] Agent MoE skill — created with 12 experts + routing logic + orchestration
- [x] 12 expert definitions — full capabilities, tools, tasks, best practices, failure modes
- [x] Systemd timers — 3 timers created, enabled, started
- [x] Automation scripts — 3 scripts created, executable
- [x] First PC snapshot — completed (2026-09-12.md)
- [x] PC knowledge document — created (16 sections, comprehensive)
- [x] ChatGPT ingestion pipeline — script + tracking JSON ready
- [x] agies memory expanded — USER.md, MEMORY.md, AEGIS_PROJECT_KNOWLEDGE.md, PC_KNOWLEDGE.md, CRONTAB_SETUP.md
- [x] Skill INDEX.md — all 16 skills documented
- [x] SKILL_REGISTRY.json updated — all 16 skills with metadata
- [x] Passwordless sudo verified — user has passwordless sudo

---

## Files Created (Session 2)

```
.hermes/profiles/agies/skills/
├── INDEX.md (39 lines) — all 16 skills
├── karpathy/
│   ├── SKILL.md (287 lines) — 15 principles + practical guide
│   └── DESCRIPTION.md (45 lines)
├── matt-wolfe/
│   ├── SKILL.md (195 lines) — tool philosophy + evaluation
│   └── DESCRIPTION.md (38 lines)
└── agent-moe/
    ├── SKILL.md (318 lines) — MoE architecture + routing
    ├── DESCRIPTION.md (55 lines)
    └── EXPERTS.md (345 lines) — 12 expert definitions

.temporary-aegis/
├── SKILL_REGISTRY.json (updated — 16 skills, 15KB)
├── memory/
│   ├── pc-state/2026-09-12.md (308 lines, 18KB) — first snapshot
│   ├── chatgpt_ingestion_tracking.json (45 lines) — pipeline config
│   ├── PC_KNOWLEDGE.md (212 lines, 8KB) — full machine model
│   └── (existing: PARA structure, MOCs, project notes, logs)
├── scripts/
│   ├── aegis-snapshot.sh (188 lines) — PC snapshot
│   ├── aegis-ingest-chatgpt.sh (275 lines) — ChatGPT ingest
│   └── aegis-learn-patterns.sh (85 lines) — pattern learning
└── config/
    └── PC_TRAINING.md (171 lines) — PC learning design

.config/systemd/user/
├── aegis-snapshot.timer + .service
├── aegis-ingest-chatgpt.timer + .service
└── aegis-learn.timer + .service

.hermes/profiles/agies/memories/
├── USER.md (48 lines)
├── MEMORY.md (44 lines)
├── AEGIS_PROJECT_KNOWLEDGE.md (160 lines, 6KB)
├── PC_KNOWLEDGE.md (212 lines, 8KB)
└── CRONTAB_SETUP.md (69 lines)
```

---

## TEMPORARY AEGIS BUILD COMPLETE

**Status:** Both sessions complete. Foundation + Skills + Cron + Full PC Knowledge built.

**Ready to use:** Start agies via `cd /home/adarshjii/.hermes/profiles/agies && hermes run`

**Next:** When you run agies, it will have:
- 16 skills (Karpathy, Matt Wolfe, Agent MoE + 12 experts, AEGIS integration, + inherited Hermes skills)
- Full PC knowledge (hardware, software, services, network, projects, memory state)
- AEGIS project knowledge (vision, architecture, risks, known issues)
- Model registry with routing (860 models → 15 curated, 10 task types)
- Tool registry (20 tools)
- Second brain (PARA, MOCs, project notes, daily logs)
- 3 automated cron jobs (snapshot, ChatGPT ingest, pattern learning)
- Passwordless sudo

**What you need to do:**
1. Export ChatGPT history → place in ~/Downloads/ → cron ingests automatically
2. Start agies and test it responds with actual knowledge
3. Over time: cron snapshots build PC history, pattern learning builds usage model
