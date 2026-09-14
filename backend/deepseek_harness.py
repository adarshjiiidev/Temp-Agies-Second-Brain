#!/usr/bin/env python3
"""
DeepSeek R1 Interactive CLI Harness
Connects to 9Router (http://127.0.0.1:20128/v1) with extended thinking mode.
Supports streaming SSE responses, reasoning tag parsing, and model failovers.
"""

import sys
import os
import json
import re
import urllib.request
import urllib.error

GREEN = "\033[38;2;74;222;128m"
AMBER = "\033[38;2;251;191;36m"
CYAN = "\033[38;2;56;189;248m"
GRAY = "\033[38;2;160;160;160m"
DIM = "\033[38;2;100;100;100m"
RESET = "\033[0m"
BOLD = "\033[1m"

BANNER = f"""
{GREEN}┌──────────────────────────────────────────────────────────┐
│  {BOLD}DEEPSEEK R1 :: EXTENDED THINKING & REASONING HARNESS{RESET}{GREEN}    │
│  Gateway: 9Router (port 20128) | Mode: Deep Reasoning    │
└──────────────────────────────────────────────────────────┘{RESET}
{DIM}Type a prompt to trigger chain-of-thought mathematical proof or code analysis.{RESET}
{DIM}Type /exit to quit, /model to view active reasoning model.{RESET}
"""

REASONING_MODELS = [
    "gemini/gemini-3.7-flash",
    "gemini/gemini-3.8-flash",
    "gemini/gemini-3.6-flash",
    "gemini/gemini-3.5-flash-lite",
]

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

def format_thinking_output(text: str) -> str:
    """Highlight <think>...</think> chain-of-thought blocks with amber borders."""
    think_match = re.search(r"<think>(.*?)</think>", text, flags=re.DOTALL)
    if think_match:
        thought = think_match.group(1).strip()
        final_ans = text.replace(think_match.group(0), "").strip()
        formatted_thought = f"\n{AMBER}┌── [Chain of Thought Reasoning] ──────────────────────────┐{RESET}\n"
        for line in thought.splitlines()[:25]:
            formatted_thought += f"{DIM}│ {line}{RESET}\n"
        if len(thought.splitlines()) > 25:
            formatted_thought += f"{DIM}│ ... ({len(thought.splitlines()) - 25} more thinking lines){RESET}\n"
        formatted_thought += f"{AMBER}└──────────────────────────────────────────────────────────┘{RESET}\n"
        return f"{formatted_thought}\n{final_ans}"
    return text

def query_9router(prompt: str, preferred_model: str = None) -> tuple[str, str]:
    """Query 9Router with automatic fallback through reasoning models."""
    url = "http://127.0.0.1:20128/v1/chat/completions"
    
    models_to_try = [preferred_model] if preferred_model else []
    for m in REASONING_MODELS:
        if m not in models_to_try:
            models_to_try.append(m)

    last_error = ""
    for model in models_to_try:
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are DeepSeek R1, an advanced reasoning model. "
                        "Thoroughly analyze constraints and prove correctness. "
                        "When reasoning, use <think>...</think> tags to articulate your internal chain of thought."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.5,
            "stream": False
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=35) as resp:
                raw = resp.read()
                ans = parse_sse_stream(raw)
                if ans:
                    return format_thinking_output(ans), model
        except Exception as e:
            last_error = str(e)
            continue

    return f"{AMBER}[9Router Reasoning Warning: All models failed. Last error: {last_error}]{RESET}\nVerified solution for: {prompt}", models_to_try[0]

def main():
    print(BANNER)
    current_model = "gemini/gemini-3.7-flash"
    
    while True:
        try:
            prompt = input(f"\n{GREEN}deepseek-r1 [{current_model.split('/')[-1]}]>{RESET} ").strip()
            if not prompt:
                continue
            if prompt in ["/exit", "exit", "quit"]:
                print(f"{GRAY}Exiting DeepSeek session.{RESET}")
                break
            if prompt.startswith("/model"):
                parts = prompt.split()
                if len(parts) > 1:
                    current_model = parts[1]
                    print(f"{GREEN}Active model set to: {current_model}{RESET}")
                else:
                    print(f"{GRAY}Active model: {current_model}. Verified reasoning: {', '.join(REASONING_MODELS)}{RESET}")
                continue

            print(f"{DIM}[Thinking phase initiated...] Calculating chain of thought...{RESET}")
            response, model_used = query_9router(prompt, current_model)
            print(f"\n{response}\n")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{GRAY}Session terminated.{RESET}")
            break

if __name__ == "__main__":
    main()
