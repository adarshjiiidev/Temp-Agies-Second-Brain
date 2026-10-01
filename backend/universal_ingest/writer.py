#!/usr/bin/env python3
"""Write redacted Obsidian notes + content-hash checkpoints for dedup."""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
VAULT_ROOT = HOME / "ObsidianVault/agies/Chats"
CKPT_PATH = HOME / ".temporary-aegis/config/ingest_checkpoints.json"


def _safe_name(s, n=80):
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", str(s))[:n].strip("_")
    return s or "session"


def _load_ckpt():
    try:
        if CKPT_PATH.exists():
            return json.loads(CKPT_PATH.read_text(errors="replace"))
    except Exception:
        pass
    return {}


def _save_ckpt(d):
    try:
        CKPT_PATH.parent.mkdir(parents=True, exist_ok=True)
        CKPT_PATH.write_text(json.dumps(d, indent=1)[:200000])
    except Exception:
        pass


def content_hash(agent, session_id, source_id, text):
    h = hashlib.sha256()
    h.update(f"{agent}|{session_id}|{source_id}|".encode())
    h.update((text or "").encode(errors="replace"))
    return h.hexdigest()[:32]


def write_note(rec):
    """Write one note. Returns ('written', path) | ('skipped', reason)."""
    ckpt = _load_ckpt()
    key = f"{rec['agent']}/{rec['session_id']}"
    ch = content_hash(rec["agent"], rec["session_id"], rec.get("source_id", rec.get("source", "")), rec["text"])
    if ckpt.get(key) == ch:
        return "skipped", "dedup-hash-match"
    date = datetime.now(timezone.utc)
    agent_dir = VAULT_ROOT / str(date.year) / date.strftime("%Y-%m") / _safe_name(rec["agent"], 40)
    try:
        agent_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return "failed", f"mkdir: {e}"
    fp = agent_dir / (_safe_name(rec["session_id"]) + ".md")
    fm = (f"---\nagent: {rec['agent']}\nproject: {_safe_name(rec.get('project',''),60)}\n"
          f"session: {rec['session_id']}\ntimestamp: {rec.get('timestamp','')}\n"
          f"source_id: {rec.get('source_id', rec.get('source',''))}\nsource: {rec.get('source','')}\n"
          f"type: {rec.get('type','chat')}\nhash: {ch}\n---\n")
    body = (rec.get("text") or "(empty)")[:28000]
    summary = " ".join(body.split())[:900] or "No textual content was available."
    try:
        fp.write_text(fm + f"\n# AEGIS session record: {rec['agent']} / {rec['session_id']}\n\n"
                      f"## Summary\n{summary}\n\n## Provenance\n"
                      f"- Agent: {rec['agent']}\n- Session: {rec['session_id']}\n- Source: {rec.get('source', '')}\n"
                      f"- Project: {rec.get('project') or 'unresolved'}\n\n"
                      f"## Extracted transcript (redacted, bounded)\n\n{body}\n",
                      errors="replace")
    except Exception as e:
        return "failed", f"write: {e}"
    ckpt[key] = ch
    _save_ckpt(ckpt)
    return "written", str(fp)
