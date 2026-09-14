#!/usr/bin/env python3
"""
AEGIS Web Dashboard — Obsidian Vault + 9Router + Skills + PC Monitor + Chat
Server: FastAPI + uvicorn
Frontend: Single HTML file with vanilla JS
"""

import json
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="AEGIS Dashboard")

# Allow all origins for local use
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

VAULT = Path("/home/adarshjii/ObsidianVault")
AEGIS_DIR = Path("/home/adarshjii/.temporary-aegis")
SCRIPTS = AEGIS_DIR / "scripts"
MEMORY = VAULT / "memory"
AGIES_MEM = VAULT / "agies-memories"
CONFIG = VAULT / "config"

# ── Utility functions ──────────────────────────────────────────────────────────

def read_markdown_file(path: Path) -> str:
    """Read and return markdown file content."""
    try:
        return path.read_text()
    except:
        return f"// File not found: {path}"

def get_vault_structure() -> dict:
    """Get vault directory structure."""
    structure = {}
    for item in sorted(VAULT.iterdir()):
        if item.is_dir():
            structure[item.name] = {
                "type": "dir",
                "children": sorted([c.name for c in item.iterdir()])
            }
        else:
            structure[item.name] = {
                "type": "file",
                "size": item.stat().st_size
            }
    return structure

def get_memory_files() -> list:
    """Get all markdown files in memory directory."""
    files = []
    for md in sorted(MEMORY.rglob("*.md")):
        files.append({
            "path": str(md.relative_to(VAULT)),
            "name": md.name,
            "size": md.stat().st_size,
            "modified": datetime.fromtimestamp(md.stat().st_mtime).isoformat()
        })
    return files

def get_mocs() -> list:
    """Get MOCs from memory/MOCs/."""
    mocs_dir = MEMORY / "MOCs"
    if not mocs_dir.exists():
        return []
    mocs = []
    for md in sorted(mocs_dir.glob("*.md")):
        content = md.read_text()
        # Extract title from first heading
        title = md.stem
        for line in content.split('\n'):
            if line.startswith('# '):
                title = line[2:].strip()
                break
        mocs.append({
            "path": f"memory/MOCs/{md.name}",
            "title": title,
            "content": content[:500]  # Preview
        })
    return mocs

def get_projects() -> list:
    """Get project notes."""
    projects_dir = MEMORY / "1-Projects"
    if not projects_dir.exists():
        return []
    projects = []
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
                    "content": content[:500]
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
                "content": content[:500]
            })
    return projects

def get_skills() -> dict:
    """Get all skills from registry + agies skills."""
    skills = {}
    
    # From SKILL_REGISTRY.json
    registry_path = AEGIS_DIR / "SKILL_REGISTRY.json"
    if registry_path.exists():
        try:
            data = json.loads(registry_path.read_text())
            for name, skill in data.get("skills", {}).items():
                skills[name] = skill
        except:
            pass
    
    # From agies skills directory (SKILL.md files)
    agies_skills_dir = Path("/home/adarshjii/.hermes/profiles/agies/skills")
    if agies_skills_dir.exists():
        for skill_dir in agies_skills_dir.iterdir():
            if skill_dir.is_dir():
                skill_md = skill_dir / "SKILL.md"
                desc_md = skill_dir / "DESCRIPTION.md"
                if skill_md.exists():
                    content = skill_md.read_text()
                    name = skill_dir.name
                    if name not in skills:
                        skills[name] = {
                            "name": name,
                            "version": "1.0",
                            "category": "agies-skill",
                            "purpose": "",
                            "description": ""
                        }
                    # Extract description from DESCRIPTION.md
                    if desc_md.exists():
                        skills[name]["description"] = desc_md.read_text()[:300]
    
    return skills

def get_models() -> dict:
    """Get model registry."""
    registry_path = AEGIS_DIR / "MODEL_REGISTRY.json"
    if registry_path.exists():
        try:
            return json.loads(registry_path.read_text())
        except:
            pass
    return {}

def get_tools() -> dict:
    """Get tool registry."""
    registry_path = AEGIS_DIR / "TOOL_REGISTRY.json"
    if registry_path.exists():
        try:
            return json.loads(registry_path.read_text())
        except:
            pass
    return {}

