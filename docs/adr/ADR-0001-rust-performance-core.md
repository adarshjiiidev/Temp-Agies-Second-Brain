# ADR-0001: Hybrid Python + Rust Performance Core

**Status:** Accepted
**Date:** 2026-08-12
**Deciders:** System Architect, Implementation Engineer
**Supersedes:** None
**Superseded by:** None (open; future sub-ADRs may refine per-crate decisions)

---

## Context

AEGIS is a local-first AI operating system with a 7-layer architecture (L1→L7). As the system grows, several subsystems will encounter performance walls:

- **L2 Crypto:** Python's `cryptography` library is fast but imposes GIL contention during bulk operations; constant-time guarantees are harder to enforce.
- **L4 Search/Graph:** Linear candidate ranking and knowledge-graph traversal over thousands of records is CPU-bound.
- **L4 P07 Scanning:** Filesystem traversal during environment discovery is I/O + CPU bound.
- **L5 Audit Chain:** Verifying a 10,000-entry hash chain in Python is measurably slow.
- **L5 Sandbox:** Low-level process isolation (resource limits, cgroup) requires syscall-level work where Python adds overhead.

Python remains the right language for:
- AI reasoning, intent interpretation, planning
- Privacy, permission, and policy enforcement
- Orchestration, lifecycle management
- Any component where correctness > throughput

---

## Decision

AEGIS adopts a **hybrid Python + Rust** architecture with:

1. **Python as the control/intelligence plane** — responsible for all governance, orchestration, and AI reasoning.
2. **Rust as the performance/systems plane** — responsible for computationally intensive, memory-safe, or syscall-level primitives.
3. **PyO3 + maturin** as the FFI bridge — providing idiomatic Python bindings, graceful fallback, and no GIL contention during Rust computation.

### Migration Scope (Phase R1 complete; R2+ pending benchmarks)

**Already exists (`crates/`):**
- `aegis_ffi_common` — shared FFI types (`AegisId`, `FfiError`)
- `aegis_crypto` — SHA-256, HMAC-SHA-256, AES-256-GCM, Base64
- `aegis_audit_chain` — append-only SHA-256 hash chain with JSON Lines persistence

**Proposed (pending Phase R2 benchmarks):**
- `aegis_search_core` — search ranking / metadata filtering kernel
- `aegis_graph_core` — knowledge graph traversal, topological sort
- `aegis_scanner_core` — filesystem scanning for P07 environment discovery
- `aegis_system_core` — process spawning, resource limits, sandbox primitives

### Components that will NOT migrate

| Component | Reason |
|-----------|--------|
| Permission/Risk/Policy engines (L5) | Governance — must remain deterministic Python |
| Privacy enforcement (L4) | Security invariant — P0/P1 boundaries are Python |
| AI reasoning / planning (L3/L6) | Intelligence — Python + LLM |
| Credential management (L3) | Security-sensitive; Python-native |
| Orchestration/lifecycle (L1/L2) | asyncio-native; Rust adds overhead |

---

## Rationale

### Why Rust specifically?

- **Memory safety without GC:** Critical for crypto and sandbox primitives where use-after-free or buffer overflows would be catastrophic.
- **Performance:** Rust is typically 5–20× faster than CPython for CPU-bound computation without GIL contention.
- **`unsafe`-free by default:** All AEGIS Rust crates use `#![forbid(unsafe_code)]`, giving the same memory safety guarantees as Python without the runtime overhead.
- **Systems access:** `setrlimit`, `seccomp`, `cgroups`, and other Linux security primitives are better accessed from Rust than Python.
- **Mature ecosystem:** `ring`, `sha2`, `aes-gcm`, `petgraph`, `walkdir`, `pyo3` are production-grade crates.

### Why PyO3 + maturin?

- Provides idiomatic Python types (bytes, str, lists) across the boundary.
- `py.allow_threads()` releases GIL during Rust computation.
- maturin produces a standard wheel; no special installation beyond `pip install`.
- When Rust is unavailable (no compiler), Python fallback is always present.

### Why NOT a full Rust rewrite?

- AEGIS's value is in AI-driven intelligence, not raw systems performance.
- Python's dynamic nature, asyncio integration, and ecosystem (Pydantic, FastAPI, httpx) are essential for L3–L6.
- A full Rust rewrite would require reimplementing asyncio semantics, LLM HTTP clients, schema validation, etc. — with no architectural benefit.
- The hybrid approach delivers performance where it matters (L2 crypto, L4 search, L5 sandbox) without abandoning the Python ecosystem.

---

## Consequences

### Positive

- Cryptographic operations gain constant-time guarantees and ~10× throughput.
- Audit chain verification scales to 100k+ entries without degrading AEGIS latency.
- Search and graph operations over large memory sets become sub-millisecond.
- P07 filesystem scanning no longer blocks the asyncio event loop.
- Rust's type system prevents entire classes of bugs at the Python↔Rust boundary.

### Negative / Risks

| Risk | Mitigation |
|------|-----------|
| Build complexity (Rust toolchain required) | Python fallback always present; Rust is optional optimization |
| FFI boundary bugs | Strict boundary schema validation; no raw pointers across boundary |
| Increased CI complexity | Separate `cargo test` step in CI; Python tests remain independent |
| Developer experience | Not all contributors know Rust; Python fallback is fully functional |
| Security at boundary | No secrets cross FFI; only bytes/primitives; all input validated |

### Rollback

If a Rust crate causes problems:
1. Python fallback is always present and tested.
2. Remove the `aegis_cffi` import and the Python fallback automatically activates.
3. No Python layer code depends on Rust being available.

---

## FFI Contract

Every Rust function exposed to Python must:

1. Accept only primitive types (`&[u8]`, `&str`, `i64`, `bool`) or bytestring containers — never Python objects
2. Return `PyResult<T>` — never panic across the boundary
3. Not hold the GIL during computation (`py.allow_threads()`)
4. Map all `FfiError` variants to appropriate `PyValueError` / `PyRuntimeError`
5. Never log, print, or emit secrets passed as key material

---

## Verification Criteria

Phase R1 verification (this ADR implementation):
- [ ] `cargo check --workspace` passes (requires cargo installation)
- [ ] `cargo test --workspace` passes (7 crypto tests, 1 audit test, 1 FFI test)
- [ ] Python test suite remains 1060/1060 (no Python regressions)
- [ ] No secrets in any Rust source files
- [ ] `#![forbid(unsafe_code)]` present in all crates

Phase R2+ verification (future):
- [ ] Benchmark results document pre- and post-migration latency
- [ ] Equivalence tests (Python == Rust output for all inputs)
- [ ] Property-based tests (fuzz inputs)

---

## Related Documents

- [RUST_PERFORMANCE_CORE.md](../architecture/RUST_PERFORMANCE_CORE.md) — Full migration map
- [P07_5_ARCHITECTURE.md](../P07_5_ARCHITECTURE.md) — LLM provider infrastructure
- [02_ARCHITECTURE.md](../02_ARCHITECTURE.md) — AEGIS layer architecture
- [09_ROADMAP.md](../09_ROADMAP.md) — Milestone roadmap
