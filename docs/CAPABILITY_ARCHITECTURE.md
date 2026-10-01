# CAPABILITY ARCHITECTURE — TEMPORARY AEGIS

> **Design Principle:** Capabilities are discovered, not hard-coded. Every tool, skill, model, and agent is registered — and AgentMoe is the operational fabric that wires them together.

---

## 1. Capability Taxonomy

```
CAPABILITIES
├── TOOLS           — Atomic operations (filesystem, terminal, browser, vision, clipboard)
├── SKILLS          — Composed sequences of tools aimed at recurring goals
├── AGENTS          — Long-running conversational actors with persistent memory
├── MODELS          — LLM inference endpoints (selected by 9Router)
└── WORKERS (MoE)   — Named roles within AgentMoe for task delegation
```

---

## 2. Tool Registry

**Source:** `registries/TOOL_REGISTRY.json` (loaded dynamically by `knowledge_graph.py`)  
**Runtime access:** `agent_moe.tools` dict

| Tool ID | Implementation | Function |
|---|---|---|
| `filesystem_read` | `agent_moe.tool_fs_read()` | Read any file under cfg.HOME |
| `filesystem_write` | `agent_moe.tool_fs_write()` | Write/create files safely |
| `terminal_run` | `agent_moe.tool_terminal_run()` | Run shell commands (timeout-bounded, 30s default) |
| `screen_ocr` | `vision_engine.capture_screen()` + `run_ocr()` | Wayland screenshot + Tesseract OCR |
| `camera_snapshot` | `vision_engine.capture_camera_frame()` | Gated camera frame (HARD_DENY default) |
| `clipboard_sync` | `computer_control.get/set_clipboard()` | `wl-paste` / `wl-copy` operations |
| `project_inspect` | `agent_moe.tool_project_inspect()` | List project files (excludes .git, node_modules) |
| `browser_navigate` | `browser_tool.extract_content()` | Headless Chrome DOM + markdown extraction |
| `browser_screenshot` | `browser_tool.capture_screenshot()` | Headless Chrome full-page screenshot |

**Security constraints on tools:**
- `terminal_run` — allowlist-checked commands; `timeout=30s` hard cap
- `filesystem_read/write` — `safe_path()` guard; must be under `cfg.HOME`
- `camera_snapshot` — HARD_DENY unless explicitly enabled; zero video persistence
- `browser_navigate` — Chrome `--headless=new` only; no persistent sessions

---

## 3. Skill Registry

**Source:** `~/.temporary-aegis/SKILL_REGISTRY.json` (auto-populated by skill discovery scan)  
**Count:** 27 skills discovered at last scan

Skill categories:
| Category | Skills |
|---|---|
| Personal Context | `personal-context`, `profile-loader`, `daily-briefing` |
| Project Intelligence | `project-resumer`, `repository-auditor`, `architecture-mapper` |
| Coding | `code-reviewer`, `bug-hunter`, `test-generator`, `refactor-assistant` |
| Research | `web-researcher`, `paper-summarizer`, `source-verifier` |
| Memory | `experience-logger`, `knowledge-consolidator`, `memory-builder` |
| Vision | `screen-reader`, `document-scanner`, `ui-annotator` |
| Automation | `task-executor`, `script-runner`, `deployment-helper` |
| System | `health-monitor`, `service-restarter`, `log-analyzer`, `snapshot-builder` |

Each skill in `SKILL_REGISTRY.json`:
```json
{
  "id": "project-resumer",
  "name": "Project Resumer",
  "description": "Reconstructs full context for a paused project from vault memory, git log, and file index",
  "tools_required": ["filesystem_read", "terminal_run", "project_inspect"],
  "model_preferred": "gemini/gemini-3.7-flash",
  "trigger_keywords": ["resume", "pick up where", "continue project"]
}
```

---

## 4. Agent Registry

**Source:** `registries/AGENT_REGISTRY.json` (loaded by `cfg.AGENT_REGISTRY`)  
**Command resolution:** `cfg.resolve_agent_command(agent_id)` — PATH-aware, never hardcodes

| Agent ID | Binary/Service | Role | Interaction Mode |
|---|---|---|---|
| `hermes` | `~/.hermes/profiles/agies/` | Orchestrator brain (Hermes 3) | PTY + chat |
| `opencode` | `~/.opencode/bin/opencode` | ACP/MCP code operator | PTY |
| `openclaw` | OpenClaw SSE daemon | Claude-native workspace | SSE stream |
| `codex` | `openai-codex` (PATH) | Code completion + edit | PTY + modal |
| `deepseek` | Local DeepSeek API | Reasoning (MoE) | HTTP API |
| `bash` | `/usr/bin/bash --login` | Raw terminal | PTY |

**Agent PTY lifecycle:**
```
cfg.resolve_agent_command(id) → spawns PTY subprocess
  → cfg.get_agent_env() provides clean environment
  → SSE output stream (/api/agent/pty/output)
  → Input via /api/agent/pty/input
  → Session tracked by UUID session_id
```

---

## 5. Model Registry & 9Router Matrix

