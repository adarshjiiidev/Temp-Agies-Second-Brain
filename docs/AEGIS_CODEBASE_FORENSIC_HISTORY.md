# AEGIS CODEBASE FORENSIC HISTORY (Phase 1)

Method: `git log --all`, `git diff --numstat HEAD`, `git diff --name-status -M HEAD`, `git status --porcelain`.

## 1. Version history is 4 commits deep and 16 days stale

| Commit | Date | Message | Scale |
|---|---|---|---|
| `8b4b148` | 2026-09-12 | Initial commit from Create Next App | 19 files, +7,090 |
| `dc76cb2` | 2026-09-14 | "Complete TEMPORARY AEGIS Second Brain - all agents, memory, vision, browser, computer control, knowledge graph, skills, dashboard" | 88 files, **+31,953** / -162 |
| `45011f1` | 2026-09-14 | Rewrite README (27 backend modules, 6 agent tabs, vision, browser, …) | +347 / -22 |
| `8ae0172` = HEAD | 2026-09-14 | Add `.temporary-aegis` to `.gitignore` | +3 |

Everything after 2026-09-14 is **uncommitted**:
`git diff --shortstat HEAD` = **63 files changed, 3,822 insertions(+), 16,733 deletions(-)**, plus **68 untracked paths**.

## 2. Nothing was deleted from version control

`git diff --name-status -M HEAD` → `63 M` and **zero `D`, zero `R`**.

Consequence: the "missing functionality" narrative is wrong. No file was removed from VCS. What actually happened:

1. **In-file replacement** - functionality removed by rewriting bodies, not by deleting files.
2. **Never-committed modules** - most of today's "core" was added but never tracked (see section 3).
3. **One intentional mass deletion** - `registries/MODEL_REGISTRY.json`: **+34 / -15,416**. This is the
   870-model 9Router catalogue. Its removal was a deliberate owner decision (9Router taken out of service),
   not data loss.

## 3. The current core has no history at all (highest structural risk)

24 backend modules and every peripheral panel are **untracked**, i.e. they exist only as working-tree bytes
with no recoverable revision:

* Executive/routing core: `execution_core.py`, `free_router.py`, `frontier_adapter.py`, `agent_supervisor.py`,
  `context_router.py`, `governance.py`, `openrouter_chat.py`, `skill_registry.py`, `spatial_mode.py`
* Memory: `mem0_engine.py`, `turboquant_store.py`, `universal_ingest/`, `ingest_daemon.py`,
  `project_intelligence.py`, `preferences.py`, `research_lab.py`
* Peripherals: `camera_registry.py`, `camera_event_store.py`, `camera_cli.py`, `org_cameras.py`,
  `vision_pipeline.py`, `cloudroom_bridge.py`, `linux_intelligence.py`, `integrations/`
* Frontend: `HomePanel`, `VoicePanel`, `TaskBoardPanel`, `DoctorPanel`, `SystemGraphPanel`,
  `SpatialMemoryCanvas`, `src/lib/graphLinks.ts`
* Tests: `test_camera_{authorization,e2e,hardware,pipeline}.py`, `test_agent_restart.py`,
  `test_openrouter_chat.py`, `graph-links.test.mjs`
* 21 certification/roadmap documents under `docs/`

A single bad `git checkout -- .` or `git clean -fd` would erase the majority of the system irrecoverably.
Action taken in this mission: an explicit safety baseline commit before any repair (third-party clones
under `repos/` excluded via `.gitignore`).

## 4. Where the churn is concentrated

| File | +/- | Interpretation |
|---|---|---|
| `registries/MODEL_REGISTRY.json` | +34 / -15,416 | Intentional 9Router catalogue removal; shell left behind |
| `backend/server.py` | +1,140 / -240 | Growth hub: routes added, periphery never wired to producers |
| `src/components/ObsidianGraph.tsx` | +656 / -317 | Graph rewrite (untracked docs call it certified) |
| `backend/model_router.py` | +27 / -59 | 9Router-era role table replaced; **new IDs still use the `cl/` namespace** |
| `src/components/ChatPanel.tsx` | +223 / -31 | Chat path hardened (cookie auth, mem0 write) |
| `src/components/AgentTabs.tsx` | +20 / -85 | Net capability loss in agent tab surface |
| `src/lib/store.tsx` | +9 / -31 | WS state consumption shrank - contributes to stale dashboard data |
| `backend/{deepseek,openclaw}_harness.py` | +42..44 / -33..47 | Migrated off 9Router transport, docstrings + registry cmd left behind |
| `registries/AGENT_REGISTRY.json` | +44 / -46 | Frontier/agent entries edited; `installed` flags and commands now wrong |

## 5. Orphans, disagreement and stale claims

* **Zero-importer modules** (dead or awaiting a caller): `agent_runner.py`, `camera_cli.py`,
  `deepseek_harness.py`, `openclaw_harness.py`, `vision_pipeline.py` (also import-broken).
* **Registry vs reality:** `AGENT_REGISTRY.json` marks `deepseek`/`openclaw` `installed: true` although no such
  binary exists and their `command` re-enters `backend.agent_runner --agent <same-id>` (self-recursion);
  marks `frontier` `installed: false` although `~/Work/FrontierAgent/.venv` exists, and stores an
  unrenderable template `python -m apodex -p <task> --mode react|agent_team --no-tui`.
  `MODEL_REGISTRY.json` retains `9router_url` and `routing.default = cl/openai/gpt-5.6-terra`.
* **Registries are 12 days stale** (`generated_at: 2026-09-18`) while `build_master_registries.py` has no scheduler.
* **Docs claim more than code does**: `AEGIS_REAL_CAMERA_CERTIFICATION.md`,
  `AEGIS_VISION_TURBOQUANT_CERTIFICATION.md`, `AEGIS_FINAL_SYSTEM_CERTIFICATION.md` describe cameras/vision
  as certified while the runtime registry contains only test rows and the vision model method has zero callers.
* **Recoverable snapshots exist only as Cline stashes** (`0435943`, `30beed0`, `7cd0773`, `8bcf2e5` …
  `cline checkpoint session=1790768451799_94wvn run=3..6`, all 2026-09-30). They are not browsable history
  and must not be relied on as the recovery path.

## 6. Which old implementation is better than the current one

| Area | Old (HEAD) | Current (worktree) | Verdict |
|---|---|---|---|
| Model catalogue | 870 concrete models with real IDs | empty `models: []` + `cl/` IDs in `config.py` | Old had truth, current has reachability; **keep current transport, rebuild catalogue from live provider list** |
| Agent tabs | 6 tab surface | 3 tab surface | Old surface richer; restore via real registry, not by reverting file |
| Chat memory | none | mem0 write-back + provenance | Current better - keep |
| Camera/vision | absent | present but test-contaminated | Keep code, quarantine state, fix truthfulness |
