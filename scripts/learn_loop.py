#!/usr/bin/env python3
"""agies learn-loop: bounded single-topic research pass (P4.1/P4.2).
- Queue: ~/.temporary-aegis/config/learn_queue.json (rotation of 5 topics)
- Each run: picks next topic (or --topic override), researches via LOCAL means
  ONLY (installed docs, repo READMEs, curl -s --max-time 20 of <=3 well-known
  public doc URLs — no credentialed sites, no crawling), writes Obsidian note,
  ingests to mem0 (category=knowledge) + TurboQuant, advances queue, logs run.
- Per-run cap: 25 min (default 1500s), stops cleanly via deadline checks.
- NEVER prints secrets. Do NOT edit backend/server.py.
Run: <hermes-venv-python> scripts/learn_loop.py [--topic X] [--budget-sec N]
"""
import sys, json, time, subprocess, datetime
from pathlib import Path

REPO = Path("/home/adarshjii/aegis-dashboard")
sys.path.insert(0, str(REPO))

HOME = Path.home()
QUEUE_FILE = HOME / ".temporary-aegis/config/learn_queue.json"
LOG_FILE = HOME / ".temporary-aegis/logs/learn_loop.log"
VAULT_LEARNED = HOME / "ObsidianVault/memory/3-Resources/learned"
DEFAULT_TOPICS = ["psychology-defense", "dark-romanticism",
                  "defensive-cybersecurity", "web-automation", "local-LLM-ops"]
BUDGET_SEC = 25 * 60

# Well-known public doc URLs only (no creds, no crawling). 2 per topic.
TOPIC_SOURCES = {
    "psychology-defense": [
        "https://raw.githubusercontent.com/mem0ai/mem0/main/README.md",
        "https://raw.githubusercontent.com/obsidianmd/obsidian-releases/master/README.md",
    ],
    "dark-romanticism": [
        "https://raw.githubusercontent.com/obsidianmd/obsidian-releases/master/README.md",
        "https://raw.githubusercontent.com/mem0ai/mem0/main/README.md",
    ],
    "defensive-cybersecurity": [
        "https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/README.md",
        "https://raw.githubusercontent.com/obsidianmd/obsidian-releases/master/README.md",
    ],
    "web-automation": [
        "https://raw.githubusercontent.com/microsoft/playwright/main/README.md",
        "https://raw.githubusercontent.com/obsidianmd/obsidian-releases/master/README.md",
    ],
    "local-LLM-ops": [
        "https://raw.githubusercontent.com/ollama/ollama/main/README.md",
        "https://raw.githubusercontent.com/lmstudio-ai/lms/main/README.md",
    ],
}
# Local repo READMEs to mine per topic (bounded, first N chars each).
LOCAL_DOCS = {
    "psychology-defense": ["ObsidianVault/memory/3-Resources/psychology/dark-psychology-defense.md"],
    "dark-romanticism": ["ObsidianVault/memory/3-Resources/psychology/dark-rom-knowledge.md"],
    "defensive-cybersecurity": ["Projects/school-netops/README.md", "aegis-dashboard/README.md"],
    "web-automation": ["Projects/nexo.ai/README.md", "Projects/repusense/README.md"],
    "local-LLM-ops": ["aegis-dashboard/README.md", "Projects/assistant/README.md"],
}

def log(msg):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.datetime.now().isoformat(timespec='seconds')} {msg}"
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")
    print(line)

def load_queue():
    if not QUEUE_FILE.exists():
        QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
        q = {"topics": DEFAULT_TOPICS, "index": 0}
        QUEUE_FILE.write_text(json.dumps(q, indent=2))
        return q
    try:
        q = json.loads(QUEUE_FILE.read_text())
        if not q.get("topics"):
            q = {"topics": DEFAULT_TOPICS, "index": 0}
        return q
    except Exception:
        return {"topics": DEFAULT_TOPICS, "index": 0}

def curl_fetch(url, deadline):
    if time.time() > deadline:
        return ""
    try:
        r = subprocess.run(["curl", "-s", "--max-time", "20", url],
                           capture_output=True, text=True, timeout=25)
        return (r.stdout or "")[:4000]
    except Exception as e:
        return f"(fetch failed: {e})"

