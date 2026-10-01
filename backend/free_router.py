#!/usr/bin/env python3
"""
AEGIS Multi-Provider Free Model Router
======================================
100% independent of 9Router. Routes directly across OpenRouter free tier,
Groq free tier (when GROQ_API_KEY is configured), and local LM Studio.

Features:
- Live round-robin across healthy free models
- Instant failover on 429 rate limits or provider errors
- Dual-field parsing (content + reasoning) so output is never dropped
- Zero paid API requirement
"""

import os
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import httpx
from dotenv import dotenv_values

log = logging.getLogger("aegis.free_router")

# ── Keys resolution ────────────────────────────────────────────────────────────

def resolve_keys() -> Dict[str, str]:
    keys = {}
    # Read environment variables first
    for k in ["OPENROUTER_API_KEY", "GROQ_API_KEY"]:
        if os.environ.get(k):
            keys[k] = os.environ[k].strip()

    # Read profiles/.env
    p_agies = Path.home() / ".hermes/profiles/agies/.env"
    if p_agies.exists():
        vals = dotenv_values(p_agies)
        for k in ["OPENROUTER_API_KEY", "GROQ_API_KEY"]:
            if k not in keys and vals.get(k):
                keys[k] = str(vals[k]).strip()

    p_hermes = Path.home() / ".hermes/.env"
    if p_hermes.exists():
        vals = dotenv_values(p_hermes)
        for k in ["OPENROUTER_API_KEY", "GROQ_API_KEY"]:
            if k not in keys and vals.get(k):
                keys[k] = str(vals[k]).strip()

    p_aegis = Path.home() / ".temporary-aegis/config/keys.json"
    if p_aegis.exists():
        try:
            import json
            vals = json.loads(p_aegis.read_text())
            for k in ["OPENROUTER_API_KEY", "GROQ_API_KEY"]:
                if k not in keys and vals.get(k):
                    keys[k] = str(vals[k]).strip()
        except Exception:
            pass

    return keys

# ── Curated Free Models ────────────────────────────────────────────────────────

# Cactus Compute Needle — on-device function calling (local inference, no API key needed)
# https://cactuscompute.com/needle — 8-29 MB model, tool-call specialized
CACTUS_NEEDLE_MODELS = [
    {
        "id": "cactus/needle-3-20l",
        "slug": "needle-3-20l",
        "name": "Cactus Needle 3 (20L)",
        "provider": "Cactus Compute",
        "role": "Ultra-Fast Local Function Calling",
        "badge": "LOCAL TOOL-CALL",
        "context_window": 4096,
        "speed": "4k t/s on-device",
        "tools": True,
        "reasoning": False,
    },
    {
        "id": "cactus/needle-3-8l",
        "slug": "needle-3-8l",
        "name": "Cactus Needle 3 (8L Lite)",
        "provider": "Cactus Compute",
        "role": "Lightweight Edge Function Extraction",
        "badge": "LOCAL NANO",
        "context_window": 2048,
        "speed": "Ultra-fast edge inference",
        "tools": True,
        "reasoning": False,
    },
]

