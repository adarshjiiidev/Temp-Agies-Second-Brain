//! Criterion benchmark: B7 — SearchEngine scoring kernel (N records).
//!
//! Run: cargo +stable bench --bench search -p bench_rust

use criterion::{criterion_group, criterion_main, BenchmarkId, Criterion, Throughput};
use aegis_search_core::{RecordInput, Importance, ProvenanceKind, score_records};

fn make_records(n: usize) -> Vec<RecordInput> {
    let now = 1_700_000_000.0_f64;
    let importances = [Importance::Low, Importance::Normal, Importance::High, Importance::Critical];
    let provs = [
        ProvenanceKind::UserConfirmed, ProvenanceKind::FileDerived,
        ProvenanceKind::ModelInferred, ProvenanceKind::ConversationDerived,
    ];
    (0..n).map(|i| {
        let age_days = (i % 365) as f64;
        RecordInput {
            confidence: ((i % 10) as f32 + 1.0) / 10.0,
            updated_at_secs: now - age_days * 86_400.0,
            importance: importances[i % importances.len()],
            provenance: provs[i % provs.len()],
            is_decay_immune: i % 20 == 0,
        }
    }).collect()
}

fn bench_search_score(c: &mut Criterion) {
    let mut group = c.benchmark_group("search_score_real");
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap()
        .as_secs_f64();

    for n in [100usize, 500, 1_000, 5_000] {
        let records = make_records(n);
        group.throughput(Throughput::Elements(n as u64));
        group.bench_with_input(BenchmarkId::from_parameter(n), &records, |b, recs| {
            b.iter(|| score_records(recs, now, 0.3))
        });
    }
    group.finish();
}

criterion_group!(benches, bench_search_score);
criterion_main!(benches);
