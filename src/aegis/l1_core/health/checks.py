"""L1 Standard health check helpers."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from typing import Any


async def health_check_timeout(
    fn: Callable[[], Awaitable[dict[str, Any]]],
    timeout_seconds: float,
    *,
    default_details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Wrap an async health check with timeout. Returns standard dict status format."""
    try:
        async with asyncio.timeout(timeout_seconds):  # type: ignore[attr-defined]
            result = await fn()
    except TimeoutError:
        return {
            "status": "unhealthy",
            "details": {"timeout_seconds": timeout_seconds, **(default_details or {})},
            "error": "timeout",
        }
    except Exception as exc:
        return {
            "status": "unhealthy",
            "details": default_details or {},
            "error": f"{type(exc).__name__}: {exc!s}",
        }
    return result


def health_check_threshold(
    statuses: Iterable[dict[str, Any]],
    *,
    max_unhealthy: int = 0,
    max_degraded: int = -1,
) -> dict[str, Any]:
    """Aggregate N component statuses with an explicit threshold rule.
    max_degraded=-1 means unlimited. Returns overall status dict."""
    from aegis.l1_core.health.registry import _aggregate, _state_from_result

    states = [_state_from_result(s) for s in statuses]
    unhealthy = sum(1 for s in states if s.value == "unhealthy")
    degraded = sum(1 for s in states if s.value == "degraded")
    if unhealthy > max_unhealthy or (max_degraded != -1 and degraded > max_degraded):
        return {"status": "unhealthy", "details": {"unhealthy": unhealthy, "degraded": degraded}}
    overall = _aggregate(states)
    return {"status": overall.value, "details": {"unhealthy": unhealthy, "degraded": degraded}}