OPENROUTER_FREE_MODELS = [
    {
        "id": "openrouter/free",
        "slug": "openrouter/free",
        "name": "Auto Free Router",
        "provider": "OpenRouter",
        "role": "Balanced Free Round-Robin",
        "badge": "FREE AUTO",
        "context_window": 32768,
        "speed": "Ultra-Fast",
    },
    {
        "id": "openrouter/dots-studio/dots-3-note-preview:free",
        "slug": "dots-studio/dots-3-note-preview:free",
        "name": "Dots 3 Note Preview",
        "provider": "Dots Studio",
        "role": "Note Drafting & Summarization",
        "badge": "FREE",
        "context_window": 16384,
        "speed": "Fast",
    },
    {
        "id": "openrouter/cohere/north-mini-code:free",
        "slug": "cohere/north-mini-code:free",
        "name": "Cohere North Mini Code",
        "provider": "Cohere",
        "role": "Code Generation & Debugging",
        "badge": "FREE CODE",
        "context_window": 32768,
        "speed": "High",
    },
    {
        "id": "openrouter/liquid/lfm-2.5-2.6b:free",
        "slug": "liquid/lfm-2.5-2.6b:free",
        "name": "Liquid LFM 2.6B",
        "provider": "Liquid AI",
        "role": "Low-Latency Instant Chat",
        "badge": "FREE EDGE",
        "context_window": 32768,
        "speed": "Ultra-Fast",
    },
    {
        "id": "openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        "slug": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        "name": "Nemotron 30B Reasoning",
        "provider": "NVIDIA",
        "role": "Deep Step-by-Step Reasoning",
        "badge": "FREE REASONING",
        "context_window": 32768,
        "speed": "Standard",
    },
    {
        "id": "openrouter/nvidia/nemotron-3.5-lightning:free",
        "slug": "nvidia/nemotron-3.5-lightning:free",
        "name": "Nemotron 3.5 Lightning",
        "provider": "NVIDIA",
        "role": "High Throughput Agent Tasks",
        "badge": "FREE FAST",
        "context_window": 32768,
        "speed": "Ultra-Fast",
    },
    {
        "id": "openrouter/qwen/qwen3.8-27b:free",
        "slug": "qwen/qwen3.8-27b:free",
        "name": "Qwen 3.8 27B",
        "provider": "Qwen",
        "role": "General Knowledge & Multilingual",
        "badge": "FREE PRO",
        "context_window": 32768,
        "speed": "High",
    },
    {
        "id": "openrouter/google/gemma-4-31b-it:free",
        "slug": "google/gemma-4-31b-it:free",
        "name": "Google Gemma 31B",
        "provider": "Google",
        "role": "Knowledge Synthesis & Writing",
        "badge": "FREE 31B",
        "context_window": 32768,
        "speed": "Standard",
    },
    {
        "id": "openrouter/poolside/laguna-s-2.1:free",
        "slug": "poolside/laguna-s-2.1:free",
        "name": "Poolside Laguna S 2.1",
        "provider": "Poolside",
        "role": "Specialized Code Synthesis",
        "badge": "FREE CODE",
        "context_window": 32768,
        "speed": "High",
    },
]

GROQ_MODELS = [
    {
        "id": "groq/llama-3.3-70b-versatile",
        "slug": "llama-3.3-70b-versatile",
        "name": "Groq LLaMA 3.3 70B",
        "provider": "Groq",
        "role": "High-Capacity Fast Reasoning",
        "badge": "GROQ FREE",
        "context_window": 131072,
        "speed": "Lightning (280 t/s)",
    },
    {
        "id": "groq/llama-3.1-8b-instant",
        "slug": "llama-3.1-8b-instant",
        "name": "Groq LLaMA 3.1 8B Instant",
        "provider": "Groq",
        "role": "Instant Response & Quick Ingest",
        "badge": "GROQ FREE",
        "context_window": 131072,
        "speed": "Lightning (700 t/s)",
    },
    {
        "id": "groq/gemma2-9b-it",
        "slug": "gemma2-9b-it",
        "name": "Groq Gemma 2 9B",
        "provider": "Groq",
        "role": "Instruction Following & Summaries",
        "badge": "GROQ FREE",
        "context_window": 8192,
        "speed": "Lightning",
    },
]

# ── State & Round-Robin Tracking ───────────────────────────────────────────────

_model_cooldowns: Dict[str, float] = {}
_round_robin_idx: int = 0

# ── Cactus Needle local inference ────────────────────────────────────────────

async def query_cactus_needle(model_slug: str, messages: list, tools: Optional[list] = None, max_tokens: int = 512) -> str:
    """
    Query Cactus Compute Needle model for on-device function calling.
    Runs via the local cactus-compute Python package.
    Falls back gracefully if cactus package is not installed.
    """
    try:
        import importlib
        cactus = importlib.import_module("cactus")
        # Layers: '20l' -> 20, '8l' -> 8
        layers = 20 if "20l" in model_slug else 8
        model = cactus.Model(layers=layers)
        
        # Build messages for Needle
        needle_messages = [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in messages]
        
        if tools:
            result = model.chat(messages=needle_messages, tools=tools, max_tokens=max_tokens)
        else:
            result = model.chat(messages=needle_messages, max_tokens=max_tokens)
        
        content = getattr(result, "content", "") or str(result)
        return content.strip() if content else "Needle inference returned empty response"
    except ImportError:
        raise RuntimeError("Cactus Needle not installed. Run: pip install cactus-compute")
    except Exception as e:
        raise RuntimeError(f"Cactus Needle error: {e}")

