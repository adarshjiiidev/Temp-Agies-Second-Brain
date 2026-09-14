# TEMPORARY AEGIS — MEMORY SYSTEM SCHEMA

**Version:** 1.0
**Date:** 2026-09-12
**Purpose:** Defines the personal memory architecture for TEMPORARY AEGIS

---

## 1. MEMORY TIERS

### 1.1 Working Memory (WM)
**Lifetime:** Current session only (volatility: high)
**Storage:** In-context (conversation history)
**Purpose:** Short-term reasoning state, current task context, temporary variables
**Schema:**
```json
{
  "type": "working_memory",
  "session_id": "uuid",
  "created_at": "ISO8601",
  "data": {},
  "ttl_seconds": 3600,
  "expires_at": "ISO8601"
}
```
**Access:** Immediate, always in context
** eviction:** End of session

### 1.2 Episodic Memory (EM)
**Lifetime:** Days to months (volatility: medium)
**Storage:** Filesystem (memory/YYYY-MM-DD.md) + SQLite
**Purpose:** Timestamped record of significant events, conversations, discoveries
**Schema:**
```json
{
  "type": "episodic",
  "event_id": "uuid",
  "date": "YYYY-MM-DD",
  "time": "HH:MM",
  "session_id": "uuid",
  "summary": "1-3 sentence description",
  "context": "what led to this",
  "outcome": "what happened",
  "importance": "high|medium|low",
  "source": "user|agent|system",
  "project": "project_name|null",
  "tags": ["tag1", "tag2"]
}
```
**Access:** Search by date, project, tags, importance
**Retention:** Review weekly, archive monthly

