#!/usr/bin/env python3
"""
AEGIS Camera Event Store
Structured storage for vision events like MOTION_DETECTED.
Does not store continuous video frames, only event metadata and references.
"""

import json
from pathlib import Path
from typing import Dict, Any, List

from backend.config import cfg
from backend.logger import get_logger

log = get_logger("camera_event_store")

class CameraEventStore:
    def __init__(self):
        self.store_file = cfg.HOME / ".temporary-aegis" / "config" / "vision_events.json"
        self.store_file.parent.mkdir(parents=True, exist_ok=True)
        self.events: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        if self.store_file.exists():
            try:
                self.events = json.loads(self.store_file.read_text())
            except Exception as e:
                log.error(f"Failed to load camera events: {e}")

    def _save(self):
        self.store_file.write_text(json.dumps(self.events, indent=2))

    def store_event(self, event: Dict[str, Any]) -> bool:
        if not event or "event_id" not in event:
            return False
        self.events.append(event)
        # Keep only the last 1000 events to prevent unbounded growth
        if len(self.events) > 1000:
            self.events = self.events[-1000:]
        self._save()
        log.info(f"Stored vision event: {event.get('type')} from {event.get('camera_id')}")
        return True

    def get_recent_events(self, camera_id: str = None, limit: int = 10) -> List[Dict]:
        if camera_id:
            filtered = [e for e in self.events if e.get("camera_id") == camera_id]
        else:
            filtered = self.events
            
        # Sort by timestamp descending
        filtered.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        return filtered[:limit]

camera_event_store = CameraEventStore()
