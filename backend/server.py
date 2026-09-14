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
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from backend.config import cfg
from backend.logger import get_logger
from backend.security import check_token, safe_path, safe_agent_id, safe_script_id, API_TOKEN
from backend.browser_tool import browser_tool

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
    """Enforce token validation on mutating endpoints (POST, PUT, DELETE, PATCH)."""
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        if not check_token(request):
            log.warning("Security reject 403 on %s %s", request.method, request.url.path)
            return JSONResponse(status_code=403, content={"error": "Forbidden: Invalid or missing X-AEGIS-Token"})
    return await call_next(request)

# ── Paths ──────────────────────────────────────────────────────────────────────

VAULT = cfg.VAULT
AEGIS_DIR = cfg.AEGIS_DIR
REGISTRIES_DIR = cfg.REGISTRIES_DIR
SCRIPTS = cfg.SCRIPTS_DIR
MEMORY = cfg.MEMORY
AGIES_MEM = cfg.AGIES_MEM
CONFIG = cfg.CONFIG_DIR
HERMES_AGIES_SKILLS = cfg.HERMES_SKILLS

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

cognitive_memory = CognitiveMemoryEngine()
vision_engine = VisionEngine()
hierarchical_planner = HierarchicalPlanner()

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

# ── 9Router ────────────────────────────────────────────────────────────────────

