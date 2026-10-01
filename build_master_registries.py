#!/usr/bin/env python3
"""
Generate comprehensive MODEL_REGISTRY.json, TOOL_REGISTRY.json, and AGENT_REGISTRY.json
from live 9Router API (870 models), local Hermes profile, and agent frameworks.
"""

import json
import urllib.request
from datetime import datetime
from pathlib import Path

HOME = Path.home()
DEST_DIR = HOME / "aegis-dashboard" / "registries"
DEST_DIR.mkdir(parents=True, exist_ok=True)
ALT_DIR = HOME / ".temporary-aegis"
ALT_DIR.mkdir(parents=True, exist_ok=True)

# ── 1. MODEL REGISTRY ─────────────────────────────────────────────────────────

def build_model_registry():
    print("Fetching 9Router models from http://127.0.0.1:20128/v1/models...")
    raw_models = []
    try:
        req = urllib.request.Request("http://127.0.0.1:20128/v1/models")
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
            raw_models = data.get("data", [])
            print(f"Loaded {len(raw_models)} models from 9Router.")
    except Exception as e:
        print(f"Failed to fetch from 9Router: {e}")

    providers = set()
    models_list = []
    mode_matrix = {
        "thinking": [],
        "streaming": [],
        "tools": [],
        "vision": [],
        "multimodal": [],
        "coding": [],
        "fast": []
    }

    for m in raw_models:
        model_id = m.get("id", "")
        if not model_id:
            continue

        owned_by = m.get("owned_by", "unknown")
        providers.add(owned_by)

        caps = m.get("capabilities", {})
        has_vision = bool(caps.get("vision") or caps.get("imageOutput"))
        has_tools = bool(caps.get("tools"))
        has_reasoning = bool(caps.get("reasoning"))
        has_multimodal = bool(has_vision or caps.get("audioInput") or caps.get("videoInput"))
        
        is_coding = any(k in model_id.lower() for k in ["code", "codex", "sol", "coder", "dev", "qwen-2.5-coder"])
        is_fast = any(k in model_id.lower() for k in ["flash", "instant", "fast", "mini", "small", "haiku", "low"])
        is_thinking = has_reasoning or any(k in model_id.lower() for k in ["r1", "o1", "o3", "thinking", "reasoning", "opus"])

        capabilities = ["streaming"]
        if is_thinking: capabilities.append("thinking")
        if has_reasoning: capabilities.append("reasoning")
        if is_coding: capabilities.append("coding")
        if has_tools: capabilities.append("tools")
        if has_vision: capabilities.append("vision")
        if has_multimodal: capabilities.append("multimodal")
        if is_fast: capabilities.append("fast")

        context_window = caps.get("contextWindow", 128000)
        max_output = caps.get("maxOutput", 8192)

        model_entry = {
            "id": model_id,
            "name": model_id.split("/")[-1].replace("-", " ").title(),
            "provider": owned_by,
            "context_window": context_window,
            "max_output": max_output,
            "capabilities": capabilities,
            "thinking_mode": is_thinking,
            "api_compatible": "openai",
            "9router_path": f"/v1/models/{model_id}"
        }
        models_list.append(model_entry)

        # Mode Matrix indexing
        if is_thinking and len(mode_matrix["thinking"]) < 40:
            mode_matrix["thinking"].append(model_id)
        if has_tools and len(mode_matrix["tools"]) < 40:
            mode_matrix["tools"].append(model_id)
        if has_vision and len(mode_matrix["vision"]) < 40:
            mode_matrix["vision"].append(model_id)
        if has_multimodal and len(mode_matrix["multimodal"]) < 40:
            mode_matrix["multimodal"].append(model_id)
        if is_coding and len(mode_matrix["coding"]) < 40:
            mode_matrix["coding"].append(model_id)
        if is_fast and len(mode_matrix["fast"]) < 40:
            mode_matrix["fast"].append(model_id)
        if len(mode_matrix["streaming"]) < 50:
            mode_matrix["streaming"].append(model_id)

    registry = {
        "generated_at": datetime.now().isoformat(),
        "9router_url": "http://127.0.0.1:20128",
        "9router_models_count": len(models_list),
        "providers": sorted(list(providers)),
        "models": models_list,
        "mode_matrix": mode_matrix,
        "routing": {
            "default": "cl/openai/gpt-5.6-terra",
            "coding": "cl/openai/gpt-5.6-sol",
            "reasoning": "cl/anthropic/claude-opus-5",
            "fast": "ag/gemini-3.8-flash",
            "multimodal": "cl/google/gemini-3.8-flash",
            "thinking": "cl/deepseek/deepseek-r1-distill-qwen-32b",
            "local_fallback": "hermes/default"
        },
        "orchestrator": {
            "model": "agies-orchestrator",
            "primary": "cl/openai/gpt-5.6-terra",
            "fallback": "ag/gemini-3.8-flash",
            "role": "Classifies every incoming user task into domain, complexity, and latency budget, routes to designated Tier pair, and dispatches to agent CLI."
        },
        "tiered_groups": {
            "tier_1_frontier": {
                "id": "tier_1_frontier",
                "name": "Tier 1: Frontier Architecture & Reasoning",
                "description": "Deep conceptual analysis, system architecture, and multi-step reasoning",
                "primary": "cl/anthropic/claude-opus-5",
                "fallback": "cl/openai/gpt-5.6-terra",
                "target_agent": "claude",
                "context_window": 200000
            },
            "tier_2_coding": {
                "id": "tier_2_coding",
                "name": "Tier 2: High-End Code Synthesis & Refactoring",
                "description": "Full-stack code generation, AST transformations, and test execution",
                "primary": "cl/openai/gpt-5.6-sol",
                "fallback": "cl/deepseek/deepseek-r1-distill-qwen-32b",
                "target_agent": "codex",
                "context_window": 372000
            },
            "tier_3_deep_thinking": {
                "id": "tier_3_deep_thinking",
                "name": "Tier 3: Mathematical Proof & Extended Thinking",
                "description": "Deep thinking chain-of-thought, symbolic proof, and algorithmic verification",
                "primary": "cl/deepseek/deepseek-r1-distill-qwen-32b",
                "fallback": "cl/anthropic/claude-opus-5",
                "target_agent": "deepseek",
                "context_window": 128000
            },
            "tier_4_multimodal": {
                "id": "tier_4_multimodal",
                "name": "Tier 4: Multimodal Vision & Diagram Analysis",
                "description": "UI layout inspection, document OCR, architectural diagrams, and image synthesis",
                "primary": "cl/google/gemini-3.8-flash",
                "fallback": "cl/openai/gpt-5.6-terra",
                "target_agent": "hermes",
                "context_window": 1048576
            },
            "tier_5_fast_throughput": {
                "id": "tier_5_fast_throughput",
                "name": "Tier 5: Ultra-Fast Throughput & Telemetry",
                "description": "Low-latency classification, quick telemetry summarization, and rapid tool loops",
                "primary": "ag/gemini-3.8-flash",
                "fallback": "ag/gemini-3.8-flash-low",
                "target_agent": "hermes",
                "context_window": 1048576
            },
            "tier_6_local_fallback": {
                "id": "tier_6_local_fallback",
                "name": "Tier 6: Local Host / Offline Fallback",
                "description": "Zero-egress offline inference when external gateways are unavailable",
                "primary": "upstage/solar-pro4:free",
                "fallback": "local/llama3.2:3b",
                "target_agent": "hermes",
                "context_window": 32768
            }
        }
    }

    for p in [DEST_DIR / "MODEL_REGISTRY.json", ALT_DIR / "MODEL_REGISTRY.json"]:
        p.write_text(json.dumps(registry, indent=2))
    print("Saved MODEL_REGISTRY.json")

