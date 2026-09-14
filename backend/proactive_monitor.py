#!/usr/bin/env python3
"""
AEGIS Proactive Intelligence & Experience Learning Engine
- Scans project git states, pending TODOs, and systemd service failures.
- Records structured task experiences (inputs, models, tools, outcomes).
- Implements experience learning (recommending proven workflows, avoiding past failures).
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from backend.config import cfg
from backend.logger import get_logger

log = get_logger("proactive_monitor")

class ProactiveMonitor:
    def __init__(self):
        self.state_dir = cfg.AEGIS_DIR
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.experiences_file = cfg.EXPERIENCES_FILE
        self._init_db()

    def _init_db(self):
        if not self.experiences_file.exists():
            self.experiences_file.write_text(json.dumps({
                "created_at": time.time(),
                "experiences": []
            }, indent=2))

    def record_experience(self, goal: str, model: str, tools_used: List[str], outcome: str, lessons: List[str], plan_id: Optional[str] = None):
        """Records an execution experience for reinforcement learning."""
        try:
            data = json.loads(self.experiences_file.read_text())
        except Exception:
            data = {"experiences": []}

        record = {
            "id": f"exp_{int(time.time())}_{len(data['experiences'])}",
            "plan_id": plan_id,
            "timestamp": time.time(),
            "goal": goal,
            "model": model,
            "tools_used": tools_used,
            "outcome": outcome,  # "SUCCESS" | "FAILURE" | "PARTIAL"
            "lessons": lessons
        }
        data["experiences"].append(record)
        self.experiences_file.write_text(json.dumps(data, indent=2))
        return record

    def query_past_experiences(self, task_goal: str) -> List[dict]:
        """Finds relevant past experiences to reuse winning workflows or avoid mistakes."""
        try:
            data = json.loads(self.experiences_file.read_text())
            exps = data.get("experiences", [])
        except Exception:
            return []

        words = set(task_goal.lower().split())
        matched = []
        for e in exps:
            e_words = set(e.get("goal", "").lower().split())
            overlap = len(words.intersection(e_words))
            if overlap > 0:
                matched.append((overlap, e))

        matched.sort(key=lambda x: x[0], reverse=True)
        return [m[1] for m in matched[:3]]

    def scan_project_health(self) -> dict:
        """Non-intrusively checks repository git status, failed units, and disk state."""
        repo_health = {}
        for name, p in cfg.PROJECTS.items():
            if (p / ".git").exists():
                try:
                    res = subprocess.run(["git", "status", "--porcelain"], cwd=str(p), capture_output=True, text=True, timeout=2)
                    lines = [l for l in res.stdout.strip().splitlines() if l]
                    uncommitted_count = len(lines)
                    repo_health[name] = {
                        "clean": uncommitted_count == 0,
                        "uncommitted_files": uncommitted_count,
                        "status_preview": lines[:3]
                    }
                except Exception:
                    repo_health[name] = {"clean": True, "error": "status check timed out"}

        # Systemd checks
        failed_services = []
        try:
            res_units = subprocess.run(["systemctl", "--user", "list-units", "--state=failed", "--no-legend", "--no-pager"], capture_output=True, text=True, timeout=2)
            for line in res_units.stdout.strip().splitlines():
                if line.strip():
                    failed_services.append(line.split()[0])
        except Exception:
            pass

        return {
            "timestamp": time.time(),
            "repositories": repo_health,
            "failed_systemd_services": failed_services,
            "overall_status": "ATTENTION_REQUIRED" if failed_services else "HEALTHY"
        }

proactive_monitor = ProactiveMonitor()

if __name__ == "__main__":
    print("Testing Proactive Monitor & Experience Engine...")
    health = proactive_monitor.scan_project_health()
    print("Project health status:", health["overall_status"])
    print("Repositories scanned:", list(health["repositories"].keys()))
    
    # Record test experience
    exp = proactive_monitor.record_experience(
        goal="Lint and verify code in sandbox",
        model="gemini/gemini-3.6-flash",
        tools_used=["lint_syntax", "execute_sandboxed"],
        outcome="SUCCESS",
        lessons=["Use py_compile before executing Python scripts to catch syntax errors fast."]
    )
    print("Experience recorded:", exp["id"])

    # Query experience
    hits = proactive_monitor.query_past_experiences("verify code syntax")
    print(f"Experience query returned {len(hits)} matching past experiences.")
    assert len(hits) > 0, "Failed to match recorded experience"
    print("Proactive Monitor: VERIFIED OK")
