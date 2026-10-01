//! Criterion benchmark: B4 — AuditChain.verify() at N = 100, 1 000, 10 000 entries.
//!
//! Run: cargo +stable bench --bench audit -p bench_rust

use criterion::{criterion_group, criterion_main, BenchmarkId, Criterion};
use std::path::PathBuf;
use tempfile::tempdir;

fn build_chain(n: usize) -> (aegis_audit_chain::AuditChain, PathBuf) {
    let dir = tempdir().unwrap();
    let path = dir.path().join("bench_audit.jsonl");
    let mut chain = aegis_audit_chain::AuditChain::new(&path);
    chain.load_or_create().unwrap();
    for i in 0..n {
        chain
            .append(
                "bench-actor",
                "bench-action",
                &format!(r#"{{"index":{i}}}"#),
                &format!("cid-{i}"),
            )
            .unwrap();
    }
    // Leak the tempdir so the file stays alive for the benchmark
    let kept_path = path.clone();
    std::mem::forget(dir);
    (chain, kept_path)
}

// ---------------------------------------------------------------------------
// B4 — Audit chain verify (N entries)
// ---------------------------------------------------------------------------

fn bench_audit_verify(c: &mut Criterion) {
    let mut group = c.benchmark_group("audit_chain_verify");
    for &n in &[100usize, 1_000, 10_000] {
        let (chain, _path) = build_chain(n);
        group.bench_with_input(BenchmarkId::from_parameter(n), &chain, |b, ch| {
            b.iter(|| ch.verify())
        });
    }
    group.finish();
}

// ---------------------------------------------------------------------------
// B4b — Audit chain append (amortised cost per entry)
// ---------------------------------------------------------------------------

fn bench_audit_append(c: &mut Criterion) {
    let mut group = c.benchmark_group("audit_chain_append");
    for &n in &[100usize, 1_000] {
        group.bench_with_input(BenchmarkId::from_parameter(n), &n, |b, &size| {
            b.iter_batched(
                || {
                    let dir = tempdir().unwrap();
                    let path = dir.path().join("audit.jsonl");
                    let mut chain = aegis_audit_chain::AuditChain::new(&path);
                    chain.load_or_create().unwrap();
                    let kept_path = path.clone();
                    std::mem::forget(dir);
                    (chain, kept_path)
                },
                |(mut chain, _path)| {
                    for i in 0..size {
                        chain
                            .append("a", "op", "{}", &format!("c{i}"))
                            .unwrap();
                    }
                },
                criterion::BatchSize::SmallInput,
            )
        });
    }
    group.finish();
}

criterion_group!(benches, bench_audit_verify, bench_audit_append);
criterion_main!(benches);
