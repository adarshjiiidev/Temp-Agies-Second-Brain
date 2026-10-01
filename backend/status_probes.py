#!/usr/bin/env python3
"""
AEGIS Status Probes — the single source of truth for health reporting.

Rule enforced here: `PASS` is never a default value. Every probe performs an
observable action (socket request, stat, binary lookup, store read, authorize
call) and returns a non-PASS status when that action does not confirm the claim.
Both `GET /api/system/graph` and `GET /api/health/doctor` consume these probes so
the dashboard and the doctor can never disagree, and so no status field can be
hardcoded at its call site again.

Status vocabulary:
  PASS            probe ran and its condition held
  DEGRADED        feature works, but a dependency/freshness condition did not
  NOT_CONFIGURED  the thing is absent by design or missing a credential
  NOT_IMPLEMENTED code path exists but is a stub, so the claim is not true
  FAIL            probe raised, or its condition was provably false
"""

import inspect
import json
import os
import shutil
import socket
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List

from backend.config import cfg
from backend.logger import get_logger

log = get_logger("status_probes")

PASS = "PASS"
DEGRADED = "DEGRADED"
NOT_CONFIGURED = "NOT_CONFIGURED"
NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
FAIL = "FAIL"


def _res(status: str, message: str, **extra: Any) -> Dict[str, Any]:
    out = {"status": status, "message": message, "probed_at": time.time()}
    out.update(extra)
    return out


def _guarded(fn: Callable[[], Dict[str, Any]], name: str) -> Dict[str, Any]:
    """A probe that raises must report FAIL, never fall back to PASS."""
    try:
        return fn()
    except Exception as e:
        return _res(FAIL, f"probe '{name}' raised {type(e).__name__}: {e}")


def probe_tcp(port: int, host: str = "127.0.0.1") -> bool:
    """Cheap TCP reachability check, for probes where HTTP would be too heavy."""
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False


# ── runtime ─────────────────────────────────────────────────────────────────

def probe_backend_api() -> Dict[str, Any]:
    """Prove the HTTP socket is bound and serving by requesting our own health."""
    def run():
        port = int(os.environ.get("AEGIS_BACKEND_PORT", "2981"))
        t0 = time.time()
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=3) as r:
            body = json.loads(r.read().decode(errors="replace"))
        ms = int((time.time() - t0) * 1000)
        if r.status != 200:
            return _res(FAIL, f"self-request returned HTTP {r.status}")
        return _res(PASS, f"serving on 127.0.0.1:{port}, self-request {ms}ms",
                    latency_ms=ms, reported=body.get("status"))
    return _guarded(run, "backend_api")


def probe_aegis_core() -> Dict[str, Any]:
    def run():
        problems = []
        if not cfg.AEGIS_DIR.is_dir():
            problems.append(f"state dir missing: {cfg.AEGIS_DIR}")
        elif not os.access(cfg.AEGIS_DIR, os.W_OK):
            problems.append(f"state dir not writable: {cfg.AEGIS_DIR}")
        from backend import governance  # noqa: F401  core must import cleanly
        from backend import execution_core  # noqa: F401
        if problems:
            return _res(FAIL, "; ".join(problems))
        return _res(PASS, "config loaded, state dir writable, core modules import",
                    state_dir=str(cfg.AEGIS_DIR))
    return _guarded(run, "aegis_core")


def probe_governance() -> Dict[str, Any]:
    """Governance is only real if authorize() answers and the audit trail writes."""
    def run():
        from backend.governance import governance
        level = int(governance.current_level)
        decision = governance.authorize("probe.status", "status_probes", {"reason": "health probe"})
        audit = getattr(governance, "audit_log_path", None)
        wrote = bool(audit and Path(audit).exists())
        if decision is None:
            return _res(FAIL, "authorize() returned None", level=level)
        if not wrote:
            return _res(DEGRADED, f"authorize() works (level {level}) but audit trail absent", level=level)
        return _res(PASS, f"authorize() responding at level {level}, audit trail present", level=level)
    return _guarded(run, "governance")

# ── MODELS ──────────────────────────────────────────────────────────────────

