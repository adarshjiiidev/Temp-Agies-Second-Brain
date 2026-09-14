# [2-Areas/development]]

**Created:** 2026-09-12
**Purpose:** Development practices, tools, techniques, and knowledge

---

## Overview

Ongoing development knowledge and practices. Not project-specific — covers skills, tools, and techniques used across projects.

---

## Model Routing

See [[Resources/model-providers/routing-strategy]] for full routing table.

### Quick Reference

| Task | Model |
|---|---|
| Simple | ag/gemini-3.8-flash-low |
| Default | cl/openai/gpt-5.6-terra |
| Coding | cl/openai/gpt-5.6-sol |
| Reasoning | cl/anthropic/claude-opus-5 |
| Review | cl/anthropic/claude-sonnet-4.6 |
| Multimodal | cl/google/gemini-3.8-flash |
| Long Context | cl/anthropic/claude-sonnet-5 |

---

## Agent Runtimes

### Hermes
- Primary agent runtime for general tasks
- 23 skills available
- Solar Pro 4 free default (via Nous)
- Can use 9Router models

### Codex
- Coding-specialized agent
- GPT-5.6-terra default
- Browser plugin, MCP servers
- For: code generation, repository edits

### OpenClaw
- Desktop/gateway layer
- Chat interface
- Orchestrates Hermes and other agents

---

## Development Environments

- **Python:** 3.11.16 via uv
- **Node:** 22.23.2 (system), 24.19.0 (OpenClaw)
- **Git:** 2.55.0
- **Docker:** 29.7.2 (available, limited use)
- **Rust:** NOT installed

---

## Testing Practices

From AEGIS experience:
- Full suite should complete without hanging (STAB-01 lesson)
- Test behavior contracts, not snapshots
- Test real paths with real imports, not mocks
- E2E validation for integration points

---

*See also: [[MOCs/AI-Development]], [[2-Areas]]*
