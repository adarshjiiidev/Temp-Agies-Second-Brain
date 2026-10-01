# AGIES Knowledge Pack — Dashboard Integration (2026-09-27)

How the full knowledge (every project + every app + dark-psychology/dark-rom) is wired into this dashboard. Boot order: `AGIES.md` (repo root) first.

## What was added
- `AGIES.md` (repo root, mirrored to `~/ObsidianVault/AGIES.md` + `~/.temporary-aegis/AGIES.md`) — first-read boot file.
- `scripts/seed_agies_knowledge.py` — seeds TurboQuant + mem0 with 20 projects + 5 knowledge entries. Run: `python3 scripts/seed_agies_knowledge.py`.
- Vault notes (auto-surfaced via Vault Explorer `/api/memory-files`, Constellation Graph `/api/obsidian-graph`, Spatial Canvas):
  - `ABOUT_ME.md`, `PROJECTS_INDEX_2026-09-27.md`, `PC_MAP_2026-09-27.md`, `WORK_OVERVIEW.md`, `APPS_INDEX_2026-09-27.md`
  - `memory/1-Projects/index.md` (17 entries) + per-project notes incl. new Amruthpaan/artemis/SkillOpt/school-netops
  - `memory/2-Areas/operations/installed-apps.md` (899 pkgs, 50+ apps)
  - `memory/3-Resources/psychology/dark-psychology-defense.md` (defense-only) + `dark-rom-knowledge.md` (3-way disambiguation)
  - `memory/pc-state/2026-09-27.md`
- `backend/config.py` `PROJECTS` now also returns known non-git roots (Amruthpaan, artemis/artemis-main, SkillOpt, school-netops, Work, netops-backups, qwen-audio-agent, pinokio) so `/api/intelligence` + workspace crawl cover ALL projects, not just git ones.

## Endpoints carrying the pack
- `GET /api/turboquant/search?q=` — semantic chunks (25 sources seeded). Try `q=Noir`, `q=gaslighting`.
- `POST /api/turboquant/ingest` — add chunks with provenance.
- `POST /api/memory/mem0/add` / `GET /api/memory/mem0/search|all` — personalized memory (27 total after seed).
- `GET /api/intelligence` — host + per-project summaries (now includes non-git projects).
- `GET /api/projects`, `/api/mocs`, `/api/obsidian-graph` — vault surfacing (automatic for new notes).

## Frontend surfacing (no new components needed)
Vault Explorer, GlobalSearchModal, Constellation Graph, Spatial Canvas, and ChatPanel (via ContextRouter + TF-IDF injection) all read the vault live — new notes appear without code changes. For Phase 7, consider: a Knowledge Pack shortcut row (dark-psychology, dark-rom, installed-apps) in VaultExplorer + a `/knowledge` chat slash command.

## Safety
Dark-psychology content is recognition-and-defense only. Chat system prompt already constrains execution claims; keep it so. Never add manipulation/phishing generation capabilities.
