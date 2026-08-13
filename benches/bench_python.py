#!/usr/bin/env python3
"""
AEGIS Phase R2 — Python Baseline Benchmarks

Measures real Python performance for the components identified as Rust candidates
in RUST_PERFORMANCE_CORE.md. Results are saved as JSON for comparison against
the Criterion Rust benchmarks.

Run from repo root:
    python benches/bench_python.py

Output: benches/results/python_results.json
        (and a printed table to stdout)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import pathlib
import random
import string
import sys
import tempfile
import timeit
import time
from dataclasses import dataclass, field, asdict
from typing import Any


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WARMUP_ITERS = 5        # iterations to warm the CPU / caches
MEASURE_ITERS = 50      # iterations to measure
PAYLOAD_SIZES = [1_024, 65_536, 1_048_576]   # 1 KB, 64 KB, 1 MB
AUDIT_CHAIN_SIZES = [100, 1_000, 10_000]
SEARCH_CANDIDATE_SIZES = [100, 1_000, 5_000]
SCAN_FILE_COUNTS = [500, 2_000, 10_000]

KEY_32 = os.urandom(32)
NONCE_12 = os.urandom(12)
AAD = b"aegis-benchmark-aad"


# ---------------------------------------------------------------------------
# Timer helper
# ---------------------------------------------------------------------------

def measure_ns(fn, n_warmup=WARMUP_ITERS, n_measure=MEASURE_ITERS) -> float:
    """Return median latency in nanoseconds."""
    for _ in range(n_warmup):
        fn()
    times = []
    for _ in range(n_measure):
        t0 = time.perf_counter_ns()
        fn()
        times.append(time.perf_counter_ns() - t0)
    times.sort()
    return float(times[len(times) // 2])   # median


# ---------------------------------------------------------------------------
# B1 — SHA-256
# ---------------------------------------------------------------------------

def bench_sha256() -> list[dict]:
    results = []
    for size in PAYLOAD_SIZES:
        data = os.urandom(size)
        ns = measure_ns(lambda: hashlib.sha256(data).hexdigest())
        throughput_mb_s = (size / (ns / 1e9)) / 1_048_576
        results.append({
            "benchmark": "sha256",
            "payload_bytes": size,
            "median_ns": ns,
            "throughput_mb_s": round(throughput_mb_s, 2),
        })
        print(f"  B1 SHA-256 {size//1024:>4}KB  {ns/1e6:8.3f} ms   {throughput_mb_s:8.1f} MB/s")
    return results


# ---------------------------------------------------------------------------
# B2 — HMAC-SHA-256
# ---------------------------------------------------------------------------

def bench_hmac() -> list[dict]:
    results = []
    for size in PAYLOAD_SIZES:
        data = os.urandom(size)
        ns = measure_ns(lambda: hmac.new(KEY_32, data, hashlib.sha256).hexdigest())
        throughput_mb_s = (size / (ns / 1e9)) / 1_048_576
        results.append({
            "benchmark": "hmac_sha256",
            "payload_bytes": size,
            "median_ns": ns,
            "throughput_mb_s": round(throughput_mb_s, 2),
        })
        print(f"  B2 HMAC    {size//1024:>4}KB  {ns/1e6:8.3f} ms   {throughput_mb_s:8.1f} MB/s")
    return results


# ---------------------------------------------------------------------------
# B3 — AES-256-GCM
# ---------------------------------------------------------------------------

def bench_aesgcm() -> list[dict]:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        cipher = AESGCM(KEY_32)
    except ImportError:
        print("  B3 SKIPPED — `cryptography` package not installed")
        return []

    results = []
    for size in PAYLOAD_SIZES:
        plaintext = os.urandom(size)
        ciphertext = cipher.encrypt(NONCE_12, plaintext, AAD)

        ns_enc = measure_ns(lambda: cipher.encrypt(NONCE_12, plaintext, AAD))
        ns_dec = measure_ns(lambda: cipher.decrypt(NONCE_12, ciphertext, AAD))
        tp_enc = (size / (ns_enc / 1e9)) / 1_048_576
        tp_dec = (size / (ns_dec / 1e9)) / 1_048_576

        results.append({
            "benchmark": "aesgcm_encrypt",
            "payload_bytes": size,
            "median_ns": ns_enc,
            "throughput_mb_s": round(tp_enc, 2),
        })
        results.append({
            "benchmark": "aesgcm_decrypt",
            "payload_bytes": size,
            "median_ns": ns_dec,
            "throughput_mb_s": round(tp_dec, 2),
        })
        print(f"  B3 AES-ENC {size//1024:>4}KB  {ns_enc/1e6:8.3f} ms   {tp_enc:8.1f} MB/s")
        print(f"  B3 AES-DEC {size//1024:>4}KB  {ns_dec/1e6:8.3f} ms   {tp_dec:8.1f} MB/s")
    return results


# ---------------------------------------------------------------------------
# B4 — Audit chain SHA-256 verify (pure Python)
# Simulates what chain.py does: SHA-256(prev_hash || fields_json)
# ---------------------------------------------------------------------------

def _make_chain_entries(n: int) -> list[dict]:
    """Build a list of synthetic chain entries (in-memory, no SQLite)."""
    entries = []
    prev = "0" * 64
    for i in range(n):
        blob = json.dumps({
            "seq": i, "actor": "bench", "action": "op",
            "payload": f'{{"i":{i}}}', "prev": prev,
        })
        h = hashlib.sha256(blob.encode()).hexdigest()
        entries.append({"hash": h, "prev": prev, "blob": blob})
        prev = h
    return entries


def bench_audit_verify() -> list[dict]:
    results = []
    for n in AUDIT_CHAIN_SIZES:
        entries = _make_chain_entries(n)

        def verify():
            prev = "0" * 64
            for e in entries:
                if e["prev"] != prev:
                    return False
                computed = hashlib.sha256(e["blob"].encode()).hexdigest()
                if computed != e["hash"]:
                    return False
                prev = e["hash"]
            return True

        ns = measure_ns(verify)
        results.append({
            "benchmark": "audit_verify",
            "entry_count": n,
            "median_ns": ns,
            "ns_per_entry": round(ns / n, 1),
        })
        print(f"  B4 AuditVerify n={n:>6}  {ns/1e6:8.3f} ms  ({ns/n:.0f} ns/entry)")
    return results


# ---------------------------------------------------------------------------
# B5 — Search ranking (BASELINE ONLY — no Rust equivalent yet)
# Mimics l4_memory/search.py _score() logic
# ---------------------------------------------------------------------------

def bench_search_rank() -> list[dict]:
    """Score K synthetic MemoryRecord-like dicts using the same formula as SearchEngine."""
    import random

    PROVENANCE_QUALITY = {0: 1.0, 1: 0.95, 2: 0.85, 3: 0.75, 4: 0.70,
                          5: 0.65, 6: 0.60, 7: 0.55, 8: 0.50, 9: 0.40}
    IMPORTANCE_WEIGHT = {0: 2.0, 1: 1.5, 2: 1.0, 3: 0.5}

    now = time.time()
    results = []

    for k in SEARCH_CANDIDATE_SIZES:
        # Build synthetic candidates
        candidates = []
        for _ in range(k):
            created = now - random.uniform(0, 86400 * 365)
            age_days = (now - created) / 86400
            recency = max(0.1, 1.0 / (1.0 + age_days / 30.0))
            confidence = random.uniform(0.5, 1.0)
            importance = random.randint(0, 3)
            provenance = random.randint(0, 9)
            candidates.append({
                "confidence": confidence,
                "importance": importance,
                "provenance": provenance,
                "recency": recency,
            })

        def rank():
            scored = []
            for c in candidates:
                score = (
                    c["confidence"]
                    * IMPORTANCE_WEIGHT[c["importance"]]
                    * c["recency"]
                    * PROVENANCE_QUALITY[c["provenance"]]
                )
                scored.append((score, c))
            scored.sort(key=lambda x: -x[0])
            return scored

        ns = measure_ns(rank)
        results.append({
            "benchmark": "search_rank",
            "candidate_count": k,
            "median_ns": ns,
            "ns_per_candidate": round(ns / k, 1),
        })
        print(f"  B5 SearchRank k={k:>5}   {ns/1e6:8.3f} ms  ({ns/k:.0f} ns/candidate)")
    return results


# ---------------------------------------------------------------------------
# B6 — Filesystem scan (BASELINE ONLY — no Rust equivalent yet)
# Mimics FilesystemExecutor._search with os.walk + lazy iterator
# ---------------------------------------------------------------------------

def _create_temp_tree(n_files: int) -> pathlib.Path:
    """Create a temp directory with n_files small files in a shallow tree."""
    root = pathlib.Path(tempfile.mkdtemp(prefix="aegis_bench_"))
    files_per_dir = max(10, n_files // 20)
    created = 0
    depth0 = root
    for d_idx in range(max(1, n_files // files_per_dir + 1)):
        subdir = depth0 / f"d{d_idx:04d}"
        subdir.mkdir(parents=True, exist_ok=True)
        for f_idx in range(files_per_dir):
            if created >= n_files:
                break
            (subdir / f"f{f_idx:06d}.txt").write_bytes(b"x" * 64)
            created += 1
        if created >= n_files:
            break
    return root


def bench_filesystem_scan() -> list[dict]:
    results = []
    for n in SCAN_FILE_COUNTS:
        root = _create_temp_tree(n)
        # Warm once
        list(root.rglob("*"))

        def scan():
            count = 0
            for _ in root.rglob("*"):
                count += 1
                if count >= n:
                    break
            return count

        ns = measure_ns(scan, n_warmup=2, n_measure=20)
        results.append({
            "benchmark": "filesystem_scan",
            "file_count": n,
            "median_ns": ns,
            "ns_per_file": round(ns / n, 1),
        })
        print(f"  B6 FSScan  n={n:>6}   {ns/1e6:8.3f} ms  ({ns/n:.0f} ns/file)")

        # Cleanup
        import shutil
        shutil.rmtree(root, ignore_errors=True)
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 65)
    print("AEGIS Phase R2 — Python Baseline Benchmarks")
    print(f"Python {sys.version.split()[0]}  |  platform: {sys.platform}")
    print("=" * 65)

    all_results: list[dict] = []

    print("\n[B1] SHA-256 throughput")
    all_results += bench_sha256()

    print("\n[B2] HMAC-SHA-256 throughput")
    all_results += bench_hmac()

    print("\n[B3] AES-256-GCM roundtrip")
    all_results += bench_aesgcm()

    print("\n[B4] Audit chain verify (in-memory SHA-256 chain)")
    all_results += bench_audit_verify()

    print("\n[B5] Search rank/score (baseline — no Rust yet)")
    all_results += bench_search_rank()

    print("\n[B6] Filesystem scan (baseline — no Rust yet)")
    all_results += bench_filesystem_scan()

    # Save results
    out_dir = pathlib.Path("benches/results")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "python_results.json"
    with open(out_file, "w") as f:
        json.dump({"python_version": sys.version.split()[0],
                   "platform": sys.platform,
                   "results": all_results}, f, indent=2)

    print(f"\n[OK] Results saved -> {out_file}")
    print("   Run `cargo +stable bench -p bench_rust` for Rust side.")


if __name__ == "__main__":
    main()
