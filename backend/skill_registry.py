#!/usr/bin/env python3
"""
AEGIS Skill Registry
Discovers, categorizes, and serves skills from multiple agent systems (Hermes, OpenClaw, AEGIS).
"""

import sys
import json
from pathlib import Path
from typing import Dict, Any, List

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from backend.config import cfg
from backend.logger import get_logger

log = get_logger("skill_registry")

class SkillRegistry:
    def __init__(self):
        self.hermes_skills_dir = cfg.HOME / ".hermes" / "profiles" / "agies" / "skills"
        self.aegis_skills_dir = cfg.HOME / ".temporary-aegis" / "skills"
        
    def _scan_hermes_skills(self) -> List[Dict[str, Any]]:
        skills = []
        manifest_path = self.hermes_skills_dir / ".bundled_manifest"
        if manifest_path.exists():
            try:
                # Assuming JSON array or dict in bundled manifest
                data = json.loads(manifest_path.read_text(errors="replace"))
                if isinstance(data, dict):
                    # Convert dict to list
                    for k, v in data.items():
                        skills.append({
                            "id": k,
                            "name": v.get("name", k),
                            "description": v.get("description", ""),
                            "source": "hermes"
                        })
                elif isinstance(data, list):
                    for item in data:
                        skills.append({
                            "id": item.get("id", ""),
                            "name": item.get("name", ""),
                            "description": item.get("description", ""),
                            "source": "hermes"
                        })
            except Exception as e:
                log.warning(f"Failed to parse Hermes skill manifest: {e}")
                
        # Also scan directories
        if self.hermes_skills_dir.exists():
            for d in self.hermes_skills_dir.iterdir():
                if d.is_dir() and not d.name.startswith("."):
                    skills.append({
                        "id": f"hermes.{d.name}",
                        "name": d.name.replace("-", " ").title(),
                        "description": "Hermes skill bundle",
                        "source": "hermes"
                    })
        return skills

    def _scan_aegis_skills(self) -> List[Dict[str, Any]]:
        skills = []
        if self.aegis_skills_dir.exists():
            for d in self.aegis_skills_dir.iterdir():
                if d.is_dir() and not d.name.startswith("."):
                    skills.append({
                        "id": f"aegis.{d.name}",
                        "name": d.name.replace("-", " ").title(),
                        "description": "AEGIS native skill",
                        "source": "aegis"
                    })
        return skills

    def get_all_skills(self) -> List[Dict[str, Any]]:
        skills = []
        skills.extend(self._scan_hermes_skills())
        skills.extend(self._scan_aegis_skills())
        
        # Deduplicate by ID
        seen = set()
        unique = []
        for s in skills:
            if s["id"] not in seen:
                seen.add(s["id"])
                
                # Risk classification heuristic
                risk = "LOW"
                if any(x in s["name"].lower() for x in ["delete", "remove", "shell", "exec", "sudo"]):
                    risk = "HIGH"
                elif any(x in s["name"].lower() for x in ["write", "create", "update", "git"]):
                    risk = "MEDIUM"
                    
                s["risk"] = risk
                s["status"] = "enabled" if risk != "HIGH" else "requires_approval"
                unique.append(s)
                
        return unique

skill_registry = SkillRegistry()

if __name__ == "__main__":
    sr = SkillRegistry()
    print("Testing Skill Registry...")
    print(json.dumps(sr.get_all_skills(), indent=2))
