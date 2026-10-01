"""L2 Event Bus — typed pub/sub with optional SQLite append-log durable topics + DLQ.
In-process by design per Prompt 01 §03 tech stack choice (in-process + SQLite durable)."""

from aegis.l2_foundation.event_bus.core import (
    CRITICAL,
    DEFAULT_TOPIC,
    HIGH,
    LOW,
    NORMAL,
    CoreEventBus,
    EventEnvelope,
    Priority,
    Subscriber,
    Topic,
)

__all__ = [
    "CRITICAL",
    "DEFAULT_TOPIC",
    "HIGH",
    "LOW",
    "NORMAL",
    "CoreEventBus",
    "EventEnvelope",
    "Priority",
    "Subscriber",
    "Topic",
]
