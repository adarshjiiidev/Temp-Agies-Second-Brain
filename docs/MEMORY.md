# AEGIS Cognitive Memory System

**Storage Location:** `/home/adarshjii/ObsidianVault/`  
**Consolidation Pipeline:** `/home/adarshjii/aegis-dashboard/aegis_consolidate.py`  
**Automated Timers:** `aegis-consolidate.timer` (15 min) & `aegis-consolidate-daily.timer` (daily 3PM)  

---

## 1. Memory Taxonomies

1. **Episodic & Agent Session Memory:**
   - Captured from Antigravity brains (`~/.gemini/antigravity-ide/brain/`), Codex CLI (`~/.codex/`), Claude, and Hermes.
   - Stored in `~/ObsidianVault/agies/by-agent/` with session notes, transcripts, files modified, and decisions.
2. **Project Living Memory:**
   - Maintained under `~/ObsidianVault/agies/PROJECTS/<project>/MEMORY.md`.
   - Tracks executive summary, key architecture, files, decisions, and discoveries for all 9 projects:
     - `aegis-dashboard`
     - `Aegis` (Rust/Python)
     - `chrome-extra`
     - `repusense`
     - `world-viewer`
     - `DeepSeek-V3`
     - `hermes-agent`
     - `openclaw`
     - `opencode`
3. **Semantic Knowledge & PARA Hierarchy:**
   - `0-Inbox/`: Captures & incoming uncurated ideas.
   - `1-Projects/`: 9 active projects with status, docs, and goals.
   - `2-Areas/`: System standards, architecture principles, OS configs.
   - `3-Resources/`: Model routing tables, benchmarks, cheat sheets.
   - `4-Archives/`: Completed milestones and historical codebases.
4. **Experience & Decision Memory:**
   - `DECISIONS.md`: Chronological architectural choices (e.g. Vite migration, SSE stream parser).
   - `ERRORS_AND_FIXES.md`: Encountered bugs and verified resolutions.
   - `DAILY_BRIEFING.md`: Consolidated summary of daily system-wide activity.

---

## 2. Dynamic Memory Retrieval

- When the user chats with Agies in `ChatPanel.tsx`, `backend/server.py` invokes `get_relevant_memory_context(query)`.
- It dynamically injects relevant living memories, architectural decisions, and daily briefings without dumping raw unprompted stats into conversational turns.
