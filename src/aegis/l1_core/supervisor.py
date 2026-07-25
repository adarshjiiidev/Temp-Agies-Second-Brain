"""L1 Supervisor.
Per-service watchdog, crash detection, restart policy with backoff, max attempts, recovery state tracking.
Prompt 02 provides primitives only; actual self-repair using LLM-assisted root-cause ships in Prompt 08/21."""
from __future__ import annotations

import asyncio
import math
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Awaitable, Callable

from aegis.l1_core.errors.base import ErrorContext, RecoveryError
from aegis.l1_core.interfaces.base import Service, ServiceState


class RestartPolicyKind(str, Enum):
    NEVER = "never"
    ON_FAILURE = "on_failure"
    ALWAYS = "always"


@dataclass
class RestartPolicy:
    kind: RestartPolicyKind = RestartPolicyKind.ON_FAILURE
    max_attempts: int = 5
    base_backoff_seconds: float = 0.25
    max_backoff_seconds: float = 10.0
    backoff_multiplier: float = 2.0
    jitter_fraction: float = 0.1
    reset_after_seconds: float = 60.0


@dataclass
class RecoveryState:
    """Tracks failure count, restart history, and next-allowed retry time per service."""
    service_id: str
    consecutive_failures: int = 0
    total_restarts: int = 0
    last_failure_at: float | None = None
    last_restart_at: float | None = None
    next_retry_at: float | None = None
    consecutive_successes: int = 0
    history: list[dict] = field(default_factory=list)


def backoff_seconds(policy: RestartPolicy, attempt: int) -> float:
    """Exponential backoff with jitter; deterministic given attempt but jittered by random fraction."""
    exp = min(attempt, 20)  # cap to avoid huge numbers
    raw = policy.base_backoff_seconds * (policy.backoff_multiplier ** exp)
    raw = min(raw, policy.max_backoff_seconds)
    jitter_range = raw * policy.jitter_fraction
    # Full jitter variant
    return raw + random.uniform(-jitter_range, jitter_range)  # noqa: S311 - non-crypto jitter


