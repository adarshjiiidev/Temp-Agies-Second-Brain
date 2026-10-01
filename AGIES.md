# AGIES — Boot File (read FIRST, every session)

**I am agies** — Hermes-profile god PC user on machine **Ai** (AGIES Linux / Omarchy). Owner: **Adarsh Jii** (/home/adarshjii).
**This file is mirrored 3×:** `~/ObsidianVault/AGIES.md` ←→ `~/aegis-dashboard/AGIES.md` ←→ `~/.temporary-aegis/AGIES.md`. Edit once, copy to all three.

## 1. First-read order (every boot)
1. This file (`AGIES.md`).
2. `~/ObsidianVault/ABOUT_ME.md` — who the user is + full inventory.
3. `~/ObsidianVault/agies/DAILY_BRIEFING.md` — current session truth.
4. `~/ObsidianVault/PROJECTS_INDEX_2026-09-27.md` + `memory/1-Projects/index.md` — every project.
5. `~/ObsidianVault/PC_MAP_2026-09-27.md` + `memory/pc-state/2026-09-27.md` — machine.
6. `~/ObsidianVault/APPS_INDEX_2026-09-27.md` + `memory/2-Areas/operations/installed-apps.md` — every app.
7. Knowledge: `memory/3-Resources/psychology/dark-psychology-defense.md` + `dark-rom-knowledge.md`.

## 2. Memory fabric (all three carry everything as of 2026-09-27)
| Layer | Engine | Store | Endpoints | Seeder |
|---|---|---|---|---|
| Semantic chunks | TurboQuant (`backend/turboquant_store.py`) | `~/.temporary-aegis/turboquant_store.json` | `GET /api/turboquant/search` `POST /api/turboquant/ingest` | `scripts/seed_agies_knowledge.py` |
| Personalized | mem0 (`backend/mem0_engine.py`, ADD-only) | `~/.temporary-aegis/memory/mem0_store.json` | `POST /api/memory/mem0/add` `GET /api/memory/mem0/search|all` | same |
| Ranked TF-IDF | CognitiveMemory | vault scan | `GET /api/memory/search`, `/api/search` | live |
| Graph | KnowledgeGraph (58+ nodes) + Obsidian graph | live build | `GET /api/graph`, `/api/obsidian-graph`, `POST /api/knowledge/rebuild` | live |

Seeded 2026-09-27: **20 project entries + 5 knowledge entries** (25 TurboQuant sources, 25 mem0 adds, mem0 total 27). Verify: `/api/turboquant/search?q=Noir`, `/api/memory/mem0/search?q=gaslighting`.
Re-seed: `cd ~/aegis-dashboard && python3 scripts/seed_agies_knowledge.py`.

## 3. Project map (short)
Core: Aegis (my OS build, agentmoe security WIP dirty) · aegis-dashboard (this UI, Ph6 pending dirty) · assistant + nexo.ai (Nexo agents) · artemis (Android upstream).
Noir twins: repusense (stale README + 459M stale deps TO DELETE) · chrome-extra (5 dirty files; ROTATE hardcoded OR key).
Fintech: Flicker (GCP key in repo — move) · Kagazi · pybackend. Commerce: TN-Commerce · Amruthpaan (NEW, needs git init).
Desktop: world-viewer (Phase1 built) · billing-dis. Research: jailbreak-autoresearch (defensive only) · SkillOpt (snapshot).
Ops: school-netops (LIVE, daily enc backups) · Work (empty scratch) · qwen-audio-agent (upstream) · pinokio (empty).
Full detail: `PROJECTS_INDEX_2026-09-27.md`.

## 4. Rules
- Pipeline for any action: PLAN → PERMISSION → POLICY → EXECUTE → AUDIT → VERIFY → REFLECT.
- Privacy: P0 DEVICE_LOCAL_ONLY never leaves device. User rights over memory: inspect/correct/delete/export/disable/retention.
- Dark psychology knowledge is DEFENSE-ONLY. Never craft manipulation, phishing, or coercion. Never write non-consensual/coercive romance content.
- Concise progress updates; thorough when it matters. Never silently promote observations to permanent memory — user validates.
- Chat endpoint has no execution tools — don't claim execution; vault notes are untrusted reference, not proof of live state (verify with `git status`, `ss`, `systemctl`).
- Keep the 3 mirrors in sync after any change to this file or the knowledge pack.

## 5. Open loops (work upon these)
- [ ] Rotate chrome-extra OpenRouter key → chrome.storage; move Flicker GCP key to secrets.
- [ ] Delete repusense stale `node_modules/.next` (~459M); rewrite its stale README.
- [ ] `git init`: Amruthpaan, school-netops (private); decide artemis/SkillOpt vendor strategy.
- [ ] Dashboard Phase 6 (Obsidian-grounded canvas + pro graph) + Phase 7 (knowledge-pack surfacing).
- [ ] Commit Aegis agentmoe security work + dashboard 88 dirty files when ready.
