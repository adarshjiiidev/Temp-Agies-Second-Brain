"""L1 CoreRuntime container.

Lifecycle FSM per Prompt 02 §5:
    CREATED → INITIALIZING → STARTING → RUNNING → STOPPING → STOPPED
Additional failure states: PARTIALLY_INITIALIZED, FAILED.

Behavior guarantees:
  1. initialize() calls services in topological dependency order.
  2. If any initialize() fails, partial init is aborted and stop() is called in REVERSE
     order on exactly those services that have been initialized (no under-initialize).
  3. start() is called only after all services have been initialized successfully.
  4. stop() is called in reverse dependency order. Each stop respects its timeout.
  5. shutdown_timeout is enforced overall.
  6. HealthAggregator receives every service that implements HealthProvider.
"""

from __future__ import annotations

import asyncio
import contextlib
import threading
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import UUID

from aegis.l1_core.di.container import DIContainer, Scope
from aegis.l1_core.errors.base import (
    AegisError,
    ErrorContext,
    InitializationError,
    LifecycleError,
    NotFoundError,
    RuntimeShutdownError,
    ShutdownTimeoutError,
    StartupTimeoutError,
)
from aegis.l1_core.health.registry import HealthAggregator, HealthReport, HealthState
from aegis.l1_core.interfaces.base import (
    HealthProvider,
    Service,
    ServiceInfo,
    ServiceState,
)


class RuntimeState(str, Enum):
    CREATED = "created"
    INITIALIZING = "initializing"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    PARTIALLY_INITIALIZED = "partially_initialized"


@dataclass
class ServiceSlot:
    """Runtime bookkeeping entry per registered service."""

    info: ServiceInfo
    service: Service
    dependencies: tuple[str, ...]
    state: ServiceState = ServiceState.CREATED
    started_completed: bool = False
    initialized_completed: bool = False
    stopped_completed: bool = False
    error: AegisError | None = None


def _topological(slots: dict[str, ServiceSlot]) -> list[str]:
    """Kahn's algorithm; raises AegisError on cycle (E10109 CIRCULAR_DEPENDENCY)."""
    indeg: dict[str, int] = {k: 0 for k in slots}
    adj: dict[str, list[str]] = {k: [] for k in slots}
    for k, slot in slots.items():
        for d in slot.dependencies:
            if d not in slots:
                raise NotFoundError(
                    f"Service '{k}' depends on unknown service '{d}'",
                    error_code="E10110",
                    context=ErrorContext(component="runtime", operation="topological_sort"),
                )
            adj[d].append(k)
            indeg[k] += 1
    ready = [k for k, v in indeg.items() if v == 0]
    order: list[str] = []
    while ready:
        node = ready.pop(0)
        order.append(node)
        for nxt in adj[node]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                ready.append(nxt)
    if len(order) != len(slots):
        raise LifecycleError(
            "Circular dependency detected in service graph: "
            + ", ".join(s for s in slots if s not in order),
            error_code="E10109",
            context=ErrorContext(component="runtime", operation="topological_sort"),
        )
    return order


