#!/usr/bin/env python3
"""Bounded per-source readers. Each reader: max files + max chars, try/except per file."""
import json
import sqlite3
from pathlib import Path

HOME = Path.home()
MAX_CHARS = 30000
MAX_LINES = 300


def _rec(agent, session_id, text, source, project="", timestamp="", rtype="chat"):
    text = (text or "")[:MAX_CHARS]
    return {"agent": agent, "session_id": str(session_id), "source_id": str(source), "text": text,
            "source": str(source), "project": project or "",
            "timestamp": timestamp or "", "type": rtype}


def _safe_lines(path, max_lines=MAX_LINES):
    try:
        out = []
        with open(path, errors="replace") as f:
            for i, line in enumerate(f):
                if i >= max_lines:
                    break
                out.append(line[:2000])
        return out
    except Exception:
        return []


def read_opencode(limit=3):
    """SQLite sessions table only (never credential/account tables)."""
    db = HOME / ".local/share/opencode/opencode.db"
    recs = []
    try:
        if not db.exists():
            return recs, "NOT_CONFIGURED"
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=10)
        try:
            rows = con.execute(
                "SELECT id,title,directory,time_updated FROM session ORDER BY time_updated DESC LIMIT ?",
                (limit,)).fetchall()
        finally:
            pass
        for sid, title, directory, tsupd in rows:
            try:
                msgs = con.execute(
                    "SELECT data FROM message WHERE session_id=? ORDER BY time_created LIMIT 120",
                    (sid,)).fetchall()
                chunks = []
                for (data,) in msgs:
                    try:
                        d = json.loads(data or "{}")
                        role = d.get("role", "?")
                        chunks.append(f"[{role}] " + json.dumps(d)[:1500])
                    except Exception:
                        chunks.append(str(data)[:1500])
                ts = ""
                try:
                    import datetime
                    ts = datetime.datetime.fromtimestamp(int(tsupd) / 1000).isoformat() if tsupd else ""
                except Exception:
                    ts = ""
                recs.append(_rec("opencode", sid, f"title: {title}\n" + "\n".join(chunks),
                                 f"opencode.db:{sid}", project=str(directory or ""), timestamp=ts))
            except Exception:
                continue
        con.close()
        return recs, "" if recs else "EMPTY"
    except Exception:
        return recs, "UNREADABLE"


def read_codex(limit=3):
    base = HOME / ".codex/sessions"
    recs = []
    try:
        if not base.exists():
            return recs, "NOT_CONFIGURED"
        files = sorted(base.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]
        for fp in files[:limit]:
            try:
                chunks = []
                for line in _safe_lines(fp):
                    try:
                        o = json.loads(line)
                        s = json.dumps(o)[:1500]
                        if any(k in s for k in ("text", "message", "content", "payload")):
                            chunks.append(s)
                    except Exception:
                        continue
                    if len("\n".join(chunks)) > MAX_CHARS:
                        break
                sid = fp.stem
                try:
                    first = json.loads(open(fp, errors="replace").readline() or "{}")
                    sid = first.get("payload", {}).get("session_id", sid)
                except Exception:
                    pass
                recs.append(_rec("codex", sid, "\n".join(chunks), f"codex:{fp.name}",
                                 timestamp="", rtype="chat"))
            except Exception:
                continue
        return recs, "" if recs else "EMPTY"
    except Exception:
        return recs, "UNREADABLE"


