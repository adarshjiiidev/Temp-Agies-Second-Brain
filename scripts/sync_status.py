import json

p = "docs/AEGIS_MASTER_TASKS.json"
d = json.load(open(p))
upd = {
    "P2.5": ("COMPLETE", "live ReAct run rc=0, PING-OK written, trace 5 lines, ingested to Obsidian+mem0+TQ"),
    "P2.7": ("COMPLETE", "registry has frontier/opencode entries; claude path fixed to latest"),
    "P2.8": ("COMPLETE", "mem0 gateway live; context packs via /api/frontier/context-pack"),
    "P2.9": ("COMPLETE", "backend/universal_ingest: 17 sessions, 7 agents, checkpoints, leak-check clean"),
    "P2.10": ("COMPLETE", "experience writeback live (frontier proof mem + spatial writes)"),
    "P2.11": ("COMPLETE", "preferences engine + 29 seeds live at /api/preferences; dashboard panel PENDING-UI"),
    "P4.1": ("COMPLETE", "learn_loop.py ran: note + mem0 + 33 TQ chunks"),
    "P4.2": ("IN_PROGRESS", "timer INSTALLED-NOT-ENABLED; needs user approval to enable"),
    "P3.1": ("COMPLETE", "profiles STANDARD/RESEARCH_LAB/RED_TEAM_LAB live at /api/lab/profile"),
    "P3.2": ("COMPLETE", "jailbreak-autoresearch inspected + documented; eval hook log-only"),
    "P3.3": ("COMPLETE", "model profiles + session auth + exact BLOCKED reasons verified"),
    "P3.4": ("COMPLETE", "lab_targets seeded (localhost+owned-repos); sessions TTL"),
    "P6.1": ("READY", "not yet implemented; learn-loop queue is the interim discovery feed"),
    "P6.2": ("COMPLETE", "backend/spatial_mode lane_sweep dry_run verified; live lanes unconsumed"),
    "P6.3": ("COMPLETE", "prompts/god_orchestrator.md + 3 role prompts"),
    "P6.4": ("IN_PROGRESS", "loop mechanics exist (spatial+experience); continuous operation not started"),
    "P6.5": ("BLOCKED", "adapter + docs done; AWAITING_CREDENTIALS (vault absent)"),
    "P6.6": ("IN_PROGRESS", "but 0.22.3 installed + rules doc; GitHub OAuth PENDING-USER"),
    "P6.7": ("COMPLETE", "docs/AEGIS_ACTIONS_AUDIT.md: 19 wired, 4 external, 24 no-UI, 0 broken"),
}
for ph in d["phases"]:
    for s in ph["sections"]:
        for t in s["tasks"]:
            if t["id"] in upd:
                t["status"], t["evidence"] = upd[t["id"]]
json.dump(d, open(p, "w"), indent=1)
print("updated")
