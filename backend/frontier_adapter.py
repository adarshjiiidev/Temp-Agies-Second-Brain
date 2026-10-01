#!/usr/bin/env python3
"""
AEGIS FrontierAgent Adapter — first-class execution backend.
AEGIS stays executive; Frontier executes (ReAct / Agent Team) via its CLI
in its own venv. Free-quota models from the AEGIS free fabric (OpenRouter
free tier) are injected as OpenAI-compatible env. No secrets in logs/traces.
"""
import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional

from backend.config import cfg
from backend.logger import get_logger

log = get_logger("frontier_adapter")

FRONTIER_ROOT = Path.home() / "Work" / "FrontierAgent"
FRONTIER_PY = FRONTIER_ROOT / ".venv" / "bin" / "python"
RUNS_ROOT = Path.home() / ".temporary-aegis" / "frontier_runs"

CAPABILITIES = ["frontier.react", "frontier.agent_team", "frontier.resume", "frontier.trace"]


def is_available() -> dict:
    return {"installed": FRONTIER_PY.exists(), "python": str(FRONTIER_PY),
            "runs_root": str(RUNS_ROOT)}


def _free_model_env(model: Optional[str] = None) -> dict:
    """Map AEGIS free fabric -> Frontier OPENAI_* env. Key never logged."""
    from backend.free_router import resolve_keys, get_round_robin_candidates
    keys = resolve_keys()
    o_key = keys.get("OPENROUTER_API_KEY", "")
    cands = get_round_robin_candidates()
    pick = model or (cands[0] if cands else cfg.MODEL_DEFAULT)
    # Strip 'cl/' prefix style used by free fabric for OpenRouter IDs
    openai_model = pick[3:] if pick.startswith("cl/") else pick
    env = {"OPENAI_BASE_URL": "https://openrouter.ai/api/v1", "OPENAI_MODEL": openai_model,
           "OPENAI_MAX_TOKENS": "16384"}
    if o_key:
        env["OPENAI_API_KEY"] = o_key
    return env


def _redacted_env(env: dict) -> dict:
    return {k: ("***" if "KEY" in k else v) for k, v in env.items()}


def build_context_pack(project: str = "", task: str = "", extra: str = "", envelope: Optional[dict] = None) -> str:
    """Assemble the lightweight AEGIS context pack (budgeted, no full memory dump)."""
    parts = [f"# AEGIS Context Pack for Frontier — {time.strftime('%Y-%m-%d %H:%M')}"]
    if envelope:
        # The caller has already assembled the canonical AEGIS envelope.  Keep
        # it bounded and do not independently invent a second context system.
        parts.append("## AEGIS execution envelope\n" + json.dumps(envelope, indent=1)[:7000])
    try:
        from backend.project_intelligence import project_intelligence
        if project and project in cfg.PROJECTS:
            parts.append("## Project\n" + json.dumps(project_intelligence.get_project_summary(project), indent=1)[:2000])
    except Exception as e:
        parts.append(f"## Project\n(unavailable: {e})")
    try:
        from backend.mem0_engine import mem0_engine
        hits = mem0_engine.search(task or project, limit=3)
        parts.append("## Relevant memory\n" + "\n".join("- " + h["text"][:300] for h in hits))
    except Exception as e:
        parts.append(f"## Relevant memory\n(unavailable: {e})")
    prefs = Path.home() / "ObsidianVault" / "ABOUT_ME.md"
    if prefs.exists():
        parts.append("## User (summary)\nAdarsh Jii. Dark premium minimal UI, orange/amber accent, high density. See vault ABOUT_ME.md.")
    if extra:
        parts.append("## Constraints\n" + extra[:1000])
    parts.append("## Governance\nL5: request approval for shell/file-write/network side effects per Frontier --yes policy (default: approvals ON).")
    return "\n\n".join(parts)


