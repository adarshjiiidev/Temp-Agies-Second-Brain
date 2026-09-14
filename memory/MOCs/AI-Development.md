# [[[MOCs/AI-Development]]]

**Created:** 2026-09-12
**Purpose:** Map of AI development knowledge, projects, and resources

---

## Overview

This MOC tracks everything related to AI development: projects, models, tools, techniques, and research.

---

## Active Projects

- [[Aegis]] — Personal Adaptive AI OS (L1-L6, 1060 tests)
  - [[Aegis/architecture]] — Layer architecture details
  - [[Aegis/AEGIS_DOCS]] — Documentation index

- [[TEMPORARY AEGIS]] — Integration build (Hermes+Codex+9Router)
  - [[TEMPORARY_AEGIS/Build Log]]
  - [[TEMPORARY_AEGIS/Model Registry]]
  - [[TEMPORARY_AEGIS/Tool Registry]]
  - [[TEMPORARY_AEGIS/Skill Registry]]

---

## Model Landscape

### 9Router (Central Model Fabric)
- **860 models** via OpenAI-compatible API on port 20128
- **10+ model families:** Claude (146), GPT (207), Gemini (81), Qwen (59), Kimi (33), DeepSeek (31), Grok (22), Muse (13), Nemotron (12), Other (256)
- **Capabilities:** 615 reasoning+tools, 527 vision+tools, 251 with 1M+ context

### Key Models for Routing

| Task | Model | Context |
|---|---|---|
| Default | cl/openai/gpt-5.6-terra | 272K |
| Coding | cl/openai/gpt-5.6-sol | 372K |
| Reasoning | cl/anthropic/claude-opus-5 | 1M |
| Fast | ag/gemini-3.8-flash | 1M |
| Multimodal | cl/google/gemini-3.8-flash | 1M |
| Long Context | cl/anthropic/claude-sonnet-5 | 1M |

**See:** [[Resources/model-providers/9Router]]

### Hermes Default
- **Model:** upstage/solar-pro4:free
- **Provider:** Nous
- **Base URL:** https://inference-api.nousresearch.com/v1
- **NOT in 9Router** — direct provider access

### Codex Default
- **Model:** gpt-5.6-terra
- **Config:** ~/.codex/config.toml
- **Plugins:** app-tools, visualize, documents, pdf, spreadsheets, presentations, template-creator, browser

### Local Model
- **LM Studio:** Gemma-4-E2B (8K context, quantized, Vulkan)
- **Port:** 40565 (llama-server), 41343 (LM Studio API)

---

## Agent Runtimes

### Hermes Agent
- **Version:** 0.5.59
- **Skills:** 23 skills across 14 categories
- **Memory:** SQLite state.db (5.4MB, FTS-enabled), 3 sessions, 501 messages
- **Config:** ~/.hermes/config.yaml
- **Features:** CLI, desktop, messaging platforms, delegation, cron, compression

### Codex
- **Version:** 0.153.4
- **Default Model:** gpt-5.6-terra
- **Plugins:** 8 enabled plugins including browser
- **MCP:** node_repl server
- **State:** ~/.codex/ (SQLite DBs, global state, models cache)

### OpenClaw
- **Version:** 2026.9.3
- **Gateway:** Port 18789, systemd service active
- **Role:** Desktop/gateway layer, chat surface

---

## Development Practices

### Model Routing Strategy
- Task-based routing (different models for different task types)
- Fallback chain for reliability
- Privacy-aware (P0 never cloud)

**See:** [[Resources/model-providers/routing-strategy]]

### Memory Systems
- AEGIS L4: 3 stores (episodic, semantic, working)
- TEMPORARY AEGIS: 11-tier memory schema
- PARA + CODE for second brain organization

**See:** [[Resources/memory-systems]]

### Security
- AEGIS risk register: 9+ identified risks with mitigations
- P0 privacy invariant: secrets NEVER cloud
- Sandbox tiers by provenance

**See:** [[Resources/security/aegis-security-model]]

---

## Research Areas

- Model provider comparisons
- Local vs remote inference tradeoffs
- Agent orchestration patterns
- Memory architectures for AI systems
- Tool use and capability discovery

---

## Resources

- [[Resources/model-providers]] — Model provider landscape
- [[Resources/memory-systems]] — Memory architecture patterns
- [[Resources/security]] — Security research and best practices
- [[Resources/tools]] — Tool comparisons and documentation

---

*See also: [[AI-Development MOC]], [[Second Brain Structure]], [[1-Projects]]*
