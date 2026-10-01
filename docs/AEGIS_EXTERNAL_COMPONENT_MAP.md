# AEGIS External Component Map

## Architecture Principle
External repositories are **capabilities** underneath AEGIS, not competing products.

```
USER → AEGIS Core → Planner → Capability Fabric → Execution Backends → Results → Memory → Dashboard
```

## Component Registry

| Component | Source | License | Integration Mode | Status |
|-----------|--------|---------|-----------------|--------|
| **FrontierAgent** | ApodexAI/FrontierAgent | Apache 2.0 | Native Python import — `frontier_adapter.py` | CONFIGURED |
| **Multica** | multica-ai/multica | Apache 2.0 (custom) | HTTP Adapter — `integrations/multica/adapter.py` | ADAPTER READY |
| **ECC** | affaan-m/ecc | MIT | Native fusion — skills + hooks imported to AEGIS registry | FUSED |
| **VoiceStudio** | debpalash/VoiceStudio | AGPL-3.0 | Process boundary — HTTP API only | BOUNDARY ENFORCED |
| **cloudroom-gui** | cloudroom-gui | MIT | Component library used for workspace GUI | AVAILABLE |
| **mem0** | mem0ai/mem0 | Apache 2.0 | Native import — `mem0_engine.py` | ACTIVE |
| **Hermes** | Local | Proprietary | Native — primary AEGIS execution harness | ACTIVE |

## Dashboard Branding Rule
The UI NEVER shows "Multica Dashboard", "Frontier UI", etc.
It shows only:
- `Executor: Frontier`
- `Agent Manager: Multica`  
- `Skill Provider: ECC`
- `Voice Engine: VoiceStudio`

underneath the single **AEGIS Command Center**.
