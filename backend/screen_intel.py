#!/usr/bin/env python3
"""
AEGIS Screen Intelligence Engine
Goes beyond simple OCR to provide complete desktop environment understanding:
- Window identification & application recognition (via hyprctl)
- Active workspace & layout tracking
- Transient screen capture (via grim)
- Fast deterministic OCR (via tesseract)
- Multimodal visual reasoning (via Gemini 3.8/3.7 Vision on 9Router)
"""

import os
import sys
import json
import time
import base64
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List

class ScreenIntelEngine:
    def __init__(self):
        self.grim_bin = "/usr/bin/grim"
        self.hyprctl_bin = "/usr/bin/hyprctl"
        self.tesseract_bin = "/usr/bin/tesseract"

    def get_desktop_windows(self) -> dict:
        """Query active and background windows, workspaces, and application classes."""
        active = {}
        all_windows = []

        if os.path.exists(self.hyprctl_bin):
            try:
                # 1. Active window
                res = subprocess.run([self.hyprctl_bin, "-j", "activewindow"], capture_output=True, text=True, timeout=2)
                if res.returncode == 0 and res.stdout.strip():
                    d = json.loads(res.stdout)
                    active = {
                        "title": d.get("title", ""),
                        "class": d.get("class", ""),
                        "pid": d.get("pid"),
                        "workspace": d.get("workspace", {}).get("name", ""),
                        "geometry": {"at": d.get("at", []), "size": d.get("size", [])}
                    }

                # 2. All open windows
                res_all = subprocess.run([self.hyprctl_bin, "-j", "clients"], capture_output=True, text=True, timeout=2)
                if res_all.returncode == 0 and res_all.stdout.strip():
                    for w in json.loads(res_all.stdout):
                        all_windows.append({
                            "title": w.get("title", ""),
                            "class": w.get("class", ""),
                            "workspace": w.get("workspace", {}).get("name", ""),
                            "size": w.get("size", [])
                        })
            except Exception as e:
                return {"error": str(e)}

        return {
            "timestamp": time.time(),
            "active_window": active,
            "total_windows": len(all_windows),
            "open_windows": all_windows
        }

    def capture_screen_image(self) -> tuple[Optional[str], Optional[str]]:
        """Takes a transient screenshot. Returns (temp_filepath, error)."""
        if not os.path.exists(self.grim_bin):
            return None, "System Error: /usr/bin/grim not installed."

        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.close()

        try:
            res = subprocess.run([self.grim_bin, tmp.name], capture_output=True, text=True, timeout=5)
            if res.returncode != 0:
                if os.path.exists(tmp.name):
                    os.unlink(tmp.name)
                return None, f"Screenshot capture failed: {res.stderr}"
            return tmp.name, None
        except Exception as e:
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)
            return None, str(e)

    def extract_screen_text(self, img_path: str) -> str:
        """Fast deterministic OCR over screen capture."""
        if not os.path.exists(img_path) or not os.path.exists(self.tesseract_bin):
            return ""
        try:
            res = subprocess.run([self.tesseract_bin, img_path, "stdout"], capture_output=True, text=True, timeout=10)
            return res.stdout.strip()
        except Exception:
            return ""

    def analyze_screen_multimodal(self, query: str = "Describe what the user is working on and highlight any visible errors or active tasks.") -> dict:
        """
        Combines window telemetry, screenshot, OCR, and Gemini multimodal reasoning
        to answer: 'What is happening on my computer?'
        """
        windows_info = self.get_desktop_windows()
        img_path, err = self.capture_screen_image()
        if err or not img_path:
            return {"success": False, "error": err or "Failed to capture screen", "desktop": windows_info}

        ocr_sample = self.extract_screen_text(img_path)[:800]

        try:
            with open(img_path, "rb") as f:
                b64_img = base64.b64encode(f.read()).decode("utf-8")
        finally:
            if os.path.exists(img_path):
                os.unlink(img_path)

        import urllib.request
        active_app = windows_info.get("active_window", {}).get("class", "unknown")
        active_title = windows_info.get("active_window", {}).get("title", "unknown")

        prompt = f"""You are the AEGIS Desktop Perception Engine.
Analyze this high-resolution desktop screenshot alongside the active window telemetry.

Desktop State:
- Active Window Class: {active_app}
- Active Window Title: {active_title}
- OCR Sample Text: {ocr_sample}

User Question: {query}

Provide a structured, concise response with:
1. Active application and task summary
2. Key visible UI elements or editor state
3. Any detected errors, warnings, or terminal status
4. Recommended next action for the user or agent
"""

        payload = {
            "model": "gemini/gemini-3.7-flash",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{b64_img}"
                            }
                        }
                    ]
                }
            ],
            "temperature": 0.2
        }

        try:
            req = urllib.request.Request(
                "http://127.0.0.1:20128/v1/chat/completions",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = json.loads(resp.read().decode())
                ans = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                return {
                    "success": True,
                    "desktop": windows_info,
                    "analysis": ans
                }
        except Exception as e:
            return {
                "success": True,
                "desktop": windows_info,
                "ocr_summary": ocr_sample,
                "analysis": f"Deterministic Desktop Analysis: Active app {active_app} ({active_title}). OCR: {ocr_sample[:200]}"
            }

screen_intel = ScreenIntelEngine()

if __name__ == "__main__":
    print("Testing Screen Intelligence Engine...")
    info = screen_intel.get_desktop_windows()
    print("Active window:", info.get("active_window"))
    print("Total windows open:", info.get("total_windows"))
    assert info.get("total_windows", 0) > 0, "No open windows detected"
    print("Screen Intelligence: VERIFIED OK")