**Source:** `registries/MODEL_REGISTRY.json` + `cfg.MODEL_*` / `cfg.FREE_CHAT_MODELS`

| Model ID | Role | Use Cases |
|---|---|---|
| `cl/nex-agi/nex-n2.5-pro:free` | Default (`cfg.MODEL_DEFAULT`) | General chat, code synthesis, architecture |
| `cl/z-ai/glm-5.2:free` | Reasoning (`cfg.MODEL_REASONING`) | Deep extended thinking, math proofs |
| `cl/nex-agi/nex-n2.5-mini:free` | Fast (`cfg.MODEL_FAST`) | Ultra-low latency chat, quick Q&A |
| `cl/dots-studio/dots-3-note-preview:free` | Lite (`cfg.MODEL_LITE`) | High-volume note & context drafting |
| `cl/google/gemma-4-31b-it:free` | Frontier General | 31B open weights reasoning |
| `cl/cohere/north-mini-code:free` | Coding Specialist | Code generation and debugging |
| `cl/inclusionai/ling-3.0-flash-vl:free` | Multimodal Vision | Screen OCR and visual UI understanding |

**9Router dynamic selection logic (`model_router.py`):**
```
IF task contains "think" / "prove" / "math"       → cfg.MODEL_REASONING (glm-5.2)
IF task contains "code" / "refactor" / "build"     → cfg.MODEL_DEFAULT (nex-n2.5-pro) or north-mini-code
IF task contains "quick" / "classify" / "ping"     → cfg.MODEL_FAST (nex-n2.5-mini)
IF task is note drafting / summary                 → cfg.MODEL_LITE (dots-3-note)
FALLBACK CHAIN: [DEFAULT → REASONING → FAST → LITE] (Zero serial latency; round-robin per turn)
```

9Router health is monitored in `/api/diagnostics/deep` and `/api/9router-health`.

---

## 6. AgentMoe — The Operational Capability Fabric

**File:** `backend/agent_moe.py`  
**Singleton:** `agent_moe = AgentMoeFabric()`

AgentMoe is the runtime capability router. It:
1. **Discovers** what tool/role matches a given goal (keyword-based → expandable to embedding-based)
2. **Delegates** subtask plans to the right tool or agent
3. **Executes** multi-step plans via `execute_plan(subtasks)`
4. **Reports** results with success/error status per step

### MoE Worker Roles

| Role | Responsibility | Primary Tools |
|---|---|---|
| `Planner` | Decompose goals into subtasks | `project_inspect`, `terminal_run` |
| `Researcher` | Gather information | `filesystem_read`, `browser_navigate` |
| `Coder` | Write and execute code | `filesystem_write`, `terminal_run` |
| `Debugger` | Find and fix issues | `terminal_run`, `filesystem_read` |
| `Auditor` | Review and validate | `filesystem_read`, `project_inspect` |
| `Vision Worker` | Process visual information | `screen_ocr`, `camera_snapshot` |
| `Browser Worker` | Web-based tasks | `browser_navigate`, `browser_screenshot` |
| `Synthesizer` | Aggregate and report results | LLM call via 9Router |

### Capability Discovery Flow
```python
agent_moe.discover_capability(goal: str) → {
  "type": "tool" | "agent",
  "target": "<tool_id>" | "<model_id>",
  "role": "<worker_role>"
}
```

Currently keyword-matching. Architecture is designed to swap in embedding-based semantic routing when a local embedding model is available.

---

## 7. Knowledge Graph — Capability Inventory

**File:** `backend/knowledge_graph.py`  
**Nodes:** Relational graph from filesystem scan + registries  
**Endpoints:** `GET /api/graph` (unified graph data) & `GET /api/obsidian-graph` (Obsidian canvas graph)

Node types:
| Type | Description |
|---|---|
| `Project` | Workspace projects (scanned dynamically from `cfg.PROJECTS`) |
| `Agent` | Registered agents (`cfg.AGENT_REGISTRY`) |
| `Tool` | Registered operational tools (`registries/TOOL_REGISTRY.json`) |
| `Model` | Verified models from `registries/MODEL_REGISTRY.json` |
| `Decision` | Key architectural records from `DECISIONS.md` / `EXPERIENCES` |

Edge types: `POWERED_BY`, `DECIDED`, `USES_TOOL`, `USES_MODEL`

The graph powers:
- `ObsidianGraph.tsx` — live interactive visual link canvas
- `/api/search/unified` — unified search across graph nodes and vault markdown notes
- `task_planner.py` — tool selection for multi-step planning

---

## 8. Capability Expansion Path

When a new capability needs to be added:

1. **Add tool** → implement in `agent_moe.py` under `self.tools`
2. **Register** → add entry to `registries/TOOL_REGISTRY.json`
3. **Wire endpoint** → add route in `backend/server.py`
4. **Update graph** → `knowledge_graph.py` will auto-pick up from registry on next request
5. **Document** → add to `SKILL_REGISTRY.json` if composable
6. **Test** → add mission to `tests/test_end_to_end_missions.py`
