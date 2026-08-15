"""Capabilities model — CapabilityHealth.

Tracks runtime availability and reliability of a single capability.

Import safety: stdlib + pydantic only.
"""

from __future__ import annotations

import time
from enum import Enum

from pydantic import BaseModel, Field

__all__ = ["HealthStatus", "CapabilityHealth"]


class HealthStatus(str, Enum):
    """Runtime availability status."""
    AVAILABLE   = "available"     # Probed and confirmed working
    UNAVAILABLE = "unavailable"   # Probed and confirmed broken/absent
    DEGRADED    = "degraded"      # Present but not fully functional
    DISABLED    = "disabled"      # Explicitly disabled by policy/user
    UNKNOWN     = "unknown"       # Not yet probed


class CapabilityHealth(BaseModel):
    """Health record for a capability."""

    model_config = {"frozen": False}

    status: HealthStatus = HealthStatus.UNKNOWN
    last_checked: float = Field(default_factory=time.time)
    failure_count: int = 0
    success_count: int = 0
    last_error: str | None = None
    latency_ms_p50: float | None = None
    version_detected: str | None = None
    path_detected: str | None = None

    @property
    def is_usable(self) -> bool:
        """True if this capability can be invoked (available or degraded)."""
        return self.status in (HealthStatus.AVAILABLE, HealthStatus.DEGRADED)

    @property
    def is_available(self) -> bool:
        """True if this capability is fully healthy."""
        return self.status == HealthStatus.AVAILABLE

    def record_success(self, latency_ms: float | None = None) -> "CapabilityHealth":
        """Return an updated health record after a successful invocation."""
        return self.model_copy(update={
            "status": HealthStatus.AVAILABLE,
            "success_count": self.success_count + 1,
            "last_error": None,
            "latency_ms_p50": latency_ms if latency_ms is not None else self.latency_ms_p50,
            "last_checked": time.time(),
        })

    def record_failure(self, error: str) -> "CapabilityHealth":
        """Return an updated health record after a failed invocation."""
        new_status = (
            HealthStatus.UNAVAILABLE
            if self.failure_count + 1 >= 3
            else HealthStatus.DEGRADED
        )
        return self.model_copy(update={
            "status": new_status,
            "failure_count": self.failure_count + 1,
            "last_error": error,
            "last_checked": time.time(),
        })
