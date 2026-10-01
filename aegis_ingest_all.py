#!/usr/bin/env python3
"""
aegis_ingest_all.py — Complete Knowledge Ingestion for Agies
Reads ALL project repos, vault files, and consolidated memory,
then produces massive ingestion documents that Agies reads at session start.

Run: python aegis_ingest_all.py
Or via systemd: systemctl --user start aegis-ingest.service
"""

import os
import re
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

HOME = Path.home()
PROJECTS_DIR = HOME / "Projects"
VAULT = HOME / "ObsidianVault"
AGIES_DIR = VAULT / "agies"
HERMES_AGIES = HOME / ".hermes" / "profiles" / "agies"
MEMORIES_DIR = HERMES_AGIES / "memories"

PROJECT_INDEX = VAULT / "memory" / "1-Projects" / "index.md"
INGESTION_OUTPUT = MEMORIES_DIR / "ALL_PROJECTS_INGESTION.md"
PROJECT_KNOWLEDGE = MEMORIES_DIR / "AEGIS_PROJECT_KNOWLEDGE.md"

MAX_FILE_READ = 50000  # chars per file

def read_file_safe(path: Path, max_chars: int = MAX_FILE_READ) -> str:
    try:
        if not path.exists():
            return ""
        size = path.stat().st_size
        if size > max_chars:
            # Read head and tail
            with open(path, 'r', errors='replace') as f:
                head = f.read(max_chars // 2)
            with open(path, 'r', errors='replace') as f:
                f.seek(max(0, size - max_chars // 2))
                tail = f.read()
            return head + "\n\n[... middle omitted ...]\n\n" + tail
        return path.read_text(errors='replace')
    except Exception as e:
        return f"[[Error reading {path}: {e}]]"

code_exts = {'.py', '.ts', '.tsx', '.js', '.jsx', '.rs', '.go', '.rb', '.java', '.c', '.cpp', '.h', '.hpp',
             '.vue', '.svelte', '.swift', '.kt', '.zig', '.lua', '.sh', '.bash', '.zsh',
             '.json', '.yaml', '.yml', '.toml', '.xml', '.html', '.css', '.scss', '.less',
             '.md', '.txt', '.cfg', '.conf', '.ini', '.env', '.sql', '.proto', '.graphql'}
    
def is_binary(path: Path) -> bool:
    try:
        with open(path, 'rb') as f:
            chunk = f.read(8192)
            if b'\x00' in chunk:
                return True
            # Check if mostly text
            text_chars = bytearray({9,10,13,32,33,34,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,94,95,96,97,98,99,100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119,120,121,122,123,124,125,126,127}.union(range(128, 256)))
            non_text = sum(1 for b in chunk if b not in text_chars)
            return non_text / len(chunk) > 0.3
    except:
        return True
    return False

def get_repo_info(repo_dir: Path) -> dict:
    """Extract key info from a git repo."""
    info = {
        "name": repo_dir.name,
        "path": str(repo_dir),
        "remote": "",
        "last_commit": "",
        "branches": [],
        "files": [],
        "readme": "",
        "key_files": {},
        "total_files": 0,
        "code_files": 0,
        "dirs": [],
    }
    
    try:
        # Remote
        import subprocess
        r = subprocess.run(["git", "remote", "-v"], cwd=repo_dir, capture_output=True, text=True)
        if r.returncode == 0:
            lines = r.stdout.strip().split('\n')
            for line in lines:
                if 'push' in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        info["remote"] = parts[1]
                        break
        
        # Last commit
        r = subprocess.run(["git", "log", "--format=%s%n%b", "-1"], cwd=repo_dir, capture_output=True, text=True)
        if r.returncode == 0:
            info["last_commit"] = r.stdout.strip()[:500]
        
        # Branches
        r = subprocess.run(["git", "branch", "-a"], cwd=repo_dir, capture_output=True, text=True)
        if r.returncode == 0:
            info["branches"] = [b.strip().lstrip('* ') for b in r.stdout.strip().split('\n') if b.strip()]
    except Exception as e:
        pass
    
    # Walk files
    code_exts = {'.py', '.ts', '.tsx', '.js', '.jsx', '.rs', '.go', '.rb', '.java', '.c', '.cpp', '.h', '.hpp',
                 '.ts', '.vue', '.svelte', '.swift', '.kt', '.zig', '.lua', '.sh', '.bash', '.zsh',
                 '.json', '.yaml', '.yml', '.toml', '.xml', '.html', '.css', '.scss', '.less',
                 '.md', '.txt', '.cfg', '.conf', '.ini', '.env', '.sql', '.proto', '.graphql'}
    
    try:
        for root, dirs, files in os.walk(repo_dir):
            # Skip hidden/vcs dirs
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('node_modules', '__pycache__', 'venv', '.git', 'dist', 'build', 'target')]
            for f in files:
                if f.startswith('.'):
                    continue
                fp = Path(root) / f
                rel = fp.relative_to(repo_dir)
                info["total_files"] += 1
                if fp.suffix in code_exts:
                    info["code_files"] += 1
                info["files"].append(str(rel))
    except Exception as e:
        pass
    
    return info

def ingest_project(repo_dir: Path) -> str:
    """Create ingestion text for one project."""
    info = get_repo_info(repo_dir)
    
    lines = []
    lines.append(f"# PROJECT: {info['name']}")
    lines.append(f"**Path:** `{info['path']}`")
    lines.append(f"**Remote:** `{info['remote']}`")
    lines.append(f"**Branches:** {', '.join(info['branches'][:10])}")
    lines.append(f"**Total files:** {info['total_files']} | **Code files:** {info['code_files']}")
    lines.append("")
    
    # Last commit
    if info['last_commit']:
        lines.append(f"## Last Commit")
        lines.append(info['last_commit'])
        lines.append("")
    
    # README
    readme_names = ['README.md', 'readme.md', 'README.txt', 'README', 'README.rst']
    for rn in readme_names:
        readme_path = repo_dir / rn
        if readme_path.exists():
            content = read_file_safe(readme_path, 8000)
            if content.strip():
                lines.append(f"## README")
                lines.append(content[:8000])
                lines.append("")
                break
    
    # Key files - look for package.json, setup.py, Cargo.toml, Makefile, etc.
    key_names = ['package.json', 'setup.py', 'setup.cfg', 'pyproject.toml', 'Cargo.toml',
                 'Cargo.toml.toml', 'Makefile', 'CMakeLists.txt', 'go.mod', 'composer.json',
                 'pom.xml', 'build.gradle', 'Gemfile', '.env.example', '.gitignore',
                 'manifest.json', 'config.yaml', 'config.yml', 'config.json']
    for kn in key_names:
        kp = repo_dir / kn
        if kp.exists():
            content = read_file_safe(kp, 3000)
            if content.strip():
                lines.append(f"## {kn}")
                lines.append(content[:3000])
                lines.append("")
    
    # Source files - sample up to 20 files
    source_files = [f for f in info['files'] if Path(f).suffix in code_exts and 
                    'test' not in f.lower() and 'spec' not in f.lower() and '__pycache__' not in f]
    
    # Prioritize important files
    priority = ['main.', 'app.', 'index.', 'src/', 'lib/', 'server.', 'cli.', 'core.', 'engine.', 'model.', 'agent.']
    prioritized = []
    for sf in source_files:
        for p in priority:
            if p in sf.lower():
                prioritized.append(sf)
                break
    remaining = [sf for sf in source_files if sf not in prioritized]
    
    sample_files = prioritized[:15] + remaining[:5]
    
    lines.append(f"## Source Files ({len(sample_files)} sampled of {len(source_files)} total)")
    for sf in sample_files[:20]:
        sf_path = repo_dir / sf
        if sf_path.exists() and not is_binary(sf_path):
            content = read_file_safe(sf_path, 4000)
            if content.strip():
                lines.append(f"### `{sf}`")
                lines.append(content[:4000])
                lines.append("")
    
    # Directory structure
    lines.append(f"## Directory Structure")
    try:
        for root, dirs, files in os.walk(repo_dir):
            rel = Path(root).relative_to(repo_dir)
            if rel == Path('.'):
                continue
            depth = len(rel.parts)
            indent = "  " * depth
            if dirs:
                lines.append(f"{indent}{rel}/")
            for f in files[:3]:  # limit files per dir
                if not f.startswith('.'):
                    fp = Path(root) / f
                    if not is_binary(fp):
                        lines.append(f"{indent}  {f}")
    except:
        pass
    lines.append("")
    
    return '\n'.join(lines)

def ingest_all_projects():
    """Ingest all projects from ~/Projects/ into comprehensive documents."""
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting full project ingestion...")
    
    # Find all project directories
    project_dirs = []
    if PROJECTS_DIR.exists():
        for item in sorted(PROJECTS_DIR.iterdir()):
            if item.is_dir() and (item / '.git').exists() or (item / 'package.json').exists() or (item / 'src').exists():
                project_dirs.append(item)
    
    print(f"Found {len(project_dirs)} projects in ~/Projects/")
    
    # Also scan for non-git projects
    for item in sorted(PROJECTS_DIR.iterdir()):
        if item.is_dir() and item not in project_dirs:
            if any(item.glob('*.py')) or any(item.glob('*.ts')) or any(item.glob('*.rs')):
                project_dirs.append(item)
    
    print(f"Total projects (including non-git): {len(project_dirs)}")
    
    # Build comprehensive ingestion
    sections = []
    sections.append(f"# AEGIS — Complete Project Ingestion for Agies")
    sections.append(f"**Generated:** {datetime.now(timezone.utc).isoformat()}")
    sections.append(f"**Source:** All projects in `~/Projects/` ({len(project_dirs)} repos)")
    sections.append("")
    sections.append("This document contains the COMPLETE knowledge from all projects on this machine.")
    sections.append("Agies reads this at session start to know everything about every project.")
    sections.append("")
    sections.append("=" * 70)
    sections.append("")
    
    for i, proj_dir in enumerate(project_dirs):
        print(f"  Ingesting {proj_dir.name}...")
        proj_text = ingest_project(proj_dir)
        sections.append(f"## PROJECT {i+1}: {proj_dir.name}")
        sections.append(f"Path: `{proj_dir}`")
        sections.append("")
        sections.append(proj_text)
        sections.append("")
        sections.append("=" * 70)
        sections.append("")
    
    # Also add vault memory project files
    print("  Adding vault project memory files...")
    vault_proj_dir = VAULT / "memory" / "1-Projects"
    if vault_proj_dir.exists():
        for md_file in sorted(vault_proj_dir.rglob("*.md")):
            if md_file.name != 'index.md':
                content = read_file_safe(md_file, 5000)
                if content.strip():
                    sections.append(f"## Vault Project Note: {md_file.relative_to(vault_proj_dir)}")
                    sections.append(f"Source: `{md_file.relative_to(VAULT)}`")
                    sections.append(content[:5000])
                    sections.append("")
    
    # Add ALL Antigravity brain chat data — every transcript, session, decision
    print("  Adding ALL Antigravity chat data...")
    antigravity_dir = AGIES_DIR / "by-agent" / "antigravity"
    if antigravity_dir.exists():
        brain_dirs = [d for d in antigravity_dir.iterdir() if d.is_dir() and not d.name.startswith('raw') and not d.name.startswith('tempmedia')]
        for brain_dir in sorted(brain_dirs):
            brain_id = brain_dir.name
            sections.append(f"## Antigravity Brain: {brain_id}")
            sections.append(f"Path: `agies/by-agent/antigravity/{brain_id}/`")
            sections.append("")
            
            # SESSION_NOTES.md
            sn = brain_dir / "SESSION_NOTES.md"
            if sn.exists():
                sections.append(read_file_safe(sn, 8000))
                sections.append("")
            
            # transcript.md (full conversation)
            tr = brain_dir / "transcript.md"
            if tr.exists():
                sections.append("### Full Conversation Transcript")
                sections.append(read_file_safe(tr, 20000))
                sections.append("")
            
            # decisions.md
            dec = brain_dir / "decisions.md"
            if dec.exists():
                sections.append("### Decisions")
                sections.append(read_file_safe(dec, 3000))
                sections.append("")
            
            # files-built.md
            fb = brain_dir / "files-built.md"
            if fb.exists():
                sections.append("### Files Built")
                sections.append(read_file_safe(fb, 3000))
                sections.append("")
            
            # tasks.md
            tk = brain_dir / "tasks.md"
            if tk.exists():
                sections.append("### Tasks & Commands")
                sections.append(read_file_safe(tk, 5000))
                sections.append("")
            
            # All other files-built data files
            for data_file in sorted(brain_dir.glob("*_data.md")):
                if data_file.name not in ('SESSION_NOTES.md', 'transcript.md', 'decisions.md', 'files-built.md', 'tasks.md'):
                    content = read_file_safe(data_file, 3000)
                    if content.strip():
                        sections.append(f"### {data_file.name}")
                        sections.append(content[:3000])
                        sections.append("")
            
            sections.append("=" * 70)
            sections.append("")
        
        # Also add raw files inventory
        raw_dir = antigravity_dir / "raw"
        if raw_dir.exists():
            raw_files = list(raw_dir.rglob("*"))
            sections.append(f"## Antigravity Raw File Archive")
            sections.append(f"Total raw files preserved: {len(raw_files)}")
            for rf in sorted(raw_files)[:50]:
                sections.append(f"- `{rf.relative_to(antigravity_dir)}` ({rf.stat().st_size} bytes)")
            if len(raw_files) > 50:
                sections.append(f"... and {len(raw_files) - 50} more")
            sections.append("")

    # Add consolidated agies memory
    print("  Adding consolidated Agies memory...")
    if AGIES_DIR.exists():
        agies_files = [
            AGIES_DIR / "DAILY_BRIEFING.md",
            AGIES_DIR / "DECISIONS.md",
            AGIES_DIR / "FINDINGS.md",
            AGIES_DIR / "ERRORS_AND_FIXES.md",
            AGIES_DIR / "SESSION_HISTORY.md",
            AGIES_DIR / "SEARCH_INDEX.md",
        ]
        for af in agies_files:
            if af.exists():
                content = read_file_safe(af, 5000)
                if content.strip():
                    sections.append(f"## Agies Consolidated: {af.name}")
                    sections.append(content[:5000])
                    sections.append("")
        
        # Project memories from PROJECTS/
        projects_mem_dir = AGIES_DIR / "PROJECTS"
        if projects_mem_dir.exists():
            for pm in sorted(projects_mem_dir.rglob("*.md")):
                if pm.name == 'MEMORY.md':
                    content = read_file_safe(pm, 5000)
                    if content.strip():
                        sections.append(f"## Agies Project Memory: {pm.relative_to(projects_mem_dir)}")
                        sections.append(content[:5000])
                        sections.append("")
    
    # Write the full ingestion document
    full_text = '\n'.join(sections)
    MEMORIES_DIR.mkdir(parents=True, exist_ok=True)
    INGESTION_OUTPUT.write_text(full_text)
    print(f"  Written: {INGESTION_OUTPUT} ({len(full_text):,} chars)")
    
    # Update AEGIS_PROJECT_KNOWLEDGE.md (condensed version for quick read)
    print("  Updating AEGIS_PROJECT_KNOWLEDGE.md...")
    knowledge = []
    knowledge.append(f"# AEGIS Project Knowledge")
    knowledge.append(f"**Last Updated:** {datetime.now(timezone.utc).isoformat()}")
    knowledge.append(f"**Projects:** {len(project_dirs)} repos in ~/Projects/")
    knowledge.append("")
    knowledge.append("## Quick Project Summary")
    for i, proj_dir in enumerate(project_dirs):
        info = get_repo_info(proj_dir)
        knowledge.append(f"### {i+1}. {info['name']}")
        knowledge.append(f"- Path: `{info['path']}`")
        knowledge.append(f"- Remote: `{info['remote']}`")
        knowledge.append(f"- Files: {info['total_files']} total, {info['code_files']} code files")
        knowledge.append(f"- Branches: {', '.join(info['branches'][:5])}")
        if info['remote']:
            knowledge.append(f"- GitHub: `{info['remote'].replace('git@github.com:', 'https://github.com/').replace('.git', '')}`")
        knowledge.append("")
    
    knowledge_text = '\n'.join(knowledge)
    PROJECT_KNOWLEDGE.write_text(knowledge_text)
    print(f"  Updated: {PROJECT_KNOWLEDGE} ({len(knowledge_text):,} chars)")
    
    # Also update MEMORY.md with project summary
    memory_file = MEMORIES_DIR / "MEMORY.md"
    if memory_file.exists():
        existing = memory_file.read_text()
        # Add project knowledge section
        if "## Projects" not in existing:
            memory_update = f"\n## Projects\n\nREAD: [[ALL_PROJECTS_INGESTION]] for complete project knowledge across all {len(project_dirs)} repos.\n\n"
            memory_file.write_text(existing + memory_update)
            print(f"  Updated: {memory_file}")
    
    # Create a compact inventory file too
    inventory = MEMORIES_DIR / "PROJECT_INVENTORY.md"
    inv_lines = []
    inv_lines.append("# Project Inventory — All Repos on This Machine")
    inv_lines.append(f"**Scanned:** {datetime.now(timezone.utc).isoformat()}")
    inv_lines.append("")
    inv_lines.append("| # | Project | Path | GitHub | Files | Code | Status |")
    inv_lines.append("|---|---------|------|--------|-------|------|--------|")
    for i, proj_dir in enumerate(project_dirs):
        info = get_repo_info(proj_dir)
        gh = info['remote'].replace('git@github.com:', 'https://github.com/').replace('.git', '') if info['remote'] else '—'
        status = "Git repo" if (proj_dir / '.git').exists() else "Project dir"
        inv_lines.append(f"| {i+1} | {info['name']} | `{info['path']}` | {gh} | {info['total_files']} | {info['code_files']} | {status} |")
    
    inventory.write_text('\n'.join(inv_lines))
    print(f"  Written: {inventory}")
    
    print(f"\n═══════════════════════════════════════════════")
    print(f"  Ingestion complete!")
    print(f"  Projects ingested: {len(project_dirs)}")
    print(f"  Full doc: {INGESTION_OUTPUT} ({len(full_text):,} chars)")
    print(f"  Knowledge: {PROJECT_KNOWLEDGE} ({len(knowledge_text):,} chars)")
    print(f"═══════════════════════════════════════════════")

if __name__ == "__main__":
    ingest_all_projects()
