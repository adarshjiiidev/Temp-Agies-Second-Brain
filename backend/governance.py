#!/usr/bin/env python3
"""
AEGIS Governance Engine (L5)
Enforces strict policy and autonomy boundaries.
All side-effecting operations (writes, git, subprocess, agent spawning)
MUST pass through this governance boundary before execution.
"""

import os
import sys
import json
import time
from enum import IntEnum
from pathlib import Path
from typing import Dict, Any, List

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from backend.config import cfg
from backend.logger import get_logger

log = get_logger("governance")

class AutonomyLevel(IntEnum):
    LEVEL_0 = 0 # Observe only
    LEVEL_1 = 1 # Research/read/analyze
    LEVEL_2 = 2 # Local modifications with verification
    LEVEL_3 = 3 # Run agents and development tasks
    LEVEL_4 = 4 # Scheduled autonomous project work
    LEVEL_5 = 5 # Broad autonomous workstation operation subject to policy

class GovernanceEngine:
    def __init__(self):
        self.config_path = cfg.HOME / ".temporary-aegis" / "config" / "governance.json"
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.current_level = AutonomyLevel.LEVEL_1 # Default safe level
        self._load_policy()
        self.audit_log_path = cfg.HOME / ".temporary-aegis" / "logs" / "governance_audit.log"
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_policy(self):
        if self.config_path.exists():
            try:
                data = json.loads(self.config_path.read_text())
                level = data.get("autonomy_level", 1)
                self.current_level = AutonomyLevel(level)
            except Exception as e:
                log.error(f"Failed to load governance policy: {e}")
        else:
            self._save_policy()

    def _save_policy(self):
        data = {"autonomy_level": int(self.current_level)}
        self.config_path.write_text(json.dumps(data, indent=2))

    def set_autonomy_level(self, level: int):
        self.current_level = AutonomyLevel(level)
        self._save_policy()
        log.info(f"Autonomy level changed to {self.current_level.name}")
        self._audit("POLICY_CHANGE", "system", {"new_level": self.current_level.name}, True)

    def _audit(self, action: str, actor: str, details: Dict[str, Any], allowed: bool):
        entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "action": action,
            "actor": actor,
            "allowed": allowed,
            "details": details,
            "autonomy_level": self.current_level.name
        }
        with open(self.audit_log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def authorize(self, capability: str, actor: str, details: Dict[str, Any]) -> bool:
        """
        Check if a given capability is authorized under the current autonomy level.
        """
        allowed = False
        reason = ""

        if self.current_level == AutonomyLevel.LEVEL_0:
            # Strictly observation (read operations only)
            if capability in ["filesystem_read", "camera_snapshot", "project_inspect"]:
                allowed = True
            else:
                reason = "Level 0 permits observation only."

        elif self.current_level == AutonomyLevel.LEVEL_1:
            # Research & analysis
            if capability in ["filesystem_read", "camera_snapshot", "project_inspect", "browser_navigate", "browser_screenshot"]:
                allowed = True
            else:
                reason = "Level 1 prohibits side-effecting operations (writes, git, terminal)."

        elif self.current_level >= AutonomyLevel.LEVEL_2:
            # Modifications allowed
            if capability in ["filesystem_write", "terminal_run", "git_commit"]:
                # Basic safeguards even at higher levels
                if capability == "terminal_run":
                    cmd = details.get("command", "").lower()
                    if "rm -rf /" in cmd or "sudo" in cmd:
                        allowed = False
                        reason = "Command violates strict safety policy."
                    else:
                        allowed = True
                else:
                    allowed = True
            else:
                allowed = True # All read ops allowed

        # Special explicitly governed capabilities regardless of level
        if capability == "git_push":
            if self.current_level < AutonomyLevel.LEVEL_4:
                allowed = False
                reason = "Git push requires Autonomy Level 4+."

        self._audit(capability, actor, details, allowed)
        if not allowed:
            log.warning(f"Governance DENIED '{capability}' to '{actor}': {reason}")
            
        return allowed

governance_engine = GovernanceEngine()
governance = governance_engine

if __name__ == "__main__":
    ge = GovernanceEngine()
    print("Testing Governance Engine...")
    print(f"Current Level: {ge.current_level.name}")
    print("Test read:", ge.authorize("filesystem_read", "agent_moe", {"path": "/tmp"}))
    print("Test write:", ge.authorize("filesystem_write", "agent_moe", {"path": "/tmp/a"}))
    ge.set_autonomy_level(3)
    print("Test write (L3):", ge.authorize("filesystem_write", "agent_moe", {"path": "/tmp/a"}))
    print("Test dangerous cmd:", ge.authorize("terminal_run", "agent_moe", {"command": "sudo rm -rf /"}))
