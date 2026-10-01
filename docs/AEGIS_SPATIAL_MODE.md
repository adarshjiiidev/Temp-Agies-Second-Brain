# AEGIS Spatial Mode (P6.2) — Lane Discipline + Self-Work Loop (P6.4)

## Lane concept
A **lane** = one project swept start-to-finish before the next begins.
Lanes are sequential, never parallel: one LLM run active at a time.

## One-by-one discipline
1. Resolve targets from `cfg.PROJECTS` (or explicit list).
2. Per lane: `build_context_pack(project, task)` → budgeted pack (project
   summary ≤2k chars + ≤3 memory hits + constraints).
3. `dry_run=True` plans only; `dry_run=False` calls `run_task` with bounded
   `max_turns` (default 20), then a 1s quota breather before next lane.

## Budgets
- `max_turns` default 20; large repos use `agent_team` + higher cap explicitly.
- `sweep_status()` is read-only (lists run dirs, counts trace lines) — free.

## Launch
API (add to server as needed):
```python
from backend.spatial_mode import lane_sweep, sweep_status
lane_sweep(["aegis-dashboard","SkillOpt"], mode="react", task="Fix lint", dry_run=True)
lane_sweep(projects=None, mode="agent_team", task="...", dry_run=False, max_turns=20)
sweep_status()
```
CLI:
```bash
VENV=/home/adarshjii/.hermes/hermes-agent/venv/bin/python
$VENV backend/spatial_mode.py            # dry plan over all projects
$VENV backend/spatial_mode.py --live     # executes (quota burn — avoid in tests)
```

## Experience writeback format (category=experience)
`mem0_engine.add(text, agent_id="spatial_mode", project_id=<lane>, category="experience")`
- text: `[spatial:<mode>] <project>: <STATUS> run_dir=<dir> task=<first 200 chars>`
- metadata: `{"mode": mode, "status": status}`
- Failures also recorded; writeback is best-effort (never aborts sweep).
