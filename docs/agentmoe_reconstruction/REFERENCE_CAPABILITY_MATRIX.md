# AGENTMOE — REFERENCE CAPABILITY MATRIX
**Date:** 2026-08-29 | **References inspected:** Hermes Agent (primary)

---

## HERMES AGENT — `/home/adarshjii/.hermes/hermes-agent/`

MIT-licensed. Production open-source agent runtime. Full source available locally.
Do NOT copy wholesale. Extract patterns/primitives only.

### Tool Inventory (127k LOC across ~120 tool files)

| Tool File | LOC | Useful For | Extract? |
|-----------|-----|-----------|---------|
| `tools/file_operations.py` | 3,410 | FS ops via shell backend, write deny list, path traversal | ✅ PATTERN |
| `tools/file_tools.py` | 2,824 | read/write/patch/search primitives | ✅ PATTERN |
| `tools/terminal_tool.py` | 4,107 | Multi-backend terminal (local/Docker/SSH/Modal/Vercel), interrupt, redaction | ✅ PATTERN |
| `tools/browser_tool.py` | 5,602 | Local Chromium + Browserbase + BrowserUse, session isolation, accessibility tree | ✅ PATTERN |
| `tools/computer_use/tool.py` | ~1,500 | Linux X11/AT-SPI/Wayland via cua-driver-rs | ✅ PATTERN |
| `tools/computer_use/backend.py` | ~400 | ActionResult, CaptureResult, ComputerUseBackend protocol | ✅ PROTOCOL |
| `tools/code_execution_tool.py` | 2,231 | UDS-RPC sandboxed Python, remote file-RPC for Docker/SSH | ✅ PATTERN |
| `tools/mcp_tool.py` | 8,584 | Full MCP client (stdio/HTTP/SSE/StreamableHTTP), OAuth, keepalive | ✅ PATTERN |
| `tools/delegate_tool.py` | 4,963 | Subagent spawning, tool grants, blocked tools, context isolation | ✅ PATTERN |
| `tools/budget_config.py` | ~200 | Per-tool/turn token+cost budget tracking | ✅ PATTERN |
| `tools/checkpoint_manager.py` | 2,196 | Checkpoint state, partial progress recovery | ✅ PATTERN |
| `tools/path_security.py` | ~150 | validate_within_dir, has_traversal_component | ✅ EXTRACT DIRECTLY |
| `tools/url_safety.py` | ~400 | SSRF prevention (RFC 1918 block, metadata endpoint block, DNS rebind) | ✅ EXTRACT PATTERN |
| `tools/threat_patterns.py` | ~300 | Prompt injection / C2 pattern scanning | ✅ EXTRACT PATTERN |
| `tools/web_tools.py` | 1,600 | Web search (Firecrawl/Tavily/SearXNG), page fetch, structured extract | ✅ PATTERN |
| `tools/process_registry.py` | 3,315 | Process lifecycle management, PID tracking, cleanup | ✅ PATTERN |
| `agent/tool_guardrails.py` | 43,705 | Idempotent vs mutating classification, dedup hash, loop detect | ✅ PATTERN |
| `agent/tool_executor.py` | 133,455 | Sequential + concurrent dispatch, timeout, retry, audit | ✅ PATTERN (high-level) |
| `tools/async_delegation.py` | 1,603 | Async worker lifecycle, futures, cancellation | ✅ PATTERN |

### What NOT to extract from Hermes

| Component | Reason |
|-----------|--------|
| `agent/anthropic_adapter.py` (144k) | Anthropic-specific — use L3 provider pattern instead |
| `agent/agent_init.py` (154k) | Hermes-specific full agent init — we use AEGIS runtime |
| `agent/chat_completion_helpers.py` (263k) | Hermes-specific conversation management |
| `agent/context_compressor.py` (414k) | Hermes context management — use L4 ContextBuilder |
| `agent/billing_*.py` | Hermes billing system — irrelevant |
| `tools/tts_tool.py`, `voice_mode.py` | Audio — not in AgentMoe scope |
| `tools/kanban_tools.py` | Hermes UI-specific |
| `tools/discord_tool.py`, `send_message_tool.py` | Communication tools — not AgentMoe scope |
| `tools/homeassistant_tool.py` | Home automation — not in scope |
| `node_modules/` | Never touch |
| `.git/` | Not relevant |
| Hermes skill system (`skills_*.py`) | Hermes-specific skill framework — AEGIS has its own |

---

## GODS-EYE-VIEW — `/home/adarshjii/Downloads/gods-eye-view-main.zip`

**Decision: IGNORE ENTIRELY.**
Contains: geospatial viewer, CCTV feeds, flight tracking, AR cockpit, undersea cables.
Zero extractable primitives for AgentMoe.

---

## INTERNAL AEGIS REFERENCES (existing code to reuse/promote)

| Component | Location | Promote To |
|-----------|----------|-----------|
| FilesystemExecutor | `l5_execution/executors/filesystem.py` | AgentMoe FilesystemTool backend |
| GitExecutor | `l5_execution/executors/git.py` | AgentMoe GitTool backend |
| ShellExecutor | `l5_execution/executors/shell.py` | AgentMoe TerminalTool backend |
| HttpExecutor | `l5_execution/executors/http.py` | AgentMoe HTTPTool + BrowserTool backend |
| PythonExecutor | `l5_execution/executors/python_exec.py` | CodingWorker execution engine |
| MCPExecutor stub | `l5_execution/executors/mcp.py` | Promote to full with Hermes MCP pattern |
| CapabilityInvoker | `capabilities/invocation/invoker.py` | Core ToolFabric.invoke() bridge |
| SemanticCapabilityRegistry | `capabilities/registry_v2/` | AgentMoe tool registration |
| CredentialResolver | `l3_intelligence/ai_kernel/credentials.py` | Extend to CredentialPool |
| CostAccountant | `l3_intelligence/ai_kernel/accounting.py` | Worker budget tracking |
| PrivacyZoneService | `l4_memory/p07/privacy/service.py` | Path access control |
| BackgroundTaskManager | `l2_foundation/scheduler/background.py` | Worker lifecycle |
