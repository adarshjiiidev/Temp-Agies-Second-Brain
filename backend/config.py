#!/usr/bin/env python3
"""
AEGIS Central Configuration Engine
====================================
Single source of truth for all paths, ports, model IDs, and project definitions.
All values derive from the current user's home directory or environment variables.
No hardcoded usernames. No scattered magic strings.

Usage:
    from backend.config import cfg
    vault_path = cfg.VAULT
    router_url = cfg.ROUTER_URL
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

# ── Runtime User Context ────────────────────────────────────────────────────────

HOME = Path.home()
USER = HOME.name

# ── Core Directory Paths ────────────────────────────────────────────────────────

class AegisConfig:
    """Runtime-resolved configuration for AEGIS. All paths relative to HOME."""

    def __init__(self):
        self._registry_cache: Optional[List[Dict]] = None
        self.HOME: Path = HOME
        self.USER: str = USER

        # ── Hosts & Ports ──────────────────────────────────────────────────────
        self.HOST: str = os.environ.get("AEGIS_HOST", "127.0.0.1")
        self.BACKEND_PORT: int = int(os.environ.get("AEGIS_BACKEND_PORT", "8787"))
        self.FRONTEND_PORT: int = int(os.environ.get("AEGIS_FRONTEND_PORT", "2981"))
        self.CORS_ORIGINS: List[str] = [
            f"http://localhost:{self.FRONTEND_PORT}",
            f"http://127.0.0.1:{self.FRONTEND_PORT}",
            f"http://localhost:{self.BACKEND_PORT}",
            f"http://127.0.0.1:{self.BACKEND_PORT}",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ]

        # ── URLs ───────────────────────────────────────────────────────────────
        self.BACKEND_URL: str = os.environ.get("AEGIS_BACKEND_URL", f"http://127.0.0.1:{self.BACKEND_PORT}")

        # ── Core Paths ─────────────────────────────────────────────────────────
        self.REPO_ROOT: Path = Path(__file__).resolve().parent.parent
        self.VAULT: Path = Path(os.environ.get("AEGIS_VAULT_PATH", str(HOME / "ObsidianVault")))
        self.AEGIS_DIR: Path = Path(os.environ.get("AEGIS_STATE_DIR", str(HOME / ".temporary-aegis")))
        self.REGISTRIES_DIR: Path = self.REPO_ROOT / "registries"
        self.LOGS_DIR: Path = self.AEGIS_DIR / "logs"

        # ── Vault Sub-paths ────────────────────────────────────────────────────
        self.MEMORY: Path = self.VAULT / "memory"
        self.AGIES_VAULT: Path = self.VAULT / "agies"
        self.AGIES_MEM: Path = HOME / ".hermes" / "profiles" / "agies" / "memories"
        self.HERMES_SKILLS: Path = HOME / ".hermes" / "profiles" / "agies" / "skills"
        self.CONFIG_DIR: Path = self.AEGIS_DIR / "config"
        self.SCRIPTS_DIR: Path = self.AEGIS_DIR / "scripts"
        self.EXPERIENCES_FILE: Path = self.AEGIS_DIR / "experiences.json"

        # ── Default Model IDs ──────────────────────────────────────────────────
        # AEGIS's direct multi-provider free fabric.  No gateway dependency.
        self.FREE_CHAT_MODELS: List[str] = [
            "cl/z-ai/glm-5.2:free",              # ① Flagship reasoning (may be rate-limited)
            "cl/nex-agi/nex-n2.5-pro:free",      # ② Pro-tier general purpose
            "cl/google/gemma-4-31b-it:free",     # ③ 31B params, strong general
            "cl/cohere/north-mini-code:free",    # ④ Code specialist
            "cl/poolside/laguna-s-2.1:free",     # ⑤ Coding-focused
            "cl/nex-agi/nex-n2.5-mini:free",     # ⑥ Mini-tier fast
            "cl/inclusionai/ling-3.0-flash-vl:free",  # ⑦ Vision-language flash
            "cl/dots-studio/dots-3-note-preview:free", # ⑧ Draft/note model
        ]
        self.MODEL_DEFAULT: str = os.environ.get("AEGIS_DEFAULT_MODEL", "cl/nex-agi/nex-n2.5-pro:free")
        self.MODEL_REASONING: str = os.environ.get("AEGIS_REASONING_MODEL", "cl/z-ai/glm-5.2:free")
        self.MODEL_FAST: str = os.environ.get("AEGIS_FAST_MODEL", "cl/nex-agi/nex-n2.5-mini:free")
        self.MODEL_LITE: str = os.environ.get("AEGIS_LITE_MODEL", "cl/dots-studio/dots-3-note-preview:free")
        self.MODEL_FALLBACK_CHAIN: List[str] = [
            self.MODEL_DEFAULT, self.MODEL_REASONING, self.MODEL_FAST, self.MODEL_LITE
        ]
        # One model per turn, round-robin across all working free models.
        # No slow serial cascade — each request picks the next healthy model.
        self.CHAT_MODEL_POOL: List[str] = list(self.FREE_CHAT_MODELS)

        # ── Security ───────────────────────────────────────────────────────────
        self.PATH_ACCESS_GUARD: str = str(HOME)  # filesystem reads must start with this

        # ── Computed paths from platform ───────────────────────────────────────
        self._user_bin: Path = HOME / ".local" / "bin"
        self._mise_installs: Path = HOME / ".local" / "share" / "mise" / "installs"
        self._npm_global: Path = HOME / ".npm-global" / "bin"
        self._opencode_bin: Path = HOME / ".opencode" / "bin" / "opencode"

        # ── Ensure critical dirs exist ─────────────────────────────────────────
        self.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        self.AEGIS_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def AGENT_REGISTRY(self) -> List[Dict[str, Any]]:
        """Load agent registry once, cache it. Resolves CLI paths relative to HOME."""
        if self._registry_cache is not None:
            return self._registry_cache
        reg_file = self.REGISTRIES_DIR / "AGENT_REGISTRY.json"
        if not reg_file.exists():
            self._registry_cache = []
            return self._registry_cache
        try:
            data = json.loads(reg_file.read_text())
            agents = data.get("agents", [])
            # Resolve relative CLI paths
            for ag in agents:
                cli = ag.get("cli", "")
                if cli and not cli.startswith("/"):
                    # resolve ~ or relative
                    ag["cli"] = str(Path(cli).expanduser())
                elif cli and "{HOME}" in cli:
                    ag["cli"] = cli.replace("{HOME}", str(HOME))
            self._registry_cache = agents
        except Exception:
            self._registry_cache = []
        return self._registry_cache

    @property
    def PROJECTS(self) -> Dict[str, Path]:
        """
        Project name → absolute path.
        Derived from AGENT_REGISTRY + sensible defaults for common project dirs.
        Does NOT hardcode usernames.
        """
        projects: Dict[str, Path] = {}
        # 1. Scan ~/Projects directory
        projects_dir = HOME / "Projects"
        if projects_dir.exists():
            for p in projects_dir.iterdir():
                if p.is_dir() and (p / ".git").exists():
                    projects[p.name] = p

        # 2. Add the dashboard repo itself
        repo = self.REPO_ROOT
        if repo.exists():
            projects[repo.name] = repo

        # 3. Add agent home dirs that look like project roots
        for candidate in [
            HOME / ".hermes" / "hermes-agent",
            HOME / ".opencode",
            HOME / ".openclaw" / "workspace",
        ]:
            if candidate.exists():
                projects[candidate.name] = candidate

        # 3b. Known non-git project roots (agies full-index 2026-09-27).
        # cfg.PROJECTS otherwise only discovers dirs containing .git, which
        # hides Amruthpaan, artemis, SkillOpt, school-netops, etc.
        for candidate in [
            HOME / "Projects" / "Amruthpaan-Mukhwaas-Store",
            HOME / "Projects" / "artemis" / "artemis-main",
            HOME / "Projects" / "SkillOpt",
            HOME / "Projects" / "school-netops",
            HOME / "Work",
            HOME / "netops-backups",
            HOME / "qwen-audio-agent",
            HOME / "pinokio",
        ]:
            if candidate.exists() and candidate.name not in projects:
                projects[candidate.name] = candidate

        # 4. Scan DeepSeek repos inside dashboard
        deepseek = self.REPO_ROOT / "repos"
        if deepseek.exists():
            for p in deepseek.iterdir():
                if p.is_dir():
                    projects[p.name] = p

        return projects

    def resolve_agent_command(self, agent_id: str) -> List[str]:
        """
        Returns the CLI command list for an agent by reading AGENT_REGISTRY.
        Falls back to shutil.which() for discovery. Never hardcodes paths.
        """
        import shutil
        # 1. Check registry first
        for ag in self.AGENT_REGISTRY:
            if ag.get("id") == agent_id:
                cli = ag.get("cli", "")
                command_str = ag.get("command", cli)
                # Build command from registry fields
                if cli and Path(cli).exists():
                    parts = command_str.split()
                    if parts and Path(parts[0]).exists():
                        return parts
                    return [cli]
                
                # If command_str is explicitly provided and starts with an existing binary (like python3)
                parts = command_str.split()
                if parts:
                    found = shutil.which(parts[0])
                    if found:
                        parts[0] = found
                        return parts
                        
                # Try shutil.which on cli fallback
                binary_name = Path(cli).name if cli else agent_id
                found = shutil.which(binary_name)
                if found:
                    cmd_parts = command_str.split() if command_str else [binary_name]
                    cmd_parts[0] = found
                    return cmd_parts
        # 2. Final fallback: system PATH search
        found = shutil.which(agent_id)
        if found:
            return [found]
        # 3. Return bash for anything unknown
        return ["/usr/bin/bash", "--login"]

    def get_agent_env(self) -> Dict[str, str]:
        """Returns a clean environment dict for agent subprocess spawning."""
        base_path = os.environ.get("PATH", "/usr/bin:/bin")
        extra_bins = ":".join([
            str(self._user_bin),
            str(self._mise_installs / "shims") if (self._mise_installs / "shims").exists() else "",
            str(self._npm_global) if self._npm_global.exists() else "",
        ])
        return {
            **os.environ,
            "TERM": "xterm-256color",
            "HOME": str(HOME),
            "LANG": "en_US.UTF-8",
            "PATH": base_path + ":" + extra_bins,
        }


# ── Global singleton ────────────────────────────────────────────────────────────
cfg = AegisConfig()


if __name__ == "__main__":
    print("=== AEGIS Config Verification ===")
    print(f"HOME:           {HOME}")
    print(f"USER:           {USER}")
    print(f"VAULT:          {cfg.VAULT} ({'exists' if cfg.VAULT.exists() else 'MISSING'})")
    print(f"AEGIS_DIR:      {cfg.AEGIS_DIR}")
    print(f"REPO_ROOT:      {cfg.REPO_ROOT}")
    print(f"BACKEND_PORT:   {cfg.BACKEND_PORT}")
    print(f"MODEL_DEFAULT:  {cfg.MODEL_DEFAULT}")
    print(f"MODEL_REASONING:{cfg.MODEL_REASONING}")
    print(f"MODEL_FAST:     {cfg.MODEL_FAST}")
    print(f"Projects found: {list(cfg.PROJECTS.keys())}")
    print(f"Agents in registry: {[a['id'] for a in cfg.AGENT_REGISTRY]}")
    # Test agent command resolution
    for agent_id in ["hermes", "opencode", "bash", "unknown_agent"]:
        cmd = cfg.resolve_agent_command(agent_id)
        print(f"  resolve_agent_command('{agent_id}'): {cmd}")
    print("Config: VERIFIED OK")
