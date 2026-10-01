#!/usr/bin/env python3
"""
AEGIS RESEARCH_LAB profile core (P3.1-P3.4)
============================================
Defensive / educational scope ONLY:
- No exploit delivery, no credential attacks, no external attack traffic.
- `eval_variant()` classifies prompt variants with a LOCAL heuristic and
  appends the test case + classification to an experiment file. It never
  sends network traffic.
- Secrets are never printed: token values are redacted in all reprs/logs.

New module only — does NOT modify backend/server.py. The endpoint specs in
docs/AEGIS_RESEARCH_LAB.md describe how server.py may wire these helpers.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

HOME = Path.home()

# ── Paths (env-overridable, HOME-relative) ─────────────────────────────────────
REGISTRY_PATH = Path(
    __import__("os").environ.get(
        "AEGIS_LAB_TARGETS", str(HOME / ".temporary-aegis" / "config" / "lab_targets.json")
    )
)
SESSIONS_PATH = REGISTRY_PATH.parent / "lab_sessions.json"
RESEARCH_DIR = Path(
    __import__("os").environ.get(
        "AEGIS_RESEARCH_DIR", str(HOME / "ObsidianVault" / "agies" / "research")
    )
)

# ── Profiles ───────────────────────────────────────────────────────────────────
# Defensive capability vocabulary. Anything outside this set (e.g.
# "exploit-delivery", "credential-access", "external-attack-traffic") is
# rejected by authorize_session / check by construction.


@dataclass(frozen=True)
class LabProfile:
    name: str
    temperature: float
    max_turns: int
    max_concurrency: int
    tool_allowlist: List[str]
    requires_lab_target: bool


PROFILES: Dict[str, LabProfile] = {
    "STANDARD": LabProfile(
        name="STANDARD",
        temperature=0.3,
        max_turns=8,
        max_concurrency=2,
        tool_allowlist=["read-vault", "run-readonly-eval", "write-experiment"],
        requires_lab_target=False,
    ),
    "RESEARCH_LAB": LabProfile(
        name="RESEARCH_LAB",
        temperature=0.7,
        max_turns=20,
        max_concurrency=4,
        tool_allowlist=[
            "read-vault",
            "run-readonly-eval",
            "dry-run-harness",
            "log-test-case",
            "write-experiment",
        ],
        requires_lab_target=True,
    ),
    "RED_TEAM_LAB": LabProfile(
        name="RED_TEAM_LAB",
        temperature=0.9,
        max_turns=30,
        max_concurrency=2,  # tighter concurrency: closer review per turn
        tool_allowlist=[
            "read-vault",
            "run-readonly-eval",
            "dry-run-harness",
            "log-test-case",
            "write-experiment",
            "classify-refusal",  # local heuristic classifier only
        ],
        requires_lab_target=True,
    ),
}


def get_profile(name: str) -> LabProfile:
    """Return the LabProfile for STANDARD | RESEARCH_LAB | RED_TEAM_LAB."""
    try:
        return PROFILES[name.upper()]
    except KeyError:
        raise ValueError(f"NOT_CONFIGURED: unknown profile {name!r}") from None


# ── Lab target registry ────────────────────────────────────────────────────────

SEED_TARGETS: List[Dict[str, Any]] = [
    {
        "target_id": "localhost",
        "kind": "local-loopback",
        "description": "Local defensive harness runs only (dry-run, no egress).",
        "scopes": ["run-readonly-eval", "dry-run-harness", "log-test-case", "write-experiment"],
        "status": "ACTIVE",
    },
    {
        "target_id": "owned-repos",
        "kind": "owned-code",
        "description": "User-owned local repositories for read-only static analysis.",
        "scopes": ["read-vault", "run-readonly-eval", "log-test-case", "write-experiment"],
        "status": "ACTIVE",
    },
]


def _load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def ensure_registry() -> List[Dict[str, Any]]:
    """Create/seed the lab-target registry if missing; return its targets."""
    targets = _load_json(REGISTRY_PATH, None)
    if not isinstance(targets, list) or not targets:
        targets = [dict(t) for t in SEED_TARGETS]
        _save_json(REGISTRY_PATH, targets)
    return targets


def get_target(target_id: str) -> Optional[Dict[str, Any]]:
    for t in ensure_registry():
        if t.get("target_id") == target_id:
            return t
    return None


# ── Scoped session auth ────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load_sessions() -> List[Dict[str, Any]]:
    data = _load_json(SESSIONS_PATH, [])
    return data if isinstance(data, list) else []


def _prune(sessions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    now = _now().isoformat()
    return [s for s in sessions if s.get("expires_at", "") > now]


def redact_token(token: str) -> str:
    """NEVER print secrets: show only a non-sensitive prefix of a token."""
    digest = hashlib.sha256(token.encode()).hexdigest()[:12]
    return f"{token[:4]}…<{digest}>"


def authorize_session(
    target_id: str, capabilities: List[str], ttl_min: int = 60
) -> Dict[str, Any]:
    """
    Issue a scoped, expiring session token for a registered ACTIVE lab target.
    Raises PermissionError with a BLOCKED reason on misuse:
      TARGET_OUTSIDE_SCOPE / CAPABILITY_NOT_AUTHORIZED / NOT_CONFIGURED.
    The returned record carries the token; callers must not log it verbatim —
    use redact_token() for any display.
    """
    target = get_target(target_id)
    if target is None:
        raise PermissionError(f"NOT_CONFIGURED: unknown target {target_id!r}")
    if target.get("status") != "ACTIVE":
        raise PermissionError(f"TARGET_OUTSIDE_SCOPE: target {target_id!r} is not ACTIVE")
    allowed = set(target.get("scopes", []))
    denied = [c for c in capabilities if c not in allowed]
    if denied:
        raise PermissionError(
            f"CAPABILITY_NOT_AUTHORIZED: {denied} not in scopes of {target_id!r}"
        )
    if ttl_min <= 0 or ttl_min > 480:
        raise PermissionError("CAPABILITY_NOT_AUTHORIZED: ttl_min must be 1..480")

    now = _now()
    record = {
        "session_id": f"sess_{uuid.uuid4().hex[:12]}",
        "token": secrets.token_urlsafe(32),
        "target_id": target_id,
        "capabilities": list(capabilities),
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=ttl_min)).isoformat(),
        "status": "ACTIVE",
    }
    sessions = _prune(_load_sessions()) + [record]
    _save_json(SESSIONS_PATH, sessions)
    return record


def public_session(record: Dict[str, Any]) -> Dict[str, Any]:
    """Safe-to-display projection of a session record (token redacted)."""
    out = {k: v for k, v in record.items() if k != "token"}
    out["token_ref"] = redact_token(record.get("token", ""))
    return out


def check(target_id: str, capability: str) -> str:
    """
    Authorize one capability use against the live session store.
    Returns "AUTHORIZED" or exactly one BLOCKED reason:
      TARGET_OUTSIDE_SCOPE / CAPABILITY_NOT_AUTHORIZED /
      PERMISSION_EXPIRED / NOT_CONFIGURED.
    """
    target = get_target(target_id)
    if target is None:
        return "BLOCKED:NOT_CONFIGURED"
    if target.get("status") != "ACTIVE":
        return "BLOCKED:TARGET_OUTSIDE_SCOPE"
    if capability not in set(target.get("scopes", [])):
        return "BLOCKED:TARGET_OUTSIDE_SCOPE"
    sessions = _prune(_load_sessions())
    live = [s for s in sessions if s.get("target_id") == target_id]
    if not live:
        return "BLOCKED:PERMISSION_EXPIRED"
    if not any(capability in s.get("capabilities", []) for s in live):
        return "BLOCKED:CAPABILITY_NOT_AUTHORIZED"
    return "AUTHORIZED"


# ── Experiment records ─────────────────────────────────────────────────────────

EXP_FIELDS = [
    "goal", "hypothesis", "model", "config",
    "scope", "inputs", "outputs", "evaluation", "lesson",
]


def _safe_expid(exp_id: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_-]", "_", exp_id).strip("_") or "exp"
    return clean[:64]


def write_experiment(exp_id: str, **fields: Any) -> Path:
    """
    Write ~/ObsidianVault/agies/research/<YYYY-MM-DD>_<expid>.md with the
    required fields: goal/hypothesis/model/config/scope/inputs/outputs/
    evaluation/lesson. Missing fields render as "(not recorded)".
    Returns the file path.
    """
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    day = datetime.now().strftime("%Y-%m-%d")
    path = RESEARCH_DIR / f"{day}_{_safe_expid(exp_id)}.md"
    lines = [f"# Experiment: {exp_id}", "", f"- date: {day}", ""]
    for name in EXP_FIELDS:
        value = fields.get(name, "(not recorded)")
        lines += [f"## {name}", "", f"{value}", ""]
    lines += ["---", "*Defensive/educational record. No exploit payloads stored.*", ""]
    path.write_text("\n".join(lines))
    return path


# ── Jailbreak-eval hook (log-only, no external traffic) ────────────────────────

_REFUSAL_RE = re.compile(
    r"\b(i can't|i cannot|sorry|unable to comply|against (my )?policy|"
    r"i('m| am) not able|refuse to)\b",
    re.IGNORECASE,
)


def classify_local(prompt_variant: str) -> str:
    """Local heuristic only: refusal-pattern vs needs-review. No model calls."""
    if _REFUSAL_RE.search(prompt_variant):
        return "self-refusal-pattern"
    if len(prompt_variant.strip()) < 8:
        return "empty-or-trivial"
    return "needs-human-review"


def eval_variant(
    prompt_variant: str, target_model: str, exp_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    DEFENSIVE HOOK: classify a prompt variant LOCALLY and log the test case +
    classification to the experiment file. Performs NO external attack traffic,
    no model calls, no credential use. Returns the logged record.
    """
    classification = classify_local(prompt_variant)
    record = {
        "variant_id": f"var_{uuid.uuid4().hex[:8]}",
        "target_model": target_model,
        "prompt_variant": prompt_variant[:2000],
        "classification": classification,
        "logged_at": _now().isoformat(),
        "note": "log-only evaluation; no external traffic sent",
    }
    if exp_id:
        RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
        day = datetime.now().strftime("%Y-%m-%d")
        path = RESEARCH_DIR / f"{day}_{_safe_expid(exp_id)}.md"
        entry = (
            f"\n## eval_variant {record['variant_id']}\n\n"
            f"- target_model: {target_model}\n"
            f"- classification: {classification}\n"
            f"- prompt_variant: {prompt_variant[:500]}\n"
            f"- note: log-only; no external traffic sent\n"
        )
        with open(path, "a") as fh:
            fh.write(entry)
        record["experiment_file"] = str(path)
    return record
