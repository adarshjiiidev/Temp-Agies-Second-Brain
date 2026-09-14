# [[[MOCs/System-Architecture]]]

**Created:** 2026-09-12
**Purpose:** Map of system architecture knowledge and configuration

---

## Overview

This MOC tracks system architecture knowledge: TEMPORARY AEGIS structure, integration patterns, configuration, and infrastructure.

---

## TEMPORARY AEGIS Architecture

### Core Concept
Transform existing tools (Hermes, Codex, 9Router, OpenClaw) into an integrated personal AI system — no new runtimes created, just intelligent integration and configuration.

**See:** [[TEMPORARY_AEGIS/Build Log]]

### Component Stack

```
User
  ↓
OpenClaw (desktop/gateway) — chat interface
  ↓
  ├── Hermes Agent — general agent runtime
  │   ├── Skills (23 available)
  │   ├── Memory (SQLite + filesystem)
  │   └── Tools (terminal, browser, filesystem, etc.)
  │
  ├── Codex — coding agent
  │   ├── GPT-5.6-terra default
  │   ├── Browser plugin
  │   └── MCP servers
  │
  └── 9Router (model fabric)
      └── 860 models via OpenAI-compatible API
```

---

## Integration Points

### Model Routing
9Router provides the model fabric. Task-based routing selects appropriate models.

**See:** [[Resources/model-providers/9Router]], [[Resources/model-providers/routing-strategy]]

### Memory System
PARA + CODE + LLM Wiki pattern for personal knowledge.

**See:** [[Second Brain Structure]], [[Resources/memory-systems]]

### Skills
10 reusable skills defined with inputs, outputs, workflows, verification.

**See:** [[TEMPORARY_AEGIS/Skill Registry]]

### Tool Registry
20 tools across execution, data, web, media, orchestration categories.

**See:** [[TEMPORARY_AEGIS/Tool Registry]]

---

## Infrastructure

### Running Services
- **9Router:** Port 20128 (model gateway)
- **OpenClaw Gateway:** Port 18789 (AI gateway)
- **LM Studio:** Port 41343 (local LLM UI)
- **llama-server:** Port 40565 (Gemma-4-E2B, 8K context)

### Hardware
- Intel i3-1215U (8 cores)
- 7.5 GB RAM (1.5 GB available)
- 475 GB NVMe (392 GB free)
- Intel UHD Graphics (no CUDA)
- AGIES Linux 4.0.3 (Arch-based)

---

## Configuration

All configuration in [[TEMPORARY_AEGIS/config/AEGIS_CONFIG]]

Key sections:
- Model routing
- Privacy (P0/P1/P2/P3)
- Memory retention
- Skill configuration
- Tool configuration
- Authorization flow
- Multi-agent orchestration
- Automation scheduling

---

*See also: [[TEMPORARY_AEGIS/Build Log]], [[MOCs/AI-Development]]*