# ── 2. TOOL REGISTRY ──────────────────────────────────────────────────────────

def build_tool_registry():
    tools = [
        {
            "name": "terminal",
            "agent": "hermes",
            "identity": "shell-terminal",
            "capability": "Execute shell commands, run scripts, manage processes on the host machine",
            "description": "Run shell commands on the host machine with configurable timeout and workdir",
            "parameters": { "command": "string", "timeout": "number", "workdir": "string", "background": "boolean" },
            "permissions": ["read", "write", "execute", "execute_local_commands"],
            "risk": "medium",
            "trust": "high",
            "agent_support": ["hermes", "claude-code", "codex", "bash"]
        },
        {
            "name": "file_read",
            "agent": "hermes",
            "identity": "filesystem-reader",
            "capability": "Read any file on the filesystem with slice offsets",
            "description": "Read any file on the filesystem",
            "parameters": { "path": "string", "offset": "number", "limit": "number" },
            "permissions": ["read", "read_any_file"],
            "risk": "low",
            "trust": "high",
            "agent_support": ["hermes", "openclaw", "claude-code", "codex"]
        },
        {
            "name": "file_write",
            "agent": "hermes",
            "identity": "filesystem-writer",
            "capability": "Write or overwrite files in the workspace or vault",
            "description": "Create new files or overwrite existing content",
            "parameters": { "path": "string", "content": "string" },
            "permissions": ["write", "write_to_workspace"],
            "risk": "medium",
            "trust": "high",
            "agent_support": ["hermes", "claude-code", "codex"]
        },
        {
            "name": "file_patch",
            "agent": "hermes",
            "identity": "code-patcher",
            "capability": "Apply surgical non-contiguous patches and diff replacements",
            "description": "Apply targeted regex or exact-match replacements to source files",
            "parameters": { "path": "string", "target": "string", "replacement": "string" },
            "permissions": ["read", "write"],
            "risk": "low",
            "trust": "high",
            "agent_support": ["hermes", "claude-code", "codex"]
        },
        {
            "name": "file_search",
            "agent": "hermes",
            "identity": "ripgrep-searcher",
            "capability": "Fast ripgrep text and regex search across directory trees",
            "description": "Search code and markdown notes across directories with glob filters",
            "parameters": { "query": "string", "path": "string", "is_regex": "boolean" },
            "permissions": ["read"],
            "risk": "low",
            "trust": "high",
            "agent_support": ["hermes", "claude-code", "codex"]
        },
        {
            "name": "browser",
            "agent": "hermes",
            "identity": "browser-automation",
            "capability": "Navigate web pages, inspect DOM, take screenshots, extract content",
            "description": "Headless browser automation for research, verification, and testing",
            "parameters": { "url": "string", "action": "navigate|click|screenshot|extract|wait" },
            "permissions": ["navigate_urls", "take_screenshots", "read_page_content"],
            "risk": "medium",
            "trust": "high",
            "agent_support": ["hermes", "openclaw"]
        },
        {
            "name": "execute_code",
            "agent": "codex",
            "identity": "python-node-sandbox",
            "capability": "Execute code snippets in Python, Node.js, and Bash sandboxes",
            "description": "Execute isolated code blocks and evaluate output",
            "parameters": { "language": "python|javascript|bash", "code": "string" },
            "permissions": ["execute"],
            "risk": "medium",
            "trust": "high",
            "agent_support": ["codex", "hermes", "deepseek"]
        },
        {
            "name": "memory_store",
            "agent": "hermes",
            "identity": "para-vault-manager",
            "capability": "Query, update, and index Obsidian PARA memory files and MOCs",
            "description": "Manage long-term knowledge in Obsidian vault and profile memories",
            "parameters": { "action": "query|store|link", "folder": "string", "note": "string" },
            "permissions": ["read", "write"],
            "risk": "low",
            "trust": "high",
            "agent_support": ["hermes", "openclaw"]
        },
        {
            "name": "delegate_task",
            "agent": "hermes",
            "identity": "subagent-orchestrator",
            "capability": "Spawn independent subagent threads with specialized prompts",
            "description": "Delegate tasks to background subagents with reactive wakeup",
            "parameters": { "task_name": "string", "prompt": "string", "tools": "list" },
            "permissions": ["spawn_processes", "execute"],
            "risk": "high",
            "trust": "high",
            "agent_support": ["hermes", "agent-moe"]
        },
        {
            "name": "vision_analyze",
            "agent": "claude-code",
            "identity": "multimodal-vision",
            "capability": "Analyze UI screenshots, diagrams, and images with vision models",
            "description": "Inspect visual assets and evaluate UI layouts",
            "parameters": { "image_path": "string", "prompt": "string" },
            "permissions": ["read"],
            "risk": "low",
            "trust": "high",
            "agent_support": ["claude-code", "hermes"]
        }
    ]

    registry = {
        "generated_at": datetime.now().isoformat(),
        "description": "Unified AEGIS AI OS Tool Registry across agent frameworks",
        "tools": tools
    }

    for p in [DEST_DIR / "TOOL_REGISTRY.json", ALT_DIR / "TOOL_REGISTRY.json"]:
        p.write_text(json.dumps(registry, indent=2))
    print("Saved TOOL_REGISTRY.json")