def run_task(task: str, mode: str = "react", cwd: Optional[str] = None,
             project: str = "", model: Optional[str] = None,
             max_turns: int = 20, auto_approve: bool = False,
             timeout: int = 600, context: Optional[dict] = None,
             task_id: str = "") -> dict:
    """Launch a Frontier run headlessly. Returns run record (never includes secrets)."""
    avail = is_available()
    if not avail["installed"]:
        return {"status": "NOT_CONFIGURED", "reason": "frontier venv python missing"}
    if mode not in ("react", "agent_team"):
        return {"status": "error", "reason": "mode must be react|agent_team"}
    # Frontier is never its own authorization boundary.  AEGIS retains the
    # side-effect decision even when a caller reaches this adapter directly.
    from backend.governance import governance
    if auto_approve and not governance.authorize(
        "terminal_run", "frontier.adapter", {"command": "apodex --yes", "task_id": task_id}
    ):
        return {"status": "BLOCKED", "reason": "AEGIS L5 denied auto approval", "task_id": task_id}
    RUNS_ROOT.mkdir(parents=True, exist_ok=True)
    workdir = Path(cwd) if cwd else (cfg.PROJECTS.get(project, Path.home() / "Work") if project else Path.home() / "Work")
    workdir = workdir.expanduser().resolve()
    if not workdir.exists() or not workdir.is_dir():
        return {"status": "FAILED", "reason": "approved workspace does not exist", "task_id": task_id}
    pack = build_context_pack(project, task, envelope=context)
    pack_file = RUNS_ROOT / f"context-{uuid.uuid4().hex[:8]}.md"
    pack_file.write_text(pack)
    env = {**os.environ, **_free_model_env(model),
           "APODEX_RUNS_ROOT": str(RUNS_ROOT), "NO_COLOR": "1"}
    cmd = [str(FRONTIER_PY), "-m", "apodex", "-p", task, "--mode", mode,
           "--cwd", str(workdir), "--input", str(pack_file),
           "--max-turns", str(max_turns), "--no-tui"]
    if auto_approve:
        cmd.append("-y")
    log.info("frontier run start mode=%s cwd=%s env=%s", mode, workdir, _redacted_env(_free_model_env(model)))
    before = set(p.name for p in RUNS_ROOT.iterdir() if p.is_dir())
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           cwd=str(FRONTIER_ROOT), env=env)
    except subprocess.TimeoutExpired:
        return {"status": "TIMEOUT", "mode": mode, "timeout": timeout}
    after = [p for p in RUNS_ROOT.iterdir() if p.is_dir() and p.name not in before]
    if not after:
        # This Frontier version roots runs at <cwd>/.apodex/runs regardless of env
        cw_runs = workdir / ".apodex" / "runs"
        if cw_runs.is_dir():
            cands = sorted([p for p in cw_runs.iterdir() if p.is_dir()],
                           key=lambda p: p.stat().st_mtime, reverse=True)
            after = cands[:1]
    run_dir = str(after[0]) if after else None
    artifacts = []
    if run_dir:
        root = Path(run_dir)
        for name in ("session.json", "trace.jsonl", "engine.log", "trajectory.json"):
            fp = root / name
            if fp.exists():
                artifacts.append({"kind": name, "path": str(fp), "bytes": fp.stat().st_size})
    return {"status": "COMPLETE" if r.returncode == 0 else "FAILED", "task_id": task_id,
            "run_id": Path(run_dir).name if run_dir else None, "session": Path(run_dir).name if run_dir else None,
            "returncode": r.returncode, "mode": mode, "run_dir": run_dir, "artifacts": artifacts,
            "stdout_tail": r.stdout[-1500:], "stderr_tail": r.stderr[-800:]}


def list_runs(limit: int = 20) -> List[dict]:
    if not RUNS_ROOT.exists():
        return []
    runs = sorted([p for p in RUNS_ROOT.iterdir() if p.is_dir()],
                  key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    out = []
    for p in runs:
        trace = p / "trace.jsonl"
        n = sum(1 for _ in open(trace)) if trace.exists() else 0
        out.append({"session": p.name, "trace_lines": n,
                    "has_session_json": (p / "session.json").exists(),
                    "has_outputs": (p / "outputs").is_dir(),
                    "mtime": p.stat().st_mtime})
    return out


def read_trace(session: str, limit: int = 50) -> dict:
    t = RUNS_ROOT / session / "trace.jsonl"
    if not t.exists():
        return {"error": "no trace"}
    lines = t.read_text(errors="replace").splitlines()[-limit:]
    return {"session": session, "lines": [json.loads(l) for l in lines if l.strip()][:limit]}


frontier_adapter = None
try:
    class _A:
        run_task = staticmethod(run_task)
        list_runs = staticmethod(list_runs)
        read_trace = staticmethod(read_trace)
        build_context_pack = staticmethod(build_context_pack)
        is_available = staticmethod(is_available)
        capabilities = CAPABILITIES
    frontier_adapter = _A()
except Exception:
    pass
