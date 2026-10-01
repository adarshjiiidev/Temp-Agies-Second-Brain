# AEGIS Model Fabric — 9Router Benchmark Report

**Benchmark Date:** 2026-09-18  
**Gateway:** 9Router (port 20128)  
**Total Gateway Models:** 870  
**Active Production Pool:** Verified Free 9Router Models (Ranked Round-Robin & Fallback)  

---

## 📊 Live Production Model Matrix (`backend/config.py`)

| Model Identifier | Specialization | Role in AEGIS | Context Window |
| :--- | :--- | :--- | :--- |
| `cl/nex-agi/nex-n2.5-pro:free` | Pro-tier General Purpose & Architecture | `cfg.MODEL_DEFAULT` | 128k |
| `cl/z-ai/glm-5.2:free` | Flagship Deep Reasoning & Math Proof | `cfg.MODEL_REASONING` | 128k |
| `cl/google/gemma-4-31b-it:free` | 31B Parameter Frontier Open Model | High-Quality Chat | 128k |
| `cl/cohere/north-mini-code:free` | Code Specialist | Code Synthesis & Debugging | 128k |
| `cl/poolside/laguna-s-2.1:free` | Autonomous Developer Coding | Coding Benchmark Runner | 128k |
| `cl/nex-agi/nex-n2.5-mini:free` | Ultra-Low Latency Conversational Chat | `cfg.MODEL_FAST` | 64k |
| `cl/inclusionai/ling-3.0-flash-vl:free`| Vision-Language Multimodal Inference | UI & OCR Grounding | 64k |
| `cl/dots-studio/dots-3-note-preview:free`| Lightweight Draft & Note Summarization | `cfg.MODEL_LITE` | 32k |

---

## 🧭 Dynamic Routing & Fallback Protocol (`backend/model_router.py`)

1. **Round-Robin Diversity:** Requests rotate across healthy free models without expensive cascading timeouts.
2. **Deterministic Fallbacks:** If the primary model encounters rate limits or errors, `model_router.py` automatically routes through `cfg.MODEL_FALLBACK_CHAIN`.
3. **Local DeepSeek MoE:** Supported for air-gapped local reasoning when configured.
4. **Zero Wildcarding:** Model identifiers are verified directly against `http://127.0.0.1:20128/v1/models`.