# ── 3. AGENT REGISTRY ─────────────────────────────────────────────────────────

def build_agent_registry():
    agents = [
        {
            "id": "hermes",
            "name": "Hermes (agies)",
            "type": "ai-os-agent",
            "repo": "https://github.com/nousresearch/hermes-agent",
            "cli": "~/.local/bin/hermes",
            "command": "hermes --profile agies chat",
            "profile": "agies",
            "installed": True,
            "default_model": "upstage/solar-pro4:free",
            "modes": ["standard", "thinking", "streaming", "coding", "tools"],
            "runs_in": "cli-terminal-tab",
            "config": "~/.hermes/profiles/agies/config.yaml",
            "skills_count": 18,
            "dashboard_tab": "Hermes (agies)",
            "icon": "MessageSquare",
            "description": "Nous Research Hermes Agent with agies profile (god PC user persona, 18 skills, 20 tools)."
        },
        {
            "id": "claude",
            "name": "Claude Code",
            "type": "anthropic-cli",
            "repo": "https://github.com/anthropics/claude-code",
            "cli": "~/.local/share/mise/installs/claude/2.1.267/bin/claude",
            "command": "claude",
            "installed": True,
            "default_model": "anthropic/claude-opus-4 (via 9Router)",
            "modes": ["standard", "thinking", "tools", "coding"],
            "runs_in": "cli-terminal-tab",
            "dashboard_tab": "Claude Code",
            "icon": "Bot",
            "description": "Anthropic Claude Code CLI — autonomous terminal agent for deep reasoning, architectural refactoring, and code analysis."
        },
        {
            "id": "codex",
            "name": "Codex",
            "type": "openai-agent",
            "repo": "https://github.com/openai/codex",
            "cli": "~/.local/share/mise/installs/codex/latest/bin/codex",
            "command": "codex",
            "installed": True,
            "default_model": "cl/openai/gpt-5.6-sol",
            "modes": ["standard", "coding", "tool-use"],
            "runs_in": "cli-terminal-tab",
            "dashboard_tab": "Codex",
            "icon": "Code2",
            "description": "OpenAI Codex CLI — specialized coding agent for rapid feature implementation, automated test runs, and debugging."
        },
        {
            "id": "deepseek",
            "name": "DeepSeek R1",
            "type": "deepseek-agent",
            "repo": "https://github.com/deepseek-ai",
            "cli": "deepseek-session",
            "command": "python3 -m backend.agent_runner --agent deepseek",
            "installed": True,
            "default_model": "cl/deepseek/deepseek-r1-distill-qwen-32b",
            "modes": ["thinking", "coding", "standard"],
            "runs_in": "cli-terminal-tab",
            "dashboard_tab": "DeepSeek R1",
            "icon": "Brain",
            "description": "DeepSeek AI harness — ultra-deep thinking and mathematical reasoning mode powered by DeepSeek R1 MoE via 9Router."
        },
        {
            "id": "openclaw",
            "name": "OpenClaw",
            "type": "anthropic-agent",
            "repo": "https://github.com/openclaw/openclaw",
            "cli": "openclaw-session",
            "command": "python3 -m backend.agent_runner --agent openclaw",
            "installed": True,
            "default_model": "anthropic/claude-sonnet-4",
            "modes": ["standard", "thinking", "claude-native"],
            "runs_in": "cli-terminal-tab",
            "dashboard_tab": "OpenClaw",
            "icon": "Terminal",
            "description": "OpenClaw Claude-native agent framework with memory synchronization and multi-step tool execution."
        },
        {
            "id": "bash",
            "name": "Host Terminal",
            "type": "system-shell",
            "repo": "https://www.gnu.org/software/bash/",
            "cli": "/usr/bin/bash",
            "command": "/usr/bin/bash",
            "installed": True,
            "default_model": "Host Native (Linux 64-bit)",
            "modes": ["standard", "interactive"],
            "runs_in": "cli-terminal-tab",
            "dashboard_tab": "Host Shell",
            "icon": "Terminal",
            "description": "Full interactive host terminal shell with access to system tools, git, python, and systemctl."
        },
        {
            "id": "9router",
            "name": "9Router Gateway",
            "type": "model-gateway",
            "repo": "https://github.com/9router/9router",
            "url": "http://127.0.0.1:20128",
            "models_count": 870,
            "installed": True,
            "modes": ["openai-compatible", "streaming", "tools", "vision", "thinking"],
            "runs_in": "model-browser-tab",
            "dashboard_tab": "9Router Models",
            "icon": "Boxes",
            "description": "Local OpenAI-compatible AI gateway aggregating 870 models across Anthropic, OpenAI, Google, DeepSeek, and OpenRouter."
        }
    ]

    registry = {
        "generated_at": datetime.now().isoformat(),
        "agents": agents
    }

    for p in [DEST_DIR / "AGENT_REGISTRY.json", ALT_DIR / "AGENT_REGISTRY.json"]:
        p.write_text(json.dumps(registry, indent=2))
    print("Saved AGENT_REGISTRY.json")

if __name__ == "__main__":
    build_model_registry()
    build_tool_registry()
    build_agent_registry()
    print("All registries successfully built!")
