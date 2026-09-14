# [[[Resources/model-providers/9Router]]]

**Created:** 2026-09-12
**Source:** 9Router /v1/models API (http://127.0.0.1:20128/v1)
**Verification:** Live API call, 860 models returned

---

## Overview

9Router is a local AI gateway providing OpenAI-compatible API access to 860 models from 10+ provider families. Running on port 20128, systemd service active.

**URL:** http://127.0.0.1:20128/v1
**API Format:** OpenAI-compatible (/v1/chat/completions, /v1/models)
**Service:** systemctl --user 9router.service (active)

---

## Model Families

| Family | Count | Examples |
|---|---|---|
| **Claude** | 146 | claude-opus-5, claude-sonnet-5, claude-opus-4.8, claude-sonnet-4.6, claude-fable-5 |
| **GPT** | 207 | gpt-5.6-terra, gpt-5.6-sol, gpt-5.5, gpt-5.4, gpt-6-astra, gpt-5.2 |
| **Gemini** | 81 | gemini-3.8-flash, gemini-3.7-flash, gemini-3.6-flash, gemini-3.5-flash-lite, gemini-3.1-pro-preview |
| **Qwen** | 59 | qwen3.7-plus, qwen3.7-max, qwen3.6-35b-a3b, qwen3.6-27b, qwen3.5-122b-a10b |
| **Kimi** | 33 | kimi-k3, kimi-k2.7-code, kimi-k2.6, kimi-k2.5 |
| **DeepSeek** | 31 | deepseek-v4-pro, deepseek-v4-flash, deepseek-v4-flash-vision-exp |
| **Grok** | 22 | grok-4.5, grok-4.3, grok-4.20, grok-build-0.1 |
| **Muse** | 13 | muse-spark-1.3, muse-spark-1.2, muse-spark-1.1 |
| **Nemotron** | 12 | nemotron-3-nano-omni-30b, nemotron-3-ultra, nemotron-3-super |
| **Other** | 256 | Various providers and specialized models |

---

## Capability Distribution

- **Reasoning + Tools:** 615 models
- **Vision + Tools:** 527 models
- **1M+ Context Window:** 251 models
- **128K+ Max Output:** 378 models

---

## Model Routing Recommendations

**Selected for TEMPORARY AEGIS:**

| Task | Model ID | Context | Max Output | Thinking |
|---|---|---|---|---|
| Default | cl/openai/gpt-5.6-terra | 272K | 128K | openai |
| Coding | cl/openai/gpt-5.6-sol | 372K | 128K | openai |
| Deep Reasoning | cl/anthropic/claude-opus-5 | 1M | 128K | claude-adaptive |
| Code Review | cl/anthropic/claude-sonnet-4.6 | 1M | 128K | claude-adaptive |
| Fast | ag/gemini-3.8-flash | 1M | 64K | gemini-level |
| Multimodal | cl/google/gemini-3.8-flash | 1M | 64K | gemini-level |
| Long Context | cl/anthropic/claude-sonnet-5 | 1M | 128K | claude-adaptive |
| Summarization | ag/gemini-3.8-flash-low | 1M | 64K | gemini-level |
| Long Horizon | kimi/kimi-k3 | 1M | 128K | kimi |

---

## Provider Prefixes

- **cl/** — Chat/LM studio models (largest collection, 445 models)
- **cx/** — Codex models (15 models, GPT-5.6 lineup)
- **ag/** — Direct Anthropic/Gemini access (20 models)
- **gh/** — GitHub Copilot models (33 models)
- **cu/** — Cursor models (223 models)
- **kr/** — Kiro models (34 models)
- **qb/** — Qwen/DeepSeek/Kimi via various providers
- **gc/** — Google Cloud models
- **kc/** — Kimi/Coding models
- **kimi/** — Kimi direct
- **gemini/** — Gemini direct
- **nvidia/** — NVIDIA-hosted models

---

## Notes

- Model availability may vary by rate limits and auth status
- Some models have `:batch` variants for batch processing
- Some models have `-review` variants specialized for code review
- Some models have `-fast` variants for speed-optimized inference
- Thinking format varies: openai, claude-adaptive, claude-budget, gemini-level, kimi, qwen, deepseek, minimax, zai, step

---

*See also: [[MOCs/AI-Development]], [[TEMPORARY_AEGIS/Model Registry]], [[AEGIS_DOCS/07_AI_STRATEGY]]*
