# AEGIS Phase R3 — Benchmark Report
## Real-Load Profiling & New Crate Implementation

**Date:** 2026-08-13  
**Rust toolchain:** stable 1.87.0 (Criterion 0.5)  
**Python:** 3.12.3  
**Platform:** Windows 11, x86-64  
**Decision threshold:** Rust must be >= 3x faster to justify new crate implementation.

---

## Executive Summary

> **Result: Both 3x thresholds met — massively exceeded.**
>
> `aegis_search_core` and `aegis_graph_core` are now implemented, tested, and benchmarked.
>
> - **B7 Search ranking**: Rust is **17-24x faster** than Python at all AEGIS-relevant sizes.  
>   At 5 000 records: Python 9.1ms → Rust 0.375ms (24x speedup).
>
> - **B8 DependencyGraph**: Rust is **8-280x faster** depending on operation and graph size.  
>   At 1 000 nodes: toposort Python 20ms → Rust 0.53ms (38x); detect_cycles 9.7ms → 0.035ms (279x).
>
> Both new crates are pure algorithmic implementations (no I/O, no FFI overhead in the inner loop)
> with identical semantics to the Python originals. They are ready as performance reference
> implementations and future PyO3 binding targets.

---

## B7 — Search Ranking Kernel (real MemoryRecord scoring)

The Python benchmark uses real `MemoryRecord` Pydantic objects and calls the actual
`SearchEngine._compute_score()`. The Rust benchmark uses equivalent flat `RecordInput` POD structs
and the identical formula in `aegis_search_core::score_records()`.

| Record count | Python (MemoryRecord) | Rust (RecordInput) | Speedup |
|---|---|---|---|
| 100 | 93 000 ns — 0.093 ms | 5 333 ns — 0.005 ms | **17.5x** |
| 500 | 493 000 ns — 0.493 ms | 30 205 ns — 0.030 ms | **16.3x** |
| 1 000 | 1 062 000 ns — 1.062 ms | 63 711 ns — 0.064 ms | **16.7x** |
| 5 000 | 9 113 000 ns — 9.113 ms | 375 170 ns — 0.375 ms | **24.3x** |

**Rust throughput:** 12.8–19.2 million records/second (vs Python ~550k–1.1M rec/s).

**Analysis:** The speedup comes from three factors:
1. Python `MemoryRecord` is a frozen Pydantic model — every attribute access goes through
   Pydantic's `__getattr__` machinery (slot access + validation). Rust uses a flat C struct.
2. Python's `dict.get()` for `_IMPORTANCE_WEIGHT` and `_PROVENANCE_QUALITY` is hash-table
   lookup + object comparison. Rust uses a `match` compiled to a jump table.
3. Python's `list.sort()` is Timsort with `key=lambda r: r.score` — function call overhead
   per comparison. Rust uses `sort_unstable_by` with inline comparator.

**Decision: IMPLEMENT — 24x faster at 5k records. Threshold exceeded by 8x.**  
**New crate:** `crates/aegis_search_core/` — 6 tests, 0 warnings. ✅

---

## B8 — DependencyGraph Operations (real DAG objects)

The Python benchmark builds real `DependencyGraph` objects (dict-based). The Rust benchmark
builds equivalent `aegis_graph_core::DependencyGraph` objects (Vec-based adjacency lists).

### B8a — Topological Sort (Kahn's algorithm)

| Nodes | Python | Rust | Speedup |
|---|---|---|---|
| 200 | 213 000 ns | 26 851 ns | **7.9x** |
| 500 | 1 353 000 ns | 122 970 ns | **11.0x** |
| 1 000 | 19 970 000 ns | 529 980 ns | **37.7x** |

### B8b — Critical Path (DP on topo order)

| Nodes | Python | Rust | Speedup |
|---|---|---|---|
| 50 | 68 000 ns | 7 672 ns | **8.9x** |
| 200 | 466 000 ns | 38 642 ns | **12.1x** |
| 500 | 3 310 000 ns | 182 290 ns | **18.2x** |
| 1 000 | 42 003 000 ns | 814 190 ns | **51.6x** |

### B8c — Cycle Detection (DFS)

| Nodes | Python | Rust | Speedup |
|---|---|---|---|
| 50 | 19 000 ns | 1 506 ns | **12.6x** |
| 200 | 115 000 ns | 6 434 ns | **17.9x** |
| 500 | 616 000 ns | 14 385 ns | **42.8x** |
| 1 000 | 9 697 000 ns | 34 708 ns | **279x** |

### B8d — Parallel Groups (level BFS)

