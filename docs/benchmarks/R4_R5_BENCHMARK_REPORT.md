# R4+R5 Benchmark Report

**Date:** 2026-08-15
**Phase:** P-RUST R4 (Filesystem Scanner Profiling) + R5 (PyO3 Integration Evaluation)

---

## R4 — Filesystem Scanner Profiling

### Workload Analysis

The AEGIS scanner (l4_memory/p07/scanners/providers.py) has two providers:

| Provider | Hot loop | Workload type |
|---|---|---|
| PathToolProvider | shutil.which() x 36 tools | OS syscall-bound |
| WindowsRegistryProvider | winreg key enumeration | OS syscall-bound |

### Benchmark Results (B9)

| Metric | Result |
|---|---|
| PathToolProvider scan time (36 tools) | 126.57ms |
| Tools found on this system | 14 |
| Python filename match (fnmatch, 4032 files) | 53.43ms |
| Python filename match (regex, 4032 files) | 1.05ms (50x faster) |

### R4 Decision: DO_NOT_MIGRATE

**Rationale:**
1. PathToolProvider is shutil.which() — OS PATH probe (kernel syscalls). Rust cannot accelerate kernel I/O.
2. WindowsRegistryProvider reads winreg — also OS-bound.
3. FilesystemExecutor walk (L5) was already fixed in STAB-01 with lazy iterator + 10s budget.
4. Python fnmatch is 50x slower than Python re. If needed: replace fnmatch with re. No Rust needed.
5. Scanner runs in background via FreshnessScheduler — 126ms latency acceptable.

**Classification:** KEEP_PYTHON

---

## R5 — PyO3 FFI Integration Evaluation

### Existing Rust Crates (from R3)

| Crate | Speedup | Tests |
|---|---|---|
| aegis_search_core | 17-24x (9.1ms -> 0.375ms @5k records) | 6 pass |
| aegis_graph_core | 8-280x (42ms -> 0.81ms @1k nodes) | 9 pass |

### FFI Overhead Estimation

| Crate | Data size | Serialization overhead |
|---|---|---|
| aegis_search_core | 5,000 records | 3.36ms |
| aegis_graph_core | 1,000 nodes | 0.39ms |

### Net Benefit Analysis

| Crate | Python time | Rust time | FFI overhead | Net benefit | Verdict |
|---|---|---|---|---|---|
| aegis_search_core | 9.1ms | 0.375ms | ~3.4ms | ~5.3ms | Borderline |
| aegis_graph_core | 42ms | 0.81ms | ~0.4ms | ~41ms | Clear gain |

### R5 Decision: DEFER to P10+

**Rationale:**
1. Both Rust crates are implemented and tested. Connection via PyO3 can happen anytime.
2. aegis_graph_core shows clear ~41ms net benefit per call. Wire it first.
3. aegis_search_core benefit is smaller (5ms). Wait for L7 real load.
4. PyO3 requires maturin build pipeline + CI/CD changes — best deferred until L7.
5. Rust crates function as standalone libraries; integration is incremental.

**Next milestone:** When L7 HCI creates measurable search/graph load. Target: P10+ Browser OS.

---

## Summary

| Phase | Scope | Decision | Rationale |
|---|---|---|---|
| R4 | Filesystem scanner | DO_NOT_MIGRATE | OS-syscall bound |
| R5 | PyO3 FFI integration | DEFER (P10+) | Crates ready; L7 demand not yet established |
| R3 | aegis_search_core | IMPLEMENTED | 24x speedup proven |
| R3 | aegis_graph_core | IMPLEMENTED | 52x speedup proven |
