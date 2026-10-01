#!/usr/bin/env python3
"""
AEGIS Camera Registry
Manages discovered vs. authorized camera states. 
Enforces that discovery != streaming permission.
"""

import os
import sys
import json
import uuid
import subprocess
import re
import socket
from pathlib import Path
from typing import Dict, Any, List

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from backend.config import cfg
from backend.logger import get_logger

log = get_logger("camera_registry")

class CameraRegistry:
    def __init__(self):
        self.registry_file = cfg.HOME / ".temporary-aegis" / "config" / "cameras.json"
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        self.cameras: Dict[str, Dict] = {}
        self._load()

    def _load(self):
        if self.registry_file.exists():
            try:
                self.cameras = json.loads(self.registry_file.read_text())
            except Exception as e:
                log.error(f"Failed to load camera registry: {e}")

    def _save(self):
        self.registry_file.write_text(json.dumps(self.cameras, indent=2))

    def register_discovered(self, name: str, uri: str, device_type: str = "network") -> str:
        """Registers a camera but sets it to UNAUTHORIZED and NO_VISION."""
        # Find if it already exists by URI
        for cid, cam in self.cameras.items():
            if cam.get("uri") == uri:
                return cid
                
        cam_id = f"cam-{str(uuid.uuid4())[:8]}"
        self.cameras[cam_id] = {
            "name": name,
            "uri": uri,
            "type": device_type,
            "authorized": False,
            "vision_enabled": False,
            "recording_enabled": False,
            "privacy_zones": []
        }
        self._save()
        log.info(f"Discovered new camera '{name}', awaiting authorization.")
        return cam_id

    def discover_cameras(self) -> List[Dict]:
        """Perform local and network discovery for cameras."""
        log.info("Starting camera discovery...")
        discovered = []

        # 1. Local Cameras (v4l2)
        try:
            res = subprocess.run("v4l2-ctl --list-devices", shell=True, capture_output=True, text=True)
            if res.returncode == 0:
                current_device = "Local USB/PCI Camera"
                for line in res.stdout.splitlines():
                    line = line.strip()
                    if line.endswith(":"):
                        current_device = line[:-1]
                    elif line.startswith("/dev/video"):
                        cid = self.register_discovered(current_device, line, "local")
                        discovered.append(self.cameras[cid])
        except Exception as e:
            log.warning(f"Local camera discovery failed: {e}")

        # 2. Network Cameras (nmap for RTSP port 554)
        try:
            # Find default subnet
            route_res = subprocess.run("ip route | grep default", shell=True, capture_output=True, text=True)
            if route_res.returncode == 0 and route_res.stdout:
                iface = route_res.stdout.split()[4]
                ip_res = subprocess.run(f"ip addr show {iface} | grep 'inet '", shell=True, capture_output=True, text=True)
                if ip_res.returncode == 0 and ip_res.stdout:
                    subnet = ip_res.stdout.split()[1] # e.g., 192.168.1.5/24
                    # Quick SYN scan for port 554 (RTSP) and 80 (HTTP) on the local subnet
                    nmap_res = subprocess.run(f"nmap -p 554 --open -T4 {subnet}", shell=True, capture_output=True, text=True)
                    if nmap_res.returncode == 0:
                        current_ip = None
                        for line in nmap_res.stdout.splitlines():
                            if line.startswith("Nmap scan report for"):
                                current_ip = line.split()[-1].strip("()")
                            elif "554/tcp" in line and "open" in line and current_ip:
                                cid = self.register_discovered(f"Network Camera ({current_ip})", f"rtsp://{current_ip}:554/stream", "network")
                                discovered.append(self.cameras[cid])
        except Exception as e:
            log.warning(f"Network camera discovery failed: {e}")

        return discovered

    def authorize_camera(self, cam_id: str) -> bool:
        if cam_id in self.cameras:
            self.cameras[cam_id]["authorized"] = True
            self._save()
            log.warning(f"Camera {cam_id} explicitly AUTHORIZED.")
            return True
        return False

    def enable_vision(self, cam_id: str) -> bool:
        if cam_id in self.cameras and self.cameras[cam_id].get("authorized"):
            self.cameras[cam_id]["vision_enabled"] = True
            self._save()
            return True
        return False

    def get_authorized_cameras(self) -> List[Dict]:
        return [c for c in self.cameras.values() if c.get("authorized")]

    def get_vision_cameras(self) -> List[Dict]:
        return [c for c in self.cameras.values() if c.get("vision_enabled") and c.get("authorized")]

camera_registry = CameraRegistry()

if __name__ == "__main__":
    cr = CameraRegistry()
    cid = cr.register_discovered("Entrance", "rtsp://192.168.1.100/stream")
    print(f"Registered: {cid}")
    cr.authorize_camera(cid)
    cr.enable_vision(cid)
    print("Authorized Cameras:", json.dumps(cr.get_authorized_cameras(), indent=2))
