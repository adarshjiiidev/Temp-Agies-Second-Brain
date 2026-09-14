# Train agies on PC — Environment Learning Setup

**Date:** 2026-09-12
**Purpose:** Enable agies to observe, learn, and build knowledge about the user's PC

---

## What "Training on PC" Means

agies observes the user's machine and builds a comprehensive environmental model:

1. **System state** — hardware, OS, services, processes, network, disk, memory
2. **Software inventory** — installed packages, CLI tools, configs, versions
3. **Project inventory** — all repos, their state, branches, recent activity
4. **Config inventory** — dotfiles, app configs, editor config, shell config
5. **Usage patterns** — recurring commands, frequent directories, active work
6. **Environment changes** — what changed since last observation

---

## How Training Works

### Phase 1: Baseline Snapshot (now)
- Full system audit (already done — SYSTEM_AUDIT.md)
- Project tree scan (done — 4 projects mapped)
- Config file inventory (pending)
- Software inventory (pending)
- Process/service inventory (pending)

### Phase 2: Incremental Updates (cron)
- Daily: check for changes (new files, git commits, package updates)
- Weekly: full re-scan + diff against baseline
- On-demand: user asks "what changed?" → run diff

### Phase 3: Learning (ongoing)
- Detect recurring patterns (commands, workflows, file access)
- Build preference model (what user likes, dislikes, avoids)
- Store as episodic + semantic memory

---

## PC Knowledge Base

agies will maintain a structured view of the entire machine:

```
PC KNOWLEDGE
├── Hardware (CPU, RAM, disk, GPU, network, peripherals)
├── OS (Arch Linux, kernel, packages, services, systemd)
├── Filesystem (home layout, project tree, important dirs, excludes)
├── Software (installed apps, CLI tools, versions, configs)
├── Projects (4 projects with full metadata)
├── Configs (dotfiles, app configs, editor, shell, git, etc.)
├── Services (running daemons, listening ports, cron jobs)
├── Network (interfaces, IP, DNS, firewall, open ports)
├── Processes (running processes, resource usage, parents)
├── Users (user accounts, groups, sudoers)
└── State changes (what changed, when, why)
```

---

## Omarchy Deep Integration

Since the user runs Omarchy, agies needs deep Omarchy knowledge:

### What agies knows about Omarchy
- Omarchy = Arch Linux + Hyprland + custom shell/Quickshell
- Config locations: ~/.config/hypr/, ~/.config/omarchy/, ~/.config/alacritty/, etc.
- Commands: omarchy <group> <action> — self-documenting CLI
- Command groups: theme, refresh, restart, toggle, bar, plugin, hook, install, launch, capture, reminder, pkg, setup, update
- Safe customization: edit ~/.config/, never /usr/share/omarchy/
- Hooks: omarchy hook install <event> <script>
- Themes: create custom in ~/.config/omarchy/themes/<name>/

### What agies can DO with Omarchy
- Change themes: `omarchy theme set <name>`
- Manage bar: `omarchy bar move ...`, `omarchy bar add ...`
- Plugins: `omarchy plugin clone <name>`, edit clone
- Hooks: `omarchy hook install <event> <script>`
- Screenshots: `omarchy capture screenshot`
- Reminders: `omarchy reminder <minutes> <message>`
- Update: `omarchy update`
- Restart components: `omarchy restart <component>`
- Debug: `omarchy debug --no-sudo --print`
- Reset: `omarchy refresh <component>`

### agies Omarchy skill path
- Shared skill: /home/adarshjii/.hermes/skills/omarchy/SKILL.md (loaded automatically)
- agies-specific notes: profiles/agies/skills/omarchy/ (if needed)

---

## ChatGPT Export Ingestion

### How ChatGPT Export Works
ChatGPT allows users to export their chat data as a ZIP file containing:
- `conversations.json` — all conversations with messages
- `*.json` — individual conversation files
- Metadata: timestamps, models used, titles

### Ingestion Pipeline

