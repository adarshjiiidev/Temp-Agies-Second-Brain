#!/usr/bin/env python3
"""
AEGIS Org Camera Hub (P6.5 scaffolding — BLOCKED on credentials).
Credential-safe: never scans subnets, never stores/guesses passwords,
never logs or returns secret values. Vault file is created ONLY by
explicit user action, never with dummy passwords.
Reuses camera_registry semantics + vision_engine HARD_DENY defaults.
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.logger import get_logger

log = get_logger("org_cameras")

# Reused states (mirror backend/camera_registry.py + vision_engine.py).
DISCOVERED = "DISCOVERED"
AUTHORIZED = "AUTHORIZED"
VISION_ENABLED = "VISION_ENABLED"
HARD_DENY = "HARD_DENY"
AWAITING_CREDENTIALS = "AWAITING_CREDENTIALS"

VAULT_PATH = Path.home() / ".temporary-aegis" / "config" / "org_cameras.json"
ALLOWED_PROTOCOLS = {"rtsp", "http", "https", "onvif"}
_FORBIDDEN_KEYS = {"password", "pass", "passwd", "secret", "token", "credential", "credentials"}
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def _redact(value: Any) -> str:
    return "[REDACTED]" if value else "[ABSENT]"


def _env_name(cam_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9]", "_", cam_id).upper()
    return f"ORG_CAM_PASS_{safe}"


class OrgCameraHub:
    """Org-wide camera visibility hub. Explicit-host only, no subnet scanning."""

    def __init__(self, vault_path: Path = VAULT_PATH):
        self.vault_path = Path(vault_path)
        self.cameras: Dict[str, Dict[str, Any]] = {}

    # -- credentials (runtime only, never logged/returned) --
    def _vault_data(self) -> Dict[str, Any]:
        if not self.vault_path.exists():
            return {}
        try:
            data = json.loads(self.vault_path.read_text())
            return data.get("cameras", {}) if isinstance(data, dict) else {}
        except Exception as e:
            log.error(f"Org vault unreadable: {e}")
            return {}

    def _has_credential(self, cam_id: str) -> bool:
        if os.environ.get(_env_name(cam_id)):
            return True
        entry = self._vault_data().get(cam_id, {})
        return bool(isinstance(entry, dict) and entry.get("username") and entry.get("password"))

    def _password_for(self, cam_id: str) -> Optional[str]:
        pw = os.environ.get(_env_name(cam_id))
        if pw:
            return pw
        entry = self._vault_data().get(cam_id, {})
        if isinstance(entry, dict):
            val = entry.get("password")
            return val if isinstance(val, str) and val else None
        return None

    # -- public API --
    def status(self) -> Dict[str, Any]:
        """Safe to call/print: never includes secrets."""
        if not self.vault_path.exists():
            return {
                "state": AWAITING_CREDENTIALS,
                "privacy": HARD_DENY,
                "vault": str(self.vault_path),
                "vault_present": False,
                "cameras": [],
                "hint": "Vault absent. Provide targets + vault file to unblock.",
            }
        cams = [
            {
                "id": c["id"], "host": c["host"], "port": c["port"],
                "protocol": c["protocol"], "state": c["state"],
                "authorized": c["authorized"], "vision_enabled": c["vision_enabled"],
                "credential": "PRESENT" if self._has_credential(c["id"]) else "ABSENT",
            }
            for c in self.cameras.values()
        ]
        return {
            "state": "CONFIGURED" if cams else AWAITING_CREDENTIALS,
            "privacy": HARD_DENY,
            "vault": str(self.vault_path),
            "vault_present": True,
            "cameras": cams,
        }

    def configure(self, targets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Accept [{id,host,port,protocol}] WITHOUT passwords. No scanning, no vault creation."""
        if not isinstance(targets, list):
            raise ValueError("targets must be a list of {id,host,port,protocol}")
        staged: Dict[str, Dict[str, Any]] = {}
        for t in targets:
            if not isinstance(t, dict):
                raise ValueError("each target must be a dict")
            lower = {str(k).lower() for k in t.keys()}
            if lower & _FORBIDDEN_KEYS:
                log.error("configure rejected: password material not accepted in targets")
                raise ValueError("passwords never accepted via configure(); use vault/env only")
            cid, host, port, proto = t.get("id"), t.get("host"), t.get("port"), t.get("protocol")
            if not (cid and isinstance(cid, str) and _ID_RE.match(cid)):
                raise ValueError("each target needs id [A-Za-z0-9_-], max 64 chars")
            if not (host and isinstance(host, str)):
                raise ValueError(f"target {cid}: host required (explicit host only, no subnets)")
            if "/" in host or " " in host:
                raise ValueError(f"target {cid}: host must be a single host/IP, not a subnet/range")
            try:
                port = int(port)
                assert 1 <= port <= 65535
            except Exception:
                raise ValueError(f"target {cid}: port must be 1-65535")
            if str(proto).lower() not in ALLOWED_PROTOCOLS:
                raise ValueError(f"target {cid}: protocol must be one of {sorted(ALLOWED_PROTOCOLS)}")
            staged[cid] = {
                "id": cid, "host": host, "port": port, "protocol": str(proto).lower(),
                "state": DISCOVERED, "authorized": False, "vision_enabled": False,
            }
        self.cameras = staged
        log.info(f"Org targets staged: {sorted(staged)} (DISCOVERED, unauthorized, no scan performed)")
        return self.status()

    def authorize(self, cam_id: str) -> bool:
        """Mirror camera_registry.authorize_camera: requires runtime credential, else deny."""
        cam = self.cameras.get(cam_id)
        if not cam:
            log.warning(f"Authorize denied: unknown camera id={cam_id}")
            return False
        if not self._has_credential(cam_id):
            log.warning(f"Authorize denied for id={cam_id}: credential ABSENT")
            return False
        cam["authorized"] = True
        cam["state"] = AUTHORIZED
        log.warning(f"Org camera id={cam_id} explicitly AUTHORIZED.")
        return True

    def enable_vision(self, cam_id: str) -> bool:
        """Mirror camera_registry.enable_vision: authorized only."""
        cam = self.cameras.get(cam_id)
        if not cam or not cam.get("authorized"):
            log.warning(f"Vision enable denied for id={cam_id}: requires AUTHORIZED first")
            return False
        if not self._has_credential(cam_id):
            log.warning(f"Vision enable denied for id={cam_id}: credential ABSENT")
            return False
        cam["vision_enabled"] = True
        cam["state"] = VISION_ENABLED
        return True

    def snapshot(self, cam_id: str) -> Tuple[Optional[bytes], Optional[str]]:
        """Allowed only for AUTHORIZED + vision-enabled cameras. Never exposes credentials."""
        cam = self.cameras.get(cam_id)
        if not cam or not (cam.get("authorized") and cam.get("vision_enabled")):
            return None, f"HARD_DENY: camera id={cam_id} not AUTHORIZED+VISION_ENABLED"
        pw = self._password_for(cam_id)
        if not pw:
            return None, f"HARD_DENY: camera id={cam_id} credential ABSENT at runtime"
        # Real capture happens via vision_engine with runtime-only credential; no URL logged.
        log.info(f"Snapshot requested for authorized camera id={cam_id} (credential held in memory only)")
        return None, "NOT_CONNECTED: credentials pending — stub returns HARD_DENY-safe denial until vault provided"

    def install_vault_entry(self, cam_id: str, username: str, password: str) -> Path:
        """Explicit user-triggered vault write only. Refuses dummy/placeholder values."""
        if cam_id not in self.cameras:
            raise ValueError(f"unknown camera id={cam_id}; call configure() first")
        if not username or not password:
            raise ValueError("username and password must both be non-empty")
        if password.strip().lower() in {"dummy", "password", "changeme", "test", "123456", "placeholder"}:
            raise ValueError("refusing dummy/placeholder password")
        self.vault_path.parent.mkdir(parents=True, exist_ok=True)
        data: Dict[str, Any] = {"cameras": {}}
        if self.vault_path.exists():
            try:
                raw = json.loads(self.vault_path.read_text())
                if isinstance(raw, dict) and isinstance(raw.get("cameras"), dict):
                    data = raw
            except Exception:
                pass
        data["cameras"][cam_id] = {"username": username, "password": password}
        text = json.dumps(data, indent=2)
        tmp = self.vault_path.with_suffix(".tmp")
        tmp.write_text(text)
        os.chmod(tmp, 0o600)
        tmp.replace(self.vault_path)
        os.chmod(self.vault_path, 0o600)
        log.info(f"Vault entry stored for id={cam_id} (mode 0600, value {_redact('x')})")
        return self.vault_path


hub = OrgCameraHub()

if __name__ == "__main__":
    print(json.dumps(hub.status(), indent=2))
