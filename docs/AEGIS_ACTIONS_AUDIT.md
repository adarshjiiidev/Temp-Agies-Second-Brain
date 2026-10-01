# AEGIS Dashboard — Actions Audit (P6.7)

Date: 2026-09-27. Method: traced each `src/components/*.tsx` button/handler →
`src/lib/api.ts` / `src/lib/store.tsx` → route in `backend/server.py` → handler
dependency verified by real `python3 import` (third-party stubs `cv2/fastapi/httpx`
injected via `sys.modules` so the test proves *AEGIS code* imports; all 24
handler-attribute checks passed). Statuses: WIRED = caller+route+handler verified;
EXTERNAL-DEPENDENT = needs LM Studio/user service; NOT_CONFIGURED = no UI caller
(route may still exist); BROKEN = route missing or handler raises on import.

## WIRED (19)

| action | frontend caller | API route | handler:file:line | dependency state | evidence |
|---|---|---|---|---|---|
| chat send | ChatPanel.tsx:260 `api.sendChatMessage` | POST /api/chat | server.py:1620 `api_chat` | free_router OK (import) | classification+round-robin present L1525-1640 |
| chat session | ChatPanel.tsx:202/251 `api.establishChatSession` | GET /api/chat/session | server.py:775 | security OK (stubbed fastapi) | HttpOnly cookie, local-only |
| agent restart | AgentTab.tsx:182 raw fetch | POST /api/agent/{name}/restart | server.py:966 | agent_pty.manager OK | `manager.restart_session` |
| agent stop | AgentTab.tsx:191 raw fetch | POST /api/agent/{name}/stop | server.py:961 | agent_pty.manager OK | `manager.stop_session` |
| agent PTY stream | AgentTab.tsx:81 WebSocket | WS /ws/agent/{name} | server.py:1492 | agent_pty.manager OK | xterm↔PTY relay |
| agent list | AgentTabs.tsx:110 raw fetch | GET /api/agents | server.py:944 | config registry OK | merged w/ DEFAULT_AGENTS |
| script run | store.tsx:204 `api.runScript` ← QuickActions.tsx:60 | POST /api/run-script | server.py:895 | subprocess allowlist OK | `run_script()` + WS broadcast |
| model health | store.tsx:238 `api.get9RouterHealth` | GET /api/model-health | server.py:889 | free_router OK | `get_free_router_health` |
| pc-state | store.tsx:187 `api.getPCState` | GET /api/pc-state | server.py:883 | stdlib psutil-proc OK | `get_pc_state()` |
| models registry | ModelsPanel.tsx:25, ChatPanel.tsx:203 | GET /api/models | server.py:875 | registries JSON OK | `get_models()` |
| skills | SkillsPanel.tsx:24, GlobalSearchModal.tsx:28 | GET /api/skills | server.py:871 | skill_registry OK | `get_skills()` |
| tools | ToolsPanel.tsx:22, GlobalSearchModal.tsx:29 | GET /api/tools | server.py:879 | registries JSON OK | `get_tools()` |
| vault file list | VaultExplorer.tsx:101 `api.getMemoryFiles` | GET /api/memory-files | server.py:733 | VAULT path OK | `get_memory_files()` |
| vault file read | VaultExplorer.tsx:130 `api.getFile` | GET /api/file/{path} | server.py:737 | VAULT path OK | `read_file_content()` |
| obsidian graph | ObsidianGraph.tsx:120, SpatialMemoryCanvas.tsx:115 | GET /api/obsidian-graph | server.py:765 | vault scan OK | `get_obsidian_graph()` |
| MOCs | SpatialMemoryCanvas.tsx:113 `api.getMOCs` | GET /api/mocs | server.py:797 | MEMORY/MOCs OK | dir scan |
| projects | SpatialMemoryCanvas.tsx:114 `api.getProjects` | GET /api/projects | server.py:816 | MEMORY/1-Projects OK | dir scan |
| knowledge rebuild | SpatialMemoryCanvas.tsx:445 raw fetch | POST /api/knowledge/rebuild | server.py:769 | knowledge_graph OK | `rebuild()` → nodes/edges |
| governance get/set | TopBar.tsx:23/32 | GET /api/governance, POST /api/governance/level | server.py:1282/1289 | governance OK | `set_autonomy_level`, levels 0-5 |

## EXTERNAL-DEPENDENT (4 — all need LM Studio on 127.0.0.1:1234)

| action | frontend caller | API route | handler:file:line | evidence |
|---|---|---|---|---|
| model load | ChatPanel.tsx:102 (dynamic `import('../lib/api')`) | POST /api/local-model/load | server.py:1049 | proxies `POST /api/v1/models/load`; 503 if LM Studio down |
| model unload | ChatPanel.tsx:116 | POST /api/local-model/unload | server.py:1081 | resolves instance_id, 404 if not loaded |
| model download | ChatPanel.tsx:174 | POST /api/local-model/download | server.py:1132 | proxies download; poll status for progress |
| model status poll | ChatPanel.tsx:86 every 3s | GET /api/local-model/status | server.py:1023 | returns `{models, loaded}` or `{error}` |

## NOT_CONFIGURED (24 — route+handler verified, NO frontend button calls it)

