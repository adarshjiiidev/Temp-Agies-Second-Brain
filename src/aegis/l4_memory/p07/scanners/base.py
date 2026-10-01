"""P07 Scanners — ScannerBase ABC.

All scanners implement this interface. Key invariants:
  - opt_in: scan is a no-op unless explicitly enabled.
  - dry_run: scan discovers but does not write to store.
  - max_seconds: hard wall-clock cap (STAB-01 precedent).
  - max_results: hard count cap.

Import safety: l4_memory.p07.model.types + stdlib ONLY.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from aegis.l4_memory.p07.model.types import ScanResult, ScannerState

__all__ = ["ScannerBase", "ScannerConfig"]


@dataclass
class ScannerConfig:
    """Configuration shared by all scanners."""
    opt_in: bool = False          # Scanner is disabled unless explicitly enabled
    dry_run: bool = False         # Discover but do not persist
    max_seconds: float = 10.0     # Wall-clock budget per scan run
    max_results: int = 500        # Maximum nodes returned per run
    privacy_tier: str = "P2"      # Default privacy tier for produced nodes


class ScannerBase(ABC):
    """Abstract base class for all P07 environment scanners.

    Subclasses implement ``_run(config, deadline)`` and return a ``ScanResult``.
    The base class wraps it with timing, error handling, and opt-in gating.
    """

    name: str = "base_scanner"

    def __init__(self, config: ScannerConfig | None = None) -> None:
        self._config = config or ScannerConfig()
        self._state: ScannerState = ScannerState.IDLE

    @property
    def state(self) -> ScannerState:
        return self._state

    @property
    def is_enabled(self) -> bool:
        return self._config.opt_in

    def enable(self) -> None:
        self._config = ScannerConfig(
            opt_in=True,
            dry_run=self._config.dry_run,
            max_seconds=self._config.max_seconds,
            max_results=self._config.max_results,
            privacy_tier=self._config.privacy_tier,
        )

    def disable(self) -> None:
        self._config = ScannerConfig(
            opt_in=False,
            dry_run=self._config.dry_run,
            max_seconds=self._config.max_seconds,
            max_results=self._config.max_results,
            privacy_tier=self._config.privacy_tier,
        )

    async def scan(self) -> ScanResult:
        """Run the scanner. Returns a no-op result if opt_in=False."""
        if not self._config.opt_in:
            return ScanResult(
                scanner_name=self.name,
                error="Scanner disabled (opt_in=False). Enable explicitly to run.",
            )

        self._state = ScannerState.RUNNING
        started = time.monotonic()
        deadline = started + self._config.max_seconds

        try:
            result = await self._run(self._config, deadline)
            result.duration_s = time.monotonic() - started
            self._state = ScannerState.DONE
            return result
        except Exception as exc:
            self._state = ScannerState.FAILED
            return ScanResult(
                scanner_name=self.name,
                error=str(exc),
                duration_s=time.monotonic() - started,
            )

    @abstractmethod
    async def _run(self, config: ScannerConfig, deadline: float) -> ScanResult:
        """Concrete scan implementation. Must respect deadline and max_results."""
        ...