| Nodes | Python | Rust | Speedup |
|---|---|---|---|
| 50 | 80 000 ns | 1 037 ns | **77x** |
| 200 | 257 000 ns | 12 999 ns | **19.8x** |
| 500 | 1 662 000 ns | 43 385 ns | **38.3x** |
| 1 000 | 21 692 000 ns | 114 330 ns | **190x** |

**Analysis:** The dominant factor is Python's `defaultdict(set)` vs Rust's `Vec<Vec<u32>>`.
Python's `set.discard()`, `set.add()`, and `len(set())` each involve hash operations.
Rust's Vec-based adjacency lists use direct index access and cache-friendly iteration.
The O(N^2) growth in Python vs O(N+E) in Rust at high node counts explains the
super-linear speedup at 1 000 nodes (cycle detection: 279x, parallel groups: 190x).

**Decision: IMPLEMENT — threshold exceeded by 13-93x. ✅**  
**New crate:** `crates/aegis_graph_core/` — 9 tests, 0 warnings. ✅

---

## Updated Migration Decision Table

| Component | Python impl | Rust impl | Speedup | Decision |
|---|---|---|---|---|
| SHA-256 | `hashlib.sha256` | `aegis_crypto::sha256_hex` | Python 1.5x faster | **KEEP_PYTHON** |
| HMAC-SHA-256 | `hmac.new` | `aegis_crypto::hmac_sha256_hex` | Python 1.7x faster | **KEEP_PYTHON** |
| AES-256-GCM | `cryptography.AESGCM` | `aegis_crypto::aes256gcm_*` | Python 5-10x faster | **DO_NOT_MIGRATE** |
| Audit verify | `chain.py` (SQLite) | `aegis_audit_chain::verify` | Different workloads | **KEEP_PYTHON** (pipeline) |
| **Search ranking** | `search.py` | `aegis_search_core::score_records` | **Rust 17-24x faster** | **IMPLEMENTED ✅** |
| **DAG toposort** | `dependency_graph.py` | `aegis_graph_core::topological_sort` | **Rust 8-38x faster** | **IMPLEMENTED ✅** |
| **DAG critical path** | `dependency_graph.py` | `aegis_graph_core::critical_path` | **Rust 9-52x faster** | **IMPLEMENTED ✅** |
| **DAG cycle detect** | `dependency_graph.py` | `aegis_graph_core::detect_cycles` | **Rust 13-279x faster** | **IMPLEMENTED ✅** |
| **DAG parallel groups** | `dependency_graph.py` | `aegis_graph_core::parallel_groups` | **Rust 20-190x faster** | **IMPLEMENTED ✅** |
| Filesystem scan | `filesystem.py` | Not implemented | ~82ms @ 10k | **DEFER** |

---

## Complete Rust Workspace State (post R3)

| Crate | Purpose | Tests | Status |
|---|---|---|---|
| `aegis_ffi_common` | UUID generation, shared FFI types | 1 | ✅ |
| `aegis_crypto` | SHA-256, HMAC, AES-256-GCM | 9 | ✅ |
| `aegis_audit_chain` | Tamper-evident JSONL audit log | 1 | ✅ |
| `aegis_search_core` | Memory record ranking kernel | 6 | ✅ NEW |
| `aegis_graph_core` | DAG ops (toposort, critical path, cycles) | 9 | ✅ NEW |
| **Total** | | **26** | |

---

## Phase R4 Recommendation

Phase R3 is complete. The Rust performance core now covers all confirmed bottleneck paths.

**Remaining candidate:** Filesystem scan (`walkdir`) — deferred. Current L5 design has explicit
10-second wall-clock limit + lazy iterator. No evidence of real bottleneck yet.

**Phase R4 entry criteria:**
- Profile real AEGIS L5 `FilesystemExecutor` under P07 app-scanning workload.
- If scan latency exceeds 5s at realistic home-directory scope, implement `aegis_scanner_core`.
- Otherwise, P-RUST phase is complete. Move to PyO3 FFI wiring (Phase R5).

**Phase R5 (future):** Wire `aegis_search_core` and `aegis_graph_core` into Python via PyO3,
replacing the Python hot paths for large-scale workloads. Requires no architecture changes —
the Rust crates are already designed as drop-in algorithmic replacements.

---

## Benchmark Artifacts

- `benches/bench_r3.py` — real-load Python profiler (B7+B8)
- `benches/results/r3_python_results.json` — raw Python results
- `benches/bench_rust/benches/search.rs` — Criterion B7 benchmark
- `benches/bench_rust/benches/graph.rs` — Criterion B8 benchmark
- `crates/aegis_search_core/` — new production crate
- `crates/aegis_graph_core/` — new production crate
