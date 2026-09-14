# [[[Resources/memory-systems]]]

**Created:** 2026-09-12
**Source:** AEGIS L4 documentation, TEMPORARY AEGIS memory schema

---

## Overview

Memory systems for AI agents range from simple key-value stores to complex multi-tier architectures with semantic search, knowledge graphs, and verification systems.

---

## AEGIS L4 Memory Architecture

From [[Aegis/architecture]]:

**3 Memory Stores:**
1. **Episodic Store** — Timestamped conversation/event log, SQLite backend
2. **Semantic Store** — Vector-indexed knowledge store, FAISS or similar
3. **Working Store** — Short-lived scratchpad for reasoning state

**Additional Components:**
- Knowledge graph for relationship tracking
- Context assembly from multiple sources
- Full-text search (FTS) + semantic search
- Memory policies for retention, privacy, verification
- Markdown loader for external knowledge
- P07 (WIP): scanners, discovery, inference

---

## TEMPORARY AEGIS Memory Schema

From [[TEMPORARY_AEGIS/Memory Schema]]:

**11 Memory Tiers:**
1. **Working Memory** — Session-only, in-context
2. **Episodic Memory** — Daily records, filesystem + SQLite
3. **Semantic Memory** — Stable facts, MEMORY.md + knowledge/
4. **Project Memory** — Per-project intelligence
5. **Decision Memory** — Decisions and rationale (permanent)
6. **Preference Memory** — User preferences (USER.md)
7. **Skill Memory** — Skill definitions with metadata
8. **Environment Memory** — Environment snapshot
9. **Goal Memory** — Active and completed goals
10. **Research Memory** — Research with source provenance
11. **Temporary Memory** — TTL-based, auto-expire

---

## Second Brain Methods

### PARA (Tiago Forte)
Organize by actionability, not topic:
- **Projects** — Active work with deadline
- **Areas** — Ongoing responsibilities
- **Resources** — Topics of interest
- **Archives** — Completed/inactive

### CODE (Tiago Forte)
Workflow for managing knowledge:
1. **Capture** — Save anything important
2. **Organize** — File into PARA
3. **Distill** — Extract key insights
4. **Express** — Use the knowledge

### LLM Wiki (Andrej Karpathy)
- Persistent, interlinked Markdown knowledge base
- Agent maintains the wiki incrementally
- Notes link to each other via [[wiki-links]]
- MOCs (Maps of Content) provide navigation

---

## Key Principles

1. **Everything is Markdown** — Portable, future-proof, editable
2. **Link, don't categorize** — Wiki-links create organic connections
3. **MOCs for navigation** — Narrative indexes, not just lists
4. **Inbox for capture** — Reduce friction, triage later
5. **Distill, don't just collect** — Extract essence from raw notes
6. **Source provenance** — Track where knowledge came from
7. **Confidence tracking** — Know what you know vs. what you think you know

---

## Implementation Patterns

### Note Format
```markdown
# Title

**Metadata:** date, source, tags, confidence

## Content

The actual knowledge.

## Connections

- [[Related Note 1]]
- [[Related Note 2]]

## Sources

- [Source 1](url)
- [Source 2](url)
```

### MOC Format
```markdown
# Topic MOC

## Overview
Brief description.

## Subtopics
### Subtopic 1
- [[Note 1]]
- [[Note 2]]

## Related
- [[Related MOC]]
```

---

*See also: [[MOCs/AI-Development]], [[TEMPORARY_AEGIS/Memory Schema]], [[Second Brain Structure]]*
