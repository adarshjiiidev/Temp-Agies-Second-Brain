#!/usr/bin/env python3
"""
AEGIS Context Router
Orchestrates context assembly before any significant LLM invocation.
Detects user intent and selectively pulls from:
- Project state (Git, deps)
- Active Memory (Skills, Tasks)
- Linux Telemetry
- Research findings
Constructs the minimal necessary context to prevent prompt bloat.
"""

import sys
import json
import time
from pathlib import Path
from typing import Dict, Any, List

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from backend.config import cfg
from backend.logger import get_logger

log = get_logger("context_router")

class ContextRouter:
    def __init__(self):
        self.workspace = cfg.HOME
        
    def detect_intent(self, user_query: str) -> Dict[str, Any]:
        """
        Uses deterministic keyword routing combined with lightweight
        heuristics to classify intent and required context domains.
        """
        query_lower = user_query.lower()
        intent = {
            "primary_domain": "general",
            "needs_project_state": False,
            "needs_git_state": False,
            "needs_system_telemetry": False,
            "needs_camera_vision": False,
            "needs_research": False,
            "target_projects": []
        }
        
        # Project mapping heuristic
        for proj_name in cfg.PROJECTS.keys():
            if proj_name.lower() in query_lower:
                intent["target_projects"].append(proj_name)
                intent["needs_project_state"] = True
                intent["needs_git_state"] = True

        if any(k in query_lower for k in ["git", "commit", "branch", "pr", "diff"]):
            intent["needs_git_state"] = True
            intent["needs_project_state"] = True
            
        if any(k in query_lower for k in ["research", "search", "find out", "paper", "documentation"]):
            intent["needs_research"] = True
            
        if any(k in query_lower for k in ["camera", "vision", "motion", "detect", "surveillance", "see"]):
            intent["needs_camera_vision"] = True
            intent["primary_domain"] = "vision"
            
        if any(k in query_lower for k in ["system", "ram", "cpu", "port", "process", "linux", "systemctl"]):
            intent["needs_system_telemetry"] = True
            intent["primary_domain"] = "system"
            
        if any(k in query_lower for k in ["code", "build", "test", "cargo", "rust", "python", "debug"]):
            intent["primary_domain"] = "development"
            intent["needs_project_state"] = True

        return intent

    def assemble_context(self, user_query: str) -> Dict[str, Any]:
        """
        Builds the unified context payload based on detected intent.
        Returns the text block to inject into the LLM system prompt.
        """
        intent = self.detect_intent(user_query)
        context_blocks = []
        
        # 1. Project & Git State
        if intent["needs_project_state"] or intent["needs_git_state"]:
            try:
                from backend.project_intelligence import project_intelligence
                for proj in intent["target_projects"]:
                    p_info = project_intelligence.get_project_summary(proj)
                    if p_info:
                        context_blocks.append(f"### Project Context: {proj}\n" + json.dumps(p_info, indent=2))
            except ImportError:
                log.warning("Project Intelligence module not yet available.")
                
        # 2. System Telemetry
        if intent["needs_system_telemetry"]:
            try:
                from backend.server import get_pc_state
                state = get_pc_state()
                sys_info = state.get("system", {})
                mem_info = state.get("memory", {})
                cpu = sys_info.get("cpu_usage") or sys_info.get("cpu_percent") or sys_info.get("cpu", "N/A")
                ram = mem_info.get("use_percent") or mem_info.get("percent", "N/A")
                procs = len(state.get("processes", []))
                context_blocks.append(f"### Linux Host State\nCPU: {cpu} | RAM: {ram}% | Processes: {procs}")
            except Exception as e:
                log.debug("Telemetry context fetch skipped: %s", e)
                
        # 3. Vision State
        if intent["needs_camera_vision"]:
            try:
                from backend.camera_registry import camera_registry
                cams = camera_registry.get_authorized_cameras()
                context_blocks.append(f"### Vision & Camera Status\nAuthorized Cameras: {len(cams)}")
            except ImportError:
                pass
                
        # Assemble
        assembled_text = "\n\n".join(context_blocks) if context_blocks else "No specific dynamic context required."
        
        return {
            "intent": intent,
            "context_text": assembled_text
        }

context_router = ContextRouter()

if __name__ == "__main__":
    cr = ContextRouter()
    print("Testing Context Router intent detection:")
    res = cr.assemble_context("How is the aegis-dashboard project git branch doing?")
    print(json.dumps(res, indent=2))
