#!/usr/bin/env python3
"""
AEGIS Cloudroom Agent Workspace & Command Guard Bridge
=====================================================
Adapted from Cloudroom GUI (https://github.com/davidondrej/cloudroom-gui) for AEGIS AI OS.
Provides:
- Multi-workspace discovery and telemetry across local developer trees
- Command Guard: Safety inspection & policy validation for agent terminal actions
- Workspace snapshotting (Git status, modified files, active processes)
"""

import sys
import os
import re
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
from backend.governance import governance, AutonomyLevel

log = get_logger("cloudroom_bridge")


class CloudroomWorkspaceBridge:
    def __init__(self):
        self.workspace_roots = [
            cfg.HOME / "Projects",
            cfg.HOME / "Work",
            cfg.HOME / "aegis-dashboard",
        ]
        self.dangerous_patterns = [
            (r'\brm\s+-(?:r|f|rf|fr)\s+/(?:$|\s)', "Root directory deletion attempted"),
            (r'\bdd\s+if=', "Low-level block device overwrite attempted"),
            (r'\bmkfs\.', "Filesystem format command detected"),
            (r'>\s*/dev/sd[a-z]', "Direct disk device write detected"),
            (r':\(\)\{\s*:\s*\|\s*:\s*&\s*\};:', "Fork bomb detected"),
            (r'\bchmod\s+-R\s+777\s+/', "Unsafe root permissions modification"),
            (r'\bgit\s+push\s+(?:--force|-f)\s+(?:origin\s+)?(?:main|master)', "Force push to production branch blocked by Command Guard"),
        ]

    def get_workspaces(self) -> List[Dict[str, Any]]:
        """Scans developer directories and returns active workspaces with git telemetry."""
        workspaces = []
        seen_paths = set()

        for root in self.workspace_roots:
            if not root.exists():
                continue

            candidates = [root] if root.name == "aegis-dashboard" else list(root.iterdir())
            for path in sorted(candidates):
                if not path.is_dir() or path.name.startswith(".") or str(path) in seen_paths:
                    continue
                seen_paths.add(str(path))

                git_dir = path / ".git"
                is_git = git_dir.exists()
                branch = "none"
                clean = True
                last_commit = ""
                untracked_count = 0

                if is_git:
                    try:
                        b_proc = subprocess.run(
                            ["git", "-C", str(path), "rev-parse", "--abbrev-ref", "HEAD"],
                            capture_output=True, text=True, timeout=2
                        )
                        if b_proc.returncode == 0:
                            branch = b_proc.stdout.strip()

                        s_proc = subprocess.run(
                            ["git", "-C", str(path), "status", "--porcelain"],
                            capture_output=True, text=True, timeout=2
                        )
                        if s_proc.returncode == 0:
                            lines = [l for l in s_proc.stdout.strip().split("\n") if l.strip()]
                            clean = len(lines) == 0
                            untracked_count = len(lines)

                        c_proc = subprocess.run(
                            ["git", "-C", str(path), "log", "-1", "--format=%s (%cr)"],
                            capture_output=True, text=True, timeout=2
                        )
                        if c_proc.returncode == 0:
                            last_commit = c_proc.stdout.strip()
                    except Exception:
                        pass

                # Detect stack
                stack = []
                if (path / "package.json").exists(): stack.append("Node/JS")
                if (path / "pyproject.toml").exists() or (path / "requirements.txt").exists(): stack.append("Python")
                if (path / "Cargo.toml").exists(): stack.append("Rust")
                if (path / "go.mod").exists(): stack.append("Go")

                workspaces.append({
                    "id": f"ws-{path.name}",
                    "name": path.name,
                    "path": str(path),
                    "is_git": is_git,
                    "branch": branch,
                    "is_clean": clean,
                    "changes_count": untracked_count,
                    "last_commit": last_commit,
                    "stack": stack or ["General"],
                    "updated_at": time.time(),
                })

        return workspaces

    def validate_command(self, command: str, target_workspace: Optional[str] = None) -> Dict[str, Any]:
        """
        Cloudroom Command Guard:
        Validates safety of agent commands before execution against policies and governance level.
        """
        trimmed = command.strip()

        # 1. Regex pattern guard for known catastrophic shell commands
        for pattern, reason in self.dangerous_patterns:
            if re.search(pattern, trimmed):
                log.warning("Command Guard BLOCKED: '%s' -> %s", trimmed, reason)
                return {
                    "allowed": False,
                    "risk_level": "CRITICAL",
                    "reason": reason,
                    "command": trimmed,
                }

        # 2. Check Governance Engine Autonomy Level
        current_autonomy = governance.current_level
        is_write = any(w in trimmed for w in [">", ">>", "git commit", "git push", "rm ", "npm install", "pip install", "touch", "mkdir"])

        if is_write and current_autonomy < AutonomyLevel.LEVEL_2:
            return {
                "allowed": False,
                "risk_level": "RESTRICTED",
                "reason": f"System autonomy is Level {int(current_autonomy)} (Read/Analyze only). Level 2+ required for modifications.",
                "command": trimmed,
            }

        return {
            "allowed": True,
            "risk_level": "LOW" if not is_write else "MODERATE",
            "reason": "Passed Cloudroom command safety rules",
            "command": trimmed,
            "autonomy_level": int(current_autonomy),
        }


cloudroom_bridge = CloudroomWorkspaceBridge()

if __name__ == "__main__":
    print("Testing Cloudroom Workspace Bridge...")
    ws = cloudroom_bridge.get_workspaces()
    print(f"Discovered {len(ws)} workspaces:")
    for w in ws[:5]:
        print(f"  • {w['name']} [{w['branch']}] clean={w['is_clean']} stack={w['stack']}")
    guard_test = cloudroom_bridge.validate_command("git status")
    print("Guard test (git status):", guard_test)
    guard_bad = cloudroom_bridge.validate_command("rm -rf /")
    print("Guard test (rm -rf /):", guard_bad)
