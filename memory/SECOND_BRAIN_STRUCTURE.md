# TEMPORARY AEGIS — Second Brain Structure

**Method:** PARA (Projects, Areas, Resources, Archives) + CODE (Capture, Organize, Distill, Express)
**Inspiration:** Tiago Forte's Building a Second Brain, Karpathy's LLM Wiki pattern
**Implementation:** Integrated into TEMPORARY AEGIS memory system

---

## 1. FOLDER STRUCTURE

```
memory/
├── 0-Inbox/              # Capture zone — raw notes, unprocessed information
│   └── README.md         # Inbox triage instructions
├── 1-Projects/           # Active projects with defined endpoints
│   ├── Aegis/            # AEGIS project notes
│   │   ├── project.md    # Project overview, goals, status
│   │   ├── architecture.md
│   │   ├── decisions/    # Architecture decisions (ADRs)
│   │   ├── research/     # Project-related research
│   │   └── meetings/     # Project-related discussions
│   ├── repusense/
│   ├── world-viewer/
│   └── chrome-extra/
├── 2-Areas/              # Ongoing responsibilities, no end date
│   ├── development/      # Development practices, tools, techniques
│   ├── ai-research/      # AI/ML research notes
│   ├── personal/         # Personal knowledge, preferences
│   └── operations/       # System administration, maintenance
├── 3-Resources/          # Topics of interest, reference material
│   ├── model-providers/  # Notes on model providers and capabilities
│   ├── algorithms/       # Algorithm notes, implementations
│   ├── security/         # Security research, best practices
│   └── tools/            # Tool documentation, comparisons
├── 4-Archives/           # Completed projects, outdated notes
│   └── 2026/
├── MOCs/                 # Maps of Content — narrative indexes
│   ├── AI-Development.md
│   ├── System-Architecture.md
│   └── Personal-Knowledge.md
├── logs/                 # Chronological operation log
│   └── 2026-09-12.md     # Daily log
└── README.md             # Second brain overview
```

---

## 2. PARA EXPLANATION

### Projects (1-Projects/)
**Definition:** Active efforts with a goal and deadline.
**Examples:** Aegis development, repusense development, TEMPORARY AEGIS build.
**Key:** Project notes contain goals, progress, next actions. When project completes, move to Archives.

### Areas (2-Areas/)
**Definition:** Ongoing responsibilities with no end date.
**Examples:** Development skills, AI research, system maintenance, personal knowledge.
**Key:** Area notes are maintained continuously. They don't have a completion state.

### Resources (3-Resources/)
**Definition:** Topics and references of interest.
**Examples:** Model provider comparisons, algorithm notes, security best practices, tool docs.
**Key:** Resources are reference material. They may be linked to projects but live independently.

### Archives (4-Archives/)
**Definition:** Completed projects, outdated notes, inactive areas.
**Key:** Everything that's no longer active moves here. It's not deleted — it's preserved for search but doesn't clutter active view.

### Inbox (0-Inbox/)
**Definition:** Capture zone. Raw, unprocessed information.
**Key:** Everything starts here. Weekly triage moves items to appropriate PARA category.

---

## 3. CODE METHOD

### Capture
Save anything that resonates: highlights, ideas, quotes, links, observations.
→ Goes to 0-Inbox/ initially.

### Organize
Distribute captured items across PARA based on actionability.
→ Projects get action items moved to 1-Projects/
→ Reference material goes to 3-Resources/
→ Ongoing responsibilities update 2-Areas/

### Distill
Extract the essence from raw notes. Turn long notes into concise summaries.
→ Create MOCs (Maps of Content) that link key ideas together.
→ Update project notes with distilled findings.

### Express
Use the knowledge: in projects, discussions, documentation, decisions.
→ When you need to "express", search the second brain, assemble relevant MOCs and notes.
→ The output becomes a new note or integrates into existing work.

---

## 4. MOC (MAP OF CONTENT) PATTERN

