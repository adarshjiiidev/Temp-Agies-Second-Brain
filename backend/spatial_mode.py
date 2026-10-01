#!/usr/bin/env python3
"""
AEGIS Spatial Multi-Agent Mode (P6.2) + Self-Work Loop (P6.4).
Sequential lane sweep: ONE project at a time, never parallel LLM storms.
Lazy/guarded imports so this module never crashes the server on import.
"""
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

# Lazy handles — resolved inside functions, never at import time.
_CFG = None
_LOG = None


def _cfg():
    global _CFG
    if _CFG is None:
        try:
            from backend.config import cfg as c
            _CFG = c
        except Exception:
            _CFG = None
    return _CFG


def _log():
    global _LOG
    if _LOG is None:
        try:
            from backend.logger import get_logger
            _LOG = get_logger("spatial_mode")
        except Exception:
            import logging
            _LOG = logging.getLogger("spatial_mode")
    return _LOG


def _frontier():
    """Guarded frontier import — returns module or None."""
    try:
        import backend.frontier_adapter as fa
        return fa
    except Exception as e:
        _log().warning("frontier unavailable: %s", e)
        return None


def _mem0():
    try:
        from backend.mem0_engine import mem0_engine
        return mem0_engine
    except Exception:
        return None


DEFAULT_MAX_TURNS = 20
VALID_MODES = ("react", "agent_team")


def lane_sweep(projects: Optional[List[str]] = None, mode: str = "react",
               task: str = "", dry_run: bool = True,
               max_turns: int = DEFAULT_MAX_TURNS,
               auto_approve: bool = False) -> dict:
    """
    Sequential per-project sweep. One-by-one discipline: iterate projects in
    order, build context pack per project, execute (or plan in dry_run).
    dry_run=True  -> returns planned queue, executes NOTHING.
    dry_run=False -> executes via frontier_adapter.run_task, writes experience.
    """
    if mode not in VALID_MODES:
        return {"status": "error", "reason": "mode must be react|agent_team"}
    fa = _frontier()
    cfg = _cfg()
    known: Dict[str, Any] = {}
    try:
        if cfg is not None:
            known = dict(cfg.PROJECTS)
    except Exception:
        known = {}
    targets = projects or sorted(known.keys())
    queue, results = [], []
    for name in targets:  # SEQUENTIAL — never parallelize this loop
        cwd = str(known.get(name, "")) if name in known else ""
        pack_preview = ""
        if fa is not None:
            try:
                pack = fa.build_context_pack(project=name, task=task or name)
                pack_preview = pack[:500]
            except Exception as e:
                pack_preview = f"(pack unavailable: {e})"
        item = {"project": name, "cwd": cwd, "mode": mode,
                "max_turns": max_turns, "pack_preview": pack_preview}
        queue.append(item)
        if dry_run:
            continue
        # --- live execution branch (bounded) ---
        if fa is None:
            results.append({**item, "status": "SKIPPED", "reason": "frontier unavailable"})
            continue
        try:
            rec = fa.run_task(task or f"Spatial lane work on {name}",
                              mode=mode, cwd=cwd or None, project=name,
                              max_turns=max_turns, auto_approve=auto_approve)
        except Exception as e:
            rec = {"status": "FAILED", "reason": str(e)[:300]}
        results.append({**item, **rec})
        # experience writeback (best-effort, never crash sweep)
        try:
            m = _mem0()
            if m is not None:
                m.add(f"[spatial:{mode}] {name}: {rec.get('status')} "
                      f"run_dir={rec.get('run_dir')} task={task[:200]}",
                      agent_id="spatial_mode", project_id=name,
                      category="experience",
                      metadata={"mode": mode, "status": rec.get("status")})
        except Exception as e:
            _log().warning("experience writeback failed: %s", e)
        time.sleep(1)  # quota breather between lanes
    return {"status": "PLANNED" if dry_run else "COMPLETE",
            "mode": mode, "dry_run": dry_run,
            "queue": queue, "results": results,
            "lanes": len(queue)}


def sweep_status(limit: int = 20) -> dict:
    """Read frontier run dirs (read-only, no LLM calls)."""
    fa = _frontier()
    if fa is None:
        return {"status": "frontier unavailable", "runs": []}
    try:
        runs = fa.list_runs(limit=limit)
        return {"status": "ok", "runs": runs, "count": len(runs)}
    except Exception as e:
        return {"status": "error", "reason": str(e)[:200], "runs": []}


if __name__ == "__main__":
    import json
    import sys
    dry = "--live" not in sys.argv
    print(json.dumps(lane_sweep(mode="react", dry_run=dry), indent=1)[:2000])
