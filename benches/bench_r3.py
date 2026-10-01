#!/usr/bin/env python3
"""
AEGIS Phase R3 -- Real-Load Profiling Benchmarks

Uses actual AEGIS model objects (MemoryRecord, DependencyGraph) to measure
hot-path performance at realistic AEGIS workload sizes.

B7: SearchEngine._compute_score() + sort over real MemoryRecord objects
B8: DependencyGraph operations (toposort, critical_path, detect_cycles, parallel_groups)

Run from repo root:
    python benches/bench_r3.py

Output: benches/results/r3_python_results.json
"""

from __future__ import annotations

import json
import os
import pathlib
import random
import sys
import time
from typing import Any

# ---------------------------------------------------------------------------
# Path setup -- add src/ so we can import AEGIS modules
# ---------------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WARMUP_ITERS = 5
MEASURE_ITERS = 50
SEARCH_SIZES   = [100, 500, 1_000, 5_000]
GRAPH_SIZES    = [50, 200, 500, 1_000]
GRAPH_DENSITY  = 0.04    # avg edges per node-pair => ~density*N*(N-1)/2 edges


# ---------------------------------------------------------------------------
# Timer
# ---------------------------------------------------------------------------

def measure_ns(fn, n_warmup=WARMUP_ITERS, n_measure=MEASURE_ITERS) -> float:
    for _ in range(n_warmup):
        fn()
    times = []
    for _ in range(n_measure):
        t0 = time.perf_counter_ns()
        fn()
        times.append(time.perf_counter_ns() - t0)
    times.sort()
    return float(times[len(times) // 2])


# ---------------------------------------------------------------------------
# B7 -- SearchEngine._compute_score() over real MemoryRecord objects
# ---------------------------------------------------------------------------

def _build_memory_records(n: int):
    """Build n real MemoryRecord objects with randomised fields."""
    from aegis.l4_memory.models import MemoryRecord, ProvenanceChain
    from aegis.l4_memory.types import (
        Importance, MemoryKind, MemoryStatus, MemoryTier, ProvenanceKind
    )

    rng = random.Random(42)
    importances = list(Importance)
    tiers       = [MemoryTier.T1_SESSION, MemoryTier.T2_EPISODIC,
                   MemoryTier.T3_SEMANTIC, MemoryTier.T5_PERSONAL]
    prov_kinds  = list(ProvenanceKind)
    kinds       = [MemoryKind.FACT, MemoryKind.OBSERVATION,
                   MemoryKind.PREFERENCE, MemoryKind.EVENT]

    now = time.time()
    records = []
    for i in range(n):
        age_days = rng.uniform(0, 365)
        records.append(
            MemoryRecord(
                key=f"bench/fact/item-{i}",
                namespace="bench",
                tier=rng.choice(tiers),
                kind=rng.choice(kinds),
                content=f"Benchmark record {i}",
                confidence=rng.uniform(0.2, 1.0),
                importance=rng.choice(importances),
                status=MemoryStatus.ACTIVE,
                is_pinned=rng.random() < 0.05,
                provenance=ProvenanceChain.single(
                    kind=rng.choice(prov_kinds),
                    subject="bench-agent",
                ),
                created_at=now - age_days * 86400,
                updated_at=now - age_days * 86400,
                privacy_tier=rng.choice(["P1", "P2", "P3"]),
            )
        )
    return records


def bench_search_score(n: int) -> dict:
    """B7: Score+sort n real MemoryRecord objects."""
    from aegis.l4_memory.search import SearchEngine, SearchQuery

    records = _build_memory_records(n)

    # Minimal stub store (we only use _compute_score, not the store)
    engine = SearchEngine(store=None)
    query  = SearchQuery(recency_weight=0.3)

    def score_and_sort():
        scored = []
        for rec in records:
            s = engine._compute_score(rec, query)
            scored.append((s, rec.id))
        scored.sort(key=lambda x: -x[0])
        return scored

    ns = measure_ns(score_and_sort)
    return {
        "benchmark": "search_score_real",
        "record_count": n,
        "median_ns": ns,
        "ns_per_record": round(ns / n, 1),
        "throughput_records_per_s": round(n / (ns / 1e9), 0),
    }


def bench_b7() -> list[dict]:
    print("\n[B7] SearchEngine._compute_score() + sort (real MemoryRecord objects)")
    results = []
    for n in SEARCH_SIZES:
        r = bench_search_score(n)
        results.append(r)
        print(f"  B7 Search score n={n:>5}  {r['median_ns']/1e6:8.3f} ms  "
              f"({r['ns_per_record']:.0f} ns/rec  {r['throughput_records_per_s']:.0f} rec/s)")
    return results


# ---------------------------------------------------------------------------
# B8 -- DependencyGraph operations on realistic DAGs
# ---------------------------------------------------------------------------

def _build_dag(n: int, density: float = GRAPH_DENSITY) -> Any:
    """Build a realistic DAG with n nodes and ~density*n*(n-1)/2 edges (no cycles)."""
    from aegis.l6_planning.decomposition.dependency_graph import DependencyGraph

    rng = random.Random(99)
    g = DependencyGraph()

    for i in range(n):
        g.add_node(
            f"t{i}",
            f"Task {i}: do something meaningful",
            weight=rng.uniform(0.5, 5.0),
        )

    # Only add edges from lower-index to higher-index nodes (guarantees DAG)
    target_edges = int(density * n * (n - 1) / 2)
    added = 0
    candidates = [(i, j) for i in range(n) for j in range(i + 1, n)]
    rng.shuffle(candidates)
    for from_i, to_i in candidates:
        if added >= target_edges:
            break
        g.add_edge(f"t{from_i}", f"t{to_i}")
        added += 1

    return g


def bench_graph_ops(n: int) -> list[dict]:
    """B8: Build DAG and benchmark all four graph operations."""
    g = _build_dag(n)
    results = []

    ops = [
        ("topological_sort",  lambda: g.topological_sort()),
        ("critical_path",     lambda: g.critical_path()),
        ("detect_cycles",     lambda: g.detect_cycles()),
        ("parallel_groups",   lambda: g.parallel_groups()),
    ]

    for op_name, fn in ops:
        ns = measure_ns(fn)
        results.append({
            "benchmark": f"dag_{op_name}",
            "node_count": n,
            "edge_count": g.edge_count,
            "median_ns": ns,
            "ns_per_node": round(ns / n, 1),
        })
        print(f"  B8 {op_name:<20} n={n:>5}  e={g.edge_count:>5}  "
              f"{ns/1e6:8.3f} ms  ({ns/n:.0f} ns/node)")

    return results


def bench_b8() -> list[dict]:
    print("\n[B8] DependencyGraph operations (real DependencyGraph objects)")
    results = []
    for n in GRAPH_SIZES:
        results += bench_graph_ops(n)
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 65)
    print("AEGIS Phase R3 -- Real-Load Python Profiling")
    print(f"Python {sys.version.split()[0]}  |  platform: {sys.platform}")
    print("=" * 65)

    all_results: list[dict] = []
    all_results += bench_b7()
    all_results += bench_b8()

    out_dir = pathlib.Path("benches/results")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "r3_python_results.json"
    with open(out_file, "w") as f:
        json.dump({
            "python_version": sys.version.split()[0],
            "platform": sys.platform,
            "results": all_results,
        }, f, indent=2)

    print(f"\n[OK] R3 results saved -> {out_file}")
    print("     Next: compare against Rust Criterion benchmarks.")


if __name__ == "__main__":
    main()
