#!/usr/bin/env python3
"""
TEMPORARY AEGIS — Model Registry Builder v2

Smarter classification that identifies the genuinely best models
for each role, preferring known families with proven capability.
"""

import json
import urllib.request
import sys
from collections import defaultdict
from datetime import datetime

ROUTER_URL = "http://127.0.0.1:20128/v1/models"

# Models we know are strong — human-verified from the audit
STRONG_MODELS = {
    "cl/openai/gpt-5.6-sol": {"role": "coding", "reason": "GPT-5.6 Sol — frontier coding model, 372K context, OpenAI thinking"},
    "cl/openai/gpt-5.6-terra": {"role": "default", "reason": "GPT-5.6 Terra — balanced general model, 272K context"},
    "cl/anthropic/claude-opus-5": {"role": "reasoning", "reason": "Claude Opus 5 — top reasoning, 1M context, adaptive thinking"},
    "cl/anthropic/claude-sonnet-5": {"role": "long_context", "reason": "Claude Sonnet 5 — strong all-rounder, 1M context"},
    "cl/google/gemini-3.8-flash": {"role": "multimodal", "reason": "Gemini 3.8 Flash — multimodal, 1M context, fast"},
    "ag/gemini-3.8-flash": {"role": "fast", "reason": "Gemini 3.8 Flash (direct) — fast, 1M context, tools+vision"},
    "cl/openai/gpt-5.5": {"role": "coding_alt", "reason": "GPT-5.5 — proven coding, 400K context"},
    "cl/openai/gpt-5.4": {"role": "established", "reason": "GPT-5.4 — mature capability, 400K context"},
    "cl/anthropic/claude-opus-4.8": {"role": "reasoning_alt", "reason": "Claude Opus 4.8 — strong reasoning, 1M context"},
    "cl/anthropic/claude-sonnet-4.6": {"role": "coding_established", "reason": "Claude Sonnet 4.6 — proven coding, 1M context"},
    "cl/qwen/qwen3.7-plus": {"role": "coding_alt2", "reason": "Qwen 3.7 Plus — coding, long context, 1M tokens"},
    "kimi/kimi-k3": {"role": "long_horizon", "reason": "Kimi K3 — long horizon agent, 1M context, 128K output"},
    "cl/openai/gpt-5.6-luna": {"role": "general", "reason": "GPT-5.6 Luna — general purpose, 400K context"},
    "gh/kimi-k3": {"role": "github_coding", "reason": "Kimi K3 via GitHub Copilot — coding, 1M context"},
    "cl/openai/gpt-5.6-luna-pro": {"role": "pro_coding", "reason": "GPT-5.6 Luna Pro — enhanced coding, 400K context"},
    "cx/gpt-5.6-sol": {"role": "cx_coding", "reason": "GPT-5.6 Sol (CX) — coding, 372K context"},
    "cx/gpt-5.6-terra": {"role": "cx_default", "reason": "GPT-5.6 Terra (CX) — general, 272K context"},
}

def fetch_models():
    try:
        req = urllib.request.Request(ROUTER_URL)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("data", data if isinstance(data, list) else [])
    except Exception as e:
        print(f"Error fetching models: {e}", file=sys.stderr)
        return []

def identify_model(mid):
    """Identify model by known patterns."""
    mid_lower = mid.lower()
    
    # Direct hit in strong models
    if mid in STRONG_MODELS:
        return STRONG_MODELS[mid]
    
    # Pattern matching for known strong families
    if "claude-opus-5" in mid_lower and "thinking" not in mid_lower and "batch" not in mid_lower:
        return {"role": "reasoning", "reason": f"Claude Opus 5 variant — top reasoning capability"}
    if "claude-sonnet-5" in mid_lower and "thinking" not in mid_lower and "batch" not in mid_lower:
        return {"role": "coding", "reason": f"Claude Sonnet 5 variant — strong coding+analysis"}
    if "gemini-3.8-flash" in mid_lower and "batch" not in mid_lower:
        return {"role": "multimodal", "reason": f"Gemini 3.8 Flash variant — multimodal, fast"}
    if "gpt-5.6-sol" in mid_lower and "review" not in mid_lower and "batch" not in mid_lower and "pro" not in mid_lower:
        return {"role": "coding", "reason": f"GPT-5.6 Sol variant — frontier coding"}
    if "gpt-5.6-terra" in mid_lower and "review" not in mid_lower and "batch" not in mid_lower and "pro" not in mid_lower:
        return {"role": "default", "reason": f"GPT-5.6 Terra variant — balanced general"}
    if "qwen3.7" in mid_lower and ("plus" in mid_lower or "max" in mid_lower) and "batch" not in mid_lower:
        return {"role": "coding", "reason": f"Qwen 3.7 variant — coding, long context"}
    if "kimi-k3" in mid_lower and "base" in mid_lower and "batch" not in mid_lower:
        return {"role": "long_horizon", "reason": f"Kimi K3 — long horizon agent"}
    
    return None

