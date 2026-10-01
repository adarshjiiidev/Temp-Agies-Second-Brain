#!/usr/bin/env python3
"""
AEGIS Preferences Store (P2.11/P5.1)
====================================
JSON-backed user-preference store. New module only — the main agent wires
these functions into backend/server.py (do NOT edit server.py here).

Store:   ~/.temporary-aegis/config/preferences.json (via backend.config.cfg)
Record:  {"value": any, "source": str, "confidence": float, "updated": iso-ts}
Sections: identity, dev, ui_style, product, workflow, research

Conventions:
- NEVER print secrets. Functions return counts/status, never raw values to logs.
- source "user" is authoritative (confidence forced to 1.0 on set/confirm).
- Inferred (non-explicit) seeded values carry confidence <= 0.6; explicit == 1.0.
- Precedence (high to low): project rule > task instruction > user pref >
  global > default. See resolve().
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from backend.config import cfg
from backend.logger import get_logger

log = get_logger("preferences")

STORE_FILE: Path = cfg.CONFIG_DIR / "preferences.json"
VAULT_DIR: Path = Path.home() / "ObsidianVault"

SECTIONS: List[str] = ["identity", "dev", "ui_style", "product", "workflow", "research"]

_PRECEDENCE = ("project_rule", "task_instruction", "user_pref", "global", "default")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record(value: Any, source: str, confidence: float) -> Dict[str, Any]:
    return {
        "value": value,
        "source": source,
        "confidence": float(confidence),
        "updated": _now(),
    }


class PreferencesStore:
    def __init__(self, path: Optional[Path] = None):
        self.path: Path = path or STORE_FILE
        self._data: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._load()

    # ── persistence ──
    def _load(self) -> None:
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    self._data = {s: v for s, v in raw.items() if s in SECTIONS and isinstance(v, dict)}
            except Exception as e:
                log.error("preferences load failed (starting empty)")
        for s in SECTIONS:
            self._data.setdefault(s, {})

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    # ── reads ──
    def get_profile(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """Full store: {section: {key: record}}."""
        return {s: dict(keys) for s, keys in self._data.items()}

    def get_section(self, section: str) -> Dict[str, Dict[str, Any]]:
        if section not in SECTIONS:
            raise KeyError(f"unknown section: {section}")
        return dict(self._data.get(section, {}))

    def get_sections(self) -> List[str]:
        return list(SECTIONS)

    # ── writes ──
    def set_pref(self, section: str, key: str, value: Any,
                 source: str = "user", confidence: Optional[float] = None) -> Dict[str, Any]:
        """Write a pref. source 'user' is authoritative -> confidence 1.0."""
        if section not in SECTIONS:
            raise KeyError(f"unknown section: {section}")
        if confidence is None:
            confidence = 1.0 if source == "user" else 0.6
        rec = _record(value, source, confidence)
        self._data[section][key] = rec
        self._save()
        return rec

    def confirm_pref(self, section: str, key: str, source: str = "user") -> Dict[str, Any]:
        """User confirms an inferred pref -> authoritative, confidence 1.0."""
        if section not in SECTIONS or key not in self._data.get(section, {}):
            raise KeyError(f"unknown pref: {section}.{key}")
        rec = self._data[section][key]
        rec["source"] = source
        rec["confidence"] = 1.0
        rec["updated"] = _now()
        self._save()
        return dict(rec)

    def delete_pref(self, section: str, key: str) -> bool:
        if section in self._data and key in self._data[section]:
            del self._data[section][key]
            self._save()
            return True
        return False

    # ── precedence resolver ──
    def _store_lookup(self, key: str) -> Optional[Dict[str, Any]]:
        for section in SECTIONS:
            if key in self._data.get(section, {}):
                rec = dict(self._data[section][key])
                rec["_section"] = section
                return rec
        return None

    def resolve(self, key: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Resolve key under precedence: project_rule > task_instruction >
        user_pref > global > default. context may carry any of those levels
        directly; user_pref falls back to this store when absent."""
        ctx = context or {}
        if "user_pref" not in ctx:
            hit = self._store_lookup(key)
            if hit is not None:
                ctx = {**ctx, "user_pref": hit.get("value")}
        for level in _PRECEDENCE:
            if level in ctx and ctx[level] is not None:
                return {"key": key, "value": ctx[level], "winner": level}
        return {"key": key, "value": None, "winner": "none"}


_store = PreferencesStore()


# ── module-level API for main-agent wiring (no server.py edits here) ──
def get_profile() -> Dict[str, Dict[str, Dict[str, Any]]]:
    return _store.get_profile()


def get_section(section: str) -> Dict[str, Dict[str, Any]]:
    return _store.get_section(section)


def get_sections() -> List[str]:
    return _store.get_sections()


def set_pref(section: str, key: str, value: Any,
             source: str = "user", confidence: Optional[float] = None) -> Dict[str, Any]:
    return _store.set_pref(section, key, value, source, confidence)


def confirm_pref(section: str, key: str, source: str = "user") -> Dict[str, Any]:
    return _store.confirm_pref(section, key, source)


def delete_pref(section: str, key: str) -> bool:
    return _store.delete_pref(section, key)


