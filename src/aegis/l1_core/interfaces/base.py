"""L1 Base interfaces — Service lifecycle, Health, Pluggable.
Everything in AEGIS that participates in the runtime lifecycle implements ModuleLifecycle.
Naming conventions per Prompt 01 §02: initialize / start / stop / health / close."""
from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Protocol, runtime_checkable


class ServiceState(str, Enum):
    """A single service's lifecycle states (CoreRuntime uses the superset RuntimeState)."""

    CREATED = "created"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    DEGRADED = "degraded"


@dataclass(frozen=True)
class ServiceInfo:
    """Runtime metadata about a registered service — stable, serializable, never secrets."""

    service_id: str
    name: str
    version: str = "0.1.0"
    depends_on: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    description: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class ModuleLifecycle(Protocol):
    """Prompt 02 core contract for every Service.
    Implementors MUST NOT perform any side effect in __init__ beyond pure-python setup.
    All I/O, connection establishment, file writes happen in initialize/start only."""

    @abstractmethod
    async def initialize(self, context: dict[str, Any] | None = None) -> None:
        """Load configuration, create internal structures, do not start any threads/tasks/IO yet.
        Called exactly once per lifecycle in dependency order.
        Raises InitializationError if cannot proceed (the runtime then aborts the startup)."""

    @abstractmethod
    async def start(self) -> None:
        """Start accepting work: open sockets, spawn workers, connect to DBs, begin timers.
        Called after all services in the dependency DAG have been initialize()d successfully.
        Raises LifecycleError on failure; runtime will attempt orderly shutdown of started services."""

    @abstractmethod
    async def stop(self, timeout: float | None = None) -> None:
        """Stop accepting work, drain in-flight, release resources.
        Called in REVERSE dependency order on shutdown or startup abort.
        Implementations should respect `timeout` and be idempotent (callable multiple times).
        Never swallow critical failures silently; log and wrap into LifecycleError if applicable."""

    @abstractmethod
    async def close(self) -> None:
        """Hard teardown. Called after stop() completes; release OS handles, close files.
        After close, the service instance is NOT reusable."""


@runtime_checkable
class HealthProvider(Protocol):
    """Anything that can be health-checked exposes this Protocol."""

    @abstractmethod
    async def health(self, timeout: float | None = None) -> dict[str, Any]:
        """Return a typed health result dict with at minimum:
        {"status": HealthState.value, "component": str, "details": {...}}
        Must return within `timeout` seconds or caller treats as UNHEALTHY/timeout."""


@runtime_checkable
class Pluggable(Protocol):
    """Contract for plugin-style components loaded by the L2 PluginLoader.
    Prompt 02: manifest is sufficient; in later prompts this expands to include hooks."""

    @property  # type: ignore[override,unused-ignore]
    @abstractmethod
    def info(self) -> ServiceInfo: ...


class Service(ModuleLifecycle, HealthProvider, Pluggable, Protocol):
    """Combined Protocol: a runtime-managed Service = lifecycle + health + identity.
    Convenience: default implementations (AbstractService) are provided below for
    cases where full Protocol conformance by structural typing isn't required."""


class AbstractService:
    """Optional base class for services (not required — Protocol-based typing is preferred).
    Provides sane no-op defaults so tiny services need only override methods they care about."""

    _state: ServiceState = ServiceState.CREATED

    @property
    def info(self) -> ServiceInfo:
        return ServiceInfo(
            service_id=self.__class__.__name__.lower(),
            name=self.__class__.__name__,
        )

    async def initialize(self, context: dict[str, Any] | None = None) -> None:
        self._state = ServiceState.INITIALIZING
        self._state = ServiceState.INITIALIZED

    async def start(self) -> None:
        self._state = ServiceState.STARTING
        self._state = ServiceState.RUNNING

    async def stop(self, timeout: float | None = None) -> None:  # noqa: ARG002 - default impl
        if self._state in {ServiceState.STOPPED, ServiceState.FAILED}:
            return
        self._state = ServiceState.STOPPING
        self._state = ServiceState.STOPPED

    async def close(self) -> None:  # pragma: no cover - trivial
        return None

    async def health(self, timeout: float | None = None) -> dict[str, Any]:  # noqa: ARG002
        return {
            "status": (
                "healthy" if self._state == ServiceState.RUNNING else
                "degraded" if self._state == ServiceState.DEGRADED else
                "unhealthy" if self._state == ServiceState.FAILED else "unknown"
            ),
            "component": self.info.service_id,
            "state": self._state.value,
            "details": {},
        }


# Type alias for functions/coroutines passed to the runtime as bare "service hooks"
LifecycleHook = Any  # Awaitable[None] | Callable[[], Awaitable[None]]