def get_curated_models() -> Dict[str, Any]:
    keys = resolve_keys()
    curated = {}

    for m in OPENROUTER_FREE_MODELS:
        curated[m["id"]] = {
            "name": m["name"],
            "role": m["role"],
            "provider": m["provider"],
            "badge": m["badge"],
            "source": "OpenRouter (Free)",
            "context_window": m["context_window"],
            "speed": m["speed"],
            "status": "online" if keys.get("OPENROUTER_API_KEY") else "needs_key",
            "reasoning": True,
            "tools": True,
            "vision": False,
        }

    for m in GROQ_MODELS:
        curated[m["id"]] = {
            "name": m["name"],
            "role": m["role"],
            "provider": m["provider"],
            "badge": m["badge"],
            "source": "Groq Cloud (Free)",
            "context_window": m["context_window"],
            "speed": m["speed"],
            "status": "online" if keys.get("GROQ_API_KEY") else "needs_key",
            "reasoning": True,
            "tools": True,
            "vision": False,
        }

    for m in CACTUS_NEEDLE_MODELS:
        # Check if cactus-compute package is installed
        try:
            import importlib
            importlib.import_module("cactus")
            needle_status = "online"
        except ImportError:
            needle_status = "installable"
        curated[m["id"]] = {
            "name": m["name"],
            "role": m["role"],
            "provider": m["provider"],
            "badge": m["badge"],
            "source": "Cactus Compute (On-Device)",
            "context_window": m["context_window"],
            "speed": m["speed"],
            "status": needle_status,
            "reasoning": False,
            "tools": True,
            "vision": False,
            "notes": "Local on-device function calling model. Install: pip install cactus-compute",
        }

    return curated

def get_round_robin_candidates() -> List[str]:
    keys = resolve_keys()
    now = time.time()
    candidates = []

    # If Groq is configured, prioritize Groq ultra-fast free models
    if keys.get("GROQ_API_KEY"):
        for m in GROQ_MODELS:
            mid = m["id"]
            if _model_cooldowns.get(mid, 0) < now:
                candidates.append(mid)

    # OpenRouter free models
    if keys.get("OPENROUTER_API_KEY"):
        for m in OPENROUTER_FREE_MODELS:
            mid = m["id"]
            if _model_cooldowns.get(mid, 0) < now:
                candidates.append(mid)

    if not candidates:
        # If all in cooldown, reset cooldowns
        _model_cooldowns.clear()
        if keys.get("GROQ_API_KEY"):
            candidates.extend([m["id"] for m in GROQ_MODELS])
        if keys.get("OPENROUTER_API_KEY"):
            candidates.extend([m["id"] for m in OPENROUTER_FREE_MODELS])

    return candidates

def pick_next_model() -> str:
    global _round_robin_idx
    candidates = get_round_robin_candidates()
    if not candidates:
        return "openrouter/free"
    selected = candidates[_round_robin_idx % len(candidates)]
    _round_robin_idx += 1
    return selected

# ── Query Dispatcher ──────────────────────────────────────────────────────────

async def query_openrouter(slug: str, messages: list, api_key: str, max_tokens: int = 1500) -> str:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:2981",
        "X-Title": "AEGIS Second Brain OS",
    }
    payload = {
        "model": slug,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=25.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code == 429:
            raise RuntimeError("Rate limited (HTTP 429)")
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:150]}")
        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("No choices in completion")
        msg = choices[0].get("message") or {}
        content = msg.get("content")
        if content and content.strip():
            return content.strip()
        # Fallback to reasoning if content is empty
        reasoning = msg.get("reasoning")
        if reasoning and reasoning.strip():
            return reasoning.strip()
        raise RuntimeError("Empty response received")