def probe_model_fabric() -> Dict[str, Any]:
    def run():
        from backend.free_router import get_free_router_health
        h = get_free_router_health()
        providers = h.get("providers", {})
        live = [p for p, s in providers.items() if s == "online"]
        pool = int(h.get("available_models", 0))
        if h.get("status") == "degraded" or not live:
            return _res(FAIL, f"no provider has a usable key (pool={pool})", providers=providers)
        if len(live) == 1:
            return _res(DEGRADED,
                        f"single-provider fabric: only {live[0]} online (pool={pool}); "
                        "failover has nowhere to go",
                        providers=providers, live=live, pool=pool)
        return _res(PASS, f"{len(live)} providers online ({', '.join(live)}), pool={pool}",
                    providers=providers, live=live, pool=pool)
    return _guarded(run, "model_fabric")


def probe_planner() -> Dict[str, Any]:
    def run():
        import backend.task_planner  # noqa: F401
        from backend.free_router import get_round_robin_candidates
        n = len(get_round_robin_candidates())
        if n == 0:
            return _res(FAIL, "task_planner imports but no model candidate is routable")
        return _res(PASS, f"task_planner importable, {n} routable candidates", candidates=n)
    return _guarded(run, "planner")


def probe_context_engine() -> Dict[str, Any]:
    def run():
        import backend.context_router as cr
        router = getattr(cr, "ContextRouter", None)
        if router is None:
            return _res(FAIL, "context_router.ContextRouter missing")
        methods = sorted(n for n in vars(router) if not n.startswith("_"))
        if not methods:
            return _res(NOT_IMPLEMENTED, "ContextRouter exposes no public method")
        return _res(PASS, f"ContextRouter exposes {', '.join(methods[:4])}")
    return _guarded(run, "context_engine")


# ── MEMORY ──────────────────────────────────────────────────────────────────

STALE_AFTER_H = float(os.environ.get("AEGIS_MEMORY_STALE_HOURS", "24"))


def _json_store_health(path: Path, label: str) -> Dict[str, Any]:
    """Count records and report the newest timestamp in a JSON record store."""
    if not path.exists():
        return _res(NOT_CONFIGURED, f"{label} store absent: {path}")
    try:
        data = json.loads(path.read_text(errors="replace"))
    except Exception as e:
        return _res(FAIL, f"{label} store unreadable: {type(e).__name__}: {e}")
    recs = list(data.values()) if isinstance(data, dict) else (data if isinstance(data, list) else None)
    if recs is None:
        return _res(FAIL, f"{label} store has unexpected shape {type(data).__name__}")
    newest = 0.0
    for r in recs:
        if isinstance(r, dict):
            for k in ("created_at", "timestamp", "ts", "updated_at"):
                v = r.get(k)
                if isinstance(v, (int, float)) and v > newest:
                    newest = float(v)
    age_h = (time.time() - newest) / 3600.0 if newest else None
    meta = {"label": label, "records": len(recs), "path": str(path),
            "age_hours": round(age_h, 1) if age_h is not None else None}
    if not recs:
        return _res(NOT_CONFIGURED, f"{label} store empty", **meta)
    if age_h is None:
        return _res(DEGRADED, f"{label}: {len(recs)} records carry no timestamp", **meta)
    if age_h > STALE_AFTER_H:
        return _res(DEGRADED, f"{label} frozen: {len(recs)} records, newest {age_h:.0f}h old "
                              f"(threshold {STALE_AFTER_H:.0f}h) — writes are not landing", **meta)
    return _res(PASS, f"{label}: {len(recs)} records, newest {age_h:.1f}h old", **meta)


def probe_memory_mem0() -> Dict[str, Any]:
    def run():
        from backend.mem0_engine import mem0_engine
        return _json_store_health(Path(mem0_engine.store_path), "mem0")
    return _guarded(run, "memory_mem0")


def probe_memory_turboquant() -> Dict[str, Any]:
    return _guarded(lambda: _json_store_health(cfg.AEGIS_DIR / "turboquant_store.json",
                                              "turboquant"), "memory_turboquant")