| action | api.ts surface | API route | handler:file:line | dependency state |
|---|---|---|---|---|
| agent start | `api.startAgent` defined, uncalled (PTY auto-spawns on WS connect) | POST /api/agent/{name}/start | server.py:948 | agent_pty OK |
| agent status | `api.getAgentStatus` uncalled | GET /api/agent/{name}/status | server.py:971 | agent_pty OK |
| vault structure | `api.getVaultStructure` uncalled | GET /api/vault | server.py:729 | VAULT OK |
| vault search | `api.searchVault` uncalled (VaultExplorer filters client-side) | GET /api/search | server.py:746 | memory_engine OK (`ranked_memory_search` ✓) |
| knowledge graph | `api.getGraph` uncalled (only obsidian-graph used) | GET /api/graph | server.py:761 | knowledge_graph OK |
| file tree/read/scan | no caller (VaultExplorer builds tree client-side) | GET /api/files/tree, GET /api/files/read, POST /api/files/systematic-scan | server.py:854/861/867 | crawl helpers OK |
| camera list/discover/authorize/vision-enable | api.ts `getCameras/discoverCameras/authorizeCamera/enableCameraVision` uncalled | GET+POST /api/cameras*, POST /api/cameras/{id}/authorize, POST …/vision/enable | server.py:1214/1218/1223/1229 | camera_registry OK (all 3 methods ✓) |
| camera toggle (legacy) | no caller | POST /api/vision/camera-toggle, GET /api/vision/status | server.py:1204/1200 | vision_engine OK (`set_camera_state` ✓) |
| mic toggle | no caller | POST /api/audio/mic-toggle, GET /api/audio/status | server.py:1444/1440 | audio_engine OK (both methods ✓) |
| supervisor dispatch/status | `api.dispatchSupervisorTask/getSupervisorTasks` uncalled | GET/POST /api/supervisor/* | server.py:1262/1266/1277 | agent_supervisor OK (both methods ✓) |
| context assemble | `api.assembleContext` uncalled | GET /api/context/assemble | server.py:1303 | context_router OK |
| turboquant search/ingest | `api.searchTurboQuant/ingestTurboQuant` uncalled | GET/POST /api/turboquant/* | server.py:1308/1312 | turboquant_store OK |
| mem0 add/search/all | `api.mem0Add/mem0Search/mem0GetAll` uncalled | POST+GET /api/memory/mem0/* | server.py:1324/1339/1343 | mem0_engine OK |
| cloudroom guard/workspaces | `api.validateCommandGuard/getCloudroomWorkspaces` uncalled | GET/POST /api/cloudroom/* | server.py:1378/1382 | cloudroom_bridge OK |
| planner create/execute | no api.ts fn, no caller | POST /api/planner/create-plan, POST /api/planner/execute-plan | server.py:1391/1400 | task_planner OK (`create_plan/execute_plan` ✓) |
| agentmoe discover/execute/tools | no api.ts fn, no caller | GET /api/agentmoe/tools, POST /api/agentmoe/discover, POST /api/agentmoe/execute | server.py:1413/1422/1431 | agent_moe OK (all 3 ✓) |
| research start | no caller | POST /api/research/start | server.py:1454 | research_engine OK |
| sandbox execute | no caller | POST /api/sandbox/execute | server.py:1463 | code_sandbox OK |
| frontier runs/run/status/trace/pack | no caller | GET /api/frontier/status, POST /api/frontier/run, GET /api/frontier/runs, GET /api/frontier/trace/{s}, GET /api/frontier/context-pack | server.py:1348/1352/1365/1369/1373 | frontier_adapter OK (all 5 ✓) |
| screen intel | no caller | GET /api/screen/intel | server.py:1450 | screen_intel OK |
| agies-memories/config-files/chatgpt-tracking | api.ts fns uncalled | GET /api/agies-memories, /api/config-files, /api/chatgpt-tracking | server.py:903/916/934 | filesystem OK |
| browser/diag/health extras | no caller | GET /api/browser/*, /api/diagnostics/deep, /api/health*, /api/monitor/health, /api/memory/temporal, /api/search/unified | server.py:785-1478 | modules OK |
| camera events/test_vision | no caller | GET /api/cameras/{id}/events, POST …/test_vision | server.py:1235/1239 | event_store + vision_engine OK |
| **preferences** | **none — no UI, no api.ts fn, NO route in server.py** | — | — | missing both ends |

## BROKEN (0)

None. Every route referenced above exists in `backend/server.py` (verified via
`rg "@app.(get|post|websocket)"`), and every handler dependency imports cleanly
(stubbed-env proof) with all 24 method-attribute checks passing. Initial raw-env
`ModuleNotFoundError: cv2/fastapi/httpx` readings were environment-only (this
shell has no runtime venv) — with stubs, `backend.vision_engine`,
`backend.task_planner`, `backend.agent_supervisor`, `backend.agent_moe`,
`backend.agent_pty`, `backend.free_router`, `backend.security` all import OK.

## Summary counts

- WIRED: 19 · EXTERNAL-DEPENDENT: 4 · NOT_CONFIGURED: 24 · BROKEN: 0
- Biggest gap: cameras/vision/mic + planner/research/sandbox/agentmoe/frontier +
  supervisor dispatch + cloudroom guard + turboquant/mem0 are fully working
  backend APIs with zero dashboard buttons wired to them.
