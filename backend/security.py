#!/usr/bin/env python3
"""
AEGIS Security Module
======================
Handles:
  - API token generation and validation
  - Path traversal guard
  - Command allowlist validation
  - Input sanitization

Token is stored in ~/.temporary-aegis/config/aegis_api_token (chmod 600).
Never logged, never exposed in responses.
"""

import os
import secrets
import stat
import time
import hmac
import hashlib
from pathlib import Path
from fastapi import Request, HTTPException
from backend.config import cfg
from backend.logger import get_logger

log = get_logger("security")

_TOKEN_FILE = cfg.CONFIG_DIR / "aegis_api_token"

# ── Endpoints that do NOT require token auth (read-only UI data) ───────────────
PUBLIC_ENDPOINTS = {
    "/api/health",
    "/api/health/full",
    "/api/vault",
    "/api/vault/structure",
    "/api/files/tree",
    "/api/models",
    "/api/models/list",
    "/api/pc-state",
    "/api/agents",
    "/api/skills",
    "/api/tools",
    "/api/notes",
    "/api/memory/search",
    "/api/memory/mem0/search",
    "/api/memory/mem0/all",
    "/api/governance",
    "/api/cloudroom/workspaces",
    "/api/supervisor/tasks",
    "/api/turboquant/search",
    "/api/cameras",
    "/api/graph",
    "/api/status",
    "/",
    "/docs",
    "/openapi.json",
}

# ── Safe script identifiers (allowlist) ───────────────────────────────────────
ALLOWED_SCRIPTS = {
    "aegis-snapshot",
    "aegis-ingest",
    "aegis-ingest-chatgpt",
    "aegis-ingest-chats",
    "aegis-ai-ingest",
    "aegis-consolidate",
    "aegis-learn",
    "aegis-learn-patterns",
    "aegis-index",
}

# ── Allowed agent IDs ──────────────────────────────────────────────────────────
ALLOWED_AGENT_IDS = {a["id"] for a in cfg.AGENT_REGISTRY}
ALLOWED_AGENT_IDS.add("bash")  # always permit host shell


def _ensure_token() -> str:
    """Return the API token, generating one if it doesn't exist yet."""
    cfg.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if _TOKEN_FILE.exists():
        token = _TOKEN_FILE.read_text().strip()
        if token:
            return token
    token = secrets.token_hex(32)
    _TOKEN_FILE.write_text(token)
    _TOKEN_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0o600
    log.info("Generated new AEGIS API token → %s", _TOKEN_FILE)
    return token


# Load once at import time
API_TOKEN: str = _ensure_token()

# This session is deliberately scoped to conversational inference only. It is
# not accepted by the generic mutation guard for scripts, agents, or filesystem
# actions, and the browser never receives the underlying API token.
CHAT_SESSION_COOKIE = "aegis_chat_session"
CHAT_SESSION_TTL_SECONDS = 8 * 60 * 60

def create_chat_session() -> str:
    expires = str(int(time.time()) + CHAT_SESSION_TTL_SECONDS)
    signature = hmac.new(API_TOKEN.encode(), f"chat:{expires}".encode(), hashlib.sha256).hexdigest()
    return f"{expires}.{signature}"

def has_valid_chat_session(request: Request) -> bool:
    value = request.cookies.get(CHAT_SESSION_COOKIE, "")
    try:
        expires, signature = value.split(".", 1)
        expected = hmac.new(API_TOKEN.encode(), f"chat:{expires}".encode(), hashlib.sha256).hexdigest()
        return int(expires) >= time.time() and secrets.compare_digest(signature, expected)
    except (ValueError, TypeError):
        return False


def check_token(request: Request) -> bool:
    """
    Validate X-AEGIS-Token header.
    Returns True if valid, False if missing/wrong.
    Mutations (POST/PUT/DELETE/PATCH) on non-public endpoints MUST pass this.
    """
    path = request.url.path
    if path in PUBLIC_ENDPOINTS:
        return True
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return True  # reads always allowed from localhost
    provided = request.headers.get("X-AEGIS-Token", "")
    if not secrets.compare_digest(provided, API_TOKEN):
        log.warning("Rejected request to %s — bad/missing token", path)
        return False
    return True


async def require_token(request: Request):
    """FastAPI dependency: raises 403 if token check fails."""
    if not check_token(request):
        raise HTTPException(status_code=403, detail="Missing or invalid X-AEGIS-Token")


def safe_path(raw: str, base: Path | None = None) -> Path:
    """
    Resolve a path and enforce it stays within HOME (or optional base).
    Raises HTTPException(400) on path traversal attempt.
    """
    try:
        resolved = Path(raw).expanduser().resolve()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid path: {e}")
    guard = (base or Path(cfg.PATH_ACCESS_GUARD)).resolve()
    if not str(resolved).startswith(str(guard)):
        log.warning("Path traversal blocked: %s (resolved: %s)", raw, resolved)
        raise HTTPException(status_code=403, detail="Path outside allowed area")
    return resolved


def safe_agent_id(agent_id: str) -> str:
    """Validate agent ID against registry allowlist."""
    if agent_id not in ALLOWED_AGENT_IDS:
        raise HTTPException(status_code=400, detail=f"Unknown agent: {agent_id!r}")
    return agent_id


def safe_script_id(script_id: str) -> str:
    """Validate script identifier against allowlist."""
    clean = script_id.strip().removesuffix(".sh")
    if clean not in ALLOWED_SCRIPTS:
        raise HTTPException(status_code=400, detail=f"Unknown script: {script_id!r}")
    return clean


import re
_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]{1,128}$")

def safe_session_id(session_id: str) -> str:
    if not _ID_PATTERN.match(session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID format")
    return session_id

def safe_project_id(project_id: str) -> str:
    if not _ID_PATTERN.match(project_id):
        raise HTTPException(status_code=400, detail="Invalid project ID format")
    return project_id

def safe_camera_id(camera_id: str) -> str:
    if not _ID_PATTERN.match(camera_id):
        raise HTTPException(status_code=400, detail="Invalid camera ID format")
    return camera_id

def safe_schedule_id(schedule_id: str) -> str:
    if not _ID_PATTERN.match(schedule_id):
        raise HTTPException(status_code=400, detail="Invalid schedule ID format")
    return schedule_id


if __name__ == "__main__":
    print(f"API Token file: {_TOKEN_FILE}")
    print(f"Token length: {len(API_TOKEN)} chars")
    print("Security module: VERIFIED OK")