def probe_memory_cognitive() -> Dict[str, Any]:
    def run():
        import backend.memory_engine as me
        if not hasattr(me, "CognitiveMemoryEngine"):
            return _res(FAIL, "memory_engine.CognitiveMemoryEngine missing")
        engine = getattr(me, "memory_engine", None)
        if engine is None:
            return _res(DEGRADED, "class present but no module-level engine instance")
        files = engine._get_memory_files()
        if not files:
            return _res(NOT_CONFIGURED, f"cognitive engine scans 0 memory files under {cfg.VAULT}")
        return _res(PASS, f"cognitive engine scans {len(files)} memory files", files=len(files))
    return _guarded(run, "memory_cognitive")


def probe_knowledge_graph() -> Dict[str, Any]:
    def run():
        from backend.knowledge_graph import KnowledgeGraph
        g = KnowledgeGraph().get_graph_data()
        counts = g.get("counts", {})
        nodes = counts.get("total_nodes", len(g.get("nodes", [])))
        edges = counts.get("total_edges", len(g.get("edges", [])))
        if nodes == 0:
            return _res(NOT_CONFIGURED, "knowledge graph holds 0 nodes (no learn job has run)")
        return _res(PASS, f"{nodes} nodes / {edges} edges", nodes=nodes, edges=edges)
    return _guarded(run, "knowledge_graph")


def probe_obsidian() -> Dict[str, Any]:
    def run():
        vault = cfg.VAULT
        if not vault.is_dir():
            return _res(FAIL, f"vault directory missing: {vault}")
        total = sum(1 for _ in vault.rglob("*.md"))
        if total == 0:
            return _res(NOT_CONFIGURED, f"vault exists but holds 0 notes: {vault}")
        return _res(PASS, f"{total} notes under {vault}", notes=total)
    return _guarded(run, "obsidian")


# ── CAPABILITIES ────────────────────────────────────────────────────────────

def probe_skills() -> Dict[str, Any]:
    def run():
        from backend.skill_registry import skill_registry
        skills = skill_registry.get_all_skills()
        unreadable = list(getattr(skill_registry, "unreadable", []) or [])
        if not skills:
            return _res(NOT_CONFIGURED, "skill registry discovered 0 skills",
                        scanned=[str(p) for p in getattr(skill_registry, "scan_dirs", [])])
        if unreadable:
            return _res(DEGRADED, f"{len(skills)} skills discovered, but sources unread: {unreadable}",
                        count=len(skills), unreadable=unreadable)
        return _res(PASS, f"{len(skills)} skills discovered from real manifests", count=len(skills))
    return _guarded(run, "skills")


def probe_ecc_skills() -> Dict[str, Any]:
    def run():
        from backend.integrations.ecc.adapter import ecc_registry
        n = len(ecc_registry.skills)
        if n == 0:
            return _res(NOT_IMPLEMENTED,
                        "ECC registry loads no manifest anywhere in the code — its skill list is "
                        "empty unless a caller injects one")
        return _res(PASS, f"{n} ECC skills imported", count=n)
    return _guarded(run, "ecc_skills")


def probe_voice() -> Dict[str, Any]:
    def run():
        sock = Path(f"/run/user/{os.getuid()}/voxtype/audio.sock")
        binary = bool(shutil.which("whisper") or shutil.which("whisperx"))
        if not sock.exists() and not binary:
            return _res(NOT_CONFIGURED, "no ASR binary and no voxtype socket present")
        return _res(NOT_IMPLEMENTED,
                    "ASR capability exists outside AEGIS "
                    f"(socket={sock.exists()}, whisper={binary}) but the VoiceStudio adapter "
                    "returns canned audio/transcript, so AEGIS voice is not real",
                    voxtype_socket=str(sock), asr_binary=binary)
    return _guarded(run, "voice")


def probe_browser_tool() -> Dict[str, Any]:
    def run():
        import backend.browser_tool  # noqa: F401
        browser = next((b for b in ("google-chrome", "chromium", "chromium-browser", "chrome")
                        if shutil.which(b)), None)
        if not browser:
            return _res(NOT_CONFIGURED, "no Chrome/Chromium binary on PATH")
        return _res(DEGRADED, f"{browser} present; actuator routes are reachable without a token "
                              "and URL validation is scheme-only", browser=browser)
    return _guarded(run, "browser_tool")


# ── EXECUTORS / IDEs ────────────────────────────────────────────────────────

