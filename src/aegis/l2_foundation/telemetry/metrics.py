"""L2 Metrics registry (Counter / Gauge / Histogram).
Prompt 02 scope: local in-memory; no Prometheus push/pull, no OTLP export yet.
Interface is OTel-compatible so later prompt can drop exporters without code changes.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _Labels:
    labels: tuple[tuple[str, str], ...] = ()

    def __hash__(self) -> int:  # pragma: no cover - trivial
        return hash(self.labels)


class Counter:
    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description
        self._values: dict[tuple[tuple[str, str], ...], float] = {}
        self._lock = threading.RLock()

    def add(self, amount: float = 1.0, **labels: str) -> None:
        if amount < 0:
            raise ValueError("Counter.add requires amount >= 0")
        key = tuple(sorted(labels.items()))
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + amount

    def inc(self, **labels: str) -> None:
        self.add(1.0, **labels)

    def snapshot(self) -> dict[tuple[tuple[str, str], ...], float]:
        with self._lock:
            return dict(self._values)


class Gauge:
    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description
        self._values: dict[tuple[tuple[str, str], ...], float] = {}
        self._lock = threading.RLock()

    def set(self, value: float, **labels: str) -> None:
        key = tuple(sorted(labels.items()))
        with self._lock:
            self._values[key] = float(value)

    def inc(self, amount: float = 1.0, **labels: str) -> None:
        key = tuple(sorted(labels.items()))
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + amount

    def dec(self, amount: float = 1.0, **labels: str) -> None:
        self.inc(-amount, **labels)

    def snapshot(self) -> dict[tuple[tuple[str, str], ...], float]:
        with self._lock:
            return dict(self._values)


class Histogram:
    """Fixed-bucket histogram. Default buckets follow common millisecond response times scaled to seconds."""

    DEFAULT_BUCKETS: tuple[float, ...] = (
        0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float("inf")
    )

    def __init__(self, name: str, description: str = "", *, buckets: tuple[float, ...] | None = None) -> None:
        self.name = name
        self.description = description
        self.buckets = tuple(sorted(buckets or self.DEFAULT_BUCKETS))
        self._counts: dict[tuple[tuple[str, str], ...], list[int]] = {}
        self._sums: dict[tuple[tuple[str, str], ...], float] = {}
        self._lock = threading.RLock()

    def observe(self, value: float, **labels: str) -> None:
        key = tuple(sorted(labels.items()))
        with self._lock:
            buckets = self._counts.setdefault(key, [0] * len(self.buckets))
            for i, upper in enumerate(self.buckets):
                if value <= upper:
                    buckets[i] += 1
            self._sums[key] = self._sums.get(key, 0.0) + value

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "buckets": self.buckets,
                "counts": {k: list(v) for k, v in self._counts.items()},
                "sums": dict(self._sums),
            }


class MetricsRegistry:
    def __init__(self) -> None:
        self.counters: dict[str, Counter] = {}
        self.gauges: dict[str, Gauge] = {}
        self.histograms: dict[str, Histogram] = {}
        self._lock = threading.RLock()

    def counter(self, name: str, description: str = "") -> Counter:
        with self._lock:
            return self.counters.setdefault(name, Counter(name, description))

    def gauge(self, name: str, description: str = "") -> Gauge:
        with self._lock:
            return self.gauges.setdefault(name, Gauge(name, description))

    def histogram(self, name: str, description: str = "", *, buckets: tuple[float, ...] | None = None) -> Histogram:
        with self._lock:
            if name not in self.histograms:
                self.histograms[name] = Histogram(name, description, buckets=buckets)
            return self.histograms[name]

    def export_all(self) -> dict[str, Any]:
        with self._lock:
            return {
                "counters": {n: c.snapshot() for n, c in self.counters.items()},
                "gauges": {n: g.snapshot() for n, g in self.gauges.items()},
                "histograms": {n: h.snapshot() for n, h in self.histograms.items()},
                "collected_at": time.time(),
            }


_GLOBAL_REGISTRY: MetricsRegistry | None = None
_GLOBAL_REGISTRY_LOCK = threading.Lock()


def get_metrics_registry() -> MetricsRegistry:
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        with _GLOBAL_REGISTRY_LOCK:
            if _GLOBAL_REGISTRY is None:
                _GLOBAL_REGISTRY = MetricsRegistry()
    return _GLOBAL_REGISTRY