```
ChatGPT Export ZIP
    ↓
Extract conversations.json
    ↓
Filter: extract useful knowledge (skip casual chit-chat)
    ↓
Parse: extract facts, decisions, code snippets, preferences, lessons
    ↓
Classify: what type of memory is this?
    ↓
Store: save to appropriate PARA folder in second brain
    ↓
Link: connect to existing project notes via [[wikilinks]]
```

### What Gets Extracted
- **Project information** — discussions about specific projects
- **Architecture decisions** — why user chose X over Y
- **Code snippets** — useful code the user generated
- **Preferences** — user's stated preferences for tools, styles, approaches
- **Lessons learned** — problems solved, mistakes made
- **Goals** — user's stated objectives and plans
- **Technical conclusions** — research results, tool comparisons

### What Gets SKIPPED
- Casual conversation ("hello", "thanks", chit-chat)
- Repetitive content (already in memory)
- Sensitive data (passwords, keys, tokens — filtered by privacy rules)
- Temporary context (already expired)

### Storage Format
Extracted knowledge stored as markdown notes in:
- `./memory/1-Projects/<project>/chatgpt-<date>.md` — project-related chats
- `./memory/2-Areas/personal/chatgpt-preferences-<date>.md` — preferences
- `./memory/3-Resources/chatgpt-lessons-<date>.md` — lessons learned
- `./memory/0-Inbox/chatgpt-raw-<date>.md` — raw extracted content for triage

---

## Cron Job Setup

### Systemd Timer Approach (preferred on Arch)

```
~/.config/systemd/user/
├── aegis-ingest-chatgpt.timer      # Daily trigger
├── aegis-ingest-chatgpt.service    # Runs ingestion script
├── aegis-snapshot.timer            # Daily system snapshot
├── aegis-snapshot.service          # Runs snapshot script
└── aegis-learn.timer               # Weekly pattern detection
    └── aegis-learn.service
```

### What Each Job Does

| Timer | Schedule | Service | Action |
|-------|----------|---------|--------|
| aegis-ingest-chatgpt | Daily 03:00 | ingest-chatgpt.sh | Check for new ChatGPT export, ingest if found |
| aegis-snapshot | Daily 02:00 | snapshot-pc.sh | Snapshot system state, diff against yesterday |
| aegis-learn | Weekly Sun 04:00 | learn-patterns.sh | Detect recurring patterns, update memory |

### Manual Trigger
```bash
systemctl --user start aegis-ingest-chatgpt
systemctl --user start aegis-snapshot
systemctl --user start aegis-learn
```

### Status Check
```bash
systemctl --user list-timers | grep aegis
journalctl --user -u aegis-ingest-chatgpt -n 20
```

---

## Implementation

### 1. PC Knowledge Baseline Script
Creates a comprehensive snapshot of the current machine state.

### 2. ChatGPT Ingestion Script
Processes ChatGPT export ZIP and extracts knowledge.

### 3. Systemd Timers
Schedules the above scripts.

### 4. agies Skill for PC Training
Skill that lets agies trigger scans, read snapshots, and answer "what changed?"

---

## Security Notes

- **Sudo password (1188):** Not stored in any file. agies uses `sudo` only when needed and prompts for password interactively. For automated tasks, configure passwordless sudo for specific commands via sudoers instead.
- **ChatGPT export:** Contains user's private conversations. Ingestion filters sensitive content. User controls what gets imported.
- **System snapshots:** Stored locally only. Never sent to cloud.

---

## Manual Setup Commands (to be run)

```bash
# Create systemd user directories
mkdir -p ~/.config/systemd/user

# Create timer and service files (done by build script)

# Enable timers
systemctl --user enable --now aegis-ingest-chatgpt.timer
systemctl --user enable --now aegis-snapshot.timer
systemctl --user enable --now aegis-learn.timer

# Check status
systemctl --user list-timers | grep aegis
```

---

## What agies Can Answer After Training

- "What's installed on my PC?"
- "What changed since yesterday?"
- "Show me my Omarchy config"
- "What was I working on in ChatGPT last week?"
- "What packages did I install recently?"
- "What's my Hyprland keybinding for X?"
- "What changed in my projects?"
- "What's running on my machine right now?"
- "How much disk space do I have?"
- "What's my system load?"
