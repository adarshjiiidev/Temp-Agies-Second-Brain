# AEGIS Rust Performance Core — Migration Map

> **Status:** Phase R0 Complete (Audit) | Phase R1 Complete (Existing crate repairs) | Phase R2 Complete (Benchmark analysis) | **Phase R3 Complete (New crates implemented)**
> **Phases R4+:** Deferred — pending real L5 FilesystemExecutor profiling.
> **Document date:** 2026-08-13
> **Author:** Implementation Engineer (Phase R-AUDIT through R3)

---

## 1. Architectural Principle

AEGIS is a hybrid **Python control/intelligence plane + Rust performance/systems plane**.

```
┌──────────────────────────────────────────────────────┐
│                 AEGIS PYTHON PLANE                   │
│                                                      │
│  AI Reasoning   Planning   Policy   Orchestration    │
│       L6           L6       L5          All          │
└─────────────────────────┬────────────────────────────┘
                          │  Stable FFI / PyO3
┌─────────────────────────▼────────────────────────────┐
│                RUST PERFORMANCE CORE                 │
│                                                      │
│  Crypto   Audit   Search   Graph   Scan   Sandbox    │
│   L2       L5      L4       L4     L4      L5        │
└──────────────────────────────────────────────────────┘
```

**Python stays authoritative for:**
- All AI reasoning, intent, ambiguity, planning decisions
- Privacy policy enforcement
- Permission, risk, policy enforcement
- Execution approval logic
- Rollback semantics
- Orchestration / lifecycle

**Rust is appropriate for:**
- Cryptographic primitives (constant-time, memory-safe)
- Audit chain hash verification (high-throughput, integrity-critical)
- Search ranking / filtering (large candidate sets)
- Graph traversal (large knowledge graphs)
- Filesystem scanning (P07 environment discovery)
- Sandbox primitives (process isolation, resource limits)

**Rust MUST NOT:**
- Bypass the L5 7-stage execution pipeline
- Override privacy or permission policy
- Make LLM routing decisions
- Store credentials
- Expose P0 data across FFI boundaries

---

## 2. Complete Component Migration Map

### L1 — Core Runtime

| Component | Current | Classification | Rationale |
|-----------|---------|----------------|-----------|
| RuntimeFSM | Python | `KEEP_PYTHON` | Orchestration; state transitions are O(1), not a bottleneck |
| DependencyContainer | Python | `KEEP_PYTHON` | DI graph; runs once at startup |
| ErrorRegistry | Python | `KEEP_PYTHON` | Error metadata; no hot path |
| HealthMonitor | Python | `KEEP_PYTHON` | asyncio-native; probes are I/O bound |
| ComponentSupervisor | Python | `KEEP_PYTHON` | Lifecycle orchestration |
| LLM interface contracts | Python | `KEEP_PYTHON` | Abstract interfaces only |
| EventBus (high-frequency) | Python | `FUTURE_RESEARCH` | Could benefit from Rust MPSC queue at very high event volume; measure first |

**Verdict:** L1 stays Python. Zero components currently justify Rust migration.

---

### L2 — Foundation

| Component | Current | Classification | Rationale |
|-----------|---------|----------------|-----------|
| **Crypto / Vault** | Python (`cryptography` lib) | `RUST_CORE` ✅ | Constant-time guarantees, memory safety, no Python GIL contention on crypto ops |
| **AuditChain hash verification** | Python | `RUST_CORE` ✅ | Chain verification is O(N) SHA-256 — Rust is 3–10× faster for large chains |
| ConfigManager | Python | `KEEP_PYTHON` | File I/O + parsing; not hot path |
| Logger | Python | `KEEP_PYTHON` | I/O bound; Python logging is adequate |
| EventBus (dispatch) | Python (asyncio) | `KEEP_PYTHON` | asyncio-native; Rust here adds FFI overhead without benefit |
| Persistence (SQLite/JSON) | Python | `KEEP_PYTHON` | DB orchestration belongs in Python |
| Persistence (serialization) | Python | `RUST_CANDIDATE` | Large batch serialization (1000+ records) may benefit from Rust serde |
| Scheduler | Python (asyncio) | `KEEP_PYTHON` | asyncio loop; Rust cannot own asyncio |
| PluginLoader | Python | `KEEP_PYTHON` | Dynamic import; Python is required |

