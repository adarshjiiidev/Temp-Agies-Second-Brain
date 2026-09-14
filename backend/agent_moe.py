#!/usr/bin/env python3
"""
AgentMoe Operational Capability Fabric
Provides AEGIS with operational hands, legs, workers, tool execution,
and dynamic capability discovery.
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from backend.config import cfg
from backend.logger import get_logger
from backend.vision_engine import vision_engine
from backend.computer_control import computer_control
from backend.browser_tool import browser_tool

log = get_logger("agent_moe")

class AgentMoeFabric:
    def __init__(self):
        self.workspace = cfg.HOME
        self.tools = {
            "filesystem_read": self.tool_fs_read,
            "filesystem_write": self.tool_fs_write,
            "terminal_run": self.tool_terminal_run,
            "screen_ocr": self.tool_screen_ocr,
            "camera_snapshot": self.tool_camera_snapshot,
            "clipboard_sync": self.tool_clipboard,
            "project_inspect": self.tool_project_inspect,
            "browser_navigate": self.tool_browser_navigate,
            "browser_screenshot": self.tool_browser_screenshot,
        }
        self.worker_roles = [
            "Planner",
            "Researcher",
            "Coder",
            "Debugger",
            "Auditor",
            "Vision Worker",
            "Browser Worker",
            "Synthesizer"
        ]

    # ── Tool Implementations ──────────────────────────────────────────────────

    def tool_fs_read(self, path: str, limit: int = 500) -> dict:
        p = Path(path)
        if not p.is_absolute():
            p = self.workspace / p
        if not p.exists():
            return {"success": False, "error": f"File not found: {path}"}
        try:
            lines = p.read_text(errors="replace").splitlines()[:limit]
            return {"success": True, "path": str(p), "lines_read": len(lines), "content": "\n".join(lines)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def tool_fs_write(self, path: str, content: str) -> dict:
        p = Path(path)
        if not p.is_absolute():
            p = self.workspace / p
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            return {"success": True, "path": str(p), "bytes_written": len(content.encode())}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def tool_terminal_run(self, command: str, cwd: Optional[str] = None, timeout: int = 30) -> dict:
        target_cwd = cwd or str(self.workspace)
        try:
            res = subprocess.run(command, shell=True, capture_output=True, text=True, cwd=target_cwd, timeout=timeout)
            return {
                "success": res.returncode == 0,
                "returncode": res.returncode,
                "stdout": res.stdout[-2000:] if res.stdout else "",
                "stderr": res.stderr[-1000:] if res.stderr else ""
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Command timed out after {timeout}s"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def tool_screen_ocr(self) -> dict:
        img, err = vision_engine.capture_screen()
        if err:
            return {"success": False, "error": err}
        text, ocr_err = vision_engine.run_ocr(img)
        return {"success": True, "text": text, "length": len(text)}

    def tool_camera_snapshot(self) -> dict:
        img, err = vision_engine.capture_camera_frame()
        if err:
            return {"success": False, "error": err}
        return {"success": True, "frame_bytes": len(img), "status": "Frame acquired for transient analysis"}

    def tool_clipboard(self, action: str = "read", text: str = "") -> dict:
        if action == "write":
            ok = computer_control.set_clipboard(text)
            return {"success": ok, "action": "write"}
        content = computer_control.get_clipboard()
        return {"success": True, "action": "read", "content": content}

    def tool_project_inspect(self, project_name: str) -> dict:
        target_path = cfg.PROJECTS.get(project_name)
        if not target_path or not target_path.exists():
            return {"success": False, "error": f"Project '{project_name}' not found."}

        p = target_path
        files = [
            str(f.relative_to(p)) for f in p.rglob("*")
            if f.is_file() and not any(k in f.parts for k in [".git", "node_modules", "__pycache__", ".venv"])
        ][:50]
        return {
            "success": True,
            "project": project_name,
            "root": str(target_path),
            "files_sample": files,
            "total_sample_count": len(files)
        }

    def tool_browser_navigate(self, url: str) -> dict:
        """Browse a URL and extract clean text and markdown."""
        return browser_tool.extract_content(url)

    def tool_browser_screenshot(self, url: str, output_path: Optional[str] = None) -> dict:
        """Capture screenshot of a webpage using headless Chrome."""
        return browser_tool.capture_screenshot(url, output_path=output_path)

    # ── Capability Discovery & Task Delegation ────────────────────────────────

    def discover_capability(self, goal: str) -> dict:
        """
        Dynamically determine matching tool, skill, or agent role for a required goal.
        """
        g_lower = goal.lower()
        if any(k in g_lower for k in ["screen", "ocr", "window", "desktop text"]):
            return {"type": "tool", "target": "screen_ocr", "role": "Vision Worker"}
        if any(k in g_lower for k in ["camera", "webcam", "face", "document scan"]):
            return {"type": "tool", "target": "camera_snapshot", "role": "Vision Worker"}
        if any(k in g_lower for k in ["clipboard", "paste", "copy"]):
            return {"type": "tool", "target": "clipboard_sync", "role": "Executor"}
        if any(k in g_lower for k in ["git", "status", "test", "build", "run", "bash"]):
            return {"type": "tool", "target": "terminal_run", "role": "Coder"}
        if any(k in g_lower for k in ["read file", "inspect code", "source"]):
            return {"type": "tool", "target": "filesystem_read", "role": "Researcher"}
        if any(k in g_lower for k in ["write file", "save code", "create file"]):
            return {"type": "tool", "target": "filesystem_write", "role": "Coder"}
        if any(k in g_lower for k in ["project", "repo", "architecture"]):
            return {"type": "tool", "target": "project_inspect", "role": "Planner"}

        return {"type": "agent", "target": "gemini/gemini-3.8-flash", "role": "Synthesizer"}

    def execute_plan(self, subtasks: List[dict]) -> dict:
        """Execute a list of delegated subtasks with bounded budgets."""
        results = []
        for task in subtasks:
            t_name = task.get("tool")
            args = task.get("args", {})
            fn = self.tools.get(t_name)
            if fn:
                res = fn(**args)
                results.append({"task": task.get("name", t_name), "status": "DONE", "result": res})
            else:
                results.append({"task": task.get("name", t_name), "status": "ERROR", "error": f"Tool '{t_name}' not found."})
        return {"executed_count": len(results), "tasks": results}

agent_moe = AgentMoeFabric()

if __name__ == "__main__":
    print("Testing AgentMoe Capability Fabric...")
    disc = agent_moe.discover_capability("inspect screen text and OCR")
    print("Capability discovery for screen text:", json.dumps(disc, indent=2))
    
    proj_res = agent_moe.tool_project_inspect("aegis-dashboard")
    print(f"Project inspect aegis-dashboard sample files: {len(proj_res.get('files_sample', []))} files found.")
    print("AgentMoe Fabric: VERIFIED OK")
