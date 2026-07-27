"""AI Kernel rolling counter registry — Prompt 03 §15 observability.

Maintains in-process counters (per-call, per-provider, per-model) without
external I/O. Produces AIMetricsSnapshot on demand for health checks.

Thread-safe: all mutations protected by threading.Lock.
Imports only: types + stdlib. No circular-import risk.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any

from aegis.l3_intelligence.ai_kernel.types import AIMetricsSnapshot


__all__ = ["AIMetricsRegistry"]

# Rolling latency window size (samples) for p50/p95 estimates.
_LATENCY_WINDOW = 200


class AIMetricsRegistry:
    """In-memory rolling metrics for the AI Kernel.

    Records are updated by the AIKernel on every generate/stream call.
    The kernel owns one AIMetricsRegistry and passes it to the router for
    per-route success feedback.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

        # Global counters
        self._requests_total: int = 0
        self._requests_succeeded: int = 0
        self._requests_failed: int = 0
        self._retries_total: int = 0
        self._fallbacks_total: int = 0
        self._cache_hits: int = 0
        self._cache_misses: int = 0
        self._rate_limit_events: int = 0
        self._budget_denials: int = 0
        self._input_tokens_total: int = 0
        self._output_tokens_total: int = 0
        self._estimated_cost_usd_total: float = 0.0

        # Rolling latency window (ms) for p50/p95 computation
        self._latencies_ms: deque[float] = deque(maxlen=_LATENCY_WINDOW)

        # Per-provider breakdowns: provider_id -> {requests, failures, cost_usd, tokens_in, tokens_out}
        self._per_provider: dict[str, dict[str, Any]] = {}
        # Per-model breakdowns: model_id -> {requests, failures, cost_usd}
        self._per_model: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Record helpers — called by AIKernel after each inference attempt.
    # ------------------------------------------------------------------

    def record_request(
        self,
        *,
        provider_id: str,
        model_id: str,
        success: bool,
        retries_used: int = 0,
        fallback_used: bool = False,
        from_cache: bool = False,
        latency_ms: float = 0.0,
        tokens_in: int = 0,
        tokens_out: int = 0,
        cost_usd: float = 0.0,
        rate_limited: bool = False,
        budget_denied: bool = False,
    ) -> None:
        with self._lock:
            self._requests_total += 1
            if success:
                self._requests_succeeded += 1
            else:
                self._requests_failed += 1
            self._retries_total += retries_used
            if fallback_used:
                self._fallbacks_total += 1
            if from_cache:
                self._cache_hits += 1
            else:
                self._cache_misses += 1
            if rate_limited:
                self._rate_limit_events += 1
            if budget_denied:
                self._budget_denials += 1
            if latency_ms > 0:
                self._latencies_ms.append(latency_ms)
            self._input_tokens_total += tokens_in
            self._output_tokens_total += tokens_out
            self._estimated_cost_usd_total += cost_usd

            # Per-provider
            prov = self._per_provider.setdefault(
                provider_id,
                {"requests": 0, "failures": 0, "cost_usd": 0.0, "tokens_in": 0, "tokens_out": 0},
            )
            prov["requests"] += 1
            if not success:
                prov["failures"] += 1
            prov["cost_usd"] += cost_usd
            prov["tokens_in"] += tokens_in
            prov["tokens_out"] += tokens_out

            # Per-model
            mod = self._per_model.setdefault(
                model_id,
                {"requests": 0, "failures": 0, "cost_usd": 0.0},
            )
            mod["requests"] += 1
            if not success:
                mod["failures"] += 1
            mod["cost_usd"] += cost_usd

    def record_cache_hit(self) -> None:
        with self._lock:
            self._cache_hits += 1

    def record_cache_miss(self) -> None:
        with self._lock:
            self._cache_misses += 1

    # ------------------------------------------------------------------
    # Snapshot — health checks + export.
    # ------------------------------------------------------------------

    def snapshot(self) -> AIMetricsSnapshot:
        with self._lock:
            latencies = list(self._latencies_ms)
            p50 = 0.0
            p95 = 0.0
            if latencies:
                sorted_lat = sorted(latencies)
                n = len(sorted_lat)
                p50 = sorted_lat[int(n * 0.50)]
                p95 = sorted_lat[min(int(n * 0.95), n - 1)]

            return AIMetricsSnapshot(
                requests_total=self._requests_total,
                requests_succeeded=self._requests_succeeded,
                requests_failed=self._requests_failed,
                retries_total=self._retries_total,
                fallbacks_total=self._fallbacks_total,
                cache_hits=self._cache_hits,
                cache_misses=self._cache_misses,
                rate_limit_events=self._rate_limit_events,
                budget_denials=self._budget_denials,
                input_tokens_total=self._input_tokens_total,
                output_tokens_total=self._output_tokens_total,
                estimated_cost_usd_total=self._estimated_cost_usd_total,
                latency_p50_ms=p50,
                latency_p95_ms=p95,
                per_provider=dict(self._per_provider),
                per_model=dict(self._per_model),
                updated_at=time.time(),
            )

    def reset(self) -> None:
        """Reset all counters. Primarily useful in tests."""
        with self._lock:
            self._requests_total = 0
            self._requests_succeeded = 0
            self._requests_failed = 0
            self._retries_total = 0
            self._fallbacks_total = 0
            self._cache_hits = 0
            self._cache_misses = 0
            self._rate_limit_events = 0
            self._budget_denials = 0
            self._input_tokens_total = 0
            self._output_tokens_total = 0
            self._estimated_cost_usd_total = 0.0
            self._latencies_ms.clear()
            self._per_provider.clear()
            self._per_model.clear()