def get_pc_snapshot() -> str:
    """Get latest PC snapshot."""
    snapshot_dir = MEMORY / "pc-state"
    if snapshot_dir.exists():
        snapshots = sorted(snapshot_dir.glob("*.md"))
        if snapshots:
            return snapshots[-1].read_text()
    return "# No PC snapshot available"

def run_script(name: str) -> dict:
    """Run a script and return result."""
    script_path = SCRIPTS / name
    if not script_path.exists():
        return {"success": False, "error": f"Script not found: {name}"}
    
    try:
        result = subprocess.run(
            ["bash", str(script_path)],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(AEGIS_DIR)
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[-2000:] if result.stdout else "",
            "stderr": result.stderr[-1000:] if result.stderr else "",
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Script timed out after 5 minutes"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_chatgpt_tracking() -> dict:
    """Get ChatGPT ingestion tracking."""
    track_path = MEMORY / "chatgpt_ingestion_tracking.json"
    if track_path.exists():
        try:
            return json.loads(track_path.read_text())
        except:
            pass
    return {}

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Serve the main dashboard HTML."""
    html = Path(__file__).parent / "dashboard.html"
    if html.exists():
        return html.read_text()
    return "<h1>Dashboard not found</h1>"

@app.get("/api/vault-structure")
async def api_vault_structure():
    return get_vault_structure()

@app.get("/api/memory-files")
async def api_memory_files():
    return get_memory_files()

@app.get("/api/mocs")
async def api_mocs():
    return get_mocs()

@app.get("/api/projects")
async def api_projects():
    return get_projects()

@app.get("/api/skills")
async def api_skills():
    return get_skills()

@app.get("/api/models")
async def api_models():
    return get_models()

@app.get("/api/tools")
async def api_tools():
    return get_tools()

@app.get("/api/pc-snapshot")
async def api_pc_snapshot():
    return {"content": get_pc_snapshot()}

@app.get("/api/file-content/{path:path}")
async def api_file_content(path: str):
    """Get content of a file in the vault."""
    file_path = VAULT / path
    if file_path.exists() and file_path.is_file():
        return {"content": file_path.read_text(), "path": path}
    return {"error": "File not found", "path": path}

@app.post("/api/run-script")
async def api_run_script(request: Request):
    """Run a script manually."""
    body = await request.json()
    script_name = body.get("script", "")
    return run_script(script_name)

@app.get("/api/chatgpt-tracking")
async def api_chatgpt_tracking():
    return get_chatgpt_tracking()

@app.get("/api/agies-memories")
async def api_agies_memories():
    """Get agies memory files."""
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
    """Get config directory files."""
    files = []
    if CONFIG.exists():
        for md in sorted(CONFIG.glob("*.md")):
            files.append({
                "path": f"config/{md.name}",
                "name": md.name,
                "content": md.read_text()[:500]
            })
        for json_file in sorted(CONFIG.glob("*.json")):
            files.append({
                "path": f"config/{json_file.name}",
                "name": json_file.name,
                "content": json_file.read_text()[:500]
            })
    return files

@app.get("/api/search")
async def api_search(query: str = ""):
    """Search vault files for a query."""
    if not query:
        return []
    results = []
    query_lower = query.lower()
    for md in Vault.rglob("*.md"):
        try:
            content = md.read_text().lower()
            if query_lower in content:
                rel_path = md.relative_to(VAULT)
                # Find context around match
                full_content = md.read_text()
                idx = full_content.lower().find(query_lower)
                start = max(0, idx - 100)
                end = min(len(full_content), idx + 200)
                context = full_content[start:end]
                results.append({
                    "path": str(rel_path),
                    "match": context,
                    "line": full_content[:idx].count('\n') + 1
                })
        except:
            continue
    return results[:20]

if __name__ == "__main__":
    print("Starting AEGIS Dashboard...")
    print(f"Vault: {VAULT}")
    print(f"Files: {len(list(VAULT.rglob('*.md')))} markdown files")
    print("Dashboard: http://localhost:8787")
    uvicorn.run(app, host="0.0.0.0", port=8787, log_level="info")
