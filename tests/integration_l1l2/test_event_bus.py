"""Prompt 02 tests: Event Bus - publish/subscribe, async handlers, DLQ, replay, SQLite durability."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

import aegis
from aegis import CoreEventBus, EventEnvelope, HIGH, NORMAL, Topic, get_logger

log = get_logger(__name__)


def _make_bus(tmp_path: Path | None = None, *, durable: bool = False) -> CoreEventBus:
    if durable and tmp_path is not None:
        db = tmp_path / "eb.db"
        return CoreEventBus(durable=True, persistence_path=str(db))
    return CoreEventBus(durable=False)


def test_publish_sync_collects_to_handlers():
    bus = _make_bus()
    bus.start()
    seen: list[EventEnvelope] = []
    bus.subscribe(Topic(name="x"), lambda ev: seen.append(ev))
    bus.publish("hello", {"n": 1}, topic=Topic(name="x"))
    assert len(seen) == 1
    assert seen[0].event_type == "hello"
    assert seen[0].payload == {"n": 1}
    bus.stop()


@pytest.mark.anyio
async def test_async_handler_invoked():
    bus = _make_bus()
    bus.start()
    results: list[int] = []

    async def handler(ev: EventEnvelope) -> None:
        results.append(ev.payload["v"])

    bus.subscribe(Topic(name="t"), handler)
    await bus.publish_async("ping", {"v": 7}, topic=Topic(name="t"))
    assert results == [7]
    bus.stop()


def test_handler_failure_moves_to_dlq():
    bus = _make_bus()
    bus.start()

    def always_raise(ev: EventEnvelope) -> None:
        raise RuntimeError("nope")

    bus.subscribe(Topic(name="t"), always_raise)
    bus.publish("boom", {}, topic=Topic(name="t"))
    assert bus.dead_letter_count(Topic(name="t")) >= 1
    bus.stop()


def test_unsubscribe_works():
    bus = _make_bus()
    bus.start()
    seen: list[EventEnvelope] = []
    sub = bus.subscribe(Topic(name="t"), lambda ev: seen.append(ev))
    bus.publish("first", {}, topic=Topic(name="t"))
    assert bus.unsubscribe(Topic(name="t"), sub) is True
    bus.publish("second", {}, topic=Topic(name="t"))
    assert [e.event_type for e in seen] == ["first"]
    bus.stop()


@pytest.mark.anyio
async def test_sqlite_durable_replay(tmp_path: Path):
    bus = _make_bus(tmp_path, durable=True)
    bus.start()
    bus.publish("e1", {"n": 1}, topic=Topic(name="t", durable=True))
    bus.publish("e2", {"n": 2}, topic=Topic(name="t", durable=True))
    replayed = bus.replay(Topic(name="t"))
    assert [e.event_type for e in replayed] == ["e1", "e2"]
    # After since_event_id:
    since = str(replayed[0].event_id)
    tail = bus.replay(Topic(name="t"), since_event_id=since)
    assert [e.event_type for e in tail] == ["e2"]
    bus.stop()


def test_handler_order_low_to_high():
    bus = _make_bus()
    bus.start()
    called: list[str] = []
    bus.subscribe(Topic(name="t"), lambda ev: called.append("last"), order=100)
    bus.subscribe(Topic(name="t"), lambda ev: called.append("first"), order=0)
    bus.subscribe(Topic(name="t"), lambda ev: called.append("mid"), order=50)
    bus.publish("ping", {}, topic=Topic(name="t"))
    assert called == ["first", "mid", "last"]
    bus.stop()
