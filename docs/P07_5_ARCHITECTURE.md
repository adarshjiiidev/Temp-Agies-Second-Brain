# P07.5 — LLM Provider & Inference Infrastructure Architecture

**Document ID:** AEGIS-DOC-P07.5
**Milestone:** P07.5 — Provider-Agnostic Inference Infrastructure
**Status:** ✅ IMPLEMENTED
**Last Updated:** 2026-08-11

---

## 1. Overview

P07.5 hardens the existing L3 AI Kernel into a fully production-grade, provider-agnostic
inference infrastructure. It adds:

- **Dynamic model discovery** — Ollama models enumerated at runtime via `/api/tags`
- **Provider health monitoring** — Background asyncio loop probes providers and updates `ModelRegistry`
- **Credential resolution** — `vault_ref` → live key resolution without raw secrets touching storage
- **Credential provisioner extension points** — `ManualProvisioner`, `EnvironmentProvisioner`, `BrowserProvisioner` stub
- **`AIKernel` introspection API** — `has_models()`, `list_models()`, `provider_count()`
- **Security test suite** — 53 new tests proving no credential leaks and P0 isolation

The existing L3 AI Kernel (router, accounting, cache, structured output, scrubber, fallback chain,
existing providers) is **unchanged** — P07.5 extends without replacing.

---

## 2. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  L6 Planning / Agents                                                        │
│                                                                              │
│   KernelReasoningProvider ──────────────────────────────────────────────┐   │
│   (aegis/reasoning/kernel_provider.py)                                  │   │
└─────────────────────────────────────────────────────────────────────────┼───┘
                                                                          │
                          ─── L3 boundary ───────────────────────────────┼──
                                                                          │
┌─────────────────────────────────────────────────────────────────────────▼───┐
│  L3 AI Kernel (aegis/l3_intelligence/ai_kernel/)                             │
│                                                                              │
│   AIKernel.generate(AIRequest) ──► Router ──► CostAccountant                 │
│   AIKernel.has_models()                                                      │
│   AIKernel.list_models()              ┌─────────────────┐                   │
│   AIKernel.provider_count()           │  ModelRegistry  │◄── ProviderHealth  │
│                                       │  (health state) │    Monitor         │
│   ┌───────────────────────────┐       └────────┬────────┘    (health.py)     │
│   │ CredentialResolver        │                │                             │
│   │ vault_ref → live key      │                │ filter_candidates()         │
│   │ env: / file: / keyring:   │                │                             │
│   └───────────────────────────┘       ┌────────▼────────┐                   │
│   ┌───────────────────────────┐       │     Router      │                   │
│   │ CredentialProvisioner     │       │  5-stage score  │                   │
│   │ Manual / Environment /    │       └────────┬────────┘                   │
│   │ Browser (stub)            │                │ RouteDecision[]             │
│   └───────────────────────────┘                │                             │
│                                       ┌────────▼────────────────────┐       │
│                                       │    ProviderRegistry         │       │
│   KeyManager                          │  ollama / groq / openrouter │       │
│   (4 rotation strategies)             │  / vllm / fake              │       │
│   vault_ref stored, not raw key       └────────┬────────────────────┘       │
│                                                │                             │
│                                  ┌─────────────▼──────────────┐             │
│                                  │  OllamaProvider             │             │
│                                  │  ├── chat()                 │             │
│                                  │  ├── chat_stream()          │             │
│                                  │  ├── health_check()  ◄─────┼─── NEW      │
│                                  │  └── discover_models() ◄───┼─── NEW      │
│                                  └────────────────────────────┘             │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Components

### 3.1 `BaseProvider` Extensions (P07.5)

**File:** `src/aegis/l3_intelligence/ai_kernel/providers/base.py`

```python
class BaseProvider:
    async def health_check(self) -> ModelHealth:
        """Default: UNKNOWN (no probe). Override in concrete providers."""
        return ModelHealth.UNKNOWN

    async def discover_models(self) -> list[ModelSpec]:
        """Default: static available_models(). Override for dynamic enumeration."""
        return self.available_models()
```

Contract:
- `health_check()` → `HEALTHY | DEGRADED | DOWN | UNKNOWN`
- `discover_models()` → list of `ModelSpec` (never raises; falls back to static list)
- `UNKNOWN` returned by providers that don't override — **never written to `ModelRegistry`**

### 3.2 `OllamaProvider` Dynamic Discovery

**File:** `src/aegis/l3_intelligence/ai_kernel/providers/ollama.py`

```
health_check()    → GET /api/version → HEALTHY (2xx) / DOWN (error/timeout)
discover_models() → GET /api/tags    → parse models[].{name, details}
                                     → fallback to static list on any error
```

Timeout: `_HEALTH_TIMEOUT = 5.0s` (separate from inference timeout of 120s).

### 3.3 `ProviderHealthMonitor`

**File:** `src/aegis/l3_intelligence/ai_kernel/health.py`

```python
config = ProviderHealthConfig(
    check_interval_seconds=60.0,  # How often to sweep all providers
    timeout_seconds=5.0,          # Per-probe timeout
    failure_threshold=3,          # Consecutive failures before marking DOWN
    shutdown_timeout_seconds=5.0, # Graceful stop wait
)
monitor = ProviderHealthMonitor(provider_registry, model_registry, config)
await monitor.start()
# ... AEGIS runs ...
await monitor.stop()
```

