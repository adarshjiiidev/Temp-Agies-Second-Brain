# TEMPORARY AEGIS — Second Brain

**Personal AI Memory & Knowledge Store** — the persistent memory layer for the Agies AI OS.

**Location:** `~/.temporary-aegis/` | **Remote:** `git@github.com:adarshjiiidev/Temp-Agies-Second-Brain.git` (branch: `second-brain`)

---

## What It Is

The Second Brain is the operational memory and configuration layer for TEMPORARY AEGIS. It stores:

- **Memory scaffold** — PARA-structured knowledge (Inbox, Projects, Areas, Resources, Archives)
- **Configuration** — AEGIS config, quick reference, PC training data
- **Scripts** — systemd-integrated automation scripts (snapshot, ingest, learn)
- **Registry data** — model, agent, tool, and skill registries
- **Build reports** — session reports, build logs, blockers
- **Personal context** — user profile, project intelligence, decision logs
- **Audit data** — system audits, self-audits, gap analysis

---

## Structure

```
.temporary-aegis/
├── SECOND_BRAIN.md              # This file
├── TEMPORARY_AEGIS_COMPLETE.md  # Build completion report
├── BLOCKERS.md                  # Active blockers
├── MASTER_TODO.md               # Master task list
├── PROJECT_STATE.json           # Project state tracking
├── SELF_AUDIT.md                # Self-audit results
├── CHANGELOG.md                 # Version history
├── BUILD_LOG.md                 # Build activity log
├── BUILD_SESSION_1_REPORT.md    # Session 1 summary
├── BUILD_SESSION_1_FULL_REPORT.md
├── SYSTEM_AUDIT.md              # System audit
├── SESSIONessages/              # Session messages
├── config/
│   ├── AEGIS_CONFIG.md          # AEGIS configuration
│   ├── QUICK_REFERENCE.md       # Quick reference card
│   ├── PC_TRAINING.md           # PC training data
│   └── aegis_api_token          # API token (chmod 600)
├── docs/
│   ├── TEMPORARY_AEGIS_SYSTEM_AUDIT.md
│   ├── MODEL_FABRIC.md
│   ├── AEGIS_MIGRATION.md
│   ├── AGENTMOE.md
│   ├── COMPUTER_CONTROL.md
│   ├── MEMORY.md
│   ├── SECURITY.md
│   ├── SKILLS.md
│   ├── TOOLS.md
│   ├── VISION.md
│   ├── TEMPORARY_AEGIS_ARCHITECTURE.md
│   ├── TEMPORARY_AEGIS_GAP_AUDIT.md
│   └── TEMPORARY_AEGIS_GAP_CLOSURE_REPORT.md
├── memory/
│   ├── 0-Inbox/                # Inbox — unprocessed items
│   ├── 1-Projects/             # Project notes (PARA)
│   │   ├── Aegis/
│   │   │   ├── project.md
│   │   │   ├── architecture.md
│   │   │   └── AEGIS_DOCS/index.md
│   │   ├── repusense.md
│   │   ├── world-viewer.md
│   │   ├── chrome-extra/
│   │   │   └── project.md
│   │   └── index.md
│   ├── 2-Areas/                # Area notes
│   │   └── development.md
│   ├── SECOND_BRAIN_STRUCTURE.md
│   ├── README.md
│   ├── MEMORY_SYSTEM_SUMMARY.md
│   ├── INGESTION_PIPELINE.md
│   └── knowledge_graph.json    # Knowledge graph data
├── scripts/
│   ├── aegis-snapshot.sh       # PC state snapshot
│   ├── aegis-ingest-chatgpt.sh # ChatGPT export ingest
│   └── aegis-learn-patterns.sh # Pattern learning
├── logs/
│   └── aegis.log               # Structured log (rotating)
├── experiences.json             # Experience learning data
├── AGENT_REGISTRY.json          # Agent registry
├── MODEL_REGISTRY.json          # Model registry
├── SKILL_REGISTRY.json          # Skill registry
├── TOOL_REGISTRY.json           # Tool registry
├── PERSONAL_CONTEXT.json        # Personal context
├── project_intelligence.json    # Project intelligence
└── build_model_registry.py      # Registry builder
```

---

## Memory System (PARA)

The memory layer follows Tiago Forte's PARA methodology:

