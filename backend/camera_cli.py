#!/usr/bin/env python3
"""
AEGIS Camera CLI Integration
Usage:
  python3 backend/camera_cli.py discover
  python3 backend/camera_cli.py list
  python3 backend/camera_cli.py authorize <cam_id>
  python3 backend/camera_cli.py vision <cam_id> <enable|disable>
  python3 backend/camera_cli.py events [cam_id]
"""

import sys
import json
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from backend.camera_registry import camera_registry
from backend.vision_engine import vision_engine
from backend.camera_event_store import camera_event_store

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
        
    cmd = sys.argv[1].lower()
    
    if cmd == "discover":
        print("Discovering cameras...")
        discovered = camera_registry.discover_cameras()
        print(json.dumps(discovered, indent=2))
        
    elif cmd == "list":
        print(json.dumps(camera_registry.cameras, indent=2))
        
    elif cmd == "authorize":
        if len(sys.argv) < 3:
            print("Missing camera ID")
            sys.exit(1)
        res = camera_registry.authorize_camera(sys.argv[2])
        print(f"Authorized: {res}")
        
    elif cmd == "vision":
        if len(sys.argv) < 4:
            print("Usage: vision <cam_id> <enable|disable>")
            sys.exit(1)
        cam_id = sys.argv[2]
        action = sys.argv[3].lower()
        if action == "enable":
            res = camera_registry.enable_vision(cam_id)
            print(f"Vision Enabled: {res}")
        else:
            # Add disable logic to registry if it doesn't exist, here we just flip the bit manually for the CLI
            if cam_id in camera_registry.cameras:
                camera_registry.cameras[cam_id]["vision_enabled"] = False
                camera_registry._save()
                print("Vision Disabled: True")
            else:
                print("Vision Disabled: False")
                
    elif cmd == "events":
        cam_id = sys.argv[2] if len(sys.argv) > 2 else None
        events = camera_event_store.get_recent_events(cam_id)
        print(json.dumps(events, indent=2))
        
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)

if __name__ == "__main__":
    main()