**Design properties:**
- Pure asyncio — no L2 BackgroundTaskManager dependency (avoids upward layer violation)
- Failure-tolerant: individual probe exceptions are caught; never crashes the loop
- UNKNOWN-safe: providers not overriding `health_check()` are silently skipped
- Threshold-gated: `DOWN` only written after N consecutive failures (prevents flapping)
- Shutdown-safe: same pattern as `FreshnessScheduler` (P07 GAP #3)

**Probe state tracked per provider:**
```
consecutive_failures: int    — resets to 0 on HEALTHY / DEGRADED
last_check_at: float         — monotonic timestamp of last probe
last_health: ModelHealth     — last observed health value
```

### 3.4 `CredentialResolver`

**File:** `src/aegis/l3_intelligence/ai_kernel/credentials.py`

Resolves `ProviderKey.vault_ref` strings to live API key values.

| Scheme | Example | Resolved From |
|--------|---------|---------------|
| `env:VAR` | `env:GROQ_API_KEY` | `os.environ["GROQ_API_KEY"]` |
| `file:/path` | `file:/run/secrets/api_key` | First non-empty line of file |
| `aegis-keyring:scope/id` | `aegis-keyring:llm/groq-1` | L2 crypto vault (future) |
| Bare name | `GROQ_API_KEY` | `os.environ["GROQ_API_KEY"]` (backward compat) |

**Security invariants:**
- Raw API keys are NEVER stored — only the `vault_ref` opaque reference
- Raw keys are NEVER logged — resolver returns values but never passes to logging
- `CredentialResolutionError` messages never contain the raw key value
- `ProviderKey.vault_ref` is the env var NAME, not the env var value

### 3.5 `CredentialProvisioner` Extension Points

| Implementation | Behavior |
|---------------|----------|
| `ManualProvisioner` | No-op. Returns already-registered key IDs. |
| `EnvironmentProvisioner` | Scans `{PROVIDER_UPPER}_API_KEY` and `{PROVIDER_UPPER}_API_KEY_N` env vars. Registers keys idempotently. |
| `BrowserProvisioner` | **NOT IMPLEMENTED.** Raises `NotImplementedError` with explicit message. Planned for P10+ Browser OS. |

### 3.6 `AIKernel` Introspection API (P07.5)

**File:** `src/aegis/l3_intelligence/ai_kernel/kernel.py`

```python
kernel.has_models()      # bool  — True if ModelRegistry is non-empty
kernel.list_models()     # list[ModelMetadata] — all registered models
kernel.provider_count()  # int   — number of registered providers
```

These are used by `KernelReasoningProvider.is_available` and by callers that need to
guard against attempting inference with an unconfigured kernel.

---

## 4. Privacy Guarantee

The L3 privacy routing is enforced at the `Router` and `ModelRegistry` levels:

| Privacy Tier | Routing Rule |
|-------------|-------------|
| `P0` (DEVICE_LOCAL_ONLY) | Hard failure if no LOCAL model available. Cloud providers NEVER called. |
| `P1` (PREFER_LOCAL) | Local preferred; cloud allowed with audit log. |
| `P2` (STANDARD) | Cloud allowed; P2/P3-capable models eligible. |
| `P3` (EXTERNAL_OK) | All providers eligible. |

`AIRouterPrivacyViolationError` is raised (not caught) if P0 has no eligible local model.

Tests in `test_credential_security.py`:
- `test_p0_request_never_reaches_cloud_provider` — assert `call_count() == 0` on cloud provider
- `test_p0_request_succeeds_with_local_provider` — P0 routes correctly to local

---

## 5. Credential Lifecycle

```
Application startup
  └─► EnvironmentProvisioner.provision(key_manager, "groq")
        └─► Discovers GROQ_API_KEY in env
        └─► Registers ProviderKey(vault_ref="env:GROQ_API_KEY")
            ← raw key never stored; only the var name

Inference request
  └─► Router selects "groq" as best candidate
  └─► KeyManager.select_key("groq") → ProviderKey with vault_ref
  └─► CredentialResolver.resolve("env:GROQ_API_KEY") → raw key (ephemeral)
  └─► Raw key passed to HTTP Authorization header
  └─► Raw key discarded after request (not stored, not logged)
```

---

## 6. Test Coverage (New in P07.5)

| File | Tests | Coverage |
|------|-------|----------|
| `test_credential_security.py` | 30 | CredentialResolver (env/file/keyring), provisioners, secret-never-in-logs, P0 isolation, response serialisation |
| `test_reasoning_integration.py` | 23 | AIKernel introspection, generate() round-trip, P0 routing, KernelReasoningProvider, health monitor, Ollama discovery |

**Total new tests:** 53
**Full suite total:** ~1060 (1007 existing + 53 new)

---

## 7. Future Work (Not in P07.5 Scope)

| Item | Target |
|------|--------|
| `BrowserProvisioner` implementation | P10+ Browser OS |
| `aegis-keyring:` resolver (L2 crypto vault) | P08+ |
| `FreshnessScheduler` → `ScanningCoordinator` wiring | P08 |
| `ProviderHealthMonitor` → AEGIS lifecycle manager wiring | P08 |
| `GroqProvider.health_check()` | P08 (add `GET /openai/models` probe) |
| `OpenRouterProvider.health_check()` | P08 |

---

## 8. Red Lines (Never Cross Without ADR)

1. Raw API keys must never be stored in any persistent store without encryption
2. P0 data must never reach cloud providers — enforced at Router level
3. `CredentialResolver` must never log resolved values
4. `ProviderHealthMonitor` must never import L2 (upward layer violation)
5. Provider additions must use `BaseProvider` and implement `health_check()` + `discover_models()`
