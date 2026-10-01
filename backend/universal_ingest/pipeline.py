#!/usr/bin/env python3
"""Pipeline: discover -> extract -> redact -> dedup -> write -> link mem0 summary."""
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.universal_ingest.adapters import READERS
from backend.universal_ingest.redact import redact
from backend.universal_ingest.writer import write_note, CKPT_PATH

MAX_PER_AGENT = 3
AGENTS = ["opencode", "codex", "claude", "gemini", "hermes", "openclaw", "antigravity", "frontier"]


def link_mem0(rec, note_path):
    """Link each durable session record to canonical AEGIS memory with provenance."""
    try:
        from backend.mem0_engine import Mem0MemoryEngine
        eng = Mem0MemoryEngine()
        summary = " ".join((rec.get("text") or "").split())[:900]
        eng.add(text=f"Ingested {rec['agent']} session {rec['session_id']}: {summary}",
                user_id="adarshjii", agent_id=rec["agent"], category="ingest",
                run_id=rec.get("session_id"), project_id=rec.get("project") or None,
                metadata={"source": "universal_ingest", "source_id": rec.get("source_id"),
                          "obsidian_note": note_path})
        return True
    except Exception as e:
        print(f"[mem0:{agent}] skipped ({type(e).__name__})")
        return False


def run(max_per_agent=MAX_PER_AGENT):
    results = {}
    for agent in AGENTS:
        ing = skip = fail = 0
        status = ""
        try:
            recs, status = READERS[agent](limit=max_per_agent)
        except Exception:
            traceback.print_exc()
            results[agent] = {"ingested": 0, "skipped": 0, "failed": 1, "status": "READER_ERROR"}
            continue
        if status in ("NOT_CONFIGURED", "EMPTY", "UNREADABLE") and not recs:
            results[agent] = {"ingested": 0, "skipped": 0, "failed": 0, "status": status}
            continue
        for rec in recs[:max_per_agent]:
            try:
                rec["text"] = redact(rec.get("text", ""))
                st, note_path = write_note(rec)
                if st == "written":
                    ing += 1
                    link_mem0(rec, note_path)
                elif st == "skipped":
                    skip += 1
                else:
                    fail += 1
            except Exception:
                fail += 1
        results[agent] = {"ingested": ing, "skipped": skip, "failed": fail,
                          "status": status or "OK"}
    return results


def main():
    import json
    res = run()
    print("agent | ingested | skipped | failed | status")
    for a, r in res.items():
        print(f"{a} | {r['ingested']} | {r['skipped']} | {r['failed']} | {r['status']}")
    print(f"checkpoints: {CKPT_PATH}")
    return res


if __name__ == "__main__":
    main()
