#!/usr/bin/env python3
"""
AEGIS Linux Intelligence Engine
Read-only host telemetry and capability discovery.
Parses systemd, active ports, hardware sensors, and package states.
"""

import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, List

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from backend.logger import get_logger

log = get_logger("linux_intel")

class LinuxIntelligence:
    def get_system_services(self) -> List[Dict[str, str]]:
        """List user-level systemd services."""
        try:
            res = subprocess.run("systemctl --user list-units --type=service --state=running --no-pager --no-legend", shell=True, capture_output=True, text=True)
            services = []
            for line in res.stdout.splitlines():
                parts = line.split()
                if len(parts) > 4:
                    services.append({
                        "unit": parts[0],
                        "status": parts[3],
                        "description": " ".join(parts[4:])
                    })
            return services
        except Exception as e:
            log.error(f"Failed to fetch system services: {e}")
            return []

    def get_available_tooling(self) -> Dict[str, bool]:
        """Detect which critical CLI tools are available."""
        tools = ["git", "cargo", "python3", "uv", "node", "npm", "docker", "docker-compose", "jq", "curl", "tesseract"]
        available = {}
        for t in tools:
            res = subprocess.run(f"which {t}", shell=True, capture_output=True)
            available[t] = res.returncode == 0
        return available
        
    def get_system_metrics(self) -> Dict[str, str]:
        """Fetch basic host telemetry: load average, memory, disk space."""
        try:
            mem = subprocess.run("free -m | grep Mem", shell=True, capture_output=True, text=True).stdout.split()
            mem_usage = f"{mem[2]}MB / {mem[1]}MB" if len(mem) >= 3 else "Unknown"
            
            disk = subprocess.run("df -h / | tail -n 1", shell=True, capture_output=True, text=True).stdout.split()
            disk_usage = f"{disk[2]} / {disk[1]} ({disk[4]})" if len(disk) >= 5 else "Unknown"
            
            with open("/proc/loadavg", "r") as f:
                load = f.read().split()[:3]
                load_avg = " ".join(load)
        except Exception as e:
            log.error(f"Failed to fetch system metrics: {e}")
            mem_usage, disk_usage, load_avg = "Error", "Error", "Error"
            
        return {
            "load_average": load_avg,
            "memory_usage": mem_usage,
            "disk_usage": disk_usage
        }

    def get_host_overview(self) -> Dict[str, Any]:
        """Combine tooling, services, kernel info, and telemetry."""
        try:
            uname = subprocess.run("uname -a", shell=True, capture_output=True, text=True).stdout.strip()
        except:
            uname = "Unknown"
            
        return {
            "kernel": uname,
            "metrics": self.get_system_metrics(),
            "services": self.get_system_services(),
            "tools": self.get_available_tooling()
        }

linux_intelligence = LinuxIntelligence()

if __name__ == "__main__":
    li = LinuxIntelligence()
    print("Testing Linux Intelligence...")
    print(json.dumps(li.get_host_overview(), indent=2))