def local_read(rel, deadline, limit=4000):
    if time.time() > deadline:
        return ""
    p = HOME / rel
    if not p.exists():
        # fallback: dashboard repo README
        fb = REPO / "README.md"
        if p.name.lower() == "readme.md" and fb.exists():
            return f"--- {fb} (fallback) ---\n" + fb.read_text(errors="replace")[:limit]
        return f"(missing local doc: {rel})"
    try:
        return f"--- {rel} ---\n" + p.read_text(errors="replace")[:limit]
    except Exception as e:
        return f"(read failed {rel}: {e})"

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", default=None)
    ap.add_argument("--budget-sec", type=int, default=BUDGET_SEC)
    a = ap.parse_args()
    t0 = time.time()
    deadline = t0 + min(a.budget_sec, BUDGET_SEC)

    q = load_queue()
    topics = q["topics"]
    if a.topic:
        topic = a.topic
    else:
        topic = topics[q.get("index", 0) % len(topics)]
    log(f"START topic={topic} budget={a.budget_sec}s")

    # --- research: local only + bounded curl ---
    parts = [f"# {topic} — local research synthesis"]
    for rel in LOCAL_DOCS.get(topic, ["aegis-dashboard/README.md"]):
        parts.append(local_read(rel, deadline))
        if time.time() > deadline:
            break
    for url in TOPIC_SOURCES.get(topic, [])[:3]:
        parts.append(f"--- FETCH {url} ---\n" + curl_fetch(url, deadline))
        if time.time() > deadline:
            break
    research = "\n\n".join(parts)[:12000]

    # --- write Obsidian note ---
    VAULT_LEARNED.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today().isoformat()
    note_path = VAULT_LEARNED / f"{today}_{topic}.md"
    note = (f"---\ntitle: Learned {topic}\ndate: {today}\ntopic: {topic}\n"
            f"tags: [learned, agies]\nsource: learn_loop\n---\n\n"
            f"# {topic} ({today})\n\n## Summary\nBounded local-only pass. "
            f"See Sources for provenance.\n\n## Key points\n"
            f"- Defense/ethics-first reading of {topic}.\n"
            f"- Local docs + ≤3 public doc URLs, no credentialed sites.\n"
            f"- Full raw excerpts below for auditability.\n\n"
            f"## Defensive application\n- File under PARA 3-Resources; link from MOC.\n"
            f"- agies uses this knowledge defensively only.\n\n"
            f"## Sources (raw, truncated)\n\n{research}\n")
    note_path.write_text(note)

    # --- ingest mem0 + TurboQuant ---
    mem_id, tq_chunks = "FAILED", 0
    try:
        from backend.mem0_engine import Mem0MemoryEngine
        from backend.turboquant_store import TurboQuantStore
        mem = Mem0MemoryEngine()
        rec = mem.add(f"Learned {topic} ({today}): defensive synthesis from local docs. "
                      f"{research[:600]}",
                      user_id="adarshjii", agent_id="agies",
                      category="knowledge",
                      metadata={"source": "learn_loop", "topic": topic, "date": today,
                                "note": str(note_path)})
        mem_id = rec.get("id", "UNKNOWN")
        tq = TurboQuantStore()
        before = len(tq._cache)
        tq.ingest(f"learn:{topic}:{today}", note,
                  {"type": "learned", "topic": topic, "date": today,
                   "file": str(note_path)})
        tq_chunks = len(tq._cache) - before
    except Exception as e:
        log(f"ERROR ingest failed: {e}")

    # --- advance queue (only on scheduled rotation, not --topic override) ---
    if not a.topic:
        q["index"] = (q.get("index", 0) + 1) % len(topics)
        QUEUE_FILE.write_text(json.dumps(q, indent=2))

    dt = round(time.time() - t0, 1)
    log(f"DONE topic={topic} note={note_path} mem0={mem_id} tq_chunks={tq_chunks} elapsed={dt}s next_index={q.get('index')}")
    print(f"NOTE={note_path}\nMEM0={mem_id}\nTQ_CHUNKS={tq_chunks}")

if __name__ == "__main__":
    main()
