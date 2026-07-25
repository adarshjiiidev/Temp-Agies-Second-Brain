"""L1 Events interface — forward-declared Protocol.
Concrete EventBus implementation in l2_foundation.event_bus.bus.
Every module-to-module notification goes through this interface; never direct method calls."""
from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Awaitable, Protocol, runtime_checkable
from uuid import UUID


class Priority(IntEnum):
    LOW = 0
    NORMAL = 50
    HIGH = 80
    CRITICAL = 100


# Convenience constants (Prompt 02 uses these names in public exports)
LOW = Priority.LOW
NORMAL = Priority.NORMAL
HIGH = Priority.HIGH
CRITICAL = Priority.CRITICAL


@dataclass(frozen=True)
class Topic:
    """Typed topic identifier. Free-form string topic names are NOT allowed — use Topic objects."""

    name: str
    version: int = 1
    durable: bool = True
    description: str = ""

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.name}/v{self.version}"


@dataclass
class EventEnvelope:
    """Typed event envelope per Prompt 02 §10. Immutable-ish (only metadata dict is mutable)."""

    event_id: UUID
    event_type: str
    timestamp: float  # POSIX seconds, UTC monotonic-preferred
    source: str
    correlation_id: UUID
    payload: dict[str, Any]
    schema_version: int = 1
    priority: Priority = Priority.NORMAL
    request_id: UUID | None = None
    task_id: UUID | None = None
    parent_op_id: UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# Handler is a sync or async function. EventBus dispatches appropriately.
EventHandler = Any  # Callable[[EventEnvelope], Awaitable[None] | None]


@runtime_checkable
class Subscriber(Protocol):
    """Structured subscriber interface for advanced handlers that need lifecycle hooks."""

    @abstractmethod
    async def handle_event(self, event: EventEnvelope) -> None: ...  # pragma: no cover


@runtime_checkable
class EventBus(Protocol):
    """Prompt 02 EventBus contract.
    publish, subscribe, async handlers, handler ordering, event history/replay, dead-letter,
    error handling, metrics, event filtering — the L2 impl satisfies all of these."""

    @abstractmethod
    async def publish(self, event: EventEnvelope, topic: Topic | None = None) -> None: ...

    @abstractmethod
    def subscribe(
        self,
        topic: Topic,
        handler: EventHandler,
        *,
        priority: Priority = Priority.NORMAL,
        filter_fn: Any | None = None,
    ) -> str:
        """Register a handler; returns subscription_id for unsubscribe()."""

    @abstractmethod
    def unsubscribe(self, subscription_id: str) -> bool: ...

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self, timeout: float | None = None) -> None: ...

    @abstractmethod
    async def replay(self, topic: Topic, since: float | None = None) -> list[EventEnvelope]:
        """Return persisted events in order; empty list if not durable."""

    @abstractmethod
    def dead_letter_count(self, topic: Topic | None = None) -> int:
        """Return DLQ size, optionally filtered to one topic."""
