#!/usr/bin/env python3
"""
AEGIS Agent Supervisor
Orchestrates multi-agent task delegation, concurrent workers, and budget enforcement.
"""

import sys
import uuid
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Any, List

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from backend.config import cfg
from backend.logger import get_logger
from backend.agent_moe import agent_moe

log = get_logger("agent_supervisor")

class TaskBudget:
    def __init__(self, max_time: int = 300, max_retries: int = 2, max_workers: int = 3):
        self.max_time = max_time
        self.max_retries = max_retries
        self.max_workers = max_workers

class AgentSupervisor:
    def __init__(self):
        self.active_tasks: Dict[str, Dict] = {}
        self.history_dir = cfg.HOME / ".temporary-aegis" / "supervisor_history"
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.executor = ThreadPoolExecutor(max_workers=5)

    def dispatch_project_task(self, project_name: str, goal: str, subtasks: List[dict], budget: TaskBudget = TaskBudget()) -> str:
        """
        Dispatches a set of subtasks to multiple concurrent workers under a strict budget.
        """
        task_id = f"sup-{str(uuid.uuid4())[:8]}"
        self.active_tasks[task_id] = {
            "project": project_name,
            "goal": goal,
            "status": "RUNNING",
            "start_time": time.time(),
            "budget": budget,
            "subtasks": subtasks,
            "results": []
        }
        
        # Submit to executor
        self.executor.submit(self._monitor_and_execute, task_id)
        log.info(f"Supervisor dispatched task {task_id} for project {project_name}")
        return task_id

    def _monitor_and_execute(self, task_id: str):
        task = self.active_tasks[task_id]
        budget = task["budget"]
        subtasks = task["subtasks"]
        results = []
        
        # Execute subtasks concurrently if safe, else sequentially. For simplicity here, sequential.
        # In a real environment, read tasks can be concurrent, write tasks sequential.
        for st in subtasks:
            if time.time() - task["start_time"] > budget.max_time:
                results.append({"task": st.get("name"), "status": "FAILED", "error": "Budget timeout exceeded."})
                break
                
            retry_count = 0
            success = False
            last_err = ""
            while retry_count <= budget.max_retries and not success:
                res = agent_moe.execute_plan([st])
                st_res = res.get("tasks", [])[0]
                if st_res.get("status") == "DONE":
                    success = True
                    results.append(st_res)
                else:
                    retry_count += 1
                    last_err = st_res.get("error", "Unknown error")
                    time.sleep(1) # wait before retry
            
            if not success:
                results.append({"task": st.get("name"), "status": "FAILED", "error": f"Max retries exceeded: {last_err}"})
                
        task["status"] = "COMPLETED" if all(r.get("status") == "DONE" for r in results) else "FAILED_PARTIAL"
        task["results"] = results
        task["end_time"] = time.time()
        
        # Write history
        history_file = self.history_dir / f"{task_id}.json"
        try:
            with open(history_file, "w") as f:
                json.dump({
                    "task_id": task_id,
                    "project": task["project"],
                    "goal": task["goal"],
                    "status": task["status"],
                    "duration": task["end_time"] - task["start_time"],
                    "results": results
                }, f, indent=2)
        except Exception as e:
            log.error(f"Failed to write supervisor history: {e}")
            
    def get_task_status(self, task_id: str) -> dict:
        return self.active_tasks.get(task_id, {"status": "NOT_FOUND"})

agent_supervisor = AgentSupervisor()

if __name__ == "__main__":
    sup = AgentSupervisor()
    print("Testing Agent Supervisor...")
    tid = sup.dispatch_project_task("aegis-dashboard", "Read basic files", [
        {"name": "Read README", "tool": "filesystem_read", "args": {"path": str(cfg.HOME / "aegis-dashboard/README.md")}},
        {"name": "Read start.sh", "tool": "filesystem_read", "args": {"path": str(cfg.HOME / "aegis-dashboard/start.sh")}}
    ])
    while sup.get_task_status(tid)["status"] == "RUNNING":
        time.sleep(0.5)
    print("Task Result:", json.dumps(sup.get_task_status(tid), indent=2))