def build_registry(models):
    registry = {
        "generated_at": "",
        "total_available": len(models),
        "families": {},
        "capability_counts": {
            "reasoning_and_tools": 0,
            "vision_and_tools": 0,
            "long_context_1m": 0,
            "max_output_128k": 0,
        },
        "curated_for_role": {},
        "routing_table": {},
    }
    
    # Count capabilities
    for m in models:
        caps = m.get("capabilities", {}) or {}
        if caps.get("reasoning") and caps.get("tools"):
            registry["capability_counts"]["reasoning_and_tools"] += 1
        if caps.get("vision") and caps.get("tools"):
            registry["capability_counts"]["vision_and_tools"] += 1
        if caps.get("contextWindow", 0) >= 1000000:
            registry["capability_counts"]["long_context_1m"] += 1
        if caps.get("maxOutput", 0) >= 128000:
            registry["capability_counts"]["max_output_128k"] += 1
        
        # Family counts
        mid = m.get("id", "?")
        family = "other"
        for f in ["claude", "gemini", "gpt", "qwen", "kimi", "grok", "deepseek", "muse", "nemotron"]:
            if f in mid.lower():
                family = f
                break
        registry["families"][family] = registry["families"].get(family, 0) + 1
    
    # Curate by role — pick the best verified model for each role
    curated = {}
    
    role_assignments = [
        ("default", "cl/openai/gpt-5.6-terra", "Balanced general-purpose model — GPT-5.6 Terra, 272K context, OpenAI reasoning"),
        ("coding", "cl/openai/gpt-5.6-sol", "Frontier coding model — GPT-5.6 Sol, 372K context, strong agentic coding"),
        ("coding_alt", "cl/anthropic/claude-sonnet-4.6", "Established coding — Claude Sonnet 4.6, 1M context, proven codebase understanding"),
        ("reasoning", "cl/anthropic/claude-opus-5", "Top reasoning — Claude Opus 5, 1M context, adaptive thinking, complex analysis"),
        ("reasoning_alt", "cl/anthropic/claude-opus-4.8", "Strong reasoning alternative — Claude Opus 4.8, 1M context"),
        ("fast", "ag/gemini-3.8-flash", "Fast execution — Gemini 3.8 Flash direct, 1M context, tools+vision+reasoning"),
        ("multimodal", "cl/google/gemini-3.8-flash", "Multimodal work — Gemini 3.8 Flash via Chat/LM, 1M context, vision+audio+video"),
        ("long_context", "cl/anthropic/claude-sonnet-5", "Maximum context — Claude Sonnet 5, 1M context, strong all-rounder"),
        ("long_horizon", "kimi/kimi-k3", "Long horizon agent — Kimi K3, 1M context, 128K output, agentic"),
        ("github_coding", "gh/kimi-k3", "GitHub Copilot coding — Kimi K3 via Copilot, 1M context"),
        ("budget", "ag/gemini-3.8-flash-low", "Budget tier — Gemini 3.8 Flash Low, 1M context, lower cost"),
        ("summarization", "ag/gemini-3.8-flash-low", "Efficient summarization — Gemini 3.8 Flash Low, fast, large context"),
        ("classification", "ag/gemini-3.8-flash-extra-low", "Fast classification — Gemini 3.8 Flash Extra Low, minimal cost"),
        ("research", "cl/anthropic/claude-opus-5", "Research synthesis — Claude Opus 5, deep reasoning, 1M context for papers"),
        ("debugging", "cl/anthropic/claude-sonnet-4.6", "Debugging — Claude Sonnet 4.6, codebase understanding, 1M context"),
        ("architecture", "cl/anthropic/claude-opus-5", "Architecture review — Claude Opus 5, comprehensive analysis"),
        ("tool_orchestration", "cl/openai/gpt-5.6-terra", "Tool use — GPT-5.6 Terra, reliable tool calling, 272K context"),
    ]
    
    for role, model_id, reason in role_assignments:
        curated[role] = {
            "model": model_id,
            "reason": reason,
            "verified": model_id in STRONG_MODELS,
        }
    
    registry["curated_for_role"] = curated
    
    # Build routing table
    registry["routing_table"] = {
        "simple_query": "ag/gemini-3.8-flash-low",
        "default": "cl/openai/gpt-5.6-terra",
        "coding_task": "cl/openai/gpt-5.6-sol",
        "deep_reasoning": "cl/anthropic/claude-opus-5",
        "code_review": "cl/anthropic/claude-sonnet-4.6",
        "architecture_review": "cl/anthropic/claude-opus-5",
        "research": "cl/anthropic/claude-opus-5",
        "debugging": "cl/anthropic/claude-sonnet-4.6",
        "multimodal": "cl/google/gemini-3.8-flash",
        "long_context_analysis": "cl/anthropic/claude-sonnet-5",
        "summarization": "ag/gemini-3.8-flash-low",
        "classification": "ag/gemini-3.8-flash-extra-low",
        "fast_tool_use": "ag/gemini-3.8-flash",
        "long_horizon_agent": "kimi/kimi-k3",
        "github_coding": "gh/kimi-k3",
        "fallback_cloud": "cl/openai/gpt-5.6-terra",
        "fallback_reasoning": "cl/anthropic/claude-opus-4.8",
    }
    
    # Model details for the curated set
    model_details = {}
    for m in models:
        mid = m.get("id", "?")
        if mid in STRONG_MODELS or any(mid.startswith(prefix) for prefix in [
            "cl/openai/gpt-5.6", "cl/anthropic/claude-opus-5", "cl/anthropic/claude-sonnet-5",
            "cl/anthropic/claude-opus-4.8", "cl/anthropic/claude-sonnet-4.6",
            "cl/google/gemini-3.8-flash", "ag/gemini-3.8-flash",
            "cl/qwen/qwen3.7", "kimi/kimi-k3", "gh/kimi-k3",
            "cx/gpt-5.6", "cl/openai/gpt-5.5", "cl/openai/gpt-5.4",
        ]):
            caps = m.get("capabilities", {}) or {}
            model_details[mid] = {
                "context_window": caps.get("contextWindow", 0),
                "max_output": caps.get("maxOutput", 0),
                "reasoning": caps.get("reasoning", False),
                "tools": caps.get("tools", False),
                "vision": caps.get("vision", False),
                "thinking_format": caps.get("thinkingFormat", ""),
                "search": caps.get("search", False),
            }
    
    registry["model_details"] = model_details
    
    return registry

