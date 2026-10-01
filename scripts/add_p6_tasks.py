import json

p = "docs/AEGIS_MASTER_TASKS.json"
d = json.load(open(p))
for ph in d["phases"]:
    for s in ph["sections"]:
        for t in s["tasks"]:
            if t["id"] == "P2.5":
                t["evidence"] = ("headless ReAct rc=0 via free model; approval gate "
                                 "stopped file write (governance intact); rerun scoped cwd + auto_approve next")
phase = {
    "gate": "Each capability demonstrated on real projects; credentials never stored in repo.",
    "id": "P6",
    "sections": [
        {"id": "P6S1", "title": "Discovery + spatial mode", "tasks": [
            {"id": "P6.1", "status": "READY",
             "title": "Auto-discovery: web search, learn, candidate repos, install, integrate, memory"},
            {"id": "P6.2", "status": "READY",
             "title": "Spatial multi-agent mode: lanes sweep new/old/selected projects"}]},
        {"id": "P6S2", "title": "Orchestration + self-work", "tasks": [
            {"id": "P6.3", "status": "READY",
             "title": "Custom system prompts per role + god orchestrator loop"},
            {"id": "P6.4", "status": "READY",
             "title": "Self-work loop: act, error, fix, one-by-one with experience writeback"}]},
        {"id": "P6S3", "title": "Org cameras + GitButler", "tasks": [
            {"id": "P6.5", "status": "BLOCKED",
             "title": "Org cameras: admin creds PENDING from user; vault adapter only"},
            {"id": "P6.6", "status": "READY",
             "title": "GitHub for all agents via GitButler (no raw git push)"}]},
        {"id": "P6S4", "title": "All-actions audit", "tasks": [
            {"id": "P6.7", "status": "READY",
             "title": "Every dashboard action traced to working backend path or NOT_CONFIGURED"}]},
    ],
    "source_prompt": "self-evolving-system",
    "title": "Self-evolving agentic system",
}
d["phases"].append(phase)
json.dump(d, open(p, "w"), indent=1)
print("phases:", len(d["phases"]))
