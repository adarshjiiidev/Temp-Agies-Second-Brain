# agies Profile — End-to-End Setup Report

**Agent:** TEMPORARY AEGIS Build Agent (Session 1)
**Date:** 2026-09-12
**Status:** COMPLETE

---

## Profile Created: agies

A Hermes Agent profile acting as a "god PC user" — a superuser-level AI assistant.

### Where

```
/home/adarshjii/.hermes/profiles/agies/
├── config.yaml          # Profile config (high reasoning, longer timeouts)
├── .env                 # Environment (AEGIS paths, project dirs)
├── SOUL.md              # Personality: god PC user
├── IDENTITY.md          # Role definition
├── PROFILE_INFO.md      # Human-readable doc
├── memories/
│   ├── USER.md          # User profile (Adarsh Jii)
│   └── MEMORY.md        # AEGIS knowledge summary
├── skills/
│   ├── README.md
│   └── aegis/           # AEGIS integration skill
│       ├── SKILL.md     # Full skill definition
│       └── DESCRIPTION.md
├── workspace/           # Working directory
└── <auto-bootstrapped>  # state.db, sessions, cron, hooks, etc.
```

### Gateway Integration

Configured in `/home/adarshjii/.hermes/config.yaml`:
```yaml
profiles:
  multiplex:
    enabled: true
    include:
      - default
      - agies
```

### Capabilities

| Capability | Detail |
|------------|--------|
| Filesystem | Full read access (within permissions) |
| Terminal | 300s timeout, 2 CPU / 8GB RAM / 100GB disk container |
| Browser | Available via browser_use backend |
| AEGIS knowledge | Full access to .temporary-aegis/ memory & registries |
| Skills | Inherits all Hermes skills + AEGIS integration skill |
| Memory | Per-profile USER.md + MEMORY.md |
| Reasoning | High effort (vs default medium) |
| Show reasoning | Enabled |

### How to Start agies

**CLI:**
```bash
# Option 1: hermes run with profile override
hero run --profile agies

# Option 2: direct (in profile dir)
cd /home/adarshjii/.hermes/profiles/agies
hermes run
```

**Gateway (multiplex):**
- If gateway.multiplex_profiles is enabled, agies appears as a selectable profile
- Users can switch to agies via the gateway profile selector

**Desktop app:**
- Use profile switcher to select "agies"

### Personality

- Name: agies
- Role: God PC user
- Tone: direct, authoritative, efficient, no-nonsense
- Knows: entire machine, AEGIS architecture, user's projects and preferences

### AEGIS Integration

agies has a dedicated AEGIS skill that provides:
- Model registry access (860 models, routing rules)
- Tool registry access (20 tools)
- Skill registry access (10 skills)
- Second brain access (PARA structure, MOCs, project notes)
- Configuration access (AEGIS_CONFIG.md, MEMORY_SCHEMA.md)

When asked about AEGIS topics, agies consults these resources directly.

---

## Build Session 1 Summary

**Total artifacts created:** 45+ files

| Category | Count | Key Files |
|----------|-------|-----------|
| Registries (JSON) | 4 | MODEL_REGISTRY.json, TOOL_REGISTRY.json, SKILL_REGISTRY.json, PERSONAL_CONTEXT.json |
| Configuration | 2 | AEGIS_CONFIG.md, MEMORY_SCHEMA.md |
| Second Brain | 22+ | PARA structure, MOCs, project notes, area notes, resource notes, logs |
| Build docs | 3 | SYSTEM_AUDIT.md, BUILD_LOG.md, BUILD_SESSION_1_REPORT.md |
| State files | 6 | PROJECT_STATE.json, MASTER_TODO.md, BLOCKERS.md, NEXT_ACTION.md, BUILD_SESSION_1_REPORT.md, CHANGELOG.md |
| agies profile | 9 | config.yaml, SOUL.md, IDENTITY.md, PROFILE_INFO.md, memories/, skills/aegis/ |

**Build mission status:** Session 1 complete — foundation + agies profile ready

---

## What's Ready to Use Right Now

1. **agies profile** — start via `hermes run --profile agies` or gateway profile selector
2. **Second brain** — read any MOC or project note
3. **Model routing** — consult MODEL_REGISTRY.json for task-appropriate models
4. **Tool registry** — consult TOOL_REGISTRY.json for available capabilities
5. **AEGIS skill** — agies can answer AEGIS-related questions using the skill

---

## Next Session Tasks (when you continue)

1. Investigate unknown projects: chrome-extra, repusense backend, world-viewer prompt.md
2. Work folder: /home/adarshjii/Work/
3. Create TEMPORARY_AEGIS_COMPLETE.md
4. Test agies via CLI or gateway
5. Enhance retrieval (semantic search, keyword search)
6. Set up daily intelligence summary