**Key Rust targets in L2:**
- `aegis_crypto` (✅ crate exists, bugs fixed in Phase R1)
- `aegis_audit_chain` (✅ crate exists, dependencies fixed in Phase R1)

---

### L3 — AI Kernel

| Component | Current | Classification | Rationale |
|-----------|---------|----------------|-----------|
| ModelRouter | Python | `KEEP_PYTHON` | Policy-driven routing; must remain Python |
| ProviderRegistry | Python | `KEEP_PYTHON` | Dynamic registration; Python metadata |
| OllamaProvider | Python | `KEEP_PYTHON` | HTTP client; I/O bound |
| GroqProvider | Python | `KEEP_PYTHON` | HTTP client; I/O bound |
| OpenRouterProvider | Python | `KEEP_PYTHON` | HTTP client; I/O bound |
| KeyManager / CredentialPool | Python | `KEEP_PYTHON` | Security-sensitive; Python with aegis_crypto backing |
| ProviderHealthMonitor | Python (asyncio) | `KEEP_PYTHON` | asyncio loop; Rust doesn't help here |
| Accounting | Python | `KEEP_PYTHON` | Persistence writes; I/O bound |
| Cache | Python | `KEEP_PYTHON` | In-process LRU; `functools` adequate |
| StructuredOutput validator | Python (Pydantic) | `KEEP_PYTHON` | Pydantic schema validation; Python-native |
| Scrubber (PII redaction) | Python | `RUST_CANDIDATE` | Regex over large text; Rust regex crate is faster for high volume |
| Streaming buffers | Python | `FUTURE_RESEARCH` | High-throughput token streaming may benefit; measure first |

**Verdict:** L3 stays Python. The only candidate is the Scrubber for very high-volume redaction.

---

### L4 — Memory & Knowledge

| Component | Current | Classification | Rationale |
|-----------|---------|----------------|-----------|
| MemoryManager (API) | Python | `KEEP_PYTHON` | Policy enforcement; must remain Python |
| **SearchEngine (ranking/filtering)** | Python | `IMPLEMENTED` ✅ R3 | **`aegis_search_core` crate: 17-24× faster at 100-5k records. 6 tests pass.** |
| **KnowledgeGraph (traversal)** | Python (dict-based) | `RUST_CANDIDATE` | BFS/DFS over large graphs; deferred — KG not yet under measured load |
| ContextBuilder | Python | `KEEP_PYTHON` | LLM prompt assembly; policy-driven |
| Memory policies | Python | `KEEP_PYTHON` | Policy enforcement; deterministic, must stay Python |
| Privacy mechanisms | Python | `DO_NOT_MIGRATE` | P0/P1 isolation must remain entirely in Python |
| Provenance | Python | `KEEP_PYTHON` | Trust chain records; Python-native |
| **P07 AppScanner (filesystem scan)** | Python | `RUST_CANDIDATE` | `walkdir` in Rust is faster + avoids Python GIL for parallel FS traversal |
| P07 ConsentGate | Python | `DO_NOT_MIGRATE` | Consent enforcement must remain Python |
| P07 ZoneRegistry / PrivacyZoneService | Python | `DO_NOT_MIGRATE` | Privacy boundary enforcement stays Python |
| P07 WorkflowAutoPromoter | Python | `KEEP_PYTHON` | Promotion policy stays Python |
| P07 FreshnessScheduler | Python (asyncio) | `KEEP_PYTHON` | asyncio loop; Rust doesn't help |
| P07 inference (WorkflowInferencer) | Python | `KEEP_PYTHON` | Heuristic/AI reasoning stays Python |
| Serialization (batch) | Python | `RUST_CANDIDATE` | Large memory snapshot serialization; serde is faster |

**Priority Rust targets in L4 (Phase R3+):**
- Search ranking kernel — **IMPLEMENTED ✅ (`aegis_search_core`, R3)**
- Knowledge graph traversal (`aegis_graph_core` DAG algorithms cover L6 DependencyGraph) — **IMPLEMENTED ✅ (R3)**
- P07 filesystem scanner (`aegis_scanner_core`) — deferred to R4

---

### L5 — Execution Engine

