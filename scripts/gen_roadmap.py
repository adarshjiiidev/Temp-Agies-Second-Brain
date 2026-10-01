import json

d = json.load(open("docs/AEGIS_MASTER_TASKS.json"))
L = ["# AEGIS Master Task Graph", "",
     "Generated " + d["generated"] + " by " + d["maintainer"] + ". " + d["note"], ""]
counts = {}
for p in d["phases"]:
    L.append("## " + p["id"] + " — " + p["title"] + " [" + p["source_prompt"] + "]")
    L.append("Gate: " + p["gate"])
    for s in p["sections"]:
        L.append("### " + s["id"] + " " + s["title"])
        for t in s["tasks"]:
            counts[t["status"]] = counts.get(t["status"], 0) + 1
            ev = (" — evidence: " + t["evidence"]) if t.get("evidence") else ""
            L.append("- [" + t["status"] + "] " + t["id"] + " " + t["title"] + ev)
    L.append("")
L.append("## Counts")
for k in sorted(counts):
    L.append("- " + k + ": " + str(counts[k]))
open("docs/AEGIS_MASTER_TASKS.md", "w").write("\n".join(L) + "\n")
print("roadmap OK", counts)