def probe_frontier() -> Dict[str, Any]:
    def run():
        from backend.frontier_adapter import frontier_adapter
        a = frontier_adapter.is_available()
        if not a.get("installed"):
            return _res(NOT_CONFIGURED, str(a.get("reason", "FrontierAgent runtime absent")))
        runs = Path(a.get("runs_root", ""))
        n_runs = sum(1 for _ in runs.glob("*")) if runs.is_dir() else 0
        if n_runs == 0:
            return _res(DEGRADED, "runtime installed but no execution has ever been recorded", **a)
        return _res(PASS, f"runtime installed, {n_runs} recorded runs", runs=n_runs)
    return _guarded(run, "frontier")


def probe_multica() -> Dict[str, Any]:
    return _res(NOT_IMPLEMENTED,
                "no Multica daemon exists; the adapter fabricates ASSIGNED then COMPLETED 100% "
                "without performing work, so any Multica status must be read as fake")


def probe_hermes() -> Dict[str, Any]:
    def run():
        py = cfg.HOME / ".hermes" / "hermes-agent" / "venv" / "bin" / "python"
        if not py.exists():
            return _res(NOT_CONFIGURED, f"hermes venv python absent: {py}")
        return _res(PASS, f"hermes harness present at {py}", python=str(py))
    return _guarded(run, "hermes")


def probe_opencode() -> Dict[str, Any]:
    binary = shutil.which("opencode")
    if not binary:
        return _res(NOT_CONFIGURED, "opencode binary not on PATH")
    return _res(PASS, f"opencode present at {binary}", binary=binary)


# ── SCHEDULING / DAEMONS ────────────────────────────────────────────────────

def _stubbed_methods(obj, names: List[str]) -> List[str]:
    """Report which methods contain no executable statements (docstring/pass only)."""
    stubs = []
    for name in names:
        fn = getattr(obj, name, None)
        if fn is None:
            continue
        try:
            raw = inspect.getsource(fn).splitlines()[1:]
        except (OSError, TypeError):
            continue
        code = [l.strip() for l in raw if l.strip()]
        if code and code[0].startswith(('"""', "'''")):
            quote = code[0][:3]
            end = next((i for i, l in enumerate(code[1:], 1) if l.endswith(quote)), 0)
            code = code[end + 1:]
        code = [l for l in code if not l.startswith("#") and l not in ("pass", "...")]
        if not code:
            stubs.append(name)
    return stubs


def probe_ingest_daemon() -> Dict[str, Any]:
    def run():
        from backend.ingest_daemon import ingest_daemon
        names = ["_poll_ide_agents", "_poll_frontier", "_poll_multica", "_poll_ecc"]
        stubs = _stubbed_methods(ingest_daemon, names)
        if stubs:
            return _res(NOT_IMPLEMENTED,
                        f"{len(stubs)}/{len(names)} poll loops are empty stubs ({', '.join(stubs)}); "
                        "the running flag is not evidence of ingestion")
        last = float(ingest_daemon.checkpoints.get("last_run", 0) or 0)
        if not last:
            return _res(DEGRADED, "poll loops implemented but no cycle has completed yet")
        age_min = (time.time() - last) / 60.0
        if age_min > 10:
            return _res(DEGRADED, f"last poll {age_min:.0f} min ago (>10 min)")
        return _res(PASS, f"last poll {age_min:.1f} min ago", age_min=round(age_min, 1))
    return _guarded(run, "ingest_daemon")


def _unit_state(unit: str) -> str:
    try:
        return subprocess.run(["systemctl", "--user", "is-active", unit],
                              capture_output=True, text=True, timeout=8).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _user_units(pattern: str) -> List[str]:
    try:
        out = subprocess.run(["systemctl", "--user", "list-unit-files", pattern, "--no-legend"],
                             capture_output=True, text=True, timeout=8).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [l.split()[0] for l in out.splitlines() if l.strip()]


