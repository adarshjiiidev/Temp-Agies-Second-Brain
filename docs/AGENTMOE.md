# AGENTMOE — Operational Capability Fabric

**Designation:** AgentMoe Capability Execution Subsystem  
**Implementation:** `backend/agent_moe.py`  
**Purpose:** Give AEGIS the hands, legs, tools, and specialized worker delegation to act upon the machine.  

---

## 1. Concept & Division of Responsibilities

- **AEGIS Layer:** Intelligence, governance, context assembly, and security authorization.
- **AgentMoe Layer:** Operational execution, capability discovery, tool invocation, and worker delegation.

```
                  AEGIS GOVERNANCE
                         │
                         ▼
               CAPABILITY DISCOVERY
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
   KNOWN TOOL       KNOWN SKILL      KNOWN AGENT
 (fs, term, ocr)  (hermes skill)   (codex, opencode)
        │                │                │
        └────────────────┼────────────────┘
                         ▼
              DELEGATED WORKER ROLES
   [Planner] [Researcher] [Coder] [Debugger] [Vision]
                         │
                         ▼
                TOOL EXECUTION FABRIC
   [Filesystem] [Terminal] [OCR] [Camera] [Clipboard]
```

---

## 2. Worker Roles

1. **Planner:** Decomposes complex user missions into dependency graphs and subtasks.
2. **Researcher:** Explores web sources, Obsidian notes, and documentation.
3. **Coder:** Synthesizes code via Codex, Claude Code, or Gemini coding backbones.
4. **Debugger:** Evaluates compiler errors, tracebacks, and test failures.
5. **Auditor:** Inspects diffs, security boundaries, and secret leaks.
6. **Vision Worker:** Executes screen captures, camera snapshots, and OCR text extraction.
7. **Browser Worker:** Automates web navigation and DOM inspection.
8. **Synthesizer:** Merges subtask deliverables into a coherent final result.

---

## 3. Tool Fabric Operations

| Tool Name | Handler | Risk Level | Trust | Description |
| :--- | :--- | :--- | :--- | :--- |
| `filesystem_read` | `agent_moe.tool_fs_read` | Low | High | Reads file slices with offset and line limits. |
| `filesystem_write`| `agent_moe.tool_fs_write`| Medium | High | Writes files within authorized workspace boundaries. |
| `terminal_run`    | `agent_moe.tool_terminal_run` | High | Medium | Executes bash commands with timeout limits. |
| `screen_ocr`      | `agent_moe.tool_screen_ocr` | Low | High | Captures Wayland desktop screen and extracts text via Tesseract. |
| `camera_snapshot` | `agent_moe.tool_camera_snapshot` | Medium | High | Takes a single frame from `/dev/video0` when permitted. |
| `clipboard_sync`  | `agent_moe.tool_clipboard` | Low | High | Reads and writes Wayland clipboard via wl-copy/wl-paste. |
| `project_inspect` | `agent_moe.tool_project_inspect` | Low | High | Analyzes project file trees across all 9 workspaces. |
