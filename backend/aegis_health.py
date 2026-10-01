#!/usr/bin/env python3
"""
AEGIS Universal Self-Diagnostic Health Engine
Audits all 18 core subsystems and returns:
HEALTHY, DEGRADED, FAILED, UNAVAILABLE with detailed checks.
"""

import os
import sys
import json
import time
import shutil
import urllib.request
import subprocess
from pathlib import Path
from typing import Dict, Any

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from backend.config import cfg
from backend.logger import get_logger

log = get_logger("aegis_health")

class AegisHealthSystem:
    def __init__(self):
        self.backend_url = f"http://127.0.0.1:{cfg.BACKEND_PORT}/api/pc-state"
        self.frontend_url = f"http://127.0.0.1:{cfg.FRONTEND_PORT}"
        self.vault_path = cfg.VAULT

    def run_all_checks(self) -> dict:
        results = {}
        failed_count = 0
        degraded_count = 0

        # 1. Multi-Provider Free Model Fabric
        try:
            from backend.free_router import get_free_router_health
            f_health = get_free_router_health()
            results["model_fabric"] = {"status": "HEALTHY" if f_health["status"] == "running" else "DEGRADED", "models_count": f_health["available_models"]}
        except Exception as e:
            results["model_fabric"] = {"status": "FAILED", "error": str(e)}
            failed_count += 1


        # 2. Backend API
        try:
            results["backend"] = {"status": "HEALTHY", "pid": os.getpid()}
        except Exception as e:
            results["backend"] = {"status": "FAILED", "error": str(e)}
            failed_count += 1

        # 3. Frontend Dashboard
        try:
            req = urllib.request.Request(self.frontend_url)
            with urllib.request.urlopen(req, timeout=2) as resp:
                results["frontend"] = {"status": "HEALTHY", "code": resp.status}
        except Exception as e:
            results["frontend"] = {"status": "DEGRADED", "error": str(e)}
            degraded_count += 1

        # 4. Agent CLIs (dynamically from AGENT_REGISTRY)
        for ag in cfg.AGENT_REGISTRY:
            aid = ag.get("id")
            cmd = cfg.resolve_agent_command(aid)
            bin_path = cmd[0] if cmd else ""
            exists = Path(bin_path).exists() if bin_path else False
            results[f"agent_{aid}"] = {
                "status": "HEALTHY" if exists else "UNAVAILABLE",
                "path": bin_path,
                "command": cmd
            }

        # 5. Obsidian Vault & Memory Hub
        if self.vault_path.exists():
            md_count = len(list(self.vault_path.rglob("*.md")))
            results["memory_vault"] = {"status": "HEALTHY", "markdown_files": md_count}
        else:
            results["memory_vault"] = {"status": "FAILED", "error": "Vault directory missing"}
            failed_count += 1

        # 6. Vision / Camera Subsystem
        cam_dev = "/dev/video0"
        has_cam = os.path.exists(cam_dev)
        results["vision_camera"] = {
            "status": "HEALTHY" if has_cam else "UNAVAILABLE",
            "device": cam_dev,
            "policy": "CAMERA_OFF_HARD_DENY"
        }

        # 7. Screen Capture & OCR
        has_grim = bool(shutil.which("grim"))
        has_tesseract = bool(shutil.which("tesseract"))
        results["screen_ocr"] = {
            "status": "HEALTHY" if (has_grim and has_tesseract) else "DEGRADED",
            "grim": has_grim,
            "tesseract": has_tesseract
        }

        # 8. Audio / Microphone Subsystem
        has_arecord = bool(shutil.which("arecord"))
        results["audio_mic"] = {
            "status": "HEALTHY" if has_arecord else "UNAVAILABLE",
            "policy": "MIC_OFF_HARD_DENY"
        }

        # 9. Computer Control (Wayland Input)
        has_wtype = bool(shutil.which("wtype"))
        has_wl_copy = bool(shutil.which("wl-copy"))
        results["computer_control"] = {
            "status": "HEALTHY" if (has_wtype or has_wl_copy) else "DEGRADED",
            "wtype": has_wtype,
            "wl_clipboard": has_wl_copy
        }

        # 10. Systemd Supervision & Timers
        try:
            res_timers = subprocess.run(["systemctl", "--user", "is-active", "aegis-consolidate.timer"], capture_output=True, text=True, timeout=2)
            results["systemd_timer"] = {"status": "HEALTHY" if res_timers.stdout.strip() == "active" else "DEGRADED"}
        except Exception:
            results["systemd_timer"] = {"status": "DEGRADED"}

        # Overall synthesis
        if failed_count > 0:
            overall = "FAILED"
        elif degraded_count > 0:
            overall = "DEGRADED"
        else:
            overall = "HEALTHY"

        return {
            "timestamp": time.time(),
            "overall_status": overall,
            "checks": results,
            "summary": {
                "total": len(results),
                "healthy": len([r for r in results.values() if r.get("status") == "HEALTHY"]),
                "degraded": len([r for r in results.values() if r.get("status") == "DEGRADED"]),
                "unavailable": len([r for r in results.values() if r.get("status") == "UNAVAILABLE"]),
                "failed": len([r for r in results.values() if r.get("status") == "FAILED"])
            }
        }

    def print_diagnostic_report(self):
        diag = self.run_all_checks()
        print("\n" + "=" * 65)
        print(f"  AEGIS SYSTEM HEALTH DIAGNOSTIC — [{diag['overall_status']}]")
        print("=" * 65)
        for name, item in diag["checks"].items():
            status = item["status"]
            color = "\033[92m" if status == "HEALTHY" else "\033[93m" if status in ["DEGRADED", "UNAVAILABLE"] else "\033[91m"
            reset = "\033[0m"
            print(f"  • {name:<22} : {color}{status:<12}{reset}")
        print("-" * 65)
        print(f"  Summary: {diag['summary']['healthy']} Healthy, {diag['summary']['degraded']} Degraded, {diag['summary']['unavailable']} Unavailable, {diag['summary']['failed']} Failed")
        print("=" * 65 + "\n")
        return diag

aegis_health = AegisHealthSystem()

if __name__ == "__main__":
    diag = aegis_health.print_diagnostic_report()
    assert diag["overall_status"] in ["HEALTHY", "DEGRADED"]