### 1.3 Semantic Memory (SM)
**Lifetime:** Years (volatility: low)
**Storage:** Filesystem (MEMORY.md, knowledge/*.md) + SQLite FTS
**Purpose:** Stable facts, learned knowledge, decisions, preferences
**Schema:**
```json
{
  "type": "semantic",
  "fact_id": "uuid",
  "category": "fact|observation|inference|preference|decision|skill",
  "content": "the actual knowledge",
  "source": "where this came from",
  "date_learned": "YYYY-MM-DD",
  "confidence": 0.0-1.0,
  "last_verified": "YYYY-MM-DD|null",
  "status": "active|superseded|archived",
  "project": "project_name|null",
  "proof_points": ["evidence1", "evidence2"]
}
```
**Access:** Full-text search, semantic search, category filter
**Retention:** Never auto-delete. Manual review quarterly.

### 1.4 Project Memory (PM)
**Lifetime:** Project lifetime (volatility: low-medium)
**Storage:** Per-project memory/ directories + project intelligence index
**Purpose:** Project-specific context, architecture, decisions, TODOs, state
**Schema:**
```json
{
  "type": "project_memory",
  "project_id": "project_name",
  "data": {
    "architecture": "description or link",
    "key_modules": ["module1", "module2"],
    "entry_points": ["file1", "file2"],
    "frameworks": ["framework1"],
    "dependencies": {"dep1": "version"},
    "active_branch": "branch_name",
    "last_commit": "hash",
    "uncommitted_changes": "description",
    "todos": [{"task": "...", "status": "open|done|blocked"}],
    "current_problems": ["problem1"],
    "known_decisions": [{"decision": "...", "rationale": "...", "date": "..."}]
  },
  "last_updated": "ISO8601",
  "update_source": "git_scan|user_mention|agent_analysis"
}
```
**Access:** Project name lookup, hierarchical drill-down
**Retention:** Updated on git changes, user mentions, periodic rescan

### 1.5 Decision Memory (DM)
**Lifetime:** Permanent (volatility: very low)
**Storage:** MEMORY.md decisions section + decisions/*.md
**Purpose:** Record of significant decisions and their rationale
**Schema:**
```json
{
  "type": "decision",
  "decision_id": "uuid",
  "title": "what was decided",
  "date": "YYYY-MM-DD",
  "context": "what problem led to this",
  "options_considered": ["option1", "option2"],
  "chosen": "what was selected",
  "rationale": "why this was chosen",
  "consequences": "what this implies",
  "reviewed": "YYYY-MM-DD|null",
  "still_valid": true|false,
  "superseded_by": "decision_id|null"
}
```
**Access:** Search by title, date, project
**Retention:** Permanent unless explicitly superseded

### 1.6 Preference Memory (Pm)
**Lifetime:** Years (volatility: low)
**Storage:** USER.md + preferences/*.md
**Purpose:** User's stable preferences, communication style, working habits
**Schema:**
```json
{
  "type": "preference",
  "preference_id": "uuid",
  "category": "communication|workflow|technical|personal",
  "directive": "imperative statement (Always/Never/Prefer)",
  "observed": "YYYY-MM-DD",
  "status": "active|superseded",
  "evidence": "what led to this observation",
  "applicability": "always|specific_context"
}
```
**Access:** Loaded at session start, referenced during interaction
**Retention:** Active until superseded. Old entries marked superseded, not deleted.

### 1.7 Skill Memory (SkM)
**Lifetime:** As long as skill is relevant (volatility: low)
**Storage:** skills/ directory + skill registry
**Purpose:** Learned and curated skills with metadata
**Schema:**
```json
{
  "type": "skill",
  "skill_id": "skill-name",
  "name": "Human-readable name",
  "version": "1.0.0",
  "purpose": "What this skill does",
  "inputs": ["required input 1", "required input 2"],
  "outputs": ["expected output 1"],
  "required_tools": ["tool1", "tool2"],
  "permissions": ["permission1"],
  "workflow": ["step1", "step2", "step3"],
  "failure_modes": ["failure1", "failure2"],
  "verification": "how to verify success",
  "confidence": 0.0-1.0,
  "tests": ["test1", "test2"],
  "created_at": "ISO8601",
  "last_verified": "ISO8601",
  "status": "active|experimental|deprecated"
}
```
**Access:** Skill name lookup, capability discovery
**Retention:** Active until deprecated or replaced

### 1.8 Environment Memory (EM)
**Lifetime:** Until environment changes (volatility: medium)
**Storage:** environment.md + environment/*.md
**Purpose:** Record of the user's development environment, tools, configurations
**Schema:**
```json
{
  "type": "environment",
  "environment_id": "uuid",
  "category": "hardware|software|tool|service|config",
  "name": "name of the thing",
  "description": "what it is",
  "version": "version or 'latest'",
  "location": "path or URL",
  "config": "relevant configuration (no secrets)",
  "status": "active|inactive|changed",
  "discovered": "YYYY-MM-DD",
  "last_verified": "YYYY-MM-DD"
}
```
**Access:** Category search, name lookup
**Retention:** Updated when environment changes detected

### 1.9 Goal Memory (GM)
**Lifetime:** Until goal achieved or abandoned (volatility: medium)
**Storage:** goals/*.md + goals.sqlite (from Codex)
**Purpose:** Active and completed goals, milestones, progress tracking
**Schema:**
```json
{
  "type": "goal",
  "goal_id": "uuid",
  "title": "goal description",
  "status": "active|in_progress|completed|abandoned|blocked",
  "priority": "high|medium|low",
  "created": "YYYY-MM-DD",
  "target": "YYYY-MM-DD|null",
  "project": "project_name|null",
  "milestones": [{"milestone": "...", "status": "...", "date": "..."}],
  " blockers": ["blocker1"],
  "notes": "progress notes"
}
```
**Access:** Goal status lookup, project filter
**Retention:** Active goals kept prominent. Completed goals archived.

### 1.10 Research Memory (RM)
**Lifetime:** Indefinitely (volatility: low)
**Storage:** research/*.md + research database
**Purpose:** Research queries, findings, sources, conclusions
**Schema:**
```json
{
  "type": "research",
  "research_id": "uuid",
  "query": "what was researched",
  "date": "YYYY-MM-DD",
  "sources": [{"url": "...", "title": "...", "reliability": "high|medium|low"}],
  "claims": [{"claim": "...", "source": "...", "confidence": 0.0-1.0}],
  "conclusion": "synthesized finding",
  "uncertainty": "what we don't know",
  "project_relation": "project_name|null",
  "follow_up": "next steps"
}
```
**Access:** Query search, topic filter, project relation
**Retention:** Permanent. Source provenance always preserved.

### 1.11 Temporary Memory (TM)
**Lifetime:** Configurable TTL (volatility: high)
**Storage:** temp/ directory + ttl index
**Purpose:** Short-lived scratch data, intermediate results, transient context
**Schema:**
```json
{
  "type": "temporary",
  "temp_id": "uuid",
  "data": {},
  "created_at": "ISO8601",
  "ttl_seconds": 3600,
  "expires_at": "ISO8601",
  "purpose": "why this exists temporarily"
}
```
**Access:** Key lookup, TTL-aware retrieval
**Retention:** Auto-expire based on TTL. Superseding: new temp replaces old.

---

## 2. MEMORY METADATA STANDARDS

Every persistent memory entry MUST have:

| Field | Type | Required | Description |
|---|---|---|---|
| `source` | string | YES | Where this memory came from (user, agent, system, external) |
| `date` | ISO8601 | YES | When this was created/recorded |
| `confidence` | float 0-1 | YES | How confident we are in this memory's accuracy |
| `type` | string | YES | Which memory tier this belongs to |
| `privacy` | string | YES | P0 (private), P1 (personal), P2 (project), P3 (public) |
| `project` | string|null | NO | Which project this relates to (if any) |
| `last_verified` | ISO8601|null | NO | When this was last checked for accuracy |
| `status` | string | YES | active, superseded, archived, expired |

---

## 3. FACT vs OBSERVATION vs INFERENCE vs PREFERENCE vs PREDICTION

TEMPORARY AEGIS maintains strict separation:

| Type | Definition | Example | Confidence |
|---|---|---|---|
| **FACT** | Directly observed, verifiable | "User has Python 3.11.16 installed" | High (0.9+) |
| **OBSERVATION** | Seen but not independently verified | "User seemed frustrated with the build" | Medium (0.5-0.8) |
| **INFERENCE** | Deduced from facts/observations | "User prefers fast models for routine tasks" | Medium-low (0.3-0.7) |
| **PREFERENCE** | User's stated or demonstrated preference | "User prefers concise responses" | High (0.8+) when stated |
| **PREDICTION** | Forecast about future | "User will work on Aegis this week" | Low (0.2-0.5) |

**RULE:** An inference MUST NOT be silently stored as a fact. If stored as inference, it must be labeled as such and have lower confidence.

---

## 4. PRIVACY CLASSIFICATION

| Level | Label | Contains | Storage | Access |
|---|---|---|---|---|
| P0 | PRIVATE | Passwords, API keys, tokens, SSH keys, secrets | Encrypted, never cloud | Local only |
| P1 | PERSONAL | Personal info, conversations, preferences | Local preferred | User + local agent |
| P2 | PROJECT | Project code, architecture, decisions | Project-local | User + project agents |
| P3 | PUBLIC | General knowledge, documentation | Any | Any |

**AUTOMATIC FILTERING:** Patterns in `.env`, `*.pem`, `*.key`, `id_rsa*`, `id_ed25519*`, `credentials*`, `secrets*`, `password*` are automatically classified P0.

---

## 5. STORAGE LAYOUT

```
~/.temporary-aegis/
├── memory/
│   ├── episodic/
│   │   └── YYYY-MM-DD.md          # Daily episodic records
│   ├── semantic/
│   │   ├── MEMORY.md              # Main semantic memory (curated)
│   │   └── knowledge/             # Organized knowledge by topic
│   ├── project/
│   │   ├── Aegis.md               # AEGIS project intelligence
│   │   ├── repusense.md           # repusense project intelligence
│   │   ├── world-viewer.md        # world-viewer project intelligence
│   │   └── chrome-extra.md        # chrome-extra project intelligence
│   ├── decisions/
│   │   └── YYYY-MM-DD_decision.md # Individual decision records
│   ├── preferences/
│   │   └── observed_preferences.md # User preference directives
│   ├── skills/
│   │   └── skill_registry.json    # Learned and curated skills
│   ├── environment/
│   │   └── environment.md         # Environment snapshot
│   ├── goals/
│   │   └── active_goals.md        # Current goals
│   ├── research/
│   │   └── research_index.json    # Research memory index
│   └── temp/
│       └── *.json                 # Temporary memory (TTL-managed)
├── PROJECT_STATE.json             # Overall project state
├── MODEL_REGISTRY.json            # Model registry
├── TOOL_REGISTRY.json             # Tool registry
├── SKILL_REGISTRY.json            # Skill registry
├── MASTER_TODO.md                 # Build TODO
├── BUILD_LOG.md                   # Build log
├── BLOCKERS.md                    # Blockers
├── CHANGELOG.md                   # Changelog
└── SELF_AUDIT.md                  # Self-audit results
```

---

## 6. RETRIEVAL STRATEGY

### 6.1 Smart Context Assembly
When responding to a user request, assemble context from:

1. **Current task context** — what the user is working on now
2. **Current project context** — project intelligence for active project
3. **Recent activity** — last 24h episodic memory
4. **Relevant semantic memory** — FTS search on query terms
5. **Relevant skills** — skills matching the task type
6. **Relevant tools** — tools that can help with this task
7. **Relevant decisions** — decisions affecting this area
8. **Environment context** — relevant environment facts

### 6.2 Retrieval Methods
- **Keyword search** — SQLite FTS for exact term matches
- **Semantic search** — embedding-based similarity (when available)
- **Metadata filter** — by project, date, type, privacy, confidence
- **Recency boost** — recent memories weighted higher
- **Importance boost** — high-importance memories weighted higher
- **Confidence filter** — low-confidence memories flagged, not suppressed

### 6.3 Reranking
After initial retrieval:
1. Filter by privacy (don't return P0 to inappropriate contexts)
2. Filter by confidence threshold (default: 0.3 minimum)
3. Rerank by relevance to current query
4. Limit total context to reasonable budget
5. Flag inferences vs facts in the assembled context

---

## 7. INGESTION STRATEGIES

### 7.1 On-Demand Ingestion
Triggered by user request: "Remember this", "Learn this", explicit save.

### 7.2 Incremental Ingestion
- **Git-triggered:** On git commit/push in watched projects, update project intelligence
- **Filesystem-triggered:** On file changes in watched directories, reindex
- **Session-triggered:** At session end, extract episodic memories from conversation

### 7.3 Scheduled Ingestion
- **Daily summary:** Each day, compile significant events into episodic memory
- **Weekly review:** Review recent memories, promote stable facts to semantic memory
- **Monthly audit:** Check for stale, duplicate, or incorrect memories

### 7.4 Deduplication
- Hash content before storing
- If identical content exists, update last_verified instead of duplicating
- If similar content exists, merge or link rather than duplicate

---

## 8. EXPIRATION AND CLEANUP

### 8.1 TTL-Based Expiration
Temporary memories auto-expire. Expired memories are moved to archive, not deleted immediately.

### 8.2 Superseding
When new information contradicts old:
1. Mark old memory as `superseded`
2. Record what supersedes it
3. Keep old memory for audit trail (unless privacy requires deletion)

### 8.3 Deletion
User can explicitly request deletion of:
- Specific memories
- Entire project memory
- Preferences
- Research records

Deletion is permanent. No undo.

---

## 9. VERIFICATION

### 9.1 Confidence Tracking
- New memories start with baseline confidence
- Verified memories have confidence boosted
- Contradicted memories have confidence reduced
- Memories below confidence threshold are flagged for review

### 9.2 Last Verified Tracking
- Every memory has `last_verified` field
- Memories not verified in 90+ days are flagged
- User can request verification of specific memories

### 9.3 Source Tracking
- Every memory records its source
- Sources can be traced back
- fabricated sources are never created

---

## 10. USER CONTROL INTERFACE

Commands the user can issue:

| Command | Action |
|---|---|
| "Inspect memory" | Show current memory contents by category |
| "Search memory for X" | Search semantic memory for X |
| "Delete this memory" | Delete specified memory |
| "Forget this project" | Delete all project-specific memory |
| "Pause ingestion" | Stop automatic ingestion temporarily |
| "Resume ingestion" | Resume automatic ingestion |
| "Run ingestion" | Trigger manual ingestion run |
| "Preview ingestion" | Show what would be ingested |
| "Export knowledge" | Export memory in portable format |
| "Audit knowledge" | Check for stale, duplicate, incorrect memories |

---

## 11. IMPLEMENTATION NOTES

### 11.1 What Exists Now
- **Hermes memory:** SQLite state.db with FTS (messages, sessions)
- **Hermes memories directory:** ~/.hermes/memories/ (currently empty)
- **OpenClaw workspace memory:** memory/ directory with daily notes
- **Codex memories:** memories_1.sqlite (Codex's own memory)

### 11.2 What TEMPORARY AEGIS Adds
- Structured memory schema (this document)
- Project intelligence indexes
- Decision memory tracking
- Preference memory from USER.md
- Skill registry with metadata
- Research memory with provenance
- Environment memory snapshot
- Goal tracking
- TTL-based temporary memory

### 11.3 Integration Points
- Hermes memory provider can be extended to use AEGIS schema
- OpenClaw memory plugin can read/write AEGIS memory format
- Codex goals can feed into AEGIS goal tracking
- All three systems can share the same underlying knowledge

---

*This schema is the foundation. Implementation follows in the memory system build phase.*
