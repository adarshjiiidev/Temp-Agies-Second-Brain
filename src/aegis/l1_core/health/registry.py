"""L1 Health monitoring.
Exactly 4 states per Prompt 02 §13: HEALTHY / DEGRADED / UNHEALTHY / UNKNOWN.
Every HealthProvider feeds the HealthAggregator, which produces aggregated HealthReports."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID

from aegis.l1_core.errors.base import TimeoutError as AegisTimeoutError
from aegis.l1_core.interfaces.base import HealthProvider


class HealthState(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


# Backwards-compat alias: docs use "states" sometimes as "HealthStatus"
HealthStatus = HealthState


@dataclass
class HealthCheck:
    """One registered health check."""

    component: str
    check_fn: Callable[[], Awaitable[dict[str, Any]]]
    timeout_seconds: float = 5.0
    dependencies: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ComponentHealth:
    component: str
    state: HealthState
    details: dict[str, Any] = field(default_factory=dict)
    latency_ms: int = 0
    error: str | None = None
    checked_at: float = 0.0


@dataclass
class HealthReport:
    report_id: UUID
    generated_at: float
    overall: HealthState
    components: dict[str, ComponentHealth]
    duration_ms: int = 0

    def summary(self) -> dict[str, Any]:
        counts = {s: 0 for s in HealthState}
        for c in self.components.values():
            counts[c.state] += 1
        return {
            "report_id": str(self.report_id),
            "overall": self.overall.value,
            "generated_at": self.generated_at,
            "duration_ms": self.duration_ms,
            "components_total": len(self.components),
            "components_by_state": {k.value: v for k, v in counts.items()},
        }


def _state_from_result(value: str | dict[str, Any]) -> HealthState:
    if isinstance(value, dict):
        v = str(value.get("status", "")).lower()
    else:
        v = str(value).lower()
    if v == "healthy":
        return HealthState.HEALTHY
    if v == "degraded":
        return HealthState.DEGRADED
    if v in ("unhealthy", "failed", "error"):
        return HealthState.UNHEALTHY
    return HealthState.UNKNOWN


def _aggregate(states: list[HealthState]) -> HealthState:
    if not states:
        return HealthState.UNKNOWN
    order = [HealthState.UNHEALTHY, HealthState.DEGRADED, HealthState.UNKNOWN, HealthState.HEALTHY]
    for s in order:
        if s in states:
            return s
    return HealthState.UNKNOWN


class HealthAggregator:
    """Collects component health and produces aggregated reports."""

    def __init__(self, default_timeout_seconds: float = 5.0) -> None:
        self._checks: dict[str, HealthCheck] = {}
        self._providers: dict[str, HealthProvider] = {}
        self._default_timeout = default_timeout_seconds

    # -------- Registration --------

    def register_check(
        self,
        component: str,
        fn: Callable[[], Awaitable[dict[str, Any]]],
        *,
        timeout_seconds: float | None = None,
        dependencies: tuple[str, ...] = (),
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._checks[component] = HealthCheck(
            component=component,
            check_fn=fn,
            timeout_seconds=timeout_seconds or self._default_timeout,
            dependencies=dependencies,
            metadata=metadata or {},
        )

    def register_provider(self, component: str, provider: HealthProvider) -> None:
        self._providers[component] = provider
        self.register_check(component, provider.health)

    def unregister(self, component: str) -> bool:
        existed = component in self._checks
        self._checks.pop(component, None)
        self._providers.pop(component, None)
        return existed

    # -------- Execution --------

    async def run_check(self, check: HealthCheck) -> ComponentHealth:
        t0 = time.perf_counter()
        try:
            async with asyncio.timeout(check.timeout_seconds):  # type: ignore[attr-defined]
                result = await check.check_fn()
            state = _state_from_result(result)
            details = result if isinstance(result, dict) else {"result": str(result)}
            return ComponentHealth(
                component=check.component,
                state=state,
                details=details,
                latency_ms=int((time.perf_counter() - t0) * 1000),
                checked_at=time.time(),
            )
        except TimeoutError as exc:
            return ComponentHealth(
                component=check.component,
                state=HealthState.UNHEALTHY,
                details={"timeout_seconds": check.timeout_seconds},
                latency_ms=int((time.perf_counter() - t0) * 1000),
                error=type(AegisTimeoutError).__name__ + ": " + str(exc),
                checked_at=time.time(),
            )
        except Exception as exc:
            return ComponentHealth(
                component=check.component,
                state=HealthState.UNHEALTHY,
                details={},
                latency_ms=int((time.perf_counter() - t0) * 1000),
                error=f"{type(exc).__name__}: {exc!s}",
                checked_at=time.time(),
            )

    async def check_all(self, aggregate_timeout: float | None = None) -> HealthReport:
        t0 = time.perf_counter()
        components_by_id: dict[str, ComponentHealth] = {}
        tasks = [self.run_check(c) for c in self._checks.values()]
        if tasks:
            if aggregate_timeout is not None:
                try:
                    async with asyncio.timeout(aggregate_timeout):  # type: ignore[attr-defined]
                        results = await asyncio.gather(*tasks)
                except TimeoutError:
                    results = []
            else:
                results = await asyncio.gather(*tasks)
        else:
            results = []
        for r in results:
            components_by_id[r.component] = r
        components_list = list(components_by_id.values())
        return HealthReport(
            report_id=uuid.uuid4(),
            generated_at=time.time(),
            overall=_aggregate([c.state for c in components_list]),
            components=components_list,
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )

    def snapshot(self) -> HealthReport:
        """Produce a report from the most-recently seen state without running checks.
        If no checks have been run yet, returns UNKNOWN overall."""
        return HealthReport(
            report_id=uuid.uuid4(),
            generated_at=time.time(),
            overall=(
                HealthState.UNHEALTHY
                if any(c.error is not None for c in vars(self).get("_last", {}).values())
                else HealthState.UNKNOWN
            ),
            components={},
            duration_ms=0,
        )
