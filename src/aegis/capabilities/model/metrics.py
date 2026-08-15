"""Capabilities model — CapabilityMetrics.

Tracks invocation statistics for a single capability.
Used by the selection engine to rank capabilities by reliability.

Import safety: stdlib + pydantic only.
"""

from __future__ import annotations

import time

from pydantic import BaseModel, Field

__all__ = ["CapabilityMetrics"]


class CapabilityMetrics(BaseModel):
    """Performance and reliability metrics for a capability."""

    model_config = {"frozen": False}

    invocation_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_latency_ms: float = 0.0
    last_used_at: float | None = None
    last_succeeded_at: float | None = None
    last_failed_at: float | None = None
    user_approval_count: int = 0    # Times user explicitly approved
    user_rejection_count: int = 0   # Times user explicitly rejected

    @property
    def success_rate(self) -> float:
        """Success rate as fraction 0.0–1.0. Returns 0.5 (neutral) if no invocations."""
        if self.invocation_count == 0:
            return 0.5
        return self.success_count / self.invocation_count

    @property
    def average_latency_ms(self) -> float | None:
        """Average latency in milliseconds, or None if no data."""
        if self.success_count == 0:
            return None
        return self.total_latency_ms / self.success_count

    @property
    def user_approval_rate(self) -> float:
        """User approval rate 0.0–1.0. Returns 1.0 if no approval events."""
        total = self.user_approval_count + self.user_rejection_count
        if total == 0:
            return 1.0
        return self.user_approval_count / total

    def record_invocation(
        self,
        *,
        success: bool,
        latency_ms: float | None = None,
    ) -> "CapabilityMetrics":
        """Return updated metrics after an invocation."""
        now = time.time()
        updates: dict = {
            "invocation_count": self.invocation_count + 1,
            "last_used_at": now,
        }
        if success:
            updates["success_count"] = self.success_count + 1
            updates["last_succeeded_at"] = now
            if latency_ms is not None:
                updates["total_latency_ms"] = self.total_latency_ms + latency_ms
        else:
            updates["failure_count"] = self.failure_count + 1
            updates["last_failed_at"] = now
        return self.model_copy(update=updates)

    def record_user_feedback(self, *, approved: bool) -> "CapabilityMetrics":
        """Return updated metrics after explicit user approval or rejection."""
        if approved:
            return self.model_copy(update={"user_approval_count": self.user_approval_count + 1})
        return self.model_copy(update={"user_rejection_count": self.user_rejection_count + 1})