def resolve(key: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return _store.resolve(key, context)


# ── vault seeder ──
def _evidence(files: Dict[str, str], *needles: str) -> bool:
    blob = "\n".join(files.values())
    return all(n in blob for n in needles)


def seed_from_vault() -> Dict[str, int]:
    """Read ABOUT_ME.md, AGIES.md, agies-memories/USER.md and write the initial
    store. Explicit vault statements -> confidence 1.0; inferred -> <= 0.6.
    Returns per-section counts. Never prints values (no secrets to stdout)."""
    paths = {
        "ABOUT_ME": VAULT_DIR / "ABOUT_ME.md",
        "AGIES": VAULT_DIR / "AGIES.md",
        "USER": VAULT_DIR / "agies-memories" / "USER.md",
    }
    files = {k: p.read_text(encoding="utf-8", errors="replace") if p.exists() else "" for k, p in paths.items()}
    missing = [k for k, v in files.items() if not v]
    if missing:
        log.error("seed missing vault files (continuing with remainder)")

    seed: Dict[str, Dict[str, Dict[str, Any]]] = {s: {} for s in SECTIONS}

    def put(section: str, key: str, value: Any, source: str, confidence: float,
            *needles: str, force: bool = False) -> None:
        if not force and needles and not _evidence(files, *needles):
            return  # no vault evidence -> skip rather than hallucinate
        seed[section][key] = _record(value, source, confidence)

    # identity — explicit in vault
    put("identity", "name", "Adarsh Jii", "vault:USER.md", 1.0, "Adarsh Jii")
    put("identity", "role", "Builder of personal AI operating systems and autonomous agents",
        "vault:ABOUT_ME.md", 1.0, "Builder of personal AI")
    put("identity", "machine", "Ai — AGIES Linux 4.0.3 (Omarchy / Arch-based)", "vault:USER.md", 1.0, "AGIES Linux 4.0.3")
    put("identity", "home", "/home/adarshjii", "vault:USER.md", 1.0, "/home/adarshjii")

    # dev — explicit in vault
    put("dev", "os", "AGIES Linux 4.0.3 (Omarchy/Arch, Hyprland)", "vault:USER.md", 1.0, "Omarchy")
    put("dev", "shell", "zsh + Starship", "vault:ABOUT_ME.md", 1.0, "zsh + Starship")
    put("dev", "editor", "VS Code", "vault:ABOUT_ME.md", 1.0, "VS Code")
    put("dev", "python", "Python 3.11 (uv)", "vault:ABOUT_ME.md", 1.0, "Python 3.11")
    put("dev", "node", "Node 22/24", "vault:ABOUT_ME.md", 1.0, "Node 22/24")
    put("dev", "projects_dir", "~/Projects", "vault:USER.md", 1.0, "~/Projects for all projects")
    put("dev", "vcs", "Git", "vault:USER.md", 1.0, "Git for version control")

    # ui_style — prescribed by task spec P2.11 (bg corroborated by repo AGENTS.md); explicit
    ui_src = "task-spec(P2.11)"
    seed["ui_style"] = {
        "bg_primary": _record("#0e0e11", ui_src, 1.0),
        "bg_deep": _record("#050608", ui_src, 1.0),
        "accent": _record("orange/amber", ui_src, 1.0),
        "surface": _record("glassmorphic dark, subtle glow borders", ui_src, 1.0),
        "density": _record("high", ui_src, 1.0),
        "sidebar": _record("minimal", ui_src, 1.0),
        "headers": _record("mono", ui_src, 1.0),
    }

    # product — per-category guidance, inferred from vault stance (local-first, privacy)
    put("product", "developer-tool",
        {"mode": "local-first", "runtimes": ["Python 3.11 (uv)", "Node 22/24", "FastAPI", "Docker"]},
        "vault-inferred:ABOUT_ME.md", 0.6, "local-first", force=True)
    put("product", "dashboard",
        {"style": "dark glassmorphic single-user console", "notes": "TEMPORARY AEGIS Second Brain"},
        "vault-inferred:USER.md", 0.6, "aegis-dashboard")
    put("product", "chat",
        {"tone": "concise progress updates during implementation, thorough when it matters"},
        "vault:USER.md", 1.0, "concise progress updates")

    # workflow — explicit in vault
    put("workflow", "pipeline", "PLAN→PERMISSION→POLICY→EXECUTE→AUDIT→VERIFY→REFLECT",
        "vault:AGIES.md", 1.0, "PLAN → PERMISSION")
    put("workflow", "memory_rule", "never silently promote observations to permanent memory — user validates",
        "vault:USER.md", 1.0, "Never silently promote")
    put("workflow", "comms", "concise progress updates during implementation, thorough when it matters",
        "vault:USER.md", 1.0, "concise progress updates")
    put("workflow", "second_brain", "Obsidian vault as source of truth (PARA + CODE + MOC)",
        "vault:USER.md", 1.0, "Obsidian vault as second brain")
    put("workflow", "privacy_tier", "P0 DEVICE_LOCAL_ONLY never leaves device",
        "vault:USER.md", 1.0, "DEVICE_LOCAL_ONLY")

    # research — explicit defensive/verify stance in vault
    put("research", "defensive_only", True, "vault:AGIES.md", 1.0, "DEFENSE-ONLY")
    put("research", "verify_live", "verify claims with live commands (git status, ss, systemctl); never guess — scan",
        "vault:AGIES.md", 1.0, "don't claim execution")
    put("research", "psychology_scope", "dark-psychology knowledge is defense-only; no manipulation/phishing/coercion",
        "vault:AGIES.md", 1.0, "Never craft manipulation")

    _store._data = seed
    _store._save()
    counts = {s: len(keys) for s, keys in seed.items()}
    log.info("preferences seeded (counts only, values not logged)")
    return counts


if __name__ == "__main__":
    print(seed_from_vault())
