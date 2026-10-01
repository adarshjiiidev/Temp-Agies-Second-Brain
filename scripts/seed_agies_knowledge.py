#!/usr/bin/env python3
"""
seed_agies_knowledge.py — agies knowledge seeder (2026-09-27)
Ingests EVERY project + apps index + dark-psychology/dark-rom pack
into TurboQuant (semantic chunks w/ provenance) AND mem0 (personalized memory).

Run:  cd /home/adarshjii/aegis-dashboard && python3 scripts/seed_agies_knowledge.py
Verify: /api/turboquant/search?q=Noir  /api/memory/mem0/search?q=Noir
Rerun-safe: ADD-only (mem0) / append-chunks (turboquant). Duplicates possible on
repeat runs — acceptable for ADD-only fidelity; dedupe by source_id if needed.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from backend.turboquant_store import TurboQuantStore
from backend.mem0_engine import Mem0MemoryEngine

VAULT = Path.home() / "ObsidianVault"

PROJECTS = {
    "Aegis": "Personal Adaptive AI OS, 7-layer Python3.12+Rust. L1-L6 done, Phase8 agentmoe security hardening WIP (9 dirty files: autonomy, budget_guard, runtime + tests). 19M, main 0078650. Owner's core build. Path ~/Projects/Aegis.",
    "aegis-dashboard": "TEMPORARY AEGIS Second Brain dashboard. Vite+React+FastAPI :2981/:8787, 6 PTY tabs, vault explorer, 58-node KG, 27 skills, free_router auto round-robin. master DIRTY 88 files, Phase6 pending. Path ~/aegis-dashboard.",
    "assistant": "Nexo FastAPI autonomous assistant. Groq compound/mini, GPT-OSS, Llama-3.3-70B, Mongo+Chroma, soul.md personality, Reddit learner, soul-evolution. main 74609be clean. Path ~/Projects/assistant.",
    "nexo.ai": "Textual TUI autonomous device agent. Groq Llama4/GPT-OSS/Qwen, LangGraph, Playwright, encrypted creds, audit. main 2d22e50 clean. Sibling of assistant. Path ~/Projects/nexo.ai.",
    "artemis": "Upstream Google ARTEMIS Android automation (LangGraph+MCP+adbutils). Unpacked, NO git, 37M. Path ~/Projects/artemis/artemis-main.",
    "repusense": "Noir MV3 new-tab dev workspace (Ox Alpha via OpenRouter, 5 engines, bookmarks, telemetry, scratchpad). Converted Sep14 from Next.js scaffold. master fd760de tracked-clean + stale untracked node_modules/.next 459M TO DELETE. README STALE. Path ~/Projects/repusense.",
    "chrome-extra": "Noir twin of repusense, actively edited (5 modified files). master c361c84. SECURITY: hardcoded OpenRouter key in config.js — ROTATE. Path ~/Projects/chrome-extra.",
    "world-viewer": "Electron33+CesiumJS geo-intel desktop. 3D globe, 14 live layers, GDELT/RSS, Groq AI, timeline. main 919835e clean, 1.6G, Phase1 built. Path ~/Projects/world-viewer.",
    "billing-dis": "Electron40+Next.js school billing desktop (invoices/students/payments, jsPDF, Mongo). main b79887c clean. Path ~/Projects/billing-dis.",
    "Flicker": "Next.js16 AI fintech (LangGraph/Groq chat, Puppeteer LTP service, Yahoo Finance, NextAuth v5, Mongo). main c45223e clean. SENSITIVE: GCP key json in repo — move to secrets. Path ~/Projects/Flicker.",
    "Kagazi": "Next.js paper-trading simulator (virtual capital, positions/PnL, watchlists, NextAuth in-progress). main 7a2db5d clean. Path ~/Projects/Kagazi.",
    "pybackend": "Daaddys AI 13-agent swarm (NSE/BSE+crypto, FastAPI SSE, Groq 8B/70B routing, Mongo, Yahoo). main 1970971 clean. Path ~/Projects/pybackend.",
    "TN-Commerce": "Next.js fashion e-commerce (Zustand cart, Stripe, NextAuth, admin charts, Nodemailer, Vercel-ready). main c857ba3 clean. Path ~/Projects/TN-Commerce.",
    "Amruthpaan-Mukhwaas-Store": "Vite+React19+Tailwind paan store (cart/checkout/orders/admin, Gemini API, jspdf). NEW Sep26, NO git, 256M. Needs git init. Path ~/Projects/Amruthpaan-Mukhwaas-Store.",
    "jailbreak-autoresearch": "Python+OpenRouter prompt-harness research loop (baseline/seeded/evolve/recombine, SQLite, Codex /goal ready). main be8b6f1 clean. Defensive research only. Path ~/Projects/jailbreak-autoresearch.",
    "SkillOpt": "Microsoft SkillOpt v0.2.0 snapshot (skills-as-parameters, sleep engine+WebUI). NO git. Path ~/Projects/SkillOpt.",
    "school-netops": "Stdlib-only Python net monitor for 7 SSIDs (ARP/ping/nmap, DNS engine, policy blocks, :8443 dashboard). NO git, LIVE with daily encrypted backups ~/netops-backups (4x Sep24-27 growing). Path ~/Projects/school-netops.",
    "qwen-audio-agent": "Upstream Qwen realtime voice v1.11.0 (Express+ws+MCP+A2A+ACP, Electron orb). Shallow clone, clean. Path ~/qwen-audio-agent.",
    "pinokio": "Empty Pinokio launcher runtime, no apps installed. Path ~/pinokio.",
    "Work": "Scratch only: .crush/crush.db, .mise.toml, empty tries/. Real work lives in Projects+dashboard. Path ~/Work.",
}

KNOWLEDGE_FILES = [
    ("dark-psychology-defense", VAULT / "memory/3-Resources/psychology/dark-psychology-defense.md",
     "Defensive guide: recognize Dark Triad/Tetrad traits and manipulation tactics (gaslighting, DARVO, love-bombing, urgency/scarcity), persuasion-vs-manipulation line, dark-pattern and phishing-pretext defense, self-defense checklist. Ethical use only — agies never helps manipulate."),
    ("dark-rom-knowledge", VAULT / "memory/3-Resources/psychology/dark-rom-knowledge.md",
     "Disambiguation: Dark Romanticism (Poe/Hawthorne/Melville), Dark Romance genre (tropes + consent/content-warning safety), Custom Android ROMs (Lineage/Graphene, flashing risks, backup flow, link to artemis Android automation)."),
    ("installed-apps", VAULT / "memory/2-Areas/operations/installed-apps.md",
     "899 pacman packages, 50+ desktop apps (Chrome, Firefox, Antigravity, Cursor, Ghostty, OBS, LocalSend...), AI runtimes (OpenClaw, Hermes, free_router, llama-server, LM Studio), secret-hygiene flags."),
    ("apps-index", VAULT / "APPS_INDEX_2026-09-27.md",
     "Master map: every system app + AI runtime + all 19 project-apps + knowledge pack + memory fabric endpoints."),
    ("about-me", VAULT / "ABOUT_ME.md",
     "Owner Adarsh Jii: builder of personal AI OS, local-first multi-model lab, full inventory, old-vs-new, agies directives."),
]


def main():
    tq = TurboQuantStore()
    mem = Mem0MemoryEngine()
    n_tq, n_mem = 0, 0

    for name, summary in PROJECTS.items():
        text = f"Project {name}: {summary}"
        tq.ingest(f"project:{name}", text + "\n\n" + text, {"type": "project", "project": name, "date": "2026-09-27"})
        n_tq += 1
        mem.add(text, user_id="adarshjii", agent_id="agies", project_id=name,
                category="project", metadata={"source": "seed_agies_knowledge", "date": "2026-09-27"})
        n_mem += 1

    for source_id, path, blurb in KNOWLEDGE_FILES:
        content = path.read_text(errors="replace") if path.exists() else blurb
        tq.ingest(source_id, content, {"type": "knowledge", "file": str(path), "date": "2026-09-27"})
        n_tq += 1
        mem.add(f"Knowledge {source_id}: {blurb}", user_id="adarshjii", agent_id="agies",
                category="knowledge", metadata={"source": "seed_agies_knowledge", "file": str(path)})
        n_mem += 1

    print(f"OK: turboquant sources={n_tq} mem0 adds={n_mem}")
    print(f"turboquant chunks total: check {tq.store_file}")
    print(f"mem0 total: {len(mem.memories)}")


if __name__ == "__main__":
    main()