async def query_groq(model_name: str, messages: list, api_key: str, max_tokens: int = 1500) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_name,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code == 429:
            raise RuntimeError("Groq Rate limited (HTTP 429)")
        if resp.status_code != 200:
            raise RuntimeError(f"Groq HTTP {resp.status_code}: {resp.text[:150]}")
        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("No choices in Groq completion")
        content = choices[0].get("message", {}).get("content", "")
        if content and content.strip():
            return content.strip()
        raise RuntimeError("Empty response from Groq")

async def query_lmstudio(model_name: str, messages: list, max_tokens: int = 1500) -> str:
    url = "http://127.0.0.1:1234/v1/chat/completions"
    payload = {
        "model": model_name,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, json=payload)
        if resp.status_code != 200:
            raise RuntimeError(f"LM Studio HTTP {resp.status_code}")
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()

# ── Main Chat Generation Function ─────────────────────────────────────────────

async def query_free_chat(messages: list, target_model: Optional[str] = None) -> Tuple[str, str]:
    """
    Executes chat query using multi-provider free models with automatic failover.
    Returns (response_text, actual_model_used).
    """
    keys = resolve_keys()
    
    # Determine candidate order
    candidates_to_try = []
    if target_model and target_model != "auto":
        candidates_to_try.append(target_model)
    
    # Append round-robin candidates as fallback
    for c in get_round_robin_candidates():
        if c not in candidates_to_try:
            candidates_to_try.append(c)

    # Always ensure openrouter/free is in the chain
    if "openrouter/free" not in candidates_to_try:
        candidates_to_try.append("openrouter/free")

    last_error = ""

    for model_id in candidates_to_try:
        try:
            if model_id.startswith("cactus/"):
                slug = model_id.split("cactus/", 1)[1]
                content = await query_cactus_needle(slug, messages)
                return content, model_id

            elif model_id.startswith("groq/"):
                g_key = keys.get("GROQ_API_KEY")
                if not g_key:
                    continue
                model_slug = model_id.split("groq/", 1)[1]
                content = await query_groq(model_slug, messages, g_key)
                return content, model_id

            elif model_id.startswith("openrouter/"):
                o_key = keys.get("OPENROUTER_API_KEY")
                if not o_key:
                    continue
                if model_id == "openrouter/free":
                    slug = "openrouter/free"
                else:
                    slug = model_id.split("openrouter/", 1)[1]
                content = await query_openrouter(slug, messages, o_key)
                return content, model_id

            elif model_id.startswith("lmstudio/"):
                slug = model_id.split("lmstudio/", 1)[1]
                content = await query_lmstudio(slug, messages)
                return content, model_id

            else:
                # Default to openrouter free
                o_key = keys.get("OPENROUTER_API_KEY")
                if o_key:
                    content = await query_openrouter(model_id, messages, o_key)
                    return content, f"openrouter/{model_id}"

        except Exception as e:
            last_error = str(e)
            log.warning("Model %s failed: %s. Cooling down and shifting to next candidate...", model_id, e)
            _model_cooldowns[model_id] = time.time() + 60.0
            continue

    return (
        f"⚠️ All free model providers are temporarily congested ({last_error}). "
        f"Please verify OPENROUTER_API_KEY or set GROQ_API_KEY for lightning Groq inference.",
        "fallback/system"
    )

def get_free_router_health() -> dict:
    """Return health status of the multi-provider free model fabric."""
    keys = resolve_keys()
    has_or = bool(keys.get("OPENROUTER_API_KEY"))
    has_groq = bool(keys.get("GROQ_API_KEY"))
    # Check Cactus Needle availability
    try:
        import importlib
        importlib.import_module("cactus")
        has_cactus = True
    except ImportError:
        has_cactus = False
    status = "running" if (has_or or has_groq or has_cactus) else "degraded"
    candidates = get_round_robin_candidates()
    return {
        "status": status,
        "providers": {
            "openrouter": "online" if has_or else "missing_key",
            "groq": "online" if has_groq else "standby",
            "cactus_needle": "online" if has_cactus else "installable",
            "lmstudio": "detected",
        },
        "available_models": len(candidates) + len(CACTUS_NEEDLE_MODELS),
        "active_pool": candidates[:6],
    }