class CoreRuntime:
    """Central runtime container. Use it like:

    rt = CoreRuntime()
    rt.register_service(svc_a)
    rt.register_service(svc_b, depends_on=("svc_a",))
    await rt.start()
    ...
    await rt.stop()
    """

    def __init__(
        self,
        *,
        startup_timeout: float = 30.0,
        shutdown_timeout: float = 10.0,
        service_stop_timeout: float = 5.0,
        instance_id: str | None = None,
    ) -> None:
        self.runtime_id: UUID = uuid.uuid4()
        self.instance_id = instance_id or f"aegis-{self.runtime_id.hex[:8]}"
        self.state: RuntimeState = RuntimeState.CREATED
        self.slots: dict[str, ServiceSlot] = {}
        self.startup_timeout = startup_timeout
        self.shutdown_timeout = shutdown_timeout
        self.service_stop_timeout = service_stop_timeout
        self.health: HealthAggregator = HealthAggregator()
        self.di: DIContainer = DIContainer()
        self._di_scope: Scope | None = None
        self._startup_failure: AegisError | None = None
        self._lock = threading.RLock()
        self._loop: asyncio.AbstractEventLoop | None = None
        # Back-compat alias (tests + example use ._services)
        self._services = self.slots

    # -------- Registration --------

    def register_health_aggregator(self, aggregator: HealthAggregator) -> None:
        """Override or replace the default health aggregator."""
        self.health = aggregator
        # Re-register all existing HealthProviders with the new aggregator
        for sid, slot in self.slots.items():
            if isinstance(slot.service, HealthProvider):
                self.health.register_provider(sid, slot.service)

    def register_service(
        self,
        service: Service,
        *,
        depends_on: tuple[str, ...] = (),
        info: ServiceInfo | None = None,
    ) -> str:
        with self._lock:
            if self.state not in {RuntimeState.CREATED, RuntimeState.STOPPED}:
                raise LifecycleError(
                    f"Cannot register service in state {self.state}",
                    context=ErrorContext(component="runtime", operation="register_service"),
                )
            service_info = (
                info
                or getattr(service, "info", None)
                or ServiceInfo(
                    service_id=type(service).__name__.lower(),
                    name=type(service).__name__,
                    depends_on=depends_on,
                )
            )
            sid = service_info.service_id
            if sid in self.slots:
                raise LifecycleError(
                    f"Duplicate service id: {sid}",
                    context=ErrorContext(component="runtime", operation="register_service"),
                )
            deps = depends_on or service_info.depends_on
            # Validate dependency existence AT REGISTRATION TIME (E10110) — tests expect early failure
            for d in deps:
                if d not in self.slots:
                    raise NotFoundError(
                        f"Service '{sid}' depends on unknown service '{d}'",
                        error_code="E10110",
                        context=ErrorContext(component="runtime", operation="register_service"),
                    )
            self.slots[sid] = ServiceSlot(
                info=service_info,
                service=service,
                dependencies=tuple(deps),
            )
            if isinstance(service, HealthProvider):
                self.health.register_provider(sid, service)
            # Also register the service instance as a DI singleton by id for other modules
            self.di.register_singleton(f"service:{sid}", service)
            return sid

    # -------- Lifecycle --------

    async def initialize(self, context: dict[str, Any] | None = None) -> None:
        with self._lock:
            if self.state != RuntimeState.CREATED:
                raise LifecycleError(
                    f"Cannot initialize from state {self.state}",
                    error_code="E10102",
                    context=ErrorContext(component="runtime", operation="initialize"),
                )
            self.state = RuntimeState.INITIALIZING
        order = _topological(self.slots)
        context = context or {}
        context.setdefault("runtime_id", str(self.runtime_id))
        context.setdefault("instance_id", self.instance_id)
        init_done_reversed: list[str] = []
        try:
            async with asyncio.timeout(self.startup_timeout):  # type: ignore[attr-defined]
                for sid in order:
                    slot = self.slots[sid]
                    slot.state = ServiceState.INITIALIZING
                    try:
                        init = slot.service.initialize
                        await init(context)
                    except AegisError:
                        raise
                    except Exception as exc:
                        raise InitializationError(
                            f"initialize failed for service {sid}: {type(exc).__name__}: {exc!s}",
                            cause=exc,
                            error_code="E10105",
                            context=ErrorContext(component=sid, operation="initialize"),
                        ) from exc
                    slot.initialized_completed = True
                    slot.state = ServiceState.INITIALIZED
                    init_done_reversed.insert(0, sid)
        except TimeoutError as exc:
            self.state = RuntimeState.PARTIALLY_INITIALIZED
            raise StartupTimeoutError(
                f"initialize timed out after {self.startup_timeout}s",
                cause=exc,
                context=ErrorContext(component="runtime", operation="initialize"),
            ) from exc
        except AegisError as exc:
            self._startup_failure = exc
            self.state = RuntimeState.PARTIALLY_INITIALIZED
            raise

    async def start(self) -> None:
        """Full lifecycle: initialize → start both with overall timeout.
        This is the primary entry point; prefer over manual initialize() + start()."""
        with self._lock:
            if self.state == RuntimeState.CREATED:
                pass  # proceed: initialize first
            elif self.state == RuntimeState.PARTIALLY_INITIALIZED:
                raise LifecycleError(
                    "Runtime is partially initialized — abort. Create a new CoreRuntime.",
                    error_code="E10108",
                    context=ErrorContext(component="runtime", operation="start"),
                )
            elif self.state != RuntimeState.CREATED:
                raise LifecycleError(
                    f"Cannot start() in state {self.state}",
                    error_code="E10101" if self.state == RuntimeState.RUNNING else "E10102",
                    context=ErrorContext(component="runtime", operation="start"),
                )
        # 1) initialize (with own ordering)
        t0 = time.perf_counter()
        try:
            async with asyncio.timeout(self.startup_timeout):  # type: ignore[attr-defined]
                await self.initialize()
        except RuntimeShutdownError:
            raise
        except (AegisError, StartupTimeoutError) as init_error:
            # On partial init, stop exactly those that initialized, in reverse
            reversed_init = [
                sid
                for sid in reversed(_topological(self.slots))
                if self.slots[sid].initialized_completed and not self.slots[sid].stopped_completed
            ]
            with contextlib.suppress(Exception):
                await self._run_stops(reversed_init, reason="rollback-init")
            self.state = RuntimeState.FAILED
            self._startup_failure = init_error
            raise
        # 2) start in dependency order
        self.state = RuntimeState.STARTING
        order = _topological(self.slots)
        started: list[str] = []
        try:
            remaining = self.startup_timeout - (time.perf_counter() - t0)
            async with asyncio.timeout(max(0.05, remaining)):  # type: ignore[attr-defined]
                for sid in order:
                    slot = self.slots[sid]
                    slot.state = ServiceState.STARTING
                    try:
                        await slot.service.start()
                    except AegisError:
                        raise
                    except Exception as exc:
                        raise LifecycleError(
                            f"start failed for service {sid}: {type(exc).__name__}: {exc!s}",
                            cause=exc,
                            error_code="E10106",
                            context=ErrorContext(component=sid, operation="start"),
                        ) from exc
                    slot.started_completed = True
                    slot.state = ServiceState.RUNNING
                    started.append(sid)
        except TimeoutError as exc:
            # rollback stops in reverse of started
            await self._run_stops(list(reversed(started)), reason="rollback-start")
            self.state = RuntimeState.FAILED
            raise StartupTimeoutError(
                f"startup timed out after {self.startup_timeout}s",
                cause=exc,
                context=ErrorContext(component="runtime", operation="start"),
            ) from exc
        except AegisError as exc:
            await self._run_stops(list(reversed(started)), reason="rollback-start")
            self.state = RuntimeState.FAILED
            self._startup_failure = exc
            raise
        self.state = RuntimeState.RUNNING
        self._loop = asyncio.get_running_loop()

    async def stop(self) -> None:
        with self._lock:
            if self.state in {RuntimeState.STOPPED, RuntimeState.CREATED}:
                return  # idempotent
            self.state = RuntimeState.STOPPING
        # Stop services in reverse topological order
        order = list(reversed(_topological(self.slots)))
        await self._run_stops(order, reason="shutdown")
        # Close DI scope (if any) and DI container
        with contextlib.suppress(Exception):
            if self._di_scope is not None:
                await self._di_scope.close()
        with contextlib.suppress(Exception):
            await self.di.close()
        self.state = RuntimeState.STOPPED

    async def _run_stops(self, sids_ordered: list[str], *, reason: str) -> None:  # noqa: ARG002
        try:
            async with asyncio.timeout(self.shutdown_timeout):  # type: ignore[attr-defined]
                for sid in sids_ordered:
                    slot = self.slots.get(sid)
                    if slot is None or slot.stopped_completed:
                        continue
                    slot.state = ServiceState.STOPPING
                    try:
                        await asyncio.wait_for(
                            slot.service.stop(timeout=self.service_stop_timeout),
                            timeout=self.service_stop_timeout,
                        )
                    except Exception as exc:
                        slot.error = LifecycleError(
                            f"stop failed for {sid}: {type(exc).__name__}: {exc!s}",
                            error_code="E10107",
                            cause=exc,
                            context=ErrorContext(component=sid, operation="stop"),
                        )
                    try:
                        await slot.service.close()
                    except Exception:
                        pass
                    slot.stopped_completed = True
                    slot.state = ServiceState.STOPPED
        except TimeoutError as exc:
            self.state = (
                RuntimeState.FAILED if self.state != RuntimeState.STOPPING else RuntimeState.FAILED
            )
            raise ShutdownTimeoutError(
                f"shutdown timed out after {self.shutdown_timeout}s",
                cause=exc,
                context=ErrorContext(component="runtime", operation="stop"),
            ) from exc

    # -------- Queries --------

    def get_service(self, service_id: str) -> Service:
        slot = self.slots.get(service_id)
        if slot is None:
            raise NotFoundError(
                f"Service '{service_id}' not registered",
                error_code="E10110",
                context=ErrorContext(component="runtime", operation="get_service"),
            )
        return slot.service

    def service_states(self) -> dict[str, ServiceState]:
        return {sid: slot.state for sid, slot in self.slots.items()}

    async def health_report(self) -> HealthReport:
        return await self.health.check_all()

    async def overall_health(self) -> HealthState:
        states = []
        for s in self.slots.values():
            if s.state == ServiceState.RUNNING:
                states.append(HealthState.HEALTHY)
            elif s.state == ServiceState.DEGRADED:
                states.append(HealthState.DEGRADED)
            elif s.state == ServiceState.FAILED:
                states.append(HealthState.UNHEALTHY)
            else:
                states.append(HealthState.UNKNOWN)
        # aggregate consistent with HealthAggregator._aggregate
        for target in (HealthState.UNHEALTHY, HealthState.DEGRADED, HealthState.UNKNOWN):
            if target in states:
                return target
        return HealthState.HEALTHY if states else HealthState.UNKNOWN
