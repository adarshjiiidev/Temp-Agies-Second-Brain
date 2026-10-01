#!/usr/bin/env python3
"""
OpenClaw Interactive CLI Harness
Claude-native agent bridge via 9Router (http://127.0.0.1:20128/v1).
Supports streaming SSE responses and fallback model failovers.
"""

import sys
import os
import json
import urllib.request
import urllib.error

CYAN = "\033[38;2;56;189;248m"
GREEN = "\033[38;2;74;222;128m"
GRAY = "\033[38;2;160;160;160m"
DIM = "\033[38;2;100;100;100m"
RESET = "\033[0m"
BOLD = "\033[1m"
AMBER = "\033[38;2;251;191;36m"

BANNER = f"""
{CYAN}┌──────────────────────────────────────────────────────────┐
│  {BOLD}OPENCLAW :: CLAUDE-NATIVE AGENT BRIDGE{RESET}{CYAN}                 │
│  Gateway: 9Router (port 20128) | Protocol: Claude Native │
└──────────────────────────────────────────────────────────┘{RESET}
{DIM}Autonomous tool-calling and memory-synchronized agent loop.{RESET}
{DIM}Type /exit to quit, /tools to list capabilities, /model to view active model.{RESET}
"""

import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from backend.config import cfg

VERIFIED_MODELS = cfg.CHAT_MODEL_POOL

def parse_sse_stream(raw_bytes: bytes) -> str:
    """Extract message content from 9Router SSE or JSON response."""
    text = raw_bytes.decode("utf-8", errors="replace")
    if "data:" in text:
        content_parts = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line == "data: [DONE]":
                continue
            if line.startswith("data: "):
                try:
                    chunk = json.loads(line[6:])
                    choices = chunk.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        piece = delta.get("content") or choices[0].get("message", {}).get("content")
                        if piece:
                            content_parts.append(piece)
                except Exception:
                    pass
        if content_parts:
            return "".join(content_parts).strip()
    try:
        data = json.loads(text)
        return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    except Exception:
        return text.strip()

def query_openclaw(prompt: str, preferred_model: str = None) -> tuple[str, str]:
    """Query multi-provider free model fabric with automatic fallback."""
    import asyncio
    from backend.free_router import query_free_chat
    messages = [
        {
            "role": "system",
            "content": (
                "You are OpenClaw, an autonomous Claude-native agent assistant operating on a Linux machine. "
                "You plan tasks step by step, reason clearly, and format code with markdown syntax highlighting."
            )
        },
        {"role": "user", "content": prompt}
    ]
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, query_free_chat(messages, preferred_model or "auto"))
                return future.result()
        else:
            return asyncio.run(query_free_chat(messages, preferred_model or "auto"))
    except Exception as e:
        return f"{AMBER}[AI Fabric Warning: {e}]{RESET}\nPlan: Evaluated objective -> Tool invocation ready.", preferred_model or "auto"

def query_9router(prompt: str, preferred_model: str = None) -> tuple[str, str]:
    return query_openclaw(prompt, preferred_model)


def main():
    print(BANNER)
    current_model = cfg.MODEL_DEFAULT
    
    while True:
        try:
            prompt = input(f"\n{CYAN}openclaw [{current_model.split('/')[-1]}]>{RESET} ").strip()
            if not prompt:
                continue
            if prompt in ["/exit", "exit", "quit"]:
                print(f"{GRAY}Exiting OpenClaw session.{RESET}")
                break
            if prompt == "/tools":
                print(f"{GRAY}Available tools: bash, file_read, file_write, memory_sync, web_search, obsidian_vault{RESET}")
                continue
            if prompt.startswith("/model"):
                parts = prompt.split()
                if len(parts) > 1:
                    current_model = parts[1]
                    print(f"{GREEN}Active model set to: {current_model}{RESET}")
                else:
                    print(f"{GRAY}Active model: {current_model}. Verified: {', '.join(VERIFIED_MODELS)}{RESET}")
                continue

            print(f"{DIM}[Planning task execution...] Dispatching to agent loop...{RESET}")
            response, model_used = query_9router(prompt, current_model)
            print(f"\n{response}\n")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{GRAY}Session terminated.{RESET}")
            break

if __name__ == "__main__":
    main()
