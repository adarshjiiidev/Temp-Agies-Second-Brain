#!/usr/bin/env python3
"""
AEGIS Universal Agent Runner
==============================
Launches and routes CLI harnesses for all registered agents.
Agent discovery is fully registry-driven via cfg.resolve_agent_command().
No hardcoded paths. No hardcoded usernames.
"""

import sys
import os
import argparse
import subprocess

_repo_root = __file__
for _ in range(2):
    _repo_root = os.path.dirname(_repo_root)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from backend.config import cfg
from backend.logger import get_logger

log = get_logger("agent_runner")


def _get_agent_ids() -> list:
    return [a["id"] for a in cfg.AGENT_REGISTRY] + ["bash"]


def main():
    all_ids = _get_agent_ids()
    parser = argparse.ArgumentParser(description="AEGIS Universal Agent Harness Runner")
    parser.add_argument(
        "--agent", required=True, choices=all_ids,
        help="Agent identifier to run (from AGENT_REGISTRY)"
    )
    parser.add_argument("--test", action="store_true", help="Run self-test query and exit")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="Additional arguments for agent")
    args = parser.parse_args()

    agent = args.agent.lower()
    log.info("Agent runner invoked: agent=%s test=%s", agent, args.test)

    if args.test:
        print(f"Testing agent harness: {agent}...")
        if agent == "openclaw":
            from backend.openclaw_harness import query_9router
            res, m = query_9router("Ping test")
            print(f"OpenClaw OK (model: {m}): {res[:80]}")
            sys.exit(0)
        elif agent == "deepseek":
            from backend.deepseek_harness import query_9router
            res, m = query_9router("1+1=")
            print(f"DeepSeek OK (model: {m}): {res[:80]}")
            sys.exit(0)
        else:
            cmd = cfg.resolve_agent_command(agent)
            if cmd and os.path.exists(cmd[0]):
                print(f"{agent} OK: Binary found at {cmd[0]}")
                sys.exit(0)
            else:
                print(f"{agent} WARNING: Binary not found at expected path, will use PATH fallback")
                sys.exit(0)

    # ── Launch interactive session ─────────────────────────────────────────────
    if agent == "deepseek":
        from backend.deepseek_harness import main as run_deepseek
        run_deepseek()
    elif agent == "openclaw":
        from backend.openclaw_harness import main as run_openclaw
        run_openclaw()
    else:
        cmd = cfg.resolve_agent_command(agent) + (args.args or [])
        log.info("Launching: %s", cmd)
        subprocess.run(cmd)


if __name__ == "__main__":
    main()