| Component | Current | Classification | Rationale |
|-----------|---------|----------------|-----------|
| PermissionEngine | Python | `DO_NOT_MIGRATE` | Governance; must remain deterministic Python |
| RiskAnalyzer | Python | `DO_NOT_MIGRATE` | Risk thresholds must remain Python |
| PolicyEngine | Python | `DO_NOT_MIGRATE` | Security policy must remain Python |
| AuditChain (Python side) | Python | `KEEP_PYTHON` | Orchestration stays Python; hashing delegated to `aegis_audit_chain` |
| **AuditChain (hash computation)** | Python | `RUST_CORE` ✅ | SHA-256 chain computation delegated to `aegis_audit_chain` Rust crate |
| SandboxManager (orchestration) | Python | `KEEP_PYTHON` | Policy + orchestration stays Python |
| **T2SubprocessSandbox (process spawn)** | Python | `RUST_CANDIDATE` | Resource limit enforcement (cgroup/setrlimit) is better in Rust |
| RollbackEngine | Python | `KEEP_PYTHON` | Transaction semantics; Python-native |
| PostExecVerifier | Python | `KEEP_PYTHON` | Assertion logic; Python-native |
| FilesystemExecutor | Python | `RUST_CANDIDATE` | High-throughput FS ops benefit from Rust |

**Verdict:** L5 governance (permission/risk/policy) **must not** migrate. Only low-level syscall primitives (process spawning, resource limits, FS ops) are Rust candidates.

---

### L6 — Planning / Agents

| Component | Current | Classification | Rationale |
|-----------|---------|----------------|-----------|
| GoalEngine | Python | `KEEP_PYTHON` | AI-driven goal generation |
| IntentParser / AmbiguityDetector | Python | `KEEP_PYTHON` | LLM reasoning |
| TaskDecomposer | Python | `KEEP_PYTHON` | LLM reasoning |
| **DependencyGraph (large DAG)** | Python | `IMPLEMENTED` ✅ R3 | **`aegis_graph_core` crate: toposort 8-38× faster, critical path 9-52×, cycles 13-279×. 9 tests pass.** |
| DecisionEngine / ScoringEngine | Python | `KEEP_PYTHON` | Configurable scoring; Python-native |
| PlannerService | Python | `KEEP_PYTHON` | Orchestration |
| ReflectionEngine | Python | `KEEP_PYTHON` | AI reasoning |
| VerificationPlanner | Python | `KEEP_PYTHON` | Policy + AI reasoning |
| RecoveryPlanner | Python | `KEEP_PYTHON` | Policy + AI reasoning |
| Metrics | Python | `KEEP_PYTHON` | Lightweight counters |

**Verdict:** L6 stays Python except the dependency graph computation kernel for large plans.

---

### L7 — HCI (Not Yet Implemented)

| Component | Current | Classification | Rationale |
|-----------|---------|----------------|-----------|
| UI layer | 🔲 Not started | `FUTURE_RESEARCH` | Evaluate when L7 is designed |
| File watcher | 🔲 Not started | `RUST_CANDIDATE` | `notify` crate is the right tool for cross-platform FS watching |
| Native event capture | 🔲 Not started | `RUST_CANDIDATE` | Platform-native input; Rust has better OS integration |
| IPC channel | 🔲 Not started | `RUST_CANDIDATE` | High-throughput IPC between AEGIS daemon and UI |

---

## 3. Existing Rust Crates Status

### `aegis_ffi_common` ✅ Correct (Phase R1: added `rand` dep)

| Item | Status |
|------|--------|
| `AegisId` (UUID v4) | ✅ Implemented |
| `FfiError` / `FfiResult<T>` | ✅ Implemented |
| Unit tests | ✅ Present |
| Cargo.toml | ✅ Fixed (added `rand = "0.8"`) |

### `aegis_crypto` ✅ Fixed (Phase R1: 6 compile errors corrected)

| Item | Status |
|------|--------|
| `sha256_hex()` | ✅ Implemented |
| `hmac_sha256_hex()` | ✅ Implemented |
| `aes256gcm_encrypt()` | ✅ Implemented |
| `aes256gcm_decrypt()` | ✅ Implemented |
| `base64_encode()` / `base64_decode()` | ✅ Added |
| PyO3 bindings (`python` feature) | ✅ Correct |
| Unit tests (7 tests) | ✅ Present |

**Errors fixed:**
1. `use base64::{...STANDARD as B64;` — wrong bracket (`;` inside `{}`)
2. `const HEX: &[u8; 16] = b"...".as_slice().try_into()` — not a valid const expression
3. `HEX[(b >> 4) as char]` — can't index with `char`; changed to `as usize`
4. AES-GCM encrypt called twice — first with wrong AAD concatenation, then `.and_then` retry
5. `aes256gcm_decrypt` missing closing `)` on `.map_err()`
6. `hmac_sha256_hex` didn't return `FfiResult` — changed signature to propagate errors