async def query_9router_models() -> dict:
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("http://127.0.0.1:20128/v1/models")
            if resp.status_code == 200:
                data = resp.json()
                return {"success": True, "count": len(data.get("data", [])), "models": data.get("data", [])[:50]}
            return {"success": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def query_9router_health() -> dict:
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get("http://127.0.0.1:20128/v1/models")
            return {"status": "running" if resp.status_code == 200 else "error", "code": resp.status_code}
    except:
        return {"status": "stopped", "code": None}

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
    skills = {}
    for p in [REGISTRIES_DIR / "SKILL_REGISTRY.json", AEGIS_DIR / "SKILL_REGISTRY.json"]:
        if p.exists():
            try:
                data = json.loads(p.read_text())
                raw_skills = data.get("skills", {})
                if isinstance(raw_skills, list):
                    for s in raw_skills:
                        sid = s.get("id", s.get("name", "skill"))
                        skills[sid] = s
                elif isinstance(raw_skills, dict):
                    skills.update(raw_skills)
            except Exception as e:
                log.warning("Failed parsing %s: %s", p, e)
    if HERMES_AGIES_SKILLS.exists():
        for skill_dir in HERMES_AGIES_SKILLS.iterdir():
            if skill_dir.is_dir():
                skill_md = skill_dir / "SKILL.md"
                desc_md = skill_dir / "DESCRIPTION.md"
                name = skill_dir.name
                if name not in skills and skill_md.exists():
                    skills[name] = {
                        "id": f"hermes-{name}",
                        "name": name,
                        "version": "1.0",
                        "category": "agies-skill",
                        "purpose": skill_md.read_text(errors="replace")[:200],
                        "description": desc_md.read_text(errors="replace")[:300] if desc_md.exists() else ""
                    }
    return skills

def get_models() -> dict:
    for p in [REGISTRIES_DIR / "MODEL_REGISTRY.json", AEGIS_DIR / "MODEL_REGISTRY.json"]:
        if p.exists():
            try:
                data = json.loads(p.read_text())
                if "curated_models" not in data or not data["curated_models"]:
                    data["curated_models"] = {
                        "gemini/gemini-3.8-flash": {
                            "role": "Frontier Multimodal & Reasoning",
                            "context_window": 1048576,
                            "max_output": 65536,
                            "reasoning": True,
                            "tools": True,
                            "vision": True,
                            "thinking_format": "gemini-level",
                            "source": "9Router (Google Gemini)",
                            "status": "online",
                            "notes": "1 Million token context window, deep reasoning, live Google search, vision & tool use."
                        },
                        "gemini/gemini-3.7-flash": {
                            "role": "High-Speed Reasoning & Code",
                            "context_window": 1048576,
                            "max_output": 65536,
                            "reasoning": True,
                            "tools": True,
                            "vision": True,
                            "thinking_format": "gemini-level",
                            "source": "9Router (Google Gemini)",
                            "status": "online",
                            "notes": "Fastest reasoning flash tier with extended thinking support."
                        },
                        "gemini/gemini-3.6-flash": {
                            "role": "Ultra-Low Latency Agent & Chat",
                            "context_window": 1048576,
                            "max_output": 65536,
                            "reasoning": True,
                            "tools": True,
                            "vision": True,
                            "thinking_format": "gemini-level",
                            "source": "9Router (Google Gemini)",
                            "status": "online",
                            "notes": "Ultra-reliable, zero cold-start, instant streaming responses."
                        },
                        "gemini/gemini-3.5-flash-lite": {
                            "role": "Lightweight High-Throughput",
                            "context_window": 1048576,
                            "max_output": 65536,
                            "reasoning": False,
                            "tools": True,
                            "vision": True,
                            "source": "9Router (Google Gemini)",
                            "status": "online",
                            "notes": "Maximum token efficiency for rapid queries and telemetry summaries."
                        },
                        "gemini/gemini-3-flash-preview": {
                            "role": "Preview Flash Model",
                            "context_window": 1048576,
                            "max_output": 65536,
                            "reasoning": True,
                            "tools": True,
                            "vision": True,
                            "source": "9Router (Google Gemini)",
                            "status": "online",
                            "notes": "Gemini 3 Flash preview checkpoint."
                        },
                        "gemini/gemini-3.1-flash-lite-preview": {
                            "role": "Compact Preview Model",
                            "context_window": 1048576,
                            "max_output": 65536,
                            "reasoning": False,
                            "tools": True,
                            "vision": True,
                            "source": "9Router (Google Gemini)",
                            "status": "online",
                            "notes": "Compact 3.1 preview checkpoint."
                        }
                    }
                if "routing_table" not in data and "routing" in data:
                    data["routing_table"] = data["routing"]
                return data
            except Exception:
                pass
    return {}

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
async def api_9router_health():
    return await query_9router_health()

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
    return get_agents()

@app.post("/api/agent/{name}/start")
async def api_agent_start(name: str):
    session = manager.get_or_create_session(name)
    return {"status": "running" if session.is_running else "stopped", "agent": name}

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

# ── Cognitive, Vision & Deep Diagnostics ───────────────────────────────────────

@app.get("/api/search/unified")
async def api_search_unified(q: str = "", limit: int = 15):
    if not q.strip():
        return []
    return knowledge_graph.unified_search(q.strip(), limit=limit)

@app.get("/api/diagnostics/deep")
async def api_diagnostics_deep():
    # 1. 9Router health & model stats
    health = await query_9router_health()
    
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
    for svc in ["aegis-backend.service", "aegis-frontend.service", "9router.service", "aegis-consolidate.timer"]:
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

@app.get("/api/memory/temporal")
async def api_memory_temporal(timeframe: str = "today"):
    return cognitive_memory.query_temporal_activity(timeframe)

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

@app.get("/api/monitor/health")
async def api_monitor_health():
    return proactive_monitor.scan_project_health()

@app.get("/api/health/full")
async def api_health_full():
    return aegis_health.run_all_checks()



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

# ── 9Router Live Query & Failover ─────────────────────────────────────────────

async def query_9router_chat(messages: list, model: str) -> tuple[str, str]:
    """
    Query 9Router API at http://127.0.0.1:20128/v1/chat/completions.
    Handles SSE event stream parsing and automatic fallback failover.
    Returns (response_text, actual_model_used).
    """
    import httpx

    # Clean requested model or pick active default from cfg
    clean_model = model.strip() if model and model.strip() != "auto" else cfg.MODEL_DEFAULT

    # Build fallback chain from cfg (registry-driven, not hardcoded)
    fallback_chain = [clean_model]
    for alt in cfg.MODEL_FALLBACK_CHAIN:
        if alt not in fallback_chain:
            fallback_chain.append(alt)

    last_error = ""
    async with httpx.AsyncClient(timeout=60.0) as client:
        for attempt_model in fallback_chain:
            try:
                payload = {
                    "model": attempt_model,
                    "messages": messages,
                    "stream": False
                }
                resp = await client.post("http://127.0.0.1:20128/v1/chat/completions", json=payload)
                if resp.status_code == 200:
                    raw_text = resp.text
                    full_content = []
                    if "data:" in raw_text:
                        for line in raw_text.splitlines():
                            line = line.strip()
                            if not line or line == "data: [DONE]":
                                continue
                            if line.startswith("data: "):
                                try:
                                    chunk = json.loads(line[6:])
                                    choices = chunk.get("choices", [])
                                    if choices:
                                        delta = choices[0].get("delta", {})
                                        content_piece = delta.get("content") or choices[0].get("message", {}).get("content")
                                        if content_piece:
                                            full_content.append(content_piece)
                                except Exception:
                                    pass
                        ans = "".join(full_content).strip()
                    else:
                        try:
                            data = resp.json()
                            ans = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                        except Exception:
                            ans = raw_text.strip()

                    if ans:
                        if attempt_model != clean_model:
                            ans += f"\n\n*(Failover: `{clean_model}` was unavailable, answered via 1:1 fallback `{attempt_model}`)*"
                        return ans, attempt_model
                else:
                    last_error = f"HTTP {resp.status_code}: {resp.text[:100]}"
            except Exception as e:
                last_error = str(e)
                continue

    return f"⚠️ 9Router Gateway call failed across all fallback models. Last error: {last_error}. Please ensure `systemctl --user status 9router` is running.", clean_model

# ── Chat endpoint ──────────────────────────────────────────────────────────────

@app.post("/api/chat")
async def api_chat(request: Request):
    body = await request.json()
    user_message = body.get("message", "")
    history = body.get("history", [])
    model = body.get("model", "")
    
    classification = classify_task_orchestrator(user_message)
    if not model or model == "auto":
        active_model = classification["primary"]
    else:
        active_model = model

    response, actual_model = await generate_chat_response(user_message, history, active_model)
    
    return {
        "content": response,
        "timestamp": datetime.now().isoformat(),
        "model": actual_model,
        "classification": classification
    }

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
            "- `/models` — View task-based model routing table and 9Router status\n"
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
        models = get_models()
        rt = models.get("routing_table", {})
        health = await query_9router_health()
        text = (
            f"### Active Model Routing Table\n\n"
            f"- **9Router Status:** `{health['status'].upper()}` (`http://127.0.0.1:20128/v1`)\n"
            f"- **Primary Frontier Agent:** `gemini/gemini-3.8-flash`\n"
            f"- **Low Latency Flash:** `gemini/gemini-3.6-flash`\n"
            f"- **Fast Reasoning:** `gemini/gemini-3.7-flash`\n"
            f"- **Lightweight Throughput:** `gemini/gemini-3.5-flash-lite`\n"
            f"- **Total 9Router Models:** 870\n"
        )
        return text, "local/models"

    if msg_lower == "/clear":
        return "Session history cleared.", "local/kernel"

    # ── Context Injection & Real LLM Generation ────────────────────────────────
    # Check if query references any consolidated projects or memories
    memory_context = get_relevant_memory_context(msg_trimmed)

    system_prompt = (
        "You are Agies, an intelligent, perceptive, and highly capable AI assistant in the AEGIS AI OS.\n"
        "You are conversing directly with the user. You speak naturally, intelligently, eloquently, and directly.\n"
        "You have complete awareness of the user's workspace and the cross-agent memory system consolidated from Antigravity, Codex, Claude, and Hermes into Obsidian (~/ObsidianVault/agies/).\n"
        "Key projects on this machine: aegis-dashboard (web UI), aegis-python (backend core), chrome-extra (extension agent), repusense (Next.js app), world-viewer (Electron app).\n\n"
        "Guidelines:\n"
        "- Respond as a natural, top-tier AI conversationalist. Answer the user's questions directly and insightfully.\n"
        "- Do NOT output unsolicited hardware telemetry, RAM/disk stats, or debug boilerplate unless the user explicitly asks about machine status or performance.\n"
        "- When asked about projects, architecture, past sessions, or prior decisions, draw upon the living memory accurately.\n"
        "- Format responses cleanly with GitHub-flavored markdown, code blocks, and clear typography."
    )

    if memory_context:
        system_prompt += f"\n\n--- Consolidated Cross-Agent Memory ---\n{memory_context}\n--------------------------------------"

    # Build messages history
    llm_messages = [{"role": "system", "content": system_prompt}]
    if history:
        for h in history[-8:]:
            role = h.get("role", "user")
            content = h.get("content", "")
            if role in ["user", "assistant"] and content:
                llm_messages.append({"role": role, "content": content})

    llm_messages.append({"role": "user", "content": message})

    target_model = model or "gemini/gemini-3.8-flash"
    reply_text, actual_model = await query_9router_chat(llm_messages, target_model)
    return reply_text, actual_model

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
        await websocket.send_text(json.dumps({
            "type": "initial_data",
            "vault": get_vault_structure(),
            "memory_files": get_memory_files(),
            "mocs_list": await api_mocs(),
            "projects_list": await api_projects(),
            "skills_data": get_skills(),
            "pc_state": get_pc_state(),
            "9router_health": await query_9router_health(),
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

@app.on_event("startup")
async def on_startup():
    asyncio.create_task(pc_monitor_loop())
    print("🖥️  PC Monitor background loop active")

if __name__ == "__main__":
    print(f"AEGIS Backend starting on {cfg.HOST}:{cfg.BACKEND_PORT}")
    print(f"Vault: {VAULT} ({len(get_vault_markdown_files())} markdown files)")
    uvicorn.run(app, host=cfg.HOST, port=cfg.BACKEND_PORT, log_level="info")

