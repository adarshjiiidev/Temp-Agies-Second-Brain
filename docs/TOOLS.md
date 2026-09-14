# AEGIS Unified Tool Layer

**Tool Registry:** `/home/adarshjii/.temporary-aegis/TOOL_REGISTRY.json`  
**Execution Fabric:** `backend/agent_moe.py`  

---

## 1. Tool Governance & Risk Classification

All tools adhere to strict trust levels, parameter schemas, and permission boundaries.

| Tool | Risk Level | Trust Level | Permission Requirements |
| :--- | :--- | :--- | :--- |
| **`terminal`** | High | Medium | Command execution; timeout required |
| **`file_read`** | Low | High | Slice offsets; workspace boundary enforced |
| **`file_write`** | Medium | High | Workspace only; secret overwrite protection |
| **`screen_ocr`** | Low | High | Transient frame capture; no background recording |
| **`camera_snapshot`**| Medium | High | Explicit user permission required; hard killswitch |
| **`clipboard_sync`** | Low | High | Desktop clipboard read/write |
| **`project_inspect`** | Low | High | Read-only directory scanning across 9 projects |
| **`systematic_scan`** | Low | High | Automated index update of all workspace codebases |

---

## 2. Tool Execution Architecture

```
USER GOAL / INTENT
        │
        ▼
   AGENTMOE DISCOVERY
        │
        ▼
   SECURITY & PERMISSION CHECK
        │ (Denied -> Abort)
        ▼ (Permitted)
   TOOL EXECUTION SANDBOX
        │
        ▼
   VERIFICATION OF OUTPUT
        │
        ▼
   EXPERIENCE MEMORY UPDATE
```
