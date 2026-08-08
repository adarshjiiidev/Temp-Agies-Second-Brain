"""P07 Model — FreshnessTracker.

Tracks per-scanner last-scan timestamps and computes staleness.

Import safety: model/types + stdlib ONLY.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


__all__ = ["FreshnessTracker", "ScannerFreshness"]


@dataclass
class ScannerFreshness:
    """Freshness record for a single scanner."""
    scanner_name: str
    last_scanned_at: float = 0.0   # Unix timestamp; 0.0 = never scanned
    default_ttl_seconds: float = 3600.0 * 24  # 24h default

    @property
    def age_seconds(self) -> float:
        if self.last_scanned_at == 0.0:
            return float("inf")
        return time.monotonic() - self.last_scanned_at

    @property
    def is_stale(self) -> bool:
        return self.age_seconds >= self.default_ttl_seconds

    @property
    def never_scanned(self) -> bool:
        return self.last_scanned_at == 0.0

    def mark_scanned(self) -> None:
        self.last_scanned_at = time.monotonic()


class FreshnessTracker:
    """Registry of per-scanner freshness records.

    Usage::

        tracker = FreshnessTracker()
        tracker.register("app_scanner", ttl_seconds=86400)
        if tracker.is_stale("app_scanner"):
            run_scanner()
        tracker.mark_scanned("app_scanner")
    """

    def __init__(self) -> None:
        self._records: dict[str, ScannerFreshness] = {}

    def register(self, scanner_name: str, ttl_seconds: float = 86400.0) -> None:
        """Register a scanner with a given TTL. Idempotent."""
        if scanner_name not in self._records:
            self._records[scanner_name] = ScannerFreshness(
                scanner_name=scanner_name,
                default_ttl_seconds=ttl_seconds,
            )

    def is_stale(self, scanner_name: str) -> bool:
        """Return True if the scanner has not run or its TTL has elapsed."""
        rec = self._records.get(scanner_name)
        if rec is None:
            return True
        return rec.is_stale

    def mark_scanned(self, scanner_name: str) -> None:
        """Record that a scanner just completed a run."""
        if scanner_name not in self._records:
            self.register(scanner_name)
        self._records[scanner_name].mark_scanned()

    def age_seconds(self, scanner_name: str) -> float:
        rec = self._records.get(scanner_name)
        return rec.age_seconds if rec else float("inf")

    def all_stale(self) -> list[str]:
        """Return names of all scanners that are stale or never ran."""
        return [name for name, rec in self._records.items() if rec.is_stale]

    def summary(self) -> dict[str, dict]:
        return {
            name: {
                "stale": rec.is_stale,
                "age_s": rec.age_seconds,
                "ttl_s": rec.default_ttl_seconds,
            }
            for name, rec in self._records.items()
        }