def probe_scheduled_jobs() -> Dict[str, Any]:
    """Timers can all be green while double-scheduling the same job; measure that."""
    def run():
        timers = _user_units("aegis-*.timer")
        if not timers:
            return _res(NOT_CONFIGURED, "no aegis-*.timer units installed for this user")
        active = [t for t in timers if _unit_state(t) == "active"]
        by_job: Dict[str, List[str]] = {}
        for t in active:
            by_job.setdefault(t.replace("-daily", "").replace(".timer", ""), []).append(t)
        duplicates = {k: v for k, v in by_job.items() if len(v) > 1}
        if duplicates:
            key, group = next(iter(duplicates.items()))
            return _res(DEGRADED,
                        f"{key} is scheduled by {len(group)} active timers ({', '.join(group)}) — "
                        "this job runs far more often than documented",
                        timers=active, duplicates=duplicates)
        return _res(PASS, f"{len(active)}/{len(timers)} aegis timers active, no duplicate schedule",
                    timers=active)
    return _guarded(run, "scheduled_jobs")


# ── REGISTRY / CONSUMERS ────────────────────────────────────────────────────

PROBES: Dict[str, Callable[[], Dict[str, Any]]] = {
    "backend_api": probe_backend_api,
    "aegis_core": probe_aegis_core,
    "context_engine": probe_context_engine,
    "planner": probe_planner,
    "memory_mem0": probe_memory_mem0,
    "memory_turboquant": probe_memory_turboquant,
    "memory_cognitive": probe_memory_cognitive,
    "knowledge_graph": probe_knowledge_graph,
    "obsidian": probe_obsidian,
    "model_fabric": probe_model_fabric,
    "skills": probe_skills,
    "ecc_skills": probe_ecc_skills,
    "voice": probe_voice,
    "browser": probe_browser_tool,
    "frontier": probe_frontier,
    "multica": probe_multica,
    "hermes": probe_hermes,
    "opencode": probe_opencode,
    "governance": probe_governance,
    "ingest_daemon": probe_ingest_daemon,
    "scheduled_jobs": probe_scheduled_jobs,
}

# system-graph node id -> probe key. A node with no entry here is a bug: the graph
# endpoint refuses to render a node it cannot probe (see api_system_graph).
GRAPH_PROBES: Dict[str, str] = {
    "aegis_core": "aegis_core",
    "context": "context_engine",
    "planner": "planner",
    "memory": "memory_mem0",
    "obsidian": "obsidian",
    "capabilities": "skills",
    "model_router": "model_fabric",
    "frontier": "frontier",
    "multica": "multica",
    "ecc_skills": "ecc_skills",
    "voicestudio": "voice",
    "opencode": "opencode",
    "hermes": "hermes",
    "l5_governance": "governance",
}

# doctor rows: (probe key, display name)
DOCTOR_CHECKS: List = [
    ("aegis_core", "AEGIS Core"),
    ("backend_api", "Backend API"),
    ("governance", "L5 Governance"),
    ("memory_mem0", "Memory (mem0)"),
    ("memory_turboquant", "Memory (TurboQuant)"),
    ("memory_cognitive", "Memory (Cognitive)"),
    ("knowledge_graph", "Knowledge Graph"),
    ("obsidian", "Obsidian Vault"),
    ("model_fabric", "Model Fabric"),
    ("planner", "Planner"),
    ("context_engine", "Context Engine"),
    ("skills", "Skill Registry"),
    ("ecc_skills", "ECC Skills"),
    ("frontier", "FrontierAgent"),
    ("multica", "Multica"),
    ("voice", "Voice / ASR"),
    ("browser", "Browser Actuator"),
    ("hermes", "Hermes Agent"),
    ("opencode", "OpenCode"),
    ("ingest_daemon", "Ingest Daemon"),
    ("scheduled_jobs", "Scheduled Jobs"),
]


def run_probes(names: List[str]) -> Dict[str, Dict[str, Any]]:
    """Run the named probes once and return {key: result}."""
    return {n: PROBES[n]() for n in names if n in PROBES}


def run_all_probes() -> Dict[str, Dict[str, Any]]:
    return run_probes(list(PROBES))


if __name__ == "__main__":
    results = run_all_probes()
    print(json.dumps(results, indent=2, default=str))
    bad = {k: v["status"] for k, v in results.items() if v["status"] != PASS}
    print(f"\n{len(results) - len(bad)}/{len(results)} probes PASS")
    for key, status in bad.items():
        print(f"  {status:15} {key}: {results[key]['message']}")