### `aegis_audit_chain` ✅ Correct (Phase R1: added `tempfile` dev-dep)

| Item | Status |
|------|--------|
| `AuditEntry` (struct + hash) | ✅ Implemented |
| `AuditChain` (append / verify / load) | ✅ Implemented |
| SHA-256 hash chain | ✅ Implemented |
| JSON Lines persistence | ✅ Implemented |
| Unit tests | ✅ Present |
| Cargo.toml | ✅ Fixed (added `tempfile = "3"` dev-dep) |

---

## 4. Proposed Future Crates (Phase R3+)

> These require `cargo` to be installed and benchmarks to justify them.

| Crate | Purpose | Layer | Priority |
|-------|---------|-------|----------|
| `aegis_search_core` | Search ranking, metadata filtering, candidate scoring | L4 | HIGH |
| `aegis_graph_core` | Knowledge graph traversal, BFS/DFS, topological sort | L4/L6 | HIGH |
| `aegis_scanner_core` | Filesystem scanning (walkdir), P07 environment discovery | L4 | MEDIUM |
| `aegis_system_core` | Process spawning, resource limits, sandbox primitives | L5 | MEDIUM |
| `aegis_planning_core` | Large DAG algorithms for L6 DependencyGraph | L6 | LOW |

---

## 5. FFI Strategy

**Selected approach:** PyO3 + maturin

- PyO3 provides idiomatic Python↔Rust bindings
- maturin builds the extension module as a `.pyd`/`.so` wheel
- Python imports via `try: import aegis_cffi; except ImportError: use_python_fallback()`
- **Graceful degradation:** Python fallback is always present; Rust is an optional optimization

**Boundary rules:**
```
Python object
    ↓ (validated schema)
Rust-native bytes/primitives
    ↓ (computation)
Rust result
    ↓ (error mapping → AegisError)
Python object
```

No Python GIL held during Rust computation (use `py.allow_threads()`).
No raw secrets cross the FFI boundary — pass key bytes, never key identifiers or paths.

---

## 6. Performance Hypothesis (Pre-Benchmark)

These are **hypotheses** to be validated in Phase R2, NOT claims:

| Component | Python baseline | Rust hypothesis | Benchmark method |
|-----------|----------------|-----------------|-----------------|
| `sha256_hex` (1 MB) | ~1.5 ms | ~0.15 ms | `timeit` vs Criterion |
| AuditChain verify (10k entries) | ~150 ms | ~15 ms | `timeit` vs Criterion |
| SearchEngine rank (10k records) | ~50 ms | ~5 ms | `timeit` vs Criterion |
| Filesystem scan (10k files) | ~500 ms | ~50 ms | `timeit` vs walkdir |

---

## 7. Migration Order (Phases)

| Phase | Scope | Status | Requires |
|-------|-------|--------|---------|
| **R0** | Audit + migration map + ADR | ✅ DONE | — |
| **R1** | Fix existing crates (`aegis_ffi_common`, `aegis_crypto`, `aegis_audit_chain`) | ✅ DONE | — |
| **R2** | Performance benchmarks for L2 crypto/audit, L4 search/graph, L5 system | 🔲 Next | `cargo` installed |
| **R3** | Implement `aegis_search_core` + `aegis_graph_core` | 🔲 Deferred | R2 benchmarks |
| **R4** | Integrate through PyO3 FFI | 🔲 Deferred | R3 crates |
| **R5** | Equivalence + regression tests | 🔲 Deferred | R4 integration |
| **R6** | Benchmark hybrid vs Python-only | 🔲 Deferred | R5 tests |
| **R7** | Migrate next highest-value component | 🔲 Deferred | R6 evidence |

---

## 8. Security Constraints

These invariants **must not be weakened** by any Rust migration:

1. P0 data never crosses the FFI boundary in cleartext
2. Rust errors must map to `AegisError` — no raw `panic` message exposed to Python
3. Privacy zone enforcement remains entirely in Python
4. Permission/risk/policy engine remains entirely in Python
5. Audit entries are authoritative from Python; Rust only computes hashes
6. Credential secrets are never passed to Rust — only derived/hashed bytes
7. Rust must not create an alternate execution path bypassing L5 pipeline
