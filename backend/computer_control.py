#!/usr/bin/env python3
"""
AEGIS Computer Control Subsystem
Integrates keyboard typing, clipboard, and desktop automation on Wayland/Linux.
Enforces permission-gating on high-impact actions.
"""

import os
import sys
import json
import time
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from backend.browser_tool import browser_tool
from backend.logger import get_logger

log = get_logger("computer_control")

class ComputerControl:
    def __init__(self):
        self.wtype_bin = shutil.which("wtype") or "/usr/bin/wtype"
        self.wl_copy_bin = shutil.which("wl-copy") or "/usr/bin/wl-copy"
        self.wl_paste_bin = shutil.which("wl-paste") or "/usr/bin/wl-paste"
        self.control_enabled = True
        self.browser = browser_tool

    def type_text(self, text: str) -> dict:
        """Type text into active focused window using wtype."""
        if not self.control_enabled:
            return {"success": False, "error": "Computer control disabled by policy."}

        env = {**os.environ, "WAYLAND_DISPLAY": os.environ.get("WAYLAND_DISPLAY", "wayland-1")}
        try:
            res = subprocess.run([self.wtype_bin, text], capture_output=True, text=True, timeout=5, env=env)
            return {
                "success": res.returncode == 0,
                "typed_characters": len(text),
                "error": res.stderr if res.returncode != 0 else None
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def press_key(self, key_name: str) -> dict:
        """Press special key (e.g. Return, BackSpace, Tab, Escape, Left, Right)."""
        if not self.control_enabled:
            return {"success": False, "error": "Computer control disabled by policy."}

        key_map = {
            "enter": "-k Return",
            "return": "-k Return",
            "tab": "-k Tab",
            "escape": "-k Escape",
            "backspace": "-k BackSpace",
            "up": "-k Up",
            "down": "-k Down",
            "left": "-k Left",
            "right": "-k Right"
        }
        arg = key_map.get(key_name.lower())
        if not arg:
            return {"success": False, "error": f"Unknown key: {key_name}"}

        env = {**os.environ, "WAYLAND_DISPLAY": os.environ.get("WAYLAND_DISPLAY", "wayland-1")}
        try:
            cmd = [self.wtype_bin] + arg.split()
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5, env=env)
            return {"success": res.returncode == 0, "key": key_name, "error": res.stderr if res.returncode != 0 else None}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_clipboard(self) -> str:
        """Read system clipboard using wl-paste."""
        env = {**os.environ, "WAYLAND_DISPLAY": os.environ.get("WAYLAND_DISPLAY", "wayland-1")}
        try:
            res = subprocess.run([self.wl_paste_bin], capture_output=True, text=True, timeout=3, env=env)
            return res.stdout if res.returncode == 0 else ""
        except Exception:
            return ""

    def set_clipboard(self, content: str) -> bool:
        """Write content to system clipboard using wl-copy."""
        env = {**os.environ, "WAYLAND_DISPLAY": os.environ.get("WAYLAND_DISPLAY", "wayland-1")}
        try:
            p = subprocess.Popen([self.wl_copy_bin], stdin=subprocess.PIPE, env=env)
            p.communicate(input=content.encode("utf-8"), timeout=3)
            return p.returncode == 0
        except Exception:
            return False

    def launch_application(self, app_command: list[str], risk_level: str = "medium") -> dict:
        """
        Launch desktop application with risk policy check.
        """
        if risk_level in ["high", "critical"]:
            return {"success": False, "error": f"High risk execution requires manual user confirmation for: {app_command}"}

        try:
            proc = subprocess.Popen(app_command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            return {"success": True, "pid": proc.pid, "command": app_command}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def browse_url(self, url: str) -> dict:
        """Fetch webpage DOM and extract structured markdown text."""
        return self.browser.extract_content(url)

    def browse_screenshot(self, url: str, output_path: Optional[str] = None) -> dict:
        """Capture screenshot of a webpage."""
        return self.browser.capture_screenshot(url, output_path=output_path)

computer_control = ComputerControl()

if __name__ == "__main__":
    print("Testing Computer Control Subsystem...")
    test_str = "AEGIS_CONTROL_TEST"
    ok = computer_control.set_clipboard(test_str)
    read_back = computer_control.get_clipboard().strip()
    print("Clipboard write status:", ok)
    print("Clipboard read back:", read_back)
    assert read_back == test_str, "Clipboard verification failed"
    print("Computer Control Subsystem: VERIFIED OK")
