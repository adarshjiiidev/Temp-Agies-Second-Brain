//! Criterion benchmarks: B1 (SHA-256), B2 (HMAC-SHA-256), B3 (AES-256-GCM).
//!
//! Run: cargo +stable bench --bench crypto -p bench_rust

use criterion::{criterion_group, criterion_main, BenchmarkId, Criterion, Throughput};
use rand::RngCore;

// ---------------------------------------------------------------------------
// B1 — SHA-256
// ---------------------------------------------------------------------------

fn bench_sha256(c: &mut Criterion) {
    let mut group = c.benchmark_group("sha256");
    for size in [1_024usize, 65_536, 1_048_576] {
        let mut data = vec![0u8; size];
        rand::thread_rng().fill_bytes(&mut data);
        group.throughput(Throughput::Bytes(size as u64));
        group.bench_with_input(BenchmarkId::from_parameter(size), &data, |b, d| {
            b.iter(|| aegis_crypto::sha256_hex(d))
        });
    }
    group.finish();
}

// ---------------------------------------------------------------------------
// B2 — HMAC-SHA-256
// ---------------------------------------------------------------------------

fn bench_hmac(c: &mut Criterion) {
    let mut group = c.benchmark_group("hmac_sha256");
    let mut key = [0u8; 32];
    rand::thread_rng().fill_bytes(&mut key);
    for size in [1_024usize, 65_536, 1_048_576] {
        let mut data = vec![0u8; size];
        rand::thread_rng().fill_bytes(&mut data);
        group.throughput(Throughput::Bytes(size as u64));
        group.bench_with_input(BenchmarkId::from_parameter(size), &data, |b, d| {
            b.iter(|| aegis_crypto::hmac_sha256_hex(&key, d).unwrap())
        });
    }
    group.finish();
}

// ---------------------------------------------------------------------------
// B3 — AES-256-GCM roundtrip
// ---------------------------------------------------------------------------

fn bench_aes_gcm(c: &mut Criterion) {
    let mut group = c.benchmark_group("aes256gcm_roundtrip");
    let mut key = [0u8; 32];
    let mut nonce = [0u8; 12];
    rand::thread_rng().fill_bytes(&mut key);
    rand::thread_rng().fill_bytes(&mut nonce);
    let aad = b"aegis-benchmark-aad";
    for size in [1_024usize, 65_536, 1_048_576] {
        let mut plaintext = vec![0u8; size];
        rand::thread_rng().fill_bytes(&mut plaintext);
        // Pre-encrypt so decrypt benchmark uses real ciphertext
        let ciphertext =
            aegis_crypto::aes256gcm_encrypt(&key, &nonce, aad, &plaintext).unwrap();
        group.throughput(Throughput::Bytes(size as u64));
        // Encrypt half
        group.bench_with_input(
            BenchmarkId::new("encrypt", size),
            &plaintext,
            |b, pt| {
                b.iter(|| aegis_crypto::aes256gcm_encrypt(&key, &nonce, aad, pt).unwrap())
            },
        );
        // Decrypt half
        group.bench_with_input(
            BenchmarkId::new("decrypt", size),
            &ciphertext,
            |b, ct| {
                b.iter(|| aegis_crypto::aes256gcm_decrypt(&key, &nonce, aad, ct).unwrap())
            },
        );
    }
    group.finish();
}

criterion_group!(benches, bench_sha256, bench_hmac, bench_aes_gcm);
criterion_main!(benches);