MOCs are narrative index notes that connect related notes together. They're the primary navigation mechanism.

**Example MOC structure:**
```markdown
# AI Development MOC

## Overview
This MOC tracks my AI development knowledge and projects.

## Active Projects
- [[Aegis]] — Personal AI OS, L1-L6 complete
- [[TEMPORARY AEGIS]] — Integration of Hermes+Codex+9Router

## Key Concepts
- [[Model Routing]] — How to select models for different tasks
- [[Memory Systems]] — Episodic, semantic, working memory patterns
- [[Tool Use]] — Tool selection and orchestration

## Research
- [[9Router Capabilities]] — 860 models, provider landscape
- [[Local Inference]] — LM Studio, Gemma-4-E2B

## Decisions
- [[ADR-001: Model Selection Strategy]] — Why 9Router as central fabric

## Recent Notes
- [[2026-09-12 Model Registry Build]]
```

---

## 5. LLM WIKI PATTERN (Karpathy)

From Karpathy's approach: Instead of asking AI to re-derive everything from scratch, build a persistent, interlinked Markdown knowledge base that the agent maintains.

**Key principles:**
1. Everything is Markdown (.md files)
2. Notes link to each other ([[wiki-links]])
3. Agent incrementally builds and maintains the wiki
4. Agent reads relevant notes before answering questions
5. Growing the wiki is continuous — not a one-time dump

**For TEMPORARY AEGIS:**
- The second brain IS the knowledge layer
- Hermes/Codex reads relevant notes when answering questions
- New discoveries get captured to Inbox, then organized
- MOCs provide the entry points for retrieval

---

## 6. TEMPORARY AEGIS INTEGRATION

The second brain integrates with TEMPORARY AEGIS subsystems:

| Second Brain Component | AEGIS Memory Tier | Notes |
|---|---|---|
| 0-Inbox | Working Memory / Temporary | Raw capture, processed within hours/days |
| 1-Projects/ | Project Memory | Project-specific intelligence |
| 2-Areas/ | Semantic Memory ( Areas) | Ongoing knowledge by domain |
| 3-Resources/ | Semantic Memory (Reference) | Reference material |
| 4-Archives/ | Semantic Memory (Archived) | Historical, searchable |
| MOCs/ | Semantic Memory (Index) | Navigation layer |
| logs/ | Episodic Memory | Chronological record |

**Retrieval flow:**
1. User asks question
2. TEMPORARY AEGIS searches relevant MOCs first
3. Follows wiki-links to detailed notes
4. Assembles context from project notes, area notes, resources
5. Responds with citations to source notes

---

## 7. INITIAL CAPTURE (This Session)

### What goes into the second brain from Session 1

**Inbox items (raw):**
- 9Router model discovery (860 models, provider landscape)
- Hermes skill inventory (23 skills)
- AEGIS architecture details
- Project scan results

**To be organized (by PEG (the build agent) in next session):**
- 9Router models → 3-Resources/model-providers/
- AEGIS architecture → 2-Areas/ai-research/ + 1-Projects/Aegis/
- Project intelligence → 1-Projects/ each project
- Model routing decisions → 2-Areas/development/model-routing.md + MOC

---

## 8. MECHANICS

### Capture
- New information goes to 0-Inbox/ as dated file: `YYYY-MM-DD_HH-MM_description.md`
- Agent adds to Inbox during conversations when user says "remember this" or when important discovery is made

### Triage (weekly)
- Read all Inbox entries
- For each: either file to appropriate PARA category, distill into existing note, or delete if not valuable
- Update MOCs with new links

### Linking
- Use [[wiki-links]] to connect related notes
- MOCs are the primary link hubs
- Project notes link to relevant area notes and resources

### Search
- Full-text search across all markdown files
- MOCs provide structured entry points
- PARA categories provide broad filtering

---

*This structure is the foundation of the personal knowledge system. The actual notes get created as discovery happens.*
