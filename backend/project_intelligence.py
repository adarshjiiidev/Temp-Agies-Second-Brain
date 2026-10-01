#!/usr/bin/env python3
"""
AEGIS Project Intelligence
Discovers and extracts deep structural, semantic, and Git state 
information from registered projects.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, List

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from backend.config import cfg
from backend.logger import get_logger

log = get_logger("project_intel")

class ProjectIntelligence:
    def __init__(self):
        self.projects = cfg.PROJECTS
        
    def get_project_summary(self, project_name: str) -> Dict[str, Any]:
        """Collect comprehensive state for a project."""
        p_path = self.projects.get(project_name)
        if not p_path or not p_path.exists():
            return {"error": "Project not found"}
            
        summary = {
            "name": project_name,
            "path": str(p_path),
            "language": self._detect_language(p_path),
            "git_state": self._get_git_state(p_path),
            "ci_status": self._get_ci_status(p_path),
            "dependencies": self._get_dependencies(p_path),
            "health": self._assess_health(p_path)
        }
        return summary

    def _detect_language(self, path: Path) -> str:
        if (path / "Cargo.toml").exists():
            return "Rust"
        if (path / "package.json").exists():
            return "TypeScript/JavaScript"
        if (path / "requirements.txt").exists() or (path / "pyproject.toml").exists():
            return "Python"
        if (path / "go.mod").exists():
            return "Go"
        return "Unknown"

    def _get_git_state(self, path: Path) -> Dict[str, Any]:
        git_dir = path / ".git"
        if not git_dir.exists():
            return {"is_git": False}
            
        def run_git(args: str) -> str:
            res = subprocess.run(f"git {args}", shell=True, cwd=str(path), capture_output=True, text=True)
            return res.stdout.strip()
            
        return {
            "is_git": True,
            "branch": run_git("rev-parse --abbrev-ref HEAD"),
            "commit": run_git("rev-parse --short HEAD"),
            "status": "clean" if not run_git("status --porcelain") else "dirty",
            "uncommitted": len(run_git("status --porcelain").splitlines()),
            "last_message": run_git("log -1 --pretty=%B"),
            "remotes": run_git("remote -v").splitlines()
        }

    def _get_ci_status(self, path: Path) -> str:
        if (path / ".github" / "workflows").exists():
            return "Active (GitHub Actions)"
        return "No CI/CD detected"

    def _get_dependencies(self, path: Path) -> Dict[str, Any]:
        deps = {"count": 0, "list": []}
        try:
            if (path / "package.json").exists():
                with open(path / "package.json") as f:
                    pkg = json.load(f)
                    d = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                    deps["list"] = list(d.keys())[:10]  # top 10
                    deps["count"] = len(d)
            elif (path / "requirements.txt").exists():
                lines = (path / "requirements.txt").read_text().splitlines()
                valid = [l.split("=")[0].strip() for l in lines if l and not l.startswith("#")]
                deps["list"] = valid[:10]
                deps["count"] = len(valid)
        except Exception as e:
            log.warning(f"Error reading dependencies for {path}: {e}")
        return deps

    def _assess_health(self, path: Path) -> str:
        """Heuristic evaluation of project health (uncommitted files, missing docs)."""
        issues = []
        if not (path / "README.md").exists():
            issues.append("Missing README.md")
            
        git_state = self._get_git_state(path)
        if git_state.get("is_git"):
            if git_state.get("uncommitted", 0) > 20:
                issues.append("Large uncommitted working tree")
                
        return "Healthy" if not issues else f"Needs Attention: {', '.join(issues)}"
        
project_intelligence = ProjectIntelligence()

if __name__ == "__main__":
    pi = ProjectIntelligence()
    print("Testing Project Intelligence...")
    print(json.dumps(pi.get_project_summary("aegis-dashboard"), indent=2))
