#!/usr/bin/env python3
"""
AEGIS Dashboard Backend — FastAPI + WebSocket
- Serves Obsidian vault files
- Proxies to 9Router API
- Runs scripts (snapshot, chatgpt ingest, learn patterns)
- PC state monitoring
- WebSocket for real-time updates
"""

import sys
import os
import json
import subprocess
import asyncio
import uuid
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from backend.config import cfg
from backend.logger import get_logger
from backend.security import (check_token, safe_path, safe_agent_id, safe_script_id, API_TOKEN,
                              CHAT_SESSION_COOKIE, CHAT_SESSION_TTL_SECONDS,
                              create_chat_session, has_valid_chat_session)
from backend.browser_tool import browser_tool
from backend.camera_registry import camera_registry
from backend.camera_event_store import camera_event_store
from backend.vision_engine import vision_engine

log = get_logger("server")

app = FastAPI(title="AEGIS Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def security_middleware(request: Request, call_next):
    """Enforce auth on mutating endpoints (POST, PUT, DELETE, PATCH).

    Two credential paths:
    1. X-AEGIS-Token header (never exposed to browser code) — anything.
    2. Chat-session cookie (HttpOnly, local-only issuance) — conversation and
       the local-HMI actions the chat UI drives: LM Studio model management and
       agent tab spawn/stop. Cookie-authenticated requests must additionally be
       same-origin (Origin/Referer host must match Host) for CSRF defense.
    """
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        path = request.url.path
        cookie_ok = has_valid_chat_session(request) and (
            path == "/api/chat"
            or path == "/api/run-script"
            or path.startswith("/api/local-model/")
            or path.startswith("/api/agentmoe/")
            or path.startswith("/api/planner/")
            or path.startswith("/api/research/")
            or path.startswith("/api/sandbox/")
            or path.startswith("/api/vision/")
            or path.startswith("/api/audio/")
            or path.startswith("/api/frontier/")
            or path.startswith("/api/spatial/")
            or path.startswith("/api/ingest/")
            or path.startswith("/api/learn/")
            or path.startswith("/api/preferences")
            or path.startswith("/api/lab/")
            or path.startswith("/api/org-cameras/")
            or path.startswith("/api/turboquant/")
            or path.startswith("/api/memory/mem0/")
            or path.startswith("/api/knowledge/")
            or path.startswith("/api/cameras/")
            or path.startswith("/api/supervisor/")
            or path.startswith("/api/cloudroom/")
            or path.startswith("/api/governance/")
            or path.startswith("/api/executions")
            or (path.startswith("/api/agent/") and path.endswith(("/start", "/stop", "/restart")))
        )
        if cookie_ok and not _same_origin_browser(request):
            log.warning("Security reject 403 (cross-origin cookie auth) on %s %s", request.method, path)
            return JSONResponse(status_code=403, content={"error": "Forbidden: cross-origin request"})
        if not cookie_ok and not check_token(request):
            log.warning("Security reject 403 on %s %s", request.method, path)
            return JSONResponse(status_code=403, content={"error": "Forbidden: Invalid or missing X-AEGIS-Token"})
    return await call_next(request)


def _same_origin_browser(request: Request) -> bool:
    """True when a browser-present Origin/Referer matches the request Host.

    Non-browser clients (curl, systemd jobs) omit Origin/Referer entirely and
    are allowed through — they authenticate by token or local session instead.
    """
    host = request.headers.get("host", "")
    origin = request.headers.get("origin", "")
    referer = request.headers.get("referer", "")
    if origin:
        return origin.split("://", 1)[-1].split("/", 1)[0] == host
    if referer:
        return referer.split("://", 1)[-1].split("/", 1)[0] == host
    return True

# ── Paths ──────────────────────────────────────────────────────────────────────

VAULT = cfg.VAULT
AEGIS_DIR = cfg.AEGIS_DIR
REGISTRIES_DIR = cfg.REGISTRIES_DIR
SCRIPTS = cfg.SCRIPTS_DIR
MEMORY = cfg.MEMORY
AGIES_MEM = cfg.AGIES_MEM
CONFIG = cfg.CONFIG_DIR
HERMES_AGIES_SKILLS = cfg.HERMES_SKILLS
FRONTEND_DIST = cfg.REPO_ROOT / "dist"

# ── Vault File Cache (30s TTL) ────────────────────────────────────────────────
_vault_md_cache: list[Path] = []
_vault_md_cache_ts: float = 0.0
_VAULT_CACHE_TTL = 30.0

def get_vault_markdown_files() -> list[Path]:
    global _vault_md_cache, _vault_md_cache_ts
    now = time.time()
    if not _vault_md_cache or (now - _vault_md_cache_ts > _VAULT_CACHE_TTL):
        if VAULT.exists():
            _vault_md_cache = [
                p for p in VAULT.rglob("*.md")
                if not any(ign in p.parts for ign in [".git", ".obsidian", ".trash"])
            ]
        else:
            _vault_md_cache = []
        _vault_md_cache_ts = now
    return _vault_md_cache

_obsidian_graph_cache = None
_obsidian_graph_cache_ts = 0.0

def get_obsidian_graph() -> dict:
    """Build an interconnected graph from real Obsidian notes, wikilinks, and cluster hubs."""
    global _obsidian_graph_cache, _obsidian_graph_cache_ts
    now = time.time()
    if _obsidian_graph_cache is not None and (now - _obsidian_graph_cache_ts) < 60.0:
        return _obsidian_graph_cache

    import re
    files = get_vault_markdown_files()
    by_rel = {str(path.relative_to(VAULT)): path for path in files if path.parent != VAULT}
    by_stem = {}
    for rel, path in by_rel.items():
        by_stem.setdefault(path.stem.lower(), []).append(rel)

    def category_for(rel: str) -> str:
        lower = rel.lower()
        if "project" in lower:
            return "projects"
        if "moc" in lower or "map of content" in lower:
            return "mocs"
        if "area" in lower or "agent" in lower or "by-agent" in lower:
            return "areas"
        if "archive" in lower or "by-date" in lower:
            return "archives"
        return "resources"

    nodes = []
    edges = set()
    folders = {}

    for rel, path in by_rel.items():
        cat = category_for(rel)
        nodes.append({
            "id": rel,
            "name": path.stem,
            "path": rel,
            "category": cat,
            "size": path.stat().st_size
        })
        parent_rel = str(path.parent.relative_to(VAULT))
        folders.setdefault(parent_rel, []).append(rel)

        # 1. Direct wikilinks & markdown links
        try:
            text = path.read_text(errors="replace")
            wlinks = re.findall(r"\[\[([^\]|#]+)", text)
            wlinks += re.findall(r"\]\(([^)#]+)(?:\.md)?\)", text)
            for raw in wlinks:
                t = raw.strip().removesuffix(".md").lstrip("./")
                t_clean = t.lower()
                if t in by_rel and t != rel:
                    edges.add(tuple(sorted((rel, t))))
                elif (t + ".md") in by_rel and (t + ".md") != rel:
                    edges.add(tuple(sorted((rel, t + ".md"))))
                elif t_clean in by_stem:
                    for cand in by_stem[t_clean][:2]:
                        if cand != rel:
                            edges.add(tuple(sorted((rel, cand))))
        except Exception:
            pass

    # 2. Folder cluster connections to folder hub
    for folder_rel, folder_files in folders.items():
        if len(folder_files) <= 1:
            continue
        folder_name = Path(folder_rel).name.lower()
        hub = None
        for f in folder_files:
            if Path(f).stem.lower() in [folder_name, "index", "readme", "overview"]:
                hub = f
                break
        if not hub:
            hub = folder_files[0]
        for f in folder_files:
            if f != hub:
                edges.add(tuple(sorted((hub, f))))

    # 3. Inter-domain and MOC connections
    moc_files = [f for f in by_rel if "moc" in f.lower()]
    agent_files = [f for f in by_rel if "by-agent" in f.lower()]
    project_files = [f for f in by_rel if "project" in f.lower()]

    for moc in moc_files:
        for p in project_files[:6]:
            edges.add(tuple(sorted((moc, p))))
        for a in agent_files[:6]:
            edges.add(tuple(sorted((moc, a))))

    # 4. Connect remaining orphans to their folder/domain
    all_connected = set()
    for s, t in edges:
        all_connected.add(s)
        all_connected.add(t)

    orphans = [r for r in by_rel if r not in all_connected]
    for o in orphans:
        top = o.split("/")[0]
        target = next((f for f in by_rel if f != o and f.startswith(top) and f in all_connected), None)
        if target:
            edges.add(tuple(sorted((o, target))))

    _obsidian_graph_cache = {
        "nodes": nodes,
        "edges": [{"source": s, "target": t, "relation": "LINKS_TO"} for s, t in sorted(edges)]
    }
    _obsidian_graph_cache_ts = now
    return _obsidian_graph_cache

try:
    from backend.agent_pty import manager
    from backend.knowledge_graph import knowledge_graph
    from backend.model_router import model_router
    from backend.memory_engine import CognitiveMemoryEngine
    from backend.vision_engine import VisionEngine
    from backend.task_planner import HierarchicalPlanner
    from backend.audio_engine import audio_engine
    from backend.screen_intel import screen_intel
    from backend.research_engine import research_engine
    from backend.code_sandbox import code_sandbox
    from backend.proactive_monitor import proactive_monitor
    from backend.aegis_health import aegis_health
    from backend.agent_moe import agent_moe, AgentMoeFabric
    from backend.linux_intelligence import linux_intelligence
    from backend.project_intelligence import project_intelligence
    from backend.skill_registry import skill_registry
    from backend.agent_supervisor import agent_supervisor
    from backend.governance import governance, AutonomyLevel
    from backend.turboquant_store import TurboQuantStore
    from backend.mem0_engine import mem0_engine
    from backend.frontier_adapter import frontier_adapter
    from backend.spatial_mode import lane_sweep, sweep_status
    from backend.org_cameras import OrgCameraHub
    import backend.preferences as preferences
    import backend.research_lab as research_lab
    from backend.cloudroom_bridge import cloudroom_bridge
    from backend.context_router import context_router
    from backend.execution_core import execution_core
except ImportError:
    from agent_pty import manager
    from knowledge_graph import knowledge_graph
    from model_router import model_router
    from memory_engine import CognitiveMemoryEngine
    from vision_engine import VisionEngine
    from task_planner import HierarchicalPlanner
    from audio_engine import audio_engine
    from screen_intel import screen_intel
    from research_engine import research_engine
    from code_sandbox import code_sandbox
    from proactive_monitor import proactive_monitor
    from aegis_health import aegis_health
    from agent_moe import agent_moe, AgentMoeFabric
    from agent_supervisor import agent_supervisor
    from governance import governance, AutonomyLevel
    from turboquant_store import TurboQuantStore
    from mem0_engine import mem0_engine
    from cloudroom_bridge import cloudroom_bridge
    from context_router import context_router

cognitive_memory = CognitiveMemoryEngine()
vision_engine = VisionEngine()
hierarchical_planner = HierarchicalPlanner()
turboquant_store = TurboQuantStore()

# ── WebSocket connections ──────────────────────────────────────────────────────

connections: dict[str, WebSocket] = {}

async def async_broadcast(message: dict):
    msg = json.dumps(message)
    for conn in list(connections.values()):
        try:
            await conn.send_text(msg)
        except Exception:
            pass

def broadcast(message: dict):
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(async_broadcast(message))
    except RuntimeError:
        asyncio.run(async_broadcast(message))

# ── Vault helpers ──────────────────────────────────────────────────────────────

def get_vault_structure() -> dict:
    structure = {}
    if not VAULT.exists():
        return structure
    for item in sorted(VAULT.iterdir()):
        if item.is_dir():
            structure[item.name] = {
                "type": "dir",
                "children": sorted([c.name for c in item.iterdir() if not c.name.startswith(".")])
            }
        else:
            structure[item.name] = {
                "type": "file",
                "size": item.stat().st_size,
                "modified": datetime.fromtimestamp(item.stat().st_mtime).isoformat()
            }
    return structure

def get_memory_files() -> list:
    files = []
    if not VAULT.exists():
        return files
    for md in sorted(get_vault_markdown_files()):
        try:
            files.append({
                "path": str(md.relative_to(VAULT)).replace("\\", "/"),
                "name": md.name,
                "size": md.stat().st_size,
                "modified": datetime.fromtimestamp(md.stat().st_mtime).isoformat()
            })
        except Exception:
            continue
    return files

def read_file_content(rel_path: str) -> Optional[dict]:
    file_path = VAULT / rel_path
    if file_path.exists() and file_path.is_file():
        return {
            "content": file_path.read_text(errors="replace"),
            "path": rel_path,
            "name": file_path.name,
            "size": file_path.stat().st_size,
            "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
        }
    return None

def search_vault(query: str) -> list:
    if not query or not VAULT.exists():
        return []
    results = []
    query_lower = query.lower()
    for md in get_vault_markdown_files():
        try:
            content = md.read_text(errors="replace")
            idx = content.lower().find(query_lower)
            if idx >= 0:
                start = max(0, idx - 150)
                end = min(len(content), idx + 250)
                context = content[start:end]
                rel_path = str(md.relative_to(VAULT)).replace("\\", "/")
                results.append({
                    "path": rel_path,
                    "name": md.name,
                    "context": context,
                    "line": content[:idx].count('\n') + 1
                })
        except Exception:
            continue
    return results[:20]

def get_relevant_memory_context(query: str) -> str:
    """
    Search the consolidated memory and living project memories using
    TF-IDF ranked retrieval, architecture decisions, and daily briefings.
    Also injects recent task experiences so past plan outcomes influence current responses.
    """
    agies_dir = cfg.AGIES_VAULT
    if not agies_dir.exists():
        return ""

    q_lower = query.lower()
    injected_parts = []

    # 1. Ranked memory retrieval across all projects and notes
    try:
        ranked_hits = cognitive_memory.ranked_memory_search(query, limit=3)
        for hit in ranked_hits:
            injected_parts.append(f"### Relevant Memory `{hit['path']}` (relevance: {hit['score']}):\n{hit['snippet']}")
    except Exception as e:
        log.warning("Ranked memory search error: %s", e)

    # 2. Key Architectural Decisions
    dec_file = agies_dir / "DECISIONS.md"
    if ("decision" in q_lower or "architecture" in q_lower or "why" in q_lower) and dec_file.exists():
        try:
            injected_parts.append(f"### Key Architectural Decisions:\n{dec_file.read_text(errors='replace')[:1200]}")
        except Exception:
            pass

    # 3. Daily Briefing
    brief_file = agies_dir / "DAILY_BRIEFING.md"
    if ("today" in q_lower or "yesterday" in q_lower or "briefing" in q_lower or "session" in q_lower or "built" in q_lower) and brief_file.exists():
        try:
            injected_parts.append(f"### Daily Briefing & Activity:\n{brief_file.read_text(errors='replace')[:1000]}")
        except Exception:
            pass

    # 4. Past task experience records — feeds executed plan outcomes back into context
    tasks_dir = agies_dir / "tasks"
    if tasks_dir.exists():
        try:
            task_files = sorted(tasks_dir.glob("TASK_*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
            # Inject up to 2 recent task experiences if query seems related to past work
            if any(k in q_lower for k in ["task", "plan", "last", "previous", "did", "ran", "executed", "result", "outcome"]):
                for tf in task_files[:2]:
                    try:
                        injected_parts.append(f"### Recent Task Experience `{tf.name}`:\n{tf.read_text(errors='replace')[:600]}")
                    except Exception:
                        pass
        except Exception as e:
            log.warning("Task experience lookup error: %s", e)

    # 5. Systematic file inspection: if query mentions a specific filename
    for word in query.split():
        clean_word = word.strip("`'\",:()")
        if any(clean_word.endswith(ext) for ext in [".py", ".tsx", ".ts", ".json", ".md", ".sh", ".toml", ".css", ".html"]):
            for root in WORKSPACE_PROJECTS.values():
                candidate = root / clean_word if not clean_word.startswith("/") else Path(clean_word)
                if candidate.exists() and candidate.is_file():
                    res = read_file_systematically(str(candidate), start_line=1, max_lines=60)
                    if res.get("success"):
                        injected_parts.append(f"### Systematic File Read: `{candidate.name}` ({res['total_lines']} lines)\n```\n{res['content']}\n```")
                    break

    return "\n\n".join(injected_parts)

# ── Systematic Workspace Crawler & File Reader ────────────────────────────────

WORKSPACE_PROJECTS = cfg.PROJECTS
IGNORE_DIRS = {".git", "node_modules", "__pycache__", "dist", ".next", ".venv", "target", "build", ".cache"}
ALLOWED_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".md", ".rs", ".html", ".css", ".sh", ".yaml", ".yml", ".toml"}

def systematic_workspace_crawl() -> dict:
    index = {}
    total_files = 0
    agies_dir = cfg.AGIES_VAULT

    for proj_id, root in WORKSPACE_PROJECTS.items():
        if not root.exists():
            continue
        proj_files = []
        try:
            for p in root.rglob("*"):
                if not p.is_file():
                    continue
                if any(ign in p.parts for ign in IGNORE_DIRS):
                    continue
                if p.suffix.lower() not in ALLOWED_EXTS and p.name not in ["Dockerfile", "Makefile"]:
                    continue
                try:
                    sz = p.stat().st_size
                    if sz > 512 * 1024:
                        continue
                    rel = str(p.relative_to(root))
                    proj_files.append({
                        "rel_path": rel,
                        "abs_path": str(p),
                        "ext": p.suffix,
                        "size_bytes": sz
                    })
                except Exception:
                    continue
        except Exception:
            pass

        index[proj_id] = {
            "root": str(root),
            "total_files": len(proj_files),
            "files": proj_files[:200]
        }
        total_files += len(proj_files)

    if agies_dir.exists():
        try:
            (agies_dir / "FILE_INDEX.json").write_text(json.dumps(index, indent=2))
        except Exception:
            pass

    return {"status": "ok", "indexed_projects": len(index), "total_files_scanned": total_files, "projects": index}

def read_file_systematically(filepath: str, start_line: int = 1, max_lines: int = 150) -> dict:
    try:
        p = safe_path(filepath)
    except HTTPException as e:
        return {"success": False, "error": f"Access denied: {e.detail}"}
    except Exception as e:
        return {"success": False, "error": f"Invalid path: {e}"}

    if not p.exists() or not p.is_file():
        return {"success": False, "error": f"File not found: {filepath}"}

    try:
        lines = p.read_text(errors="replace").splitlines()
        total_lines = len(lines)
        start_idx = max(0, start_line - 1)
        end_idx = min(total_lines, start_idx + max_lines)
        sliced = lines[start_idx:end_idx]
        formatted = "\n".join([f"{start_idx + i + 1:4d} | {line}" for i, line in enumerate(sliced)])
        return {
            "success": True,
            "path": str(p),
            "total_lines": total_lines,
            "start_line": start_idx + 1,
            "end_line": end_idx,
            "content": formatted
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

# ── Free Model Router ─────────────────────────────────────────────────────────

async def query_model_health() -> dict:
    from backend.free_router import get_free_router_health
    return get_free_router_health()


# ── Scripts ────────────────────────────────────────────────────────────────────

def run_script(name: str) -> dict:
    try:
        clean_name = safe_script_id(name)
    except HTTPException as e:
        return {"success": False, "error": f"Invalid script: {e.detail}"}
    except Exception as e:
        return {"success": False, "error": f"Invalid script identifier: {e}"}

    script_path = SCRIPTS / f"{clean_name}.sh"
    if not script_path.exists():
        script_path = SCRIPTS / clean_name
        if not script_path.exists():
            return {"success": False, "error": f"Script not found: {name}"}
    try:
        result = subprocess.run(
            ["bash", str(script_path)],
            capture_output=True, text=True, timeout=300,
            cwd=str(AEGIS_DIR), env=cfg.get_agent_env()
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[-3000:] if result.stdout else "",
            "stderr": result.stderr[-1500:] if result.stderr else "",
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timed out (5 min)"}
    except Exception as e:
        log.error("run_script error on %s: %s", name, e)
        return {"success": False, "error": str(e)}

# ── PC Monitoring ──────────────────────────────────────────────────────────────

def get_pc_state() -> dict:
    state = {
        "timestamp": datetime.now().isoformat(),
        "system": {},
        "memory": {"total_kb": 0, "free_kb": 0, "available_kb": 0, "used_kb": 0},
        "disk": {"filesystem": "", "size": "", "used": "", "avail": "", "use_percent": "", "mounted": ""},
        "processes": [],
        "network": {},
        "ports": [],
    }
    
    # System info
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    state["system"][k] = v.strip('"')
    except:
        pass
    
    # Memory
    try:
        with open("/proc/meminfo") as f:
            meminfo = {}
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    meminfo[parts[0].rstrip(":")] = int(parts[1])
            state["memory"] = {
                "total_kb": meminfo.get("MemTotal", 0),
                "free_kb": meminfo.get("MemFree", 0),
                "available_kb": meminfo.get("MemAvailable", 0),
                "used_kb": meminfo.get("MemTotal", 0) - meminfo.get("MemFree", 0),
            }
    except:
        pass
    
    # Disk
    try:
        result = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, timeout=5)
        lines = result.stdout.strip().split("\n")
        if len(lines) >= 2:
            parts = lines[1].split()
            state["disk"] = {
                "filesystem": parts[0],
                "size": parts[1] if len(parts) > 1 else "",
                "used": parts[2] if len(parts) > 2 else "",
                "avail": parts[3] if len(parts) > 3 else "",
                "use_percent": parts[4] if len(parts) > 4 else "",
                "mounted": parts[5] if len(parts) > 5 else "",
            }
    except:
        pass
    
    # Top processes
    try:
        result = subprocess.run(["ps", "aux", "--sort=-%mem"], capture_output=True, text=True, timeout=5)
        lines = result.stdout.strip().split("\n")[1:16]
        for line in lines:
            parts = line.split(None, 10)
            if len(parts) >= 11:
                state["processes"].append({
                    "user": parts[0],
                    "pid": parts[1],
                    "cpu": parts[2],
                    "mem": parts[3],
                    "vsz": parts[4],
                    "rss": parts[5],
                    "command": parts[10][:80]
                })
    except:
        pass
    
    # Listening ports
    try:
        result = subprocess.run(["ss", "-tlnp"], capture_output=True, text=True, timeout=5)
        lines = result.stdout.strip().split("\n")[1:]
        for line in lines:
            parts = line.split()
            if len(parts) >= 4:
                state["ports"].append({
                    "state": parts[0],
                    "recv_q": parts[1],
                    "send_q": parts[2],
                    "local_addr": parts[3],
                    "peer": parts[4] if len(parts) > 4 else "",
                    "process": parts[6] if len(parts) > 6 and "," in parts[6] else ""
                })
    except:
        pass
    
    # Network interfaces
    try:
        result = subprocess.run(["ip", "-brief", "addr"], capture_output=True, text=True, timeout=5)
        lines = result.stdout.strip().split("\n")[1:]
        for line in lines:
            parts = line.split()
            if len(parts) >= 3:
                state["network"][parts[0]] = {
                    "type": parts[1],
                    "state": parts[2],
                    "addresses": parts[3:] if len(parts) > 3 else []
                }
    except:
        pass
    
    return state

async def pc_monitor_loop():
    while True:
        state = get_pc_state()
        broadcast({"type": "pc_update", "data": state})
        await asyncio.sleep(30)

# ── Skills / Models / Tools ────────────────────────────────────────────────────

def get_skills() -> dict:
    skills = skill_registry.get_all_skills()
    # Convert list to dict keyed by ID for existing API compatibility
    return {s["id"]: s for s in skills}

def get_models() -> dict:
    from backend.free_router import get_curated_models
    curated = get_curated_models()
    return {
        "curated_models": curated,
        "default": "openrouter/free",
        "providers": ["openrouter", "groq", "lmstudio"]
    }

def get_tools() -> dict:
    for p in [REGISTRIES_DIR / "TOOL_REGISTRY.json", AEGIS_DIR / "TOOL_REGISTRY.json"]:
        if p.exists():
            try:
                return json.loads(p.read_text())
            except Exception:
                pass
    return {}

def get_agents() -> dict:
    for p in [REGISTRIES_DIR / "AGENT_REGISTRY.json", AEGIS_DIR / "AGENT_REGISTRY.json"]:
        if p.exists():
            try:
                return json.loads(p.read_text())
            except Exception:
                pass
    return {"agents": []}

# ── REST API ───────────────────────────────────────────────────────────────────

@app.get("/api/vault")
async def api_vault():
    return get_vault_structure()

@app.get("/api/memory-files")
async def api_memory_files():
    return get_memory_files()

@app.get("/api/file/{path:path}")
async def api_file(path: str):
    from urllib.parse import unquote
    decoded_path = unquote(path)
    result = read_file_content(decoded_path)
    if result:
        return result
    raise HTTPException(404, f"File not found: {path}")

@app.get("/api/search")
async def api_search(query: str = "", limit: int = 20):
    if not query.strip():
        return []
    ranked = cognitive_memory.ranked_memory_search(query.strip(), limit=limit)
    if ranked:
        return ranked
    return search_vault(query)

@app.get("/api/memory/search")
async def api_memory_search(q: str = "", limit: int = 15):
    if not q.strip():
        return []
    return cognitive_memory.ranked_memory_search(q.strip(), limit=limit)

@app.get("/api/graph")
async def api_graph():
    return knowledge_graph.get_graph_data()

@app.get("/api/obsidian-graph")
async def api_obsidian_graph():
    return get_obsidian_graph()

@app.post("/api/knowledge/rebuild")
async def api_knowledge_rebuild():
    data = knowledge_graph.rebuild()
    return {"status": "ok", "nodes": len(data["nodes"]), "edges": len(data["edges"])}


@app.get("/api/chat/session")
async def api_chat_session(request: Request):
    """Issue a local, HttpOnly credential usable only for POST /api/chat."""
    if request.client is None or request.client.host not in {"127.0.0.1", "::1"}:
        raise HTTPException(status_code=403, detail="Chat sessions are local-only")
    response = JSONResponse({"status": "ready"})
    response.set_cookie(CHAT_SESSION_COOKIE, create_chat_session(), max_age=CHAT_SESSION_TTL_SECONDS,
                        httponly=True, samesite="strict", path="/api")
    return response

@app.get("/api/browser/extract")
async def api_browser_extract(url: str, max_chars: int = 8000):
    return browser_tool.extract_content(url, max_chars=max_chars)

@app.get("/api/browser/screenshot")
async def api_browser_screenshot(url: str):
    return browser_tool.capture_screenshot(url)

@app.get("/api/browser/dom")
async def api_browser_dom(url: str):
    return browser_tool.fetch_dom(url)

@app.get("/api/mocs")
async def api_mocs():
    mocs_dir = MEMORY / "MOCs"
    mocs = []
    if mocs_dir.exists():
        for md in sorted(mocs_dir.glob("*.md")):
            content = md.read_text()
            title = md.stem
            for line in content.split('\n'):
                if line.startswith('# '):
                    title = line[2:].strip()
                    break
            mocs.append({
                "path": f"memory/MOCs/{md.name}",
                "title": title,
                "preview": content[:400]
            })
    return mocs

@app.get("/api/projects")
async def api_projects():
    projects_dir = MEMORY / "1-Projects"
    projects = []
    if projects_dir.exists():
        for item in projects_dir.iterdir():
            if item.is_dir():
                for md in item.glob("*.md"):
                    content = md.read_text()
                    title = md.stem
                    status = "unknown"
                    for line in content.split('\n'):
                        if line.startswith('**Status:**'):
                            status = line.split(':', 1)[1].strip().replace('**', '')
                        if line.startswith('# '):
                            title = line[2:].strip()
                            break
                    projects.append({
                        "path": f"memory/1-Projects/{item.name}/{md.name}",
                        "name": item.name,
                        "title": title,
                        "status": status,
                        "preview": content[:400]
                    })
            elif item.suffix == '.md':
                content = item.read_text()
                title = item.stem
                for line in content.split('\n'):
                    if line.startswith('# '):
                        title = line[2:].strip()
                        break
                projects.append({
                    "path": f"memory/1-Projects/{item.name}",
                    "title": title,
                    "preview": content[:400]
                })
    return projects

@app.get("/api/files/tree")
async def api_files_tree(project: str = ""):
    idx = systematic_workspace_crawl()
    if project and project in idx.get("projects", {}):
        return idx["projects"][project]
    return idx

@app.get("/api/files/read")
async def api_files_read(path: str, start: int = 1, lines: int = 150):
    from urllib.parse import unquote
    decoded = unquote(path)
    return read_file_systematically(decoded, start_line=start, max_lines=lines)

@app.post("/api/files/systematic-scan")
async def api_files_scan():
    return systematic_workspace_crawl()

@app.get("/api/skills")
async def api_skills():
    return get_skills()

@app.get("/api/models")
async def api_models():
    return get_models()

@app.get("/api/tools")
async def api_tools():
    return get_tools()

@app.get("/api/pc-state")
async def api_pc_state():
    return get_pc_state()

@app.get("/api/9router-health")
@app.get("/api/model-health")
async def api_model_health():
    from backend.free_router import get_free_router_health
    return get_free_router_health()


@app.post("/api/run-script")
async def api_run_script(request: Request):
    body = await request.json()
    script_name = body.get("script", "")
    result = run_script(script_name)
    broadcast({"type": "script_result", "script": script_name, "result": result})
    return result

@app.get("/api/agies-memories")
async def api_agies_memories():
    files = []
    if AGIES_MEM.exists():
        for md in sorted(AGIES_MEM.glob("*.md")):
            files.append({
                "path": f"agies-memories/{md.name}",
                "name": md.name,
                "size": md.stat().st_size,
                "content": md.read_text()[:500]
            })
    return files

@app.get("/api/config-files")
async def api_config_files():
    files = []
    if CONFIG.exists():
        for md in sorted(CONFIG.glob("*.md")):
            files.append({
                "path": f"config/{md.name}",
                "name": md.name,
                "preview": md.read_text()[:400]
            })
        for jf in sorted(CONFIG.glob("*.json")):
            files.append({
                "path": f"config/{jf.name}",
                "name": jf.name,
                "preview": jf.read_text()[:400]
            })
    return files

@app.get("/api/chatgpt-tracking")
async def api_chatgpt_tracking():
    track_path = MEMORY / "chatgpt_ingestion_tracking.json"
    if track_path.exists():
        try:
            return json.loads(track_path.read_text())
        except:
            pass
    return {}

@app.get("/api/agents")
async def api_agents():
    # Runtime availability is authoritative; static registry data is metadata.
    return {"agents": execution_core.registry()}

@app.get("/api/tasks")
async def api_tasks():
    return {"tasks": execution_core.list()}

@app.get("/api/capabilities")
async def api_capabilities():
    from backend.config import cfg
    caps = getattr(cfg, "CAPABILITIES", ["frontier.react", "frontier.agent_team", "frontier.resume", "frontier.trace"])
    return {"capabilities": caps}

@app.get("/api/skills")
async def api_skills():
    from backend.integrations.ecc.adapter import ecc_registry
    
    # Mock some imported skills if empty for demonstration
    if not ecc_registry.skills:
        ecc_registry.import_ecc_skill({
            "id": "ecc.code.analyze", "name": "Code Analysis Engine", 
            "desc": "Deep semantic code parsing using AST.", "category": "Development", "source": "ECC"
        })
        ecc_registry.import_ecc_skill({
            "id": "frontier.research.deep", "name": "Deep Research", 
            "desc": "Autonomous multi-step web scraping and synthesis.", "category": "Research", "source": "FrontierAgent"
        })
        ecc_registry.import_ecc_skill({
            "id": "multica.coord", "name": "Sub-Agent Coordinator", 
            "desc": "Spawns and manages specialized sub-agents.", "category": "Management", "source": "Multica"
        })
        
    return {"skills": [s.model_dump() for s in ecc_registry.skills.values()]}

@app.post("/api/tasks")
async def api_create_task(request: Request):
    body = await request.json()
    task_str = body.get("task", "")
    project = body.get("project", "")
    kind = body.get("kind", "general")
    if not task_str:
        raise HTTPException(status_code=400, detail="task is required")
    record = execution_core.create(task_str, project=project, kind=kind)
    return record

@app.post("/api/tasks/{task_id}/dispatch")
async def api_dispatch_task(task_id: str, request: Request):
    body = {}
    try:
        body = await request.json()
    except Exception:
        body = {}
    auto_approve = bool(body.get("auto_approve", False))
    return execution_core.dispatch(task_id, auto_approve=auto_approve)

@app.get("/api/system/graph")
async def api_system_graph():
    """Returns the AEGIS capability/execution system graph for dashboard visualization."""
    from backend.frontier_adapter import frontier_adapter
    from backend.integrations.multica.adapter import multica_daemon
    frontier_ok = frontier_adapter.is_available().get("installed", False)
    nodes = [
        {"id": "aegis_core",    "label": "AEGIS Core",      "type": "core",       "status": "PASS",        "description": "Executive intelligence"},
        {"id": "context",       "label": "Context Engine",  "type": "core",       "status": "PASS",        "description": "Project + memory + git envelope"},
        {"id": "planner",       "label": "Planner",         "type": "core",       "status": "PASS",        "description": "Task decomposition and routing"},
        {"id": "memory",        "label": "Memory (mem0)",   "type": "memory",     "status": "PASS",        "description": "Unified vector + Obsidian memory"},
        {"id": "obsidian",      "label": "Obsidian Vault",  "type": "memory",     "status": "PASS",        "description": "Human-readable persistent notes"},
        {"id": "capabilities",  "label": "Capabilities",    "type": "capability", "status": "PASS",        "description": "Skill registry and router"},
        {"id": "model_router",  "label": "Model Router",    "type": "core",       "status": "PASS",        "description": "Free + OpenRouter + Groq + local"},
        {"id": "frontier",      "label": "FrontierAgent",   "type": "executor",   "status": "PASS" if frontier_ok else "NOT_CONFIGURED", "implementation": "ApodexAI/FrontierAgent", "description": "ReAct + AgentTeam executor"},
        {"id": "multica",       "label": "Multica",         "type": "executor",   "status": "NOT_CONFIGURED", "implementation": "multica-ai/multica", "description": "Agent daemon + lifecycle"},
        {"id": "ecc_skills",    "label": "ECC Skills",      "type": "skill",      "status": "PASS",        "implementation": "affaan-m/ecc", "description": "Hooks, rules, learning loop"},
        {"id": "voicestudio",   "label": "VoiceStudio",     "type": "capability", "status": "NOT_CONFIGURED", "implementation": "debpalash/VoiceStudio", "description": "ASR + TTS (AGPL boundary)"},
        {"id": "opencode",      "label": "OpenCode",        "type": "ide",        "status": "NOT_CONFIGURED", "description": "AI coding IDE adapter"},
        {"id": "hermes",        "label": "Hermes",          "type": "ide",        "status": "PASS",        "description": "Primary AEGIS agent harness"},
        {"id": "l5_governance", "label": "L5 Governance",   "type": "core",       "status": "PASS",        "description": "Deterministic security layer"},
    ]
    edges = [
        {"source": "aegis_core", "target": "context"},
        {"source": "aegis_core", "target": "planner"},
        {"source": "aegis_core", "target": "memory"},
        {"source": "context", "target": "memory"},
        {"source": "context", "target": "obsidian"},
        {"source": "planner", "target": "capabilities"},
        {"source": "planner", "target": "model_router"},
        {"source": "capabilities", "target": "frontier"},
        {"source": "capabilities", "target": "multica"},
        {"source": "capabilities", "target": "ecc_skills"},
        {"source": "capabilities", "target": "voicestudio"},
        {"source": "capabilities", "target": "opencode"},
        {"source": "capabilities", "target": "hermes"},
        {"source": "frontier", "target": "l5_governance"},
        {"source": "multica", "target": "l5_governance"},
        {"source": "frontier", "target": "memory", "label": "results"},
        {"source": "hermes", "target": "memory", "label": "sessions"},
    ]
    return {"nodes": nodes, "edges": edges}

@app.get("/api/voice/status")
async def api_voice_status():
    """Returns current VoiceStudio/audio layer status."""
    import shutil
    whisper_ok = bool(shutil.which("whisper") or shutil.which("whisperx"))
    return {
        "engine": "VoiceStudio (AGPL boundary)",
        "available": whisper_ok,
        "mic_state": "OFF",
        "tts_state": "IDLE",
        "recent_transcripts": []
    }

@app.post("/api/voice/transcribe")
async def api_voice_transcribe(request: Request):
    from backend.integrations.voicestudio.adapter import voice_studio
    body = await request.json()
    audio_b64 = body.get("audio", "")
    transcript = await voice_studio.transcribe(audio_b64.encode())
    return {"transcript": transcript}

@app.post("/api/voice/speak")
async def api_voice_speak(request: Request):
    from backend.integrations.voicestudio.adapter import voice_studio
    body = await request.json()
    text = body.get("text", "")
    await voice_studio.speak(text)
    return {"status": "ok", "audio_url": None}

@app.get("/api/health/doctor")
async def api_health_doctor():
    """AEGIS Doctor — checks all connected systems and returns pass/warn/fail for each."""
    import shutil
    from pathlib import Path
    from backend.frontier_adapter import frontier_adapter
    from backend.config import cfg

    checks = []
    def chk(name, ok, msg=""):
        checks.append({"name": name, "status": "PASS" if ok else "FAIL", "message": msg})

    # Core
    chk("AEGIS Core", True, "Executive layer active")
    chk("Backend API", True, "FastAPI serving requests")

    # Memory
    try:
        from backend.mem0_engine import mem0_engine
        chk("Memory (mem0)", True, "mem0 engine initialized")
    except Exception as e:
        chk("Memory (mem0)", False, str(e))

    # Obsidian
    vault = Path(cfg.OBSIDIAN_VAULT) if hasattr(cfg, "OBSIDIAN_VAULT") else None
    if vault is None:
        try:
            from backend.server import VAULT
            vault = VAULT
        except Exception:
            vault = None
    chk("Obsidian Vault", vault is not None and vault.exists(), f"{vault}")

    # Model Router
    try:
        from backend.free_router import get_free_router_health
        h = get_free_router_health()
        chk("Model Router", h.get("status") in ("running", "online", "degraded"), h.get("engine", "free_router"))
    except Exception as e:
        chk("Model Router", False, str(e))

    # FrontierAgent
    fa = frontier_adapter.is_available()
    chk("FrontierAgent", fa.get("installed", False), fa.get("reason", ""))

    # Multica
    checks.append({"name": "Multica", "status": "NOT_CONFIGURED", "message": "Daemon not running"})

    # ECC Skills
    from backend.integrations.ecc.adapter import ecc_registry
    chk("ECC Skills", True, f"{len(ecc_registry.skills)} skills registered")

    # VoiceStudio
    whisper_ok = bool(shutil.which("whisper") or shutil.which("whisperx"))
    checks.append({"name": "VoiceStudio", "status": "PASS" if whisper_ok else "NOT_CONFIGURED", "message": "ASR binary " + ("found" if whisper_ok else "not found")})

    # Hermes
    hermes_ok = Path("/home/adarshjii/.hermes/hermes-agent/venv/bin/python").exists()
    chk("Hermes Agent", hermes_ok, "")

    # OpenCode
    opencode_ok = bool(shutil.which("opencode"))
    checks.append({"name": "OpenCode", "status": "PASS" if opencode_ok else "NOT_CONFIGURED", "message": ""})

    # Git
    git_ok = bool(shutil.which("git"))
    chk("Git", git_ok, "")

    # Ingest Daemon
    from backend.ingest_daemon import ingest_daemon
    chk("Ingest Daemon", ingest_daemon.running, "Background polling active")

    return {"checks": checks}

@app.get("/api/ide-adapters")
async def api_ide_adapters():
    """Returns status of all discovered AI IDE/agent adapters."""
    import shutil
    adapters = [
        {
            "id": "hermes", "name": "Hermes Agent",
            "installed": Path("/home/adarshjii/.hermes/hermes-agent/venv/bin/python").exists(),
            "capabilities": ["coding", "research", "chat"],
            "memory_bridge": True, "context_bridge": True,
        },
        {
            "id": "opencode", "name": "OpenCode",
            "installed": bool(shutil.which("opencode")),
            "capabilities": ["coding"],
            "memory_bridge": False, "context_bridge": False,
        },
        {
            "id": "frontier", "name": "FrontierAgent",
            "installed": Path("/home/adarshjii/Work/FrontierAgent/.venv").exists(),
            "capabilities": ["frontier.react", "frontier.agent_team", "research"],
            "memory_bridge": True, "context_bridge": True,
        },
        {
            "id": "multica", "name": "Multica",
            "installed": False,
            "capabilities": ["agent_management", "task_assignment"],
            "memory_bridge": False, "context_bridge": False,
        },
        {
            "id": "claude", "name": "Claude (Anthropic)",
            "installed": bool(shutil.which("claude")),
            "capabilities": ["coding", "research", "reasoning"],
            "memory_bridge": False, "context_bridge": False,
        },
    ]
    for a in adapters:
        a["status"] = "AVAILABLE" if a["installed"] else "NOT_CONFIGURED"
    return {"adapters": adapters}


@app.post("/api/agent/{name}/start")
async def api_agent_start(name: str, request: Request):
    safe_agent_id(name)
    body = {}
    try:
        body = await request.json()
    except Exception:
        body = {}
    cwd = body.get("cwd") if isinstance(body, dict) else None
    cwd = safe_path(cwd) if cwd else None  # raises 403 outside allowed area
    session = manager.get_or_create_session(name, cwd=cwd)
    return {"status": "running" if session.is_running else "stopped", "agent": name, "cwd": str(session.cwd)}

@app.post("/api/agent/{name}/stop")
async def api_agent_stop(name: str):
    manager.stop_session(name)
    return {"status": "stopped", "agent": name}

@app.post("/api/agent/{name}/restart")
async def api_agent_restart(name: str):
    session = manager.restart_session(name)
    return {"status": "running" if session.is_running else "stopped", "agent": name}

@app.get("/api/agent/{name}/status")
async def api_agent_status(name: str):
    session = manager.sessions.get(name)
    return {"agent": name, "running": session.is_running if session else False}


# ── LM Studio local model management ───────────────────────────────────────────
# LM Studio exposes a v1 REST API on port 1234 by default (http://127.0.0.1:1234).
# The dashboard's "Load Qwen" / "Unload Qwen" buttons call these endpoints, which
# proxy to LM Studio.  If LM Studio is not running these endpoints return 503.
#
# Qwen uncensored model slot is pinned to `lmstudio/local-qwen` in the frontend
# selector so the user can pick it from the pill bar and load/unload at will.
#
# Model management:
#   GET  /api/local-model/status   → list models LM Studio knows about + load state
#   POST /api/local-model/load     → POST /api/v1/models/load  { "model": "<id>" }
#   POST /api/local-model/unload   → POST /api/v1/models/unload { "model": "<id>" }
#   POST /api/local-model/download → POST /api/v1/models/download { "model": "<id>" }
#
# The default Qwen id used by the frontend toggle is LMSTUDIO_LOCAL_QWEN_ID from
# backend/config.py (falls back to "lmstudio/qwen2.5-7b-instruct" when unset).

LMSTUDIO_BASE = "http://127.0.0.1:1234"
LMSTUDIO_LOCAL_QWEN_ID = getattr(cfg, "LMSTUDIO_LOCAL_QWEN_ID", None) or "lmstudio/qwen2.5-7b-instruct"


async def _lmstudio_request(method: str, path: str, payload: dict | None = None, timeout: float = 60.0) -> dict:
    """Proxy a request to LM Studio's API. Returns {"ok": True, "data": ...}
    or {"ok": False, "error": "..."}. Uses LM STUDIO PORT from env or 41343.
    LM Studio also exposes /api/v1/models/loaded when supported; fall back.
    """
    import httpx
    url = f"{LMSTUDIO_BASE}{path}"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(method, url, json=payload)
            if resp.status_code in {200, 201, 202, 204}:
                text = resp.text.strip()
                if not text:
                    return {"ok": True, "data": None}
                try:
                    return {"ok": True, "data": resp.json()}
                except Exception:
                    return {"ok": True, "data": text}
            return {"ok": False, "error": f"LM Studio HTTP {resp.status_code}: {resp.text[:200]}"}
    except httpx.ConnectError:
        return {"ok": False, "error": "LM Studio not reachable — is it running on port 1234?"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/local-model/status")
async def api_local_model_status():
    """List models visible to LM Studio and whether any are currently loaded."""
    # LM Studio /api/v1/models returns {"models": [...]}
    # where each model has: key, display_name, size_bytes, loaded_instances, type, etc.
    r = await _lmstudio_request("GET", "/api/v1/models")
    if not r["ok"]:
        return {"models": [], "loaded": [], "error": r.get("error")}
    raw = r["data"]
    models_list: list[dict] = []
    data = raw.get("models") if isinstance(raw, dict) else raw
    if isinstance(data, list):
        for entry in data:
            if not isinstance(entry, dict):
                continue
            mid = entry.get("key") or entry.get("id") or entry.get("name") or entry.get("display_name") or ""
            models_list.append({
                "id": mid,
                "name": entry.get("display_name") or entry.get("name") or mid,
                "size": entry.get("size_bytes") or entry.get("size") or "",
                "type": entry.get("type") or "",
                "loaded": bool(entry.get("loaded_instances")),
            })
    return {"models": models_list, "loaded": [], "error": None}


@app.post("/api/local-model/load")
async def api_local_model_load(request: Request):
    """Load a model into LM Studio memory.

    Idempotent: if the model already has a loaded instance, return it instead of
    spawning a duplicate (LM Studio would otherwise create `key:2`, `key:3`, ...).
    No auth required beyond the chat-session middleware — local HMI action.
    """
    body = await request.json()
    model_id = body.get("model") if body else None
    if not model_id:
        model_id = LMSTUDIO_LOCAL_QWEN_ID

    # Check for an existing loaded instance first.
    status_r = await _lmstudio_request("GET", "/api/v1/models", timeout=30.0)
    if status_r["ok"]:
        data = status_r.get("data")
        models_list = data.get("models", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        for m in models_list:
            if not isinstance(m, dict) or (m.get("key") or m.get("id") or "") != model_id:
                continue
            instances = m.get("loaded_instances") or []
            if instances:
                return {"status": "already-loaded", "model": model_id,
                        "instance_id": instances[0].get("id")}

    r = await _lmstudio_request("POST", "/api/v1/models/load", {"model": model_id}, timeout=180.0)
    if not r["ok"]:
        raise HTTPException(status_code=503, detail=r.get("error", "Failed to load model in LM Studio"))
    return {"status": "loaded", "model": model_id}


@app.post("/api/local-model/unload")
async def api_local_model_unload(request: Request):
    """Unload a model from LM Studio memory.

    LM Studio's /api/v1/models/unload requires ``instance_id`` (the per-load
    session id), not the model ``key``.  Resolve it from /api/v1/models first.
    No auth required — this is a local HMI action.
    Defaults to the Qwen uncensored slot configured in config.LMSTUDIO_LOCAL_QWEN_ID.
    """
    body = await request.json()
    model_id = body.get("model") if body else None
    if not model_id:
        model_id = LMSTUDIO_LOCAL_QWEN_ID

    # Resolve instance_id from the loaded_instances list on the model entry.
    models_r = await _lmstudio_request("GET", "/api/v1/models", timeout=30.0)
    instance_id: str | None = None
    if models_r["ok"]:
        data = models_r.get("data")
        if isinstance(data, dict):
            models_list = data.get("models") or []
        elif isinstance(data, list):
            models_list = data
        else:
            models_list = []
        for m in models_list:
            if not isinstance(m, dict):
                continue
            key = m.get("key") or m.get("id") or ""
            if key != model_id:
                continue
            for inst in (m.get("loaded_instances") or []):
                iid = inst.get("id") if isinstance(inst, dict) else None
                if iid:
                    instance_id = iid
                    break
            if instance_id:
                break

    if not instance_id:
        raise HTTPException(status_code=404, detail=f"Model {model_id!r} is not loaded in LM Studio")

    r = await _lmstudio_request(
        "POST", "/api/v1/models/unload",
        {"instance_id": instance_id}, timeout=30.0
    )
    if not r["ok"]:
        raise HTTPException(status_code=503, detail=r.get("error", "Failed to unload model from LM Studio"))
    return {"status": "unloaded", "model": model_id, "instance_id": instance_id}


@app.post("/api/local-model/download")
async def api_local_model_download(request: Request):
    """Request LM Studio to download a model from the HuggingFace hub.
    Body: {"model": "<hub-id>"} or {"model_id": "<hub-id>"}.
    Returns immediately; poll /api/local-model/status for progress.
    No auth required — this is a local HMI action."""
    body = await request.json()
    model_id = body.get("model") or body.get("model_id") or body.get("model_name")
    if not model_id:
        raise HTTPException(status_code=400, detail="model id required")
    r = await _lmstudio_request("POST", "/api/v1/models/download", {"model": model_id}, timeout=120.0)
    if not r["ok"]:
        raise HTTPException(status_code=503, detail=r.get("error", "Failed to start download in LM Studio"))
    return {"status": "downloading", "model": model_id}

# ── Cognitive, Vision & Deep Diagnostics ───────────────────────────────────────

@app.get("/api/search/unified")
async def api_search_unified(q: str = "", limit: int = 15):
    if not q.strip():
        return []
    return knowledge_graph.unified_search(q.strip(), limit=limit)

@app.get("/api/diagnostics/deep")
async def api_diagnostics_deep():
    # 1. Model fabric health & stats
    health = await query_model_health()
    
    # 2. Vision status
    vis_status = vision_engine.get_camera_status()
    
    # 3. Agents status check (dynamically from AGENT_REGISTRY)
    agents_state = {}
    for ag in cfg.AGENT_REGISTRY:
        aid = ag.get("id")
        cmd = cfg.resolve_agent_command(aid)
        bin_path = cmd[0] if cmd else ""
        exists = Path(bin_path).exists() if bin_path else False
        agents_state[aid] = {
            "installed": exists,
            "path": bin_path,
            "command": cmd
        }

    # 4. Systemd services
    services_state = {}
    for svc in ["aegis-backend.service", "aegis-frontend.service", "aegis-consolidate.timer"]:
        try:
            res = subprocess.run(["systemctl", "--user", "is-active", svc], capture_output=True, text=True, timeout=2)
            services_state[svc] = res.stdout.strip()
        except Exception:
            services_state[svc] = "unknown"

    return {
        "timestamp": datetime.now().isoformat(),
        "status": "HEALTHY",
        "router": health,
        "model_router_stats": model_router.stats,
        "vision": vis_status,
        "agents": agents_state,
        "systemd": services_state,
        "knowledge_graph": {
            "nodes": len(knowledge_graph.nodes),
            "edges": len(knowledge_graph.edges)
        },
        "vault_markdown_count": len(get_vault_markdown_files())
    }

@app.get("/api/vision/status")
async def api_vision_status():
    return vision_engine.get_camera_status()

@app.post("/api/vision/camera-toggle")
async def api_vision_toggle(request: Request):
    body = await request.json()
    enabled = bool(body.get("enabled", False))
    return vision_engine.set_camera_state(enabled)

# ==============================================================================
# Camera & Vision Endpoints (Phase C5)
# ==============================================================================

@app.get("/api/cameras")
async def get_cameras():
    return {"cameras": camera_registry.cameras}

@app.post("/api/cameras/discover")
async def discover_cameras():
    discovered = camera_registry.discover_cameras()
    return {"status": "success", "discovered": discovered}

@app.post("/api/cameras/{cam_id}/authorize")
async def authorize_camera(cam_id: str):
    if camera_registry.authorize_camera(cam_id):
        return {"status": "success", "authorized": True}
    raise HTTPException(status_code=404, detail="Camera not found")

@app.post("/api/cameras/{cam_id}/vision/enable")
async def enable_camera_vision(cam_id: str):
    if camera_registry.enable_vision(cam_id):
        return {"status": "success", "vision_enabled": True}
    raise HTTPException(status_code=403, detail="Camera not authorized or not found")

@app.get("/api/cameras/{cam_id}/events")
async def get_camera_events(cam_id: str):
    return {"events": camera_event_store.get_recent_events(camera_id=cam_id)}

@app.post("/api/cameras/{cam_id}/test_vision")
async def test_camera_vision(cam_id: str):
    # Retrieve camera to test real capture
    cam = camera_registry.cameras.get(cam_id)
    if not cam or not cam.get("vision_enabled"):
        raise HTTPException(status_code=403, detail="Vision not enabled for camera")
        
    # Test frame capture
    frame = vision_engine.capture_frame(cam["uri"])
    if frame is None:
        return {"status": "failed", "reason": "Failed to capture frame"}
        
    event = vision_engine.process_motion(frame, cam_id)
    if event:
        camera_event_store.store_event(event)
        
    return {"status": "success", "motion_event_generated": bool(event)}

@app.get("/api/memory/temporal")
async def api_memory_temporal(timeframe: str = "today"):
    return cognitive_memory.query_temporal_activity(timeframe)

# ── Agent Supervisor Endpoints ───────────────────────────────────────────────
@app.get("/api/supervisor/tasks")
async def api_supervisor_tasks():
    return {"active_tasks": agent_supervisor.active_tasks}

@app.post("/api/supervisor/dispatch")
async def api_supervisor_dispatch(request: Request):
    body = await request.json()
    project = body.get("project", "aegis-dashboard")
    goal = body.get("goal", "")
    subtasks = body.get("subtasks", [])
    if not goal:
        raise HTTPException(400, "Goal is required")
    task_id = agent_supervisor.dispatch_project_task(project, goal, subtasks)
    return {"status": "dispatched", "task_id": task_id}

@app.get("/api/supervisor/tasks/{task_id}")
async def api_supervisor_task_status(task_id: str):
    return agent_supervisor.get_task_status(task_id)

# ── Governance Endpoints ─────────────────────────────────────────────────────
@app.get("/api/governance")
async def api_governance_get():
    return {
        "autonomy_level": int(governance.current_level),
        "level_name": governance.current_level.name,
    }

@app.post("/api/governance/level")
async def api_governance_set_level(request: Request):
    body = await request.json()
    level = body.get("level")
    if level is None or not (0 <= level <= 5):
        raise HTTPException(400, "Level must be between 0 and 5")
    governance.set_autonomy_level(level)
    return {
        "status": "ok",
        "autonomy_level": int(governance.current_level),
        "level_name": governance.current_level.name,
    }

# ── Context Router Endpoint ──────────────────────────────────────────────────
@app.get("/api/context/assemble")
async def api_context_assemble(q: str):
    return context_router.assemble_context(q)

# ── TurboQuant Semantic Store Endpoints ──────────────────────────────────────
@app.get("/api/turboquant/search")
async def api_turboquant_search(q: str, limit: int = 5):
    return {"results": turboquant_store.search(q, limit=limit)}

@app.post("/api/turboquant/ingest")
async def api_turboquant_ingest(request: Request):
    body = await request.json()
    source_id = body.get("source_id", "manual")
    content = body.get("content", "")
    metadata = body.get("metadata", {})
    if not content:
        raise HTTPException(400, "Content cannot be empty")
    turboquant_store.ingest(source_id, content, metadata)
    return {"status": "ok", "source_id": source_id}

# ── Mem0 Personalized Memory Layer Endpoints ─────────────────────────────────
@app.post("/api/memory/mem0/add")
async def api_mem0_add(request: Request):
    body = await request.json()
    text = body.get("text", "")
    if not text:
        raise HTTPException(400, "Text is required")
    mem = mem0_engine.add(
        text=text,
        user_id=body.get("user_id", "adarshjii"),
        agent_id=body.get("agent_id", "default"),
        category=body.get("category", "general"),
        metadata=body.get("metadata", {}),
    )
    return {"status": "ok", "memory": mem}

@app.get("/api/memory/mem0/search")
async def api_mem0_search(q: str, limit: int = 5):
    return {"results": mem0_engine.search(q, limit=limit)}

@app.get("/api/memory/mem0/all")
async def api_mem0_all(limit: int = 50):
    return {"memories": mem0_engine.get_all(limit=limit)}

# ── FrontierAgent Execution Backend Endpoints ────────────────────────────
@app.get("/api/frontier/status")
async def api_frontier_status():
    return frontier_adapter.is_available()

@app.post("/api/frontier/run")
async def api_frontier_run(request: Request):
    body = await request.json()
    task = body.get("task", "")
    if not task:
        raise HTTPException(400, "task required")
    # Compatibility route: execution still enters through the AEGIS-owned
    # task lifecycle.  Callers cannot inject arbitrary cwd or bypass L5.
    mode = body.get("mode", "react")
    record = execution_core.create(task, project=body.get("project", ""), kind="research",
                                   parallelism=2 if mode == "agent_team" else 1,
                                   long_horizon=True, requested_agent="frontier")
    return execution_core.dispatch(record["id"], auto_approve=bool(body.get("auto_approve", False)),
                                   timeout=int(body.get("timeout", 600)))

@app.get("/api/executions")
async def api_executions(limit: int = 50):
    return {"tasks": execution_core.list(limit=limit)}

@app.get("/api/executions/{task_id}")
async def api_execution(task_id: str):
    record = execution_core.get(task_id)
    if not record:
        raise HTTPException(404, "AEGIS task not found")
    return record

@app.post("/api/executions")
async def api_execution_create(request: Request):
    body = await request.json()
    task = str(body.get("task", "")).strip()
    if not task:
        raise HTTPException(400, "task required")
    return execution_core.create(task, project=str(body.get("project", "")), kind=str(body.get("kind", "general")),
                                 parallelism=max(1, int(body.get("parallelism", 1))),
                                 long_horizon=bool(body.get("long_horizon", False)),
                                 requested_agent=str(body.get("requested_agent", "")))

@app.post("/api/executions/{task_id}/dispatch")
async def api_execution_dispatch(task_id: str, request: Request):
    body = await request.json()
    return execution_core.dispatch(task_id, auto_approve=bool(body.get("auto_approve", False)),
                                   timeout=min(3600, max(1, int(body.get("timeout", 600)))))

@app.get("/api/agents/registry")
async def api_agents_registry():
    return {"agents": execution_core.registry()}

@app.get("/api/frontier/runs")
async def api_frontier_runs(limit: int = 20):
    return {"runs": frontier_adapter.list_runs(limit=limit)}

@app.get("/api/frontier/trace/{session}")
async def api_frontier_trace(session: str, limit: int = 50):
    return frontier_adapter.read_trace(session, limit=limit)

@app.get("/api/frontier/context-pack")
async def api_frontier_context_pack(project: str = "", task: str = ""):
    return {"pack": frontier_adapter.build_context_pack(project, task)}

# ── Spatial Mode (one-by-one multi-project lanes) ───────────────────────
@app.post("/api/spatial/sweep")
async def api_spatial_sweep(request: Request):
    body = await request.json()
    return lane_sweep(projects=body.get("projects"), mode=body.get("mode", "react"),
                      task=body.get("task", ""), dry_run=bool(body.get("dry_run", True)),
                      max_turns=int(body.get("max_turns", 20)),
                      auto_approve=bool(body.get("auto_approve", False)))

@app.get("/api/spatial/status")
async def api_spatial_status(limit: int = 20):
    return sweep_status(limit=limit)

# ── Org Cameras (credential-vault gated, default HARD_DENY) ─────────────
def _org_hub():
    return OrgCameraHub()

@app.get("/api/org-cameras/status")
async def api_org_cameras_status():
    return _org_hub().status()

@app.post("/api/org-cameras/configure")
async def api_org_cameras_configure(request: Request):
    body = await request.json()
    targets = body.get("targets", [])
    if not isinstance(targets, list) or not targets:
        raise HTTPException(400, "targets list required (no passwords — vault/env only)")
    return _org_hub().configure(targets)

@app.post("/api/org-cameras/{cam_id}/authorize")
async def api_org_cameras_authorize(cam_id: str):
    if _org_hub().authorize(cam_id):
        return {"status": "authorized", "cam_id": cam_id}
    raise HTTPException(404, "camera not found or vault locked")

# ── Preferences (user profile / style / product) ────────────────────────
@app.get("/api/preferences")
async def api_preferences_all():
    return {"sections": preferences.get_sections(), "profile": preferences.get_profile()}

@app.get("/api/preferences/{section}")
async def api_preferences_section(section: str):
    return {"section": section, "prefs": preferences.get_section(section)}

@app.post("/api/preferences/set")
async def api_preferences_set(request: Request):
    body = await request.json()
    for k in ("section", "key", "value"):
        if k not in body:
            raise HTTPException(400, f"{k} required")
    return preferences.set_pref(body["section"], body["key"], body["value"],
                                source=body.get("source", "user"), confidence=float(body.get("confidence", 1.0)))

@app.post("/api/preferences/confirm")
async def api_preferences_confirm(request: Request):
    body = await request.json()
    if "section" not in body or "key" not in body:
        raise HTTPException(400, "section+key required")
    return preferences.confirm_pref(body["section"], body["key"])

@app.get("/api/preferences/resolve/{key}")
async def api_preferences_resolve(key: str):
    return preferences.resolve(key)

# ── Research Lab (profiles + scoped sessions + experiments) ─────────────
@app.get("/api/lab/profile/{name}")
async def api_lab_profile(name: str):
    try:
        p = research_lab.get_profile(name)
    except Exception:
        raise HTTPException(404, "unknown profile (STANDARD/RESEARCH_LAB/RED_TEAM_LAB)")
    return {"name": name, "temperature": p.temperature, "max_turns": p.max_turns,
            "max_concurrency": p.max_concurrency, "requires_lab_target": p.requires_lab_target}

@app.post("/api/lab/authorize")
async def api_lab_authorize(request: Request):
    body = await request.json()
    if "target_id" not in body:
        raise HTTPException(400, "target_id required")
    rec = research_lab.authorize_session(body["target_id"], body.get("capabilities", []),
                                         ttl_min=int(body.get("ttl_min", 60)))
    return research_lab.public_session(rec)

@app.post("/api/lab/check")
async def api_lab_check(request: Request):
    body = await request.json()
    return {"result": research_lab.check(body.get("target_id", ""), body.get("capability", ""))}

@app.post("/api/lab/experiment")
async def api_lab_experiment(request: Request):
    body = await request.json()
    exp_id = body.get("exp_id", f"exp-{int(time.time())}")
    body.pop("exp_id", None)
    path = research_lab.write_experiment(exp_id, **{k: v for k, v in body.items() if isinstance(v, (str, int, float))})
    return {"exp_id": exp_id, "path": str(path)}

# ── Universal Ingest (bounded pass over agent sessions) ─────────────────
@app.post("/api/ingest/run")
async def api_ingest_run(request: Request):
    from backend.universal_ingest.pipeline import run as ingest_run
    body = {}
    try:
        body = await request.json()
    except Exception:
        body = {}
    return ingest_run(max_per_agent=int(body.get("max_per_agent", 3)))

# ── Learn Loop (single bounded auto-research run) ───────────────────────
@app.post("/api/learn/run")
async def api_learn_run(request: Request):
    import sys as _sys
    body = {}
    try:
        body = await request.json()
    except Exception:
        body = {}
    topic = (body.get("topic") or "").strip() or None
    script = cfg.REPO_ROOT / "scripts" / "learn_loop.py"
    if not script.exists():
        raise HTTPException(404, "learn_loop.py not installed")
    cmd = [_sys.executable, str(script)]
    if topic:
        cmd += ["--topic", topic]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1500,
                           cwd=str(cfg.REPO_ROOT), env=cfg.get_agent_env())
        return {"status": "ok" if r.returncode == 0 else "failed",
                "returncode": r.returncode,
                "stdout_tail": (r.stdout or "")[-1500:], "stderr_tail": (r.stderr or "")[-800:]}
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "learn run exceeded 25 min budget")

# ── Cloudroom Workspace & Command Guard Endpoints ────────────────────────────
@app.get("/api/cloudroom/workspaces")
async def api_cloudroom_workspaces():
    return {"workspaces": cloudroom_bridge.get_workspaces()}

@app.post("/api/cloudroom/guard")
async def api_cloudroom_guard(request: Request):
    body = await request.json()
    command = body.get("command", "")
    if not command:
        raise HTTPException(400, "Command required")
    return cloudroom_bridge.validate_command(command, body.get("workspace"))


@app.post("/api/planner/create-plan")
async def api_planner_create_plan(request: Request):
    body = await request.json()
    goal = body.get("goal", "")
    if not goal:
        raise HTTPException(400, "Goal cannot be empty")
    plan = hierarchical_planner.create_plan(goal)
    return plan.to_dict()

@app.post("/api/planner/execute-plan")
async def api_planner_execute_plan(request: Request):
    """Execute a previously created plan or create+execute in one shot."""
    body = await request.json()
    goal = body.get("goal", "")
    if not goal:
        raise HTTPException(400, "Goal cannot be empty")
    plan = hierarchical_planner.create_plan(goal)
    executed = hierarchical_planner.execute_plan(plan)
    result = executed.to_dict()
    # Attach tool results for each step
    return result

@app.get("/api/agentmoe/tools")
async def api_agentmoe_tools():
    """Return the list of available AgentMoe tools with metadata."""
    return {
        "tools": list(agent_moe.tools.keys()),
        "worker_roles": agent_moe.worker_roles,
        "tool_count": len(agent_moe.tools)
    }

@app.post("/api/agentmoe/discover")
async def api_agentmoe_discover(request: Request):
    """Given a goal string, return the best capability match."""
    body = await request.json()
    goal = body.get("goal", "")
    if not goal:
        raise HTTPException(400, "Goal required")
    return agent_moe.discover_capability(goal)

@app.post("/api/agentmoe/execute")
async def api_agentmoe_execute(request: Request):
    """Execute a list of tool subtasks directly via AgentMoe."""
    body = await request.json()
    subtasks = body.get("subtasks", [])
    if not subtasks:
        raise HTTPException(400, "subtasks list cannot be empty")
    return agent_moe.execute_plan(subtasks)

@app.get("/api/audio/status")
async def api_audio_status():
    return audio_engine.get_audio_status()

@app.post("/api/audio/mic-toggle")
async def api_audio_mic_toggle(request: Request):
    body = await request.json()
    enabled = bool(body.get("enabled", False))
    return audio_engine.set_mic_state(enabled)

@app.get("/api/screen/intel")
async def api_screen_intel():
    return screen_intel.analyze_screen_multimodal()

@app.post("/api/research/start")
async def api_research_start(request: Request):
    body = await request.json()
    topic = body.get("topic", "")
    if not topic:
        raise HTTPException(400, "Topic required")
    depth = body.get("depth", "standard")
    return research_engine.conduct_research(topic, depth=depth)

@app.post("/api/sandbox/execute")
async def api_sandbox_execute(request: Request):
    body = await request.json()
    code = body.get("code", "")
    lang = body.get("language", "python")
    return code_sandbox.execute_sandboxed(code, language=lang)

@app.get("/api/health")
async def api_health():
    return {"status": "ok", "service": "aegis-backend", "host": cfg.HOST, "port": cfg.BACKEND_PORT}

@app.get("/api/monitor/health")
async def api_monitor_health():
    return proactive_monitor.scan_project_health()

@app.get("/api/health/full")
async def api_health_full():
    return aegis_health.run_all_checks()

@app.get("/api/intelligence")
async def api_intelligence():
    """Unifies host telemetry and project state into a single God Mode intelligence view."""
    return {
        "host": linux_intelligence.get_host_overview(),
        "projects": {p: project_intelligence.get_project_summary(p) for p in cfg.PROJECTS.keys()}
    }



@app.websocket("/ws/agent/{name}")
async def websocket_agent_endpoint(websocket: WebSocket, name: str):
    await websocket.accept()
    session = manager.get_or_create_session(name)
    session.subscribers.append(websocket)
    
    # Replay buffered history for instant display
    for chunk in list(session.history):
        try:
            await websocket.send_json({"type": "output", "data": chunk})
        except Exception:
            break

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                mtype = msg.get("type")
                if mtype == "input":
                    session.write(msg.get("data", ""))
                elif mtype == "resize":
                    cols = msg.get("cols", 80)
                    rows = msg.get("rows", 24)
                    session.resize(rows, cols)
            except json.JSONDecodeError:
                session.write(data)
    except WebSocketDisconnect:
        if websocket in session.subscribers:
            session.subscribers.remove(websocket)

# ── Orchestrator Task Classification ──────────────────────────────────────────

def classify_task_orchestrator(message: str) -> dict:
    """Classify message into a tier and route to the appropriate model via cfg.MODEL_*."""
    msg_lower = message.lower()

    # Coding & Full-Stack Development
    if any(k in msg_lower for k in ["code", "script", "program", "function", "refactor", "bug", "python", "javascript", "react", "html", "css", "rust", "build a", "write a", "implement"]):
        return {
            "domain": "Code Synthesis & Software Engineering",
            "complexity": "High",
            "tier_id": "tier_2_coding",
            "tier_name": "Tier 2: High-End Code Synthesis",
            "primary": cfg.MODEL_DEFAULT,
            "fallback": cfg.MODEL_FAST,
            "target_agent": "codex",
            "target_tab": "Codex"
        }

    # Deep Mathematical & Extended Chain-of-Thought Reasoning
    if any(k in msg_lower for k in ["think deeply", "prove", "proof", "theorem", "math", "algorithm", "derive", "chain of thought", "logic puzzle", "reason through"]):
        return {
            "domain": "Mathematical Proof & Deep Reasoning",
            "complexity": "Deep Reasoning",
            "tier_id": "tier_3_deep_thinking",
            "tier_name": "Tier 3: Mathematical Proof & Extended Thinking",
            "primary": cfg.MODEL_DEFAULT,
            "fallback": cfg.MODEL_REASONING,
            "target_agent": "deepseek",
            "target_tab": "DeepSeek R1"
        }

    # Frontier Architecture & System Design
    if any(k in msg_lower for k in ["architecture", "design pattern", "system design", "compare", "tradeoff", "strategy", "karpathy", "paradigm"]):
        return {
            "domain": "Frontier Architecture & Synthesis",
            "complexity": "Architectural",
            "tier_id": "tier_1_frontier",
            "tier_name": "Tier 1: Frontier Architecture & Reasoning",
            "primary": cfg.MODEL_DEFAULT,
            "fallback": cfg.MODEL_REASONING,
            "target_agent": "claude",
            "target_tab": "Claude Code"
        }

    # Multimodal & Vision
    if any(k in msg_lower for k in ["image", "screenshot", "diagram", "chart", "ui layout", "visual", "ocr"]):
        return {
            "domain": "Multimodal Vision & Diagram Analysis",
            "complexity": "Multimodal",
            "tier_id": "tier_4_multimodal",
            "tier_name": "Tier 4: Multimodal Vision & Diagram Analysis",
            "primary": cfg.MODEL_DEFAULT,
            "fallback": cfg.MODEL_FAST,
            "target_agent": "hermes",
            "target_tab": "Hermes (agies)"
        }

    # System Administration & Host Telemetry
    if any(k in msg_lower for k in ["pc", "telemetry", "ram", "memory", "storage", "disk", "process", "port", "network", "systemctl"]):
        return {
            "domain": "System Administration & Host Telemetry",
            "complexity": "Real-time Telemetry",
            "tier_id": "tier_5_fast_throughput",
            "tier_name": "Tier 5: Ultra-Fast Throughput & Telemetry",
            "primary": cfg.MODEL_FAST,
            "fallback": cfg.MODEL_LITE,
            "target_agent": "hermes",
            "target_tab": "Hermes (agies)"
        }

    # Default General Knowledge & Vault
    return {
        "domain": "General Knowledge & Vault Retrieval",
        "complexity": "Standard",
        "tier_id": "tier_1_frontier",
        "tier_name": "Tier 1: Frontier Architecture & Reasoning",
        "primary": cfg.MODEL_DEFAULT,
        "fallback": cfg.MODEL_FAST,
        "target_agent": "hermes",
        "target_tab": "Hermes (agies)"
    }

# ── Free Model Live Query & Failover ──────────────────────────────────────────

def next_chat_model() -> str:
    """Pick next healthy free model from pool."""
    from backend.free_router import pick_next_model
    return pick_next_model()

async def _query_free_router(messages: list, model: str) -> tuple[str, str]:
    """Route to AEGIS free model fabric (OpenRouter / Groq / local)."""
    from backend.free_router import query_free_chat
    return await query_free_chat(messages, model)

# ── Chat endpoint ──────────────────────────────────────────────────────────────

@app.post("/api/chat")
async def api_chat(request: Request):
    body = await request.json()
    user_message = body.get("message", "")
    history = body.get("history", [])
    model = body.get("model", "")
    
    classification = classify_task_orchestrator(user_message)
    if not model or model == "auto":
        active_model = next_chat_model()
    else:
        active_model = model

    response, actual_model = await generate_chat_response(user_message, history, active_model)
    
    return {
        "content": response,
        "timestamp": datetime.now().isoformat(),
        "model": actual_model,
        "classification": classification
    }


async def query_lmstudio_chat(messages: list, model: str) -> tuple[str, str]:
    """Chat through LM Studio's OpenAI-compatible endpoint on port 1234.

    Used when the requested model is a `lmstudio/<key>` route — inference stays
    fully local and never touches any cloud router. Returns (text, actual_model).
    """
    import httpx

    key = model[len("lmstudio/"):].strip()
    if not key:
        return "⚠️ Empty local model key.", model
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                "http://127.0.0.1:1234/v1/chat/completions",
                json={"model": key, "messages": messages, "stream": False},
            )
            if resp.status_code != 200:
                return f"⚠️ LM Studio returned HTTP {resp.status_code} for `{key}`: {resp.text[:120]}", model
            data = resp.json()
            choices = data.get("choices") or []
            ans = (((choices[0] or {}).get("message") or {}).get("content") or "").strip()
            if not ans:
                return f"⚠️ LM Studio returned an empty completion for `{key}`.", model
            return ans, model
    except Exception as e:
        return f"⚠️ LM Studio not reachable for `{key}`: {e}", model


async def generate_chat_response(message: str, history: list = None, model: str = None) -> tuple[str, str]:
    msg_trimmed = message.strip()
    msg_lower = msg_trimmed.lower()
    
    # ── Slash Commands ─────────────────────────────────────────────────────────
    if msg_lower.startswith("/help"):
        return (
            "### AEGIS OS Kernel & Hermes Assistant Commands\n\n"
            "- `/pc` — Real-time telemetry, RAM, storage, top processes, network interfaces\n"
            "- `/vault [query]` — Search Obsidian PARA notes or view knowledge structure\n"
            "- `/skills` — Inspect 16 registered agent skills and capabilities\n"
            "- `/models` — View task-based model routing table and free fabric status\n"
            "- `/clear` — Wipe active session chat transcript\n"
            "- `/help` — Display this command reference\n\n"
            "You can also ask open-ended questions about your 4 projects (Aegis, chrome-extra, repusense, world-viewer), Karpathy's LLM engineering principles, software engineering, or system administration."
        ), "local/kernel"

    if msg_lower.startswith("/pc"):
        pc = get_pc_state()
        m = pc["memory"]
        d = pc["disk"]
        used_ram = round(m["used_kb"] / 1024 / 1024, 1)
        total_ram = round(m["total_kb"] / 1024 / 1024, 1)
        avail_ram = round(m["available_kb"] / 1024 / 1024, 1)
        ram_pct = round((m["used_kb"] / m["total_kb"]) * 100) if m["total_kb"] > 0 else 0

        top_proc_text = ""
        for p in pc["processes"][:4]:
            top_proc_text += f"- **PID {p['pid']}** (`{p['user']}`): {p['command'][:45]} — {p['mem']}% RAM, {p['cpu']}% CPU\n"

        net_text = ""
        for iface, info in pc["network"].items():
            if "inet" in str(info.get("addresses", [])):
                net_text += f"- `{iface}` ({info['state']}): {', '.join(info['addresses'])}\n"

        return (
            f"### [TELEMETRY] Local Machine State\n\n"
            f"**Host OS:** {pc['system'].get('PRETTY_NAME', 'Linux')} | **Time:** {datetime.now().strftime('%H:%M:%S')}\n\n"
            f"**Memory:** {used_ram} GB / {total_ram} GB used ({ram_pct}%) | {avail_ram} GB available\n"
            f"**Root Disk (/):** {d['used']} / {d['size']} ({d['use_percent']} used) | {d['avail']} free\n\n"
            f"**Top Memory Consumers:**\n{top_proc_text}\n"
            f"**Network Links:**\n{net_text or '- No active inet interfaces'}"
        ), "local/telemetry"

    if msg_lower.startswith("/vault"):
        query = msg_trimmed[6:].strip()
        if not query:
            return (
                "### Obsidian Knowledge Base (PARA Structure)\n\n"
                "- `0-Inbox/` — Incoming notes & uncurated captures\n"
                "- `1-Projects/` — Aegis (AI OS), chrome-extra, repusense, world-viewer\n"
                "- `2-Areas/` — Ongoing development standards and system configs\n"
                "- `3-Resources/` — 9Router gateways, model benchmarks, routing strategies\n"
                "- `4-Archives/` — Completed milestones & legacy code\n"
                "- `MOCs/` — Maps of Content (AI Development, System Architecture)\n\n"
                "*Tip: Provide a query like `/vault aegis` or `/vault router` to search note content.*"
            ), "local/vault"
        results = search_vault(query)
        if results:
            text = f"### Vault Search Results for \"{query}\" ({len(results)} found)\n\n"
            for r in results[:5]:
                text += f"- **[{r['name']}](file://{r['path']})** (line {r['line']}):\n  > {r['context'].strip()[:140]}...\n\n"
            return text, "local/vault"
        return f"No matches found in Obsidian vault for \"{query}\".", "local/vault"

    if msg_lower.startswith("/skills"):
        all_skills = get_skills()
        text = f"### Registered Agent Skills ({len(all_skills)})\n\n"
        for name, sk in list(all_skills.items())[:8]:
            text += f"- **`{name}`** ({sk.get('category', 'general')}): {sk.get('purpose', sk.get('description', ''))[:100]}...\n"
        text += f"\n*Use the Skills Panel in the dock to inspect complete workflows and permissions.*"
        return text, "local/skills"

    if msg_lower.startswith("/models"):
        from backend.free_router import get_free_router_health, get_round_robin_candidates
        health = get_free_router_health()
        candidates = get_round_robin_candidates()
        text = (
            f"### Active Multi-Provider Free Model Fabric\n\n"
            f"- **Router Status:** `{health['status'].upper()}`\n"
            f"- **OpenRouter Free Tier:** `{health['providers'].get('openrouter', 'offline').upper()}`\n"
            f"- **Groq Free Tier:** `{health['providers'].get('groq', 'standby').upper()}`\n"
            f"- **Active Model Pool ({len(candidates)} models):**\n"
        )
        for c in candidates[:8]:
            text += f"  - `{c}`\n"
        return text, "local/models"

    if msg_lower == "/clear":
        return "Session history cleared.", "local/kernel"

    # ── Context Injection & Real LLM Generation ────────────────────────────────
    from backend.context_router import context_router
    router_data = context_router.assemble_context(msg_trimmed)
    memory_context = get_relevant_memory_context(msg_trimmed)

    # ── mem0 Semantic Memory Retrieval ─────────────────────────────────────────
    from backend.mem0_engine import mem0_engine
    mem0_hits = mem0_engine.search(msg_trimmed, user_id="adarsh", limit=4)
    mem0_context = ""
    if mem0_hits:
        lines = [f"- [{h['category']}] {h['text']} (score:{h['score']})" for h in mem0_hits]
        mem0_context = "\n".join(lines)

    system_prompt = (
        "You are AEGIS — an intelligent, perceptive AI OS assistant.\n"
        "You are conversing directly with Adarsh (the owner of this system).\n"
        "Speak naturally, intelligently, and directly. Use only supplied context.\n"
        "You do not have execution tools in this chat endpoint; do not claim to execute tasks.\n"
        "Key projects: aegis-dashboard (web UI), aegis-python (backend core), chrome-extra (extension agent), repusense (Next.js app), world-viewer (Electron app).\n\n"
        "Guidelines:\n"
        "- Answer questions directly and insightfully.\n"
        "- Do NOT output unsolicited hardware telemetry unless asked about machine status.\n"
        "- When asked about projects, architecture, past sessions, draw upon living memory accurately.\n"
        "- Format responses cleanly with GitHub-flavored markdown."
    )

    if router_data["context_text"] and router_data["context_text"] != "No specific dynamic context required.":
        system_prompt += f"\n\n--- Dynamic Context ---\n{router_data['context_text']}\n---"
    elif memory_context:
        system_prompt += f"\n\n--- Consolidated Memory ---\n{memory_context}\n---"

    if mem0_context:
        system_prompt += f"\n\n--- Persistent Memory (AEGIS mem0) ---\n{mem0_context}\n---"

    # Build message history
    llm_messages = [{"role": "system", "content": system_prompt}]
    if history:
        for h in history[-8:]:
            role = h.get("role", "user")
            content = h.get("content", "")
            if role in ["user", "assistant"] and content:
                llm_messages.append({"role": role, "content": content})

    llm_messages.append({"role": "user", "content": message})

    from backend.free_router import query_free_chat
    result_text, actual_model = await query_free_chat(llm_messages, model)

    # ── Store interaction in mem0 for future retrieval ─────────────────────────
    try:
        mem0_engine.add(
            text=f"User asked: {message[:300]} | AEGIS replied: {result_text[:300]}",
            user_id="adarsh",
            agent_id="aegis-chat",
            category="experience",
            metadata={"model": actual_model, "session": "chat"},
        )
    except Exception:
        pass  # Never block chat on memory write failure

    return result_text, actual_model

# ── WebSocket ──────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session_id = str(uuid.uuid4())
    connections[session_id] = websocket
    
    await websocket.send_text(json.dumps({
        "type": "connected",
        "session_id": session_id,
        "timestamp": datetime.now().isoformat()
    }))
    
    # Send initial data
    try:
        from backend.free_router import get_free_router_health
        await websocket.send_text(json.dumps({
            "type": "initial_data",
            "vault": get_vault_structure(),
            "memory_files": get_memory_files(),
            "mocs_list": await api_mocs(),
            "projects_list": await api_projects(),
            "skills_data": get_skills(),
            "pc_state": get_pc_state(),
            "9router_health": get_free_router_health(),
            "timestamp": datetime.now().isoformat()
        }))
    except Exception as e:
        print(f"Error sending initial WebSocket data: {e}")
    
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            
            if msg.get("type") == "subscribe_pc":
                await websocket.send_text(json.dumps({"type": "pc_subscribed"}))
            elif msg.get("type") == "subscribe_scripts":
                await websocket.send_text(json.dumps({"type": "scripts_subscribed"}))
            elif msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong", "timestamp": datetime.now().isoformat()}))
    except WebSocketDisconnect:
        if session_id in connections:
            del connections[session_id]

@app.get("/api/logs")
async def api_logs(limit: int = 200):
    log_file = cfg.LOGS_DIR / "aegis.log"
    if not log_file.exists():
        return []
    try:
        lines = log_file.read_text(errors="replace").splitlines()
        logs = []
        for line in reversed(lines[-limit:]):
            try:
                logs.append(json.loads(line))
            except:
                pass
        return logs
    except Exception as e:
        return {"error": str(e)}

@app.on_event("startup")
async def on_startup():
    from backend.ingest_daemon import ingest_daemon
    asyncio.create_task(pc_monitor_loop())
    asyncio.create_task(ingest_daemon.run())
    print("🖥️  PC Monitor and AEGIS Ingest Daemon background loops active")

# One production process serves both the compiled UI and the API. Vite's dev
# server was repeatedly OOM-killed on this 8 GB host.
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="dashboard")

if __name__ == "__main__":
    print(f"AEGIS Backend starting on {cfg.HOST}:{cfg.BACKEND_PORT}")
    print(f"Vault: {VAULT} ({len(get_vault_markdown_files())} markdown files)")
    uvicorn.run(app, host=cfg.HOST, port=cfg.BACKEND_PORT, log_level="info")