class Supervisor:
    """Watchdog + restarter for managed services.

    Typical use with CoreRuntime:
        sv = Supervisor(restart_policy=RestartPolicy(max_attempts=3))
        sv.register(rt.get_service("foo"), service_id="foo", get_state_fn=lambda: foo._state)
        await sv.start()  # starts watchdog loop (run in background task)
        ...
        await sv.stop()

    Prompt 02 scope: generic recovery primitives only. Self-repair/auto-harness using AI
    is Prompt 08/21 and explicitly NOT implemented here.
    """

    def __init__(
        self,
        *,
        restart_policy: RestartPolicy | None = None,
        watchdog_interval_seconds: float = 0.5,
        on_recovery_hook: Callable[[str, RecoveryState], Awaitable[None] | None] | None = None,
        on_failure_give_up: Callable[[str, RecoveryState], Awaitable[None] | None] | None = None,
    ) -> None:
        self.default_policy = restart_policy or RestartPolicy()
        self.watchdog_interval = watchdog_interval_seconds
        self._services: dict[str, dict] = {}
        self._recovery: dict[str, RecoveryState] = {}
        self._policies: dict[str, RestartPolicy] = {}
        self._watchdog_task: asyncio.Task[None] | None = None
        self._running = False
        self._on_recovery_hook = on_recovery_hook
        self._on_give_up = on_failure_give_up

    # -------- registration --------

    def register(
        self,
        service: Service,
        *,
        service_id: str,
        restart_policy: RestartPolicy | None = None,
        get_state_fn: Callable[[], ServiceState] | None = None,
        restart_fn: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self._services[service_id] = {
            "service": service,
            "get_state_fn": get_state_fn or (lambda: service._state if hasattr(service, "_state") else ServiceState.RUNNING),
            "restart_fn": restart_fn,
        }
        self._recovery[service_id] = RecoveryState(service_id=service_id)
        self._policies[service_id] = restart_policy or self.default_policy

    # -------- lifecycle --------

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._watchdog_task = asyncio.create_task(self._watchdog_loop(), name="aegis-supervisor")

    async def stop(self) -> None:
        self._running = False
        if self._watchdog_task is not None and not self._watchdog_task.done():
            self._watchdog_task.cancel()
            try:
                await asyncio.wait_for(self._watchdog_task, timeout=1.0)
            except (TimeoutError, asyncio.TimeoutError, asyncio.CancelledError):
                pass
            self._watchdog_task = None

    # -------- watchdog --------

    async def _watchdog_loop(self) -> None:
        while self._running:
            await asyncio.sleep(self.watchdog_interval)
            try:
                await self._tick()
            except Exception:  # noqa: BLE001 - watchdog never dies
                pass

    async def _tick(self) -> None:
        for sid, entry in list(self._services.items()):
            get_state = entry["get_state_fn"]
            try:
                state = get_state()
            except Exception:  # noqa: BLE001
                state = ServiceState.FAILED
            policy = self._policies[sid]
            rec = self._recovery[sid]
            # Reset consecutive failures after a sufficiently long healthy run
            if state == ServiceState.RUNNING and rec.last_failure_at is not None:
                if (time.time() - rec.last_failure_at) > policy.reset_after_seconds:
                    rec.consecutive_failures = 0
                rec.consecutive_successes += 1
                continue
            # Nothing to do if not failed
            if state not in (ServiceState.FAILED, ServiceState.DEGRADED):
                continue
            # Decide whether to restart
            if policy.kind == RestartPolicyKind.NEVER:
                continue
            now = time.time()
            if rec.next_retry_at is not None and now < rec.next_retry_at:
                continue
            if rec.consecutive_failures >= policy.max_attempts:
                if self._on_give_up is not None:
                    try:
                        await self._maybe_await(self._on_give_up(sid, rec))
                    except Exception:  # noqa: BLE001
                        pass
                continue
            # Attempt restart
            rec.consecutive_failures += 1
            attempt = rec.consecutive_failures
            rec.last_failure_at = now
            try:
                restart_fn = entry["restart_fn"] or self._default_restart(sid, entry)
                await restart_fn()
                rec.last_restart_at = time.time()
                rec.total_restarts += 1
                rec.next_retry_at = rec.last_restart_at + backoff_seconds(policy, attempt)
                rec.history.append({
                    "t": now, "attempt": attempt, "outcome": "scheduled_restart",
                    "next_at": rec.next_retry_at,
                })
                if self._on_recovery_hook is not None:
                    try:
                        await self._maybe_await(self._on_recovery_hook(sid, rec))
                    except Exception:  # noqa: BLE001
                        pass
            except Exception as exc:  # noqa: BLE001
                rec.next_retry_at = time.time() + backoff_seconds(policy, attempt)
                rec.history.append({"t": now, "attempt": attempt, "outcome": "restart_error", "error": str(exc)})
                if rec.consecutive_failures >= policy.max_attempts and self._on_give_up is not None:
                    try:
                        await self._maybe_await(self._on_give_up(sid, rec))
                    except Exception:  # noqa: BLE001
                        pass

    def _default_restart(self, sid: str, entry: dict) -> Callable[[], Awaitable[None]]:
        async def _do() -> None:
            svc = entry["service"]
            try:
                with contextlib.suppress(Exception):
                    await svc.stop(timeout=2.0)
            except Exception:  # noqa: BLE001
                pass
            await svc.initialize({})
            await svc.start()
        import contextlib
        return _do

    @staticmethod
    async def _maybe_await(result: Awaitable[None] | None) -> None:
        if hasattr(result, "__await__"):
            await result  # type: ignore[misc]

    # -------- Queries --------

    def recovery_state(self, service_id: str) -> RecoveryState:
        return self._recovery[service_id]

    async def force_recover(self, service_id: str, *, max_attempts_override: int | None = None) -> None:
        """Manual recovery trigger. Resets consecutive failure counter up to the override; then attempts restart once."""
        if service_id not in self._services:
            raise KeyError(service_id)
        rec = self._recovery[service_id]
        policy = self._policies[service_id]
        if max_attempts_override is not None:
            # Temporarily allow retries: just reset counter
            rec.consecutive_failures = max(0, rec.consecutive_failures - max_attempts_override)
        rec.next_retry_at = time.time()
        rec.last_failure_at = time.time()
        entry = self._services[service_id]
        try:
            restart_fn = entry["restart_fn"] or self._default_restart(service_id, entry)
            await restart_fn()
            rec.consecutive_failures = 0
            rec.total_restarts += 1
        except Exception as exc:  # noqa: BLE001
            raise RecoveryError(
                f"Manual recovery failed for {service_id}: {type(exc).__name__}: {exc!s}",
                cause=exc,
                error_code="E10111",
                context=ErrorContext(component="supervisor", operation="force_recover"),
            ) from exc