def read_claude(limit=3):
    base = HOME / ".claude/projects"
    recs = []
    try:
        if not base.exists():
            return recs, "NOT_CONFIGURED"
        files = sorted(base.glob("*/*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]
        for fp in files[:limit]:
            try:
                chunks = []
                for line in _safe_lines(fp):
                    try:
                        o = json.loads(line)
                        m = o.get("message", {})
                        c = m.get("content", "")
                        if isinstance(c, list):
                            t = " ".join(
                                (b.get("text", "") if isinstance(b, dict) else str(b)) for b in c)[:1500]
                        else:
                            t = str(c)[:1500]
                        role = m.get("role", o.get("type", "?"))
                        if t.strip():
                            chunks.append(f"[{role}] {t}")
                    except Exception:
                        continue
                    if len("\n".join(chunks)) > MAX_CHARS:
                        break
                recs.append(_rec("claude", fp.stem, "\n".join(chunks), f"claude:{fp.parent.name}/{fp.name}",
                                 project=fp.parent.name, rtype="chat"))
            except Exception:
                continue
        return recs, "" if recs else "EMPTY"
    except Exception:
        return recs, "UNREADABLE"


def read_gemini(limit=3):
    base = HOME / ".gemini/tmp"
    recs = []
    try:
        if not base.exists():
            return recs, "NOT_CONFIGURED"
        files = sorted(base.glob("*/logs.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
        for fp in files:
            try:
                raw = fp.read_text(errors="replace")[:MAX_CHARS]
                try:
                    items = json.loads(raw)
                    chunks = [json.dumps(m)[:1500] for m in items[:100]]
                    text = "\n".join(chunks)
                except Exception:
                    text = raw
                recs.append(_rec("gemini", fp.parent.name, text, f"gemini:{fp.parent.name}/logs.json",
                                 project=fp.parent.name, rtype="chat"))
            except Exception:
                continue
        return recs, "" if recs else "EMPTY"
    except Exception:
        return recs, "UNREADABLE"


def read_hermes(limit=3):
    base = HOME / ".hermes/profiles/agies/sessions"
    recs = []
    try:
        if not base.exists():
            return recs, "NOT_CONFIGURED"
        files = sorted(base.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:3]
        for fp in files[:limit]:
            try:
                raw = fp.read_text(errors="replace")[:MAX_CHARS]
                try:
                    o = json.loads(raw)
                    body = o.get("request", {}).get("body", {})
                    msgs = body.get("messages", [])
                    chunks = [f"[{m.get('role','?')}] {str(m.get('content',''))[:1500]}"
                              for m in msgs[:60]]
                    text = f"reason: {o.get('reason','')}\nsession: {o.get('session_id',fp.stem)}\n" \
                           + "\n".join(chunks)
                    ts = str(o.get("timestamp", ""))
                except Exception:
                    text, ts = raw, ""
                recs.append(_rec("hermes", fp.stem, text, f"hermes:{fp.name}",
                                 timestamp=ts, rtype="chat"))
            except Exception:
                continue
        return recs, "" if recs else "EMPTY"
    except Exception:
        return recs, "UNREADABLE"


def read_openclaw(limit=3):
    base = HOME / ".openclaw/agents/main/sessions"
    recs = []
    try:
        if not base.exists():
            return recs, "NOT_CONFIGURED"
        files = [p for p in sorted(base.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
                 if p.suffix in (".jsonl", ".json", ".md")][:limit]
        for fp in files:
            try:
                text = "\n".join(_safe_lines(fp))[:MAX_CHARS]
                recs.append(_rec("openclaw", fp.name, text, f"openclaw:{fp.name}", rtype="chat"))
            except Exception:
                continue
        return recs, "" if recs else "EMPTY"
    except Exception:
        return recs, "UNREADABLE"


def read_antigravity(limit=3):
    base = HOME / ".gemini/antigravity/brain"
    recs = []
    try:
        if not base.exists():
            return recs, "NOT_CONFIGURED"
        files = sorted(base.glob("*/task.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]
        for fp in files[:limit]:
            try:
                text = fp.read_text(errors="replace")[:MAX_CHARS]
                recs.append(_rec("antigravity", fp.parent.name, text,
                                 f"antigravity:{fp.parent.name}/task.md", rtype="task"))
            except Exception:
                continue
        return recs, "" if recs else "EMPTY"
    except Exception:
        return recs, "UNREADABLE"


def read_frontier(limit=3):
    recs = []
    try:
        cands = []
        fr = HOME / ".temporary-aegis/frontier_runs"
        try:
            if fr.exists():
                for run in sorted([p for p in fr.iterdir() if p.is_dir()],
                                  key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
                    cands.extend(fp for fp in (run / "session.json", run / "trace.jsonl", run / "engine.log") if fp.exists())
        except Exception:
            pass
        if not cands:
            return recs, "NOT_CONFIGURED"
        for fp in cands[:limit]:
            try:
                if fp.suffix == ".jsonl":
                    text = "\n".join(_safe_lines(fp, 120))[:MAX_CHARS]
                else:
                    text = fp.read_text(errors="replace")[:MAX_CHARS]
                recs.append(_rec("frontier", fp.parent.name if fp.parent.name.startswith("2026") else fp.name,
                                 text, f"frontier:{fp}", rtype="run"))
            except Exception:
                continue
        return recs, "" if recs else "EMPTY"
    except Exception:
        return recs, "UNREADABLE"


READERS = {"opencode": read_opencode, "codex": read_codex, "claude": read_claude,
           "gemini": read_gemini, "hermes": read_hermes, "openclaw": read_openclaw,
           "antigravity": read_antigravity, "frontier": read_frontier}
