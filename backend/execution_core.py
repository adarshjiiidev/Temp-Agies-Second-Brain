"""AEGIS-owned execution lifecycle.

This module is the single entry point for work that may select an internal
agent capability.  It deliberately records AEGIS IDs first and treats agent
IDs, provider session IDs, traces, and artifacts as linked external details.
It does not make a provider an alternate control plane.
"""
from __future__ import annotations

import json
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from backend.config import cfg
from backend.governance import governance
from backend.logger import get_logger

log = get_logger("execution_core")
TASK_STATES = ("BACKLOG", "READY", "RUNNING", "BLOCKED", "VERIFYING", "DONE", "FAILED", "NOT_CONFIGURED")


class AegisExecutionCore:
    """Persisted task, context, capability-selection, and result boundary."""

    def __init__(self, state_dir: Optional[Path] = None) -> None:
        self.state_dir = state_dir or cfg.AEGIS_DIR / "executions"
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, task_id: str) -> Path:
        return self.state_dir / f"{task_id}.json"

    def _save(self, record: Dict[str, Any]) -> Dict[str, Any]:
        record["updated_at"] = time.time()
        self._path(record["id"]).write_text(json.dumps(record, indent=2, default=str))
        return record

    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        path = self._path(task_id)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return None

    def list(self, limit: int = 50) -> list[Dict[str, Any]]:
        records = [self.get(p.stem) for p in self.state_dir.glob("aegis-*.json")]
        return sorted((r for r in records if r), key=lambda r: r.get("created_at", 0), reverse=True)[:limit]

    def registry(self) -> list[Dict[str, Any]]:
        """Return runtime-derived agent facts; never trust static installed flags."""
        result = []
        for source in cfg.AGENT_REGISTRY:
            item = dict(source)
            agent_id = item.get("id", "")
            command = cfg.resolve_agent_command(agent_id)
            binary = command[0] if command else ""
            installed = bool(binary and (Path(binary).exists() or shutil.which(binary)))
            item.update({
                "binary": binary or None,
                "version": None,  # discovery is intentionally non-executing
                "status": "AVAILABLE" if installed else "NOT_CONFIGURED",
                "health": "UNKNOWN" if installed else "NOT_CONFIGURED",
                "adapter": item.get("adapter", agent_id),
                "workspace_support": bool(item.get("workspace_support", True)),
                "memory_support": bool(item.get("memory_support", True)),
                "context_support": bool(item.get("context_support", True)),
                "session_support": bool(item.get("session_support", False)),
                "ingest_support": bool(item.get("ingest_support", False)),
            })
            if agent_id == "frontier":
                from backend.frontier_adapter import frontier_adapter
                availability = frontier_adapter.is_available()
                item["status"] = "AVAILABLE" if availability["installed"] else "NOT_CONFIGURED"
                item["health"] = item["status"]
                item["frontier"] = availability
            result.append(item)
        return result

    def envelope(self, task: str, project: str = "", task_id: str = "") -> Dict[str, Any]:
        """A budgeted envelope shared by every adapter (not a vault dump)."""
        memory: list[Dict[str, Any]] = []
        project_summary: Dict[str, Any] = {}
        preferences: Dict[str, Any] = {}
        try:
            from backend.mem0_engine import mem0_engine
            memory = mem0_engine.search(task, project_id=project or None, limit=5)
        except Exception as exc:
            log.warning("memory lookup unavailable: %s", type(exc).__name__)
        try:
            from backend.project_intelligence import project_intelligence
            if project:
                project_summary = project_intelligence.get_project_summary(project)
        except Exception as exc:
            log.warning("project lookup unavailable: %s", type(exc).__name__)
        try:
            import backend.preferences as preferences_store
            preferences = preferences_store.get_profile()
        except Exception as exc:
            log.warning("preferences lookup unavailable: %s", type(exc).__name__)
        return {
            "aegis_task_id": task_id,
            "project": project,
            "task": task[:8000],
            "project_state": project_summary,
            "relevant_memory": [{"id": m.get("id"), "text": m.get("text", "")[:500], "source": m.get("agent_id")}
                                for m in memory],
            "preferences": preferences,
            "governance": {"level": governance.current_level.name, "side_effects_require_authorization": True},
            "verification": "Report files, commands/tests, result, failures, and next step to AEGIS.",
        }

    @staticmethod
    def _required_capabilities(kind: str, parallelism: int, long_horizon: bool) -> set[str]:
        if parallelism > 1:
            return {"frontier.agent_team"}
        if long_horizon or kind == "research":
            return {"frontier.react"}
        if kind == "coding":
            return {"coding"}
        return set()

    def select(self, *, kind: str = "general", parallelism: int = 1,
               long_horizon: bool = False, requested_agent: str = "") -> Dict[str, Any]:
        """Score declared capabilities and live availability, never text-keyword tabs."""
        candidates = self.registry()
        if requested_agent:
            candidates = [a for a in candidates if a.get("id") == requested_agent]
        needed = self._required_capabilities(kind, parallelism, long_horizon)
        scored = []
        for agent in candidates:
            caps = set(agent.get("capabilities", [])) | set(agent.get("modes", [])) | {agent.get("type", "")}
            score = 0
            score += 100 if agent.get("status") == "AVAILABLE" else -100
            score += 50 * len(needed & caps)
            if kind == "coding" and ("coding" in caps or agent.get("id") in {"codex", "opencode"}): score += 20
            if long_horizon and "frontier.react" in caps: score += 20
            if parallelism > 1 and "frontier.agent_team" in caps: score += 20
            scored.append((score, agent))
        if not scored:
            return {"id": "aegis", "status": "AVAILABLE", "reason": "AEGIS handles planning-only request"}
        score, selected = max(scored, key=lambda pair: pair[0])
        return {"id": selected.get("id"), "name": selected.get("name"), "adapter": selected.get("adapter"),
                "status": selected.get("status"), "score": score, "required_capabilities": sorted(needed)}

    def create(self, task: str, *, project: str = "", kind: str = "general", parallelism: int = 1,
               long_horizon: bool = False, requested_agent: str = "") -> Dict[str, Any]:
        task_id = f"aegis-{uuid.uuid4().hex[:12]}"
        chosen = self.select(kind=kind, parallelism=parallelism, long_horizon=long_horizon,
                             requested_agent=requested_agent)
        record = {"id": task_id, "status": "READY", "created_at": time.time(), "task": task,
                  "project": project, "kind": kind, "parallelism": parallelism, "long_horizon": long_horizon,
                  "selected": chosen, "context": self.envelope(task, project, task_id), "events": [],
                  "external": {"agent_id": chosen.get("id"), "run_id": None, "session_id": None,
                               "trace": [], "artifacts": []}, "result": None}
        record["events"].append({"at": time.time(), "type": "TASK_CREATED", "actor": "aegis"})
        return self._save(record)

    def dispatch(self, task_id: str, *, auto_approve: bool = False, timeout: int = 600) -> Dict[str, Any]:
        record = self.get(task_id)
        if not record:
            return {"status": "NOT_FOUND", "id": task_id}
        selected = record["selected"]
        if selected.get("status") != "AVAILABLE":
            record["status"] = "NOT_CONFIGURED"
            record["result"] = {"reason": f"{selected.get('id', 'selected adapter')} is not configured"}
            return self._save(record)
        if selected.get("id") == "multica":
            # Phase 1: Multica Integration (Agent Management)
            from backend.integrations.multica.adapter import multica_daemon
            import asyncio
            # In a real sync method we'd run the loop, but this is a stub
            try:
                loop = asyncio.get_running_loop()
                task_assign = loop.create_task(multica_daemon.assign_task(task_id, "agent_123", record["context"]))
            except RuntimeError:
                asyncio.run(multica_daemon.assign_task(task_id, "agent_123", record["context"]))
                
            record["status"] = "RUNNING"
            record["result"] = {"reason": "Assigned to Multica daemon."}
            return self._save(record)
            
        if selected.get("id") != "frontier":
            record["status"] = "BLOCKED"
            record["result"] = {"reason": "Adapter dispatch is not implemented for this capability; no fallback subprocess was launched."}
            return self._save(record)
        if auto_approve and not governance.authorize("terminal_run", "aegis.execution", {"command": "frontier --yes", "task_id": task_id}):
            record["status"] = "BLOCKED"
            record["result"] = {"reason": "L5 denied automatic approval"}
            return self._save(record)
        record["status"] = "RUNNING"
        record["events"].append({"at": time.time(), "type": "EXECUTION_STARTED", "actor": "frontier"})
        self._save(record)
        from backend.frontier_adapter import frontier_adapter
        mode = "agent_team" if record["parallelism"] > 1 else "react"
        output = frontier_adapter.run_task(record["task"], mode=mode, project=record["project"],
                                           context=record["context"], task_id=task_id,
                                           auto_approve=auto_approve, timeout=timeout)
        record["external"].update({"run_id": output.get("run_id"), "session_id": output.get("session"),
                                   "artifacts": output.get("artifacts", [])})
        record["result"] = output
        record["status"] = "VERIFYING" if output.get("status") == "COMPLETE" else output.get("status", "FAILED")
        record["events"].append({"at": time.time(), "type": "EXECUTION_FINISHED", "actor": "frontier", "status": record["status"]})
        return self._save(record)


execution_core = AegisExecutionCore()