def main():
    models = fetch_models()
    if not models:
        print("No models fetched. Is 9Router running on port 20128?", file=sys.stderr)
        sys.exit(1)
    
    registry = build_registry(models)
    registry["generated_at"] = datetime.now().isoformat()
    
    # Save JSON
    json_path = "/home/adarshjii/.temporary-aegis/MODEL_REGISTRY.json"
    with open(json_path, "w") as f:
        json.dump(registry, f, indent=2)
    print(f"Model registry saved to {json_path}")
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"TEMPORARY AEGIS — MODEL REGISTRY")
    print(f"{'='*60}")
    print(f"Total models available via 9Router: {registry['total_available']}")
    print(f"\nFamily distribution:")
    for fam, count in sorted(registry["families"].items(), key=lambda x: -x[1]):
        print(f"  {fam:15s}: {count:4d} models")
    
    print(f"\nCapability summary:")
    for cap, count in registry["capability_counts"].items():
        print(f"  {cap:30s}: {count:4d}")
    
    print(f"\n{'='*60}")
    print(f"CURATED MODEL ROUTING TABLE")
    print(f"{'='*60}")
    for role in sorted(registry["routing_table"].keys()):
        model = registry["routing_table"][role]
        detail = registry["model_details"].get(model, {})
        ctx = detail.get("context_window", 0)
        print(f"  {role:30s} → {model:45s} (ctx={ctx})")
    
    print(f"\n{'='*60}")
    print(f"KEY MODEL DETAILS")
    print(f"{'='*60}")
    for mid in sorted(registry["model_details"].keys()):
        d = registry["model_details"][mid]
        caps_str = []
        if d["reasoning"]: caps_str.append("reasoning")
        if d["tools"]: caps_str.append("tools")
        if d["vision"]: caps_str.append("vision")
        if d["search"]: caps_str.append("search")
        print(f"  {mid:45s} ctx={d['context_window']:>10d} out={d['max_output']:>6d} [{', '.join(caps_str)}]")
    
    print(f"\n{'='*60}")
    print(f"ROLE → MODEL MAP (curated_for_role)")
    print(f"{'='*60}")
    for role, info in sorted(registry["curated_for_role"].items()):
        print(f"  [{role:25s}] {info['model']:45s}")
        print(f"                   {info['reason']}")

if __name__ == "__main__":
    main()
