//! Criterion benchmark: B8 — DependencyGraph operations (N nodes, realistic density).
//!
//! Run: cargo +stable bench --bench graph -p bench_rust

use criterion::{criterion_group, criterion_main, BenchmarkId, Criterion};
use aegis_graph_core::DependencyGraph;

/// Build a realistic DAG with n nodes and ~density * n*(n-1)/2 edges.
/// Only forward edges (i → j where j > i) to guarantee acyclicity.
fn build_dag(n: usize, density: f64) -> DependencyGraph {
    let mut g = DependencyGraph::new(n);
    // Set random-ish weights
    for i in 0..n as u32 {
        g.set_weight(i, 0.5 + (i as f64 % 9.0) * 0.5);
    }

    let target_edges = (density * n as f64 * (n - 1) as f64 / 2.0) as usize;
    let mut added = 0usize;
    // Deterministic pseudo-shuffle using a simple LCG
    let mut rng: u64 = 0xDEAD_BEEF;
    let max_pairs = n * (n - 1) / 2;

    for _ in 0..max_pairs {
        if added >= target_edges { break; }
        rng = rng.wrapping_mul(6_364_136_223_846_793_005).wrapping_add(1_442_695_040_888_963_407);
        let idx = (rng >> 33) as usize % max_pairs;
        // Convert linear index to (i, j) pair where i < j
        let i = (((2 * n + 1) as f64 - ((2 * n + 1) as f64 * (2 * n + 1) as f64 - 8.0 * idx as f64).sqrt()) / 2.0) as usize;
        let j = idx - (i * (2 * n - i - 1) / 2) + i + 1;
        if j < n {
            g.add_edge(i as u32, j as u32);
            added += 1;
        }
    }
    g
}

fn bench_dag_toposort(c: &mut Criterion) {
    let mut group = c.benchmark_group("dag_topological_sort");
    for n in [50usize, 200, 500, 1_000] {
        let g = build_dag(n, 0.04);
        group.bench_with_input(BenchmarkId::from_parameter(n), &g, |b, dag| {
            b.iter(|| dag.topological_sort().unwrap())
        });
    }
    group.finish();
}

fn bench_dag_critical_path(c: &mut Criterion) {
    let mut group = c.benchmark_group("dag_critical_path");
    for n in [50usize, 200, 500, 1_000] {
        let g = build_dag(n, 0.04);
        group.bench_with_input(BenchmarkId::from_parameter(n), &g, |b, dag| {
            b.iter(|| dag.critical_path().unwrap())
        });
    }
    group.finish();
}

fn bench_dag_detect_cycles(c: &mut Criterion) {
    let mut group = c.benchmark_group("dag_detect_cycles");
    for n in [50usize, 200, 500, 1_000] {
        let g = build_dag(n, 0.04);
        group.bench_with_input(BenchmarkId::from_parameter(n), &g, |b, dag| {
            b.iter(|| dag.detect_cycles())
        });
    }
    group.finish();
}

fn bench_dag_parallel_groups(c: &mut Criterion) {
    let mut group = c.benchmark_group("dag_parallel_groups");
    for n in [50usize, 200, 500, 1_000] {
        let g = build_dag(n, 0.04);
        group.bench_with_input(BenchmarkId::from_parameter(n), &g, |b, dag| {
            b.iter(|| dag.parallel_groups())
        });
    }
    group.finish();
}

criterion_group!(
    benches,
    bench_dag_toposort,
    bench_dag_critical_path,
    bench_dag_detect_cycles,
    bench_dag_parallel_groups,
);
criterion_main!(benches);
