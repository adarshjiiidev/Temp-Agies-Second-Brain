# [[[Resources/model-providers/routing-strategy]]]

**Created:** 2026-09-12
**Source:** Derived from TEMPORARY AEGIS model registry and routing configuration

---

## Overview

Task-based model routing selects the most appropriate model for each type of task. The goal is to use the right amount of capability for each task — fast models for simple tasks, powerful models for complex reasoning.

---

## Routing Principles

### 1. Match Capability to Task Complexity
- Simple queries → fast, cheap models
- Complex reasoning → strongest reasoning models
- Coding → coding-optimized models
- Multimodal → vision-capable models
- Long context → models with appropriate context window

### 2. Prefer Specialized Models
- Coding tasks → GPT-5.6-Sol (coding-optimized)
- Analysis tasks → Claude Opus 5 (reasoning-optimized)
- Speed tasks → Gemini Flash (fast, efficient)

### 3. Fallback Strategy
When primary model is unavailable:
1. Try next model in fallback chain
2. Wait 2s, retry once if rate-limited
3. If context overflow, try model with larger context
4. If tool failure, retry once then alternate model
5. If all fail, report blocker

---

## Routing Table

| Task Type | Primary Model | Fallback | Rationale |
|---|---|---|---|
| Simple Query | ag/gemini-3.8-flash-low | ag/gemini-3.8-flash-extra-low | Fast, cheap, sufficient capability |
| Default | cl/openai/gpt-5.6-terra | cl/openai/gpt-5.5 | Balanced general purpose |
| Coding | cl/openai/gpt-5.6-sol | cl/anthropic/claude-sonnet-4.6 | GPT-5.6 Sol is coding frontier |
| Deep Reasoning | cl/anthropic/claude-opus-5 | cl/anthropic/claude-opus-4.8 | Opus 5 has strongest reasoning |
| Code Review | cl/anthropic/claude-sonnet-4.6 | cl/openai/gpt-5.6-sol | Sonnet 4.6 proven for codebase understanding |
| Architecture Review | cl/anthropic/claude-opus-5 | cl/anthropic/claude-sonnet-5 | Opus 5 for comprehensive analysis |
| Research | cl/anthropic/claude-opus-5 | cl/anthropic/claude-sonnet-5 | Deep synthesis requires strong reasoning |
| Debugging | cl/anthropic/claude-sonnet-4.6 | cl/anthropic/claude-opus-4.8 | Sonnet 4.6 for code debugging |
| Multimodal | cl/google/gemini-3.8-flash | ag/gemini-3.8-flash | Gemini for vision+audio+video |
| Long Context | cl/anthropic/claude-sonnet-5 | cl/anthropic/claude-opus-5 | 1M context for large analysis |
| Summarization | ag/gemini-3.8-flash-low | ag/gemini-3.8-flash | Fast, sufficient for summarization |
| Classification | ag/gemini-3.8-flash-extra-low | ag/gemini-3.8-flash-low | Minimal cost for classification |
| Long Horizon Agent | kimi/kimi-k3 | cl/anthropic/claude-sonnet-5 | Kimi K3 for agentic long tasks |

---

## Special Considerations

### Privacy
- **P0 (secrets, credentials):** NEVER route to cloud. Only local models. If no local model available, raise error.
- **P1 (personal):** Cloud OK with consent
- **P2 (project):** Cloud OK
- **P3 (public):** Cloud OK

### Context Requirements
- Check required context window before routing
- If task needs 500K context, don't route to 200K model
- If task needs <50K, prefer smaller/faster model

### Tool Requirements
- If task requires tool use, route to model with tool capability
- Some models have tools disabled — check before routing

---

## Implementation

The routing table is stored in:
- `TEMPORARY_AEGIS/config/AEGIS_CONFIG.md` — Configuration format
- `TEMPORARY_AEGIS/MODEL_REGISTRY.json` — Curated model details

---

*See also: [[MOCs/AI-Development]], [[9Router]], [[TEMPORARY_AEGIS/Model Registry]]*