| Folder | Purpose |
|--------|---------|
| `0-Inbox` | Unprocessed items — quick capture, unsorted |
| `1-Projects` | Active projects with defined goals and endpoints |
| `2-Areas` | Ongoing responsibilities without deadlines |
| `3-Resources` | Reference material, interests, research |
| `4-Archives` | Completed projects, inactive items |

Each project in `1-Projects/` has:
- `project.md` — project overview, status, key files
- `architecture.md` — architecture notes
- `AEGIS_DOCS/index.md` — linked AEGIS documentation

---

## Configuration

### AEGIS_CONFIG.md
Central configuration reference — paths, ports, model IDs, service names, environment variables.

### QUICK_REFERENCE.md
Quick reference card — commands, endpoints, service status, common operations.

### PC_TRAINING.md
PC-specific training data — hardware profile, installed tools, known issues, preferences.

### aegis_api_token
256-bit hex API token for authenticating dashboard script execution requests. Stored with `chmod 600`.

---

## Scripts

| Script | Purpose | Systemd Service |
|--------|---------|-----------------|
| `aegis-snapshot.sh` | Capture PC state (uptime, processes, disk, memory, network) | `aegis-snapshot.service` |
| `aegis-ingest-chatgpt.sh` | Ingest ChatGPT export ZIP into Obsidian | `aegis-ingest-chatgpt.service` |
| `aegis-learn-patterns.sh` | Pattern learning from experiences | `aegis-learn.service` |

---

## Registries

### AGENT_REGISTRY.json
Registered AI agents with CLI paths, harnesses, default models, and roles.

### MODEL_REGISTRY.json
Model catalog — 870+ models from 9Router with provider, context window, capabilities.

### SKILL_REGISTRY.json
27 skills across OpenClaw plugins and Hermes agies profile.

### TOOL_REGISTRY.json
Operational tools — terminal, filesystem, vision, browser, clipboard, etc.

---

## Build Reports

### TEMPORARY_AEGIS_COMPLETE.md
Complete build report — what was built, verified, and activated.

### BUILD_SESSION_1_REPORT.md
Session 1 summary — key accomplishments, files built, decisions made.

### BUILD_SESSION_1_FULL_REPORT.md
Full session 1 report — detailed build log with timestamps.

### BUILD_LOG.md
Build activity log — chronological build events.

### BLOCKERS.md
Active blockers and their status.

### MASTER_TODO.md
Master task list — all pending and in-progress tasks.

---

## Audit & Self-Assessment

### SYSTEM_AUDIT.md
System-level audit — service health, port status, process verification.

### SELF_AUDIT.md
Self-audit — internal consistency checks, configuration validation.

### docs/TEMPORARY_AEGIS_GAP_AUDIT.md
Gap audit — identified gaps from forensic audit.

### docs/TEMPORARY_AEGIS_GAP_CLOSURE_REPORT.md
Gap closure report — how each gap was remediated and verified.

---

## Integration with Dashboard

The dashboard backend (`backend/server.py`) reads from `.temporary-aegis/`:

- **Config:** `backend/config.py` resolves paths from `AegisConfig`
- **Registries:** `AGENT_REGISTRY.json`, `MODEL_REGISTRY.json`, `SKILL_REGISTRY.json`, `TOOL_REGISTRY.json` loaded at runtime
- **Scripts:** `aegis-snapshot.sh`, `aegis-ingest-chatgpt.sh`, `aegis-consolidate.py` executed via `POST /api/run-script`
- **Memory:** `memory/` PARA structure mirrored in Obsidian vault at `~/ObsidianVault/memory/`
- **Knowledge graph:** `memory/knowledge_graph.json` used to populate `/api/graph`

---

## Remote

This Second Brain is pushed to `Temp-Agies-Second-Brain.git` on the `second-brain` branch.

Dashboard (Vite+React+FastAPI) is on the `master` branch of the same remote.

---

## Quick Commands

```bash
# View second brain structure
find ~/.temporary-aegis -maxdepth 2 -type f | head -40

# View config
cat ~/.temporary-aegis/config/AEGIS_CONFIG.md

# View registries
cat ~/.temporary-aegis/AGENT_REGISTRY.json | python3 -m json.tool | head -20

# Run snapshot script
bash ~/.temporary-aegis/scripts/aegis-snapshot.sh

# View build log
cat ~/.temporary-aegis/BUILD_LOG.md
```
