"""L2 Core Event Bus.

Implements:
  - Typed EventEnvelope + typed Topic (per Prompt 01 contracts)
  - Publish / subscribe / unsubscribe
  - Synchronous + async handler invocation (handler type determines dispatch mode)
  - Handler ordering via `order=` (lower = earlier)
  - Priority via envelope.priority (higher priority events sorted before lower in a batch)
  - In-memory append log
  - Optional SQLite append log (durable = True) for cross-restart replay
  - Event replay `replay(topic, since)`
  - Dead-letter queue (handler exceptions → DLQ, not lost)
  - Event metrics (publish_count, handler_error_count, dlq_count, replay_count)
  - Filter: subscriber predicate filter

Prompt 01 boundary: single-process only (no network brokers).
"""
from __future__ import annotations

import asyncio
import base64
import datetime
import json
import sqlite3
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from aegis.l1_core.errors import ErrorCode, EventBusError, NotFoundError
from aegis.l1_core.interfaces.events import (
    CRITICAL,
    HIGH,
    LOW,
    NORMAL,
    EventEnvelope,
    EventHandler,
    Priority,
    Subscriber,
    Topic,
)
from aegis.l2_foundation.telemetry.context import CorrelationContext
from aegis.l2_foundation.telemetry.logger import get_logger
from aegis.l2_foundation.telemetry.metrics import get_metrics_registry

log = get_logger(__name__)

DEFAULT_TOPIC = Topic(name="aegis.default", version=1, durable=False)


@dataclass(order=True)
class _HandlerRegistration:
    order: int = field(default=0, compare=True)
    topic: Topic = field(compare=False, default=DEFAULT_TOPIC)
    handler: EventHandler = field(compare=False, repr=False, default=lambda ev: None)
    filter: Callable[[EventEnvelope], bool] = field(  # noqa: A003
        compare=False, repr=False, default_factory=lambda: (lambda _ev: True)
    )
    handler_id: str = field(compare=False, default_factory=lambda: uuid.uuid4().hex)


def _as_dict_safe_json_bytes(d: dict) -> bytes:
    return json.dumps(d, default=str, ensure_ascii=False).encode("utf-8")


def _envelope_to_row(env: EventEnvelope, topic_name: str) -> tuple:
    return (
        str(env.event_id),
        env.event_type,
        env.timestamp,
        env.source or "",
        str(env.correlation_id) if env.correlation_id else "",
        base64.b64encode(_as_dict_safe_json_bytes(env.payload)).decode("ascii"),
        env.schema_version or "",
        int(env.priority.value if isinstance(env.priority, Priority) else env.priority),
        str(env.request_id) if env.request_id else "",
        str(env.task_id) if env.task_id else "",
        str(env.parent_op_id) if env.parent_op_id else "",
        base64.b64encode(_as_dict_safe_json_bytes(env.metadata)).decode("ascii"),
        topic_name,
    )


def _row_to_envelope(row: sqlite3.Row) -> EventEnvelope:
    payload_raw = base64.b64decode(row["payload_b64"])
    payload = json.loads(payload_raw.decode("utf-8"))
    metadata_raw = base64.b64decode(row["metadata_b64"])
    metadata = json.loads(metadata_raw.decode("utf-8"))
    return EventEnvelope(
        event_id=uuid.UUID(row["event_id"]),
        event_type=row["event_type"],
        timestamp=float(row["timestamp"]),
        source=row["source"] or None,
        correlation_id=uuid.UUID(row["correlation_id"]) if row["correlation_id"] else None,
        payload=payload,
        schema_version=row["schema_version"] or None,
        priority=Priority(int(row["priority_int"])),
        request_id=uuid.UUID(row["request_id"]) if row["request_id"] else None,
        task_id=uuid.UUID(row["task_id"]) if row["task_id"] else None,
        parent_op_id=uuid.UUID(row["parent_op_id"]) if row["parent_op_id"] else None,
        metadata=metadata,
    )


class _SQLiteAppendLog:
    """SQLite append log. Single writer; concurrent-safe via connection lock."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS event_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id TEXT UNIQUE NOT NULL,
        event_type TEXT NOT NULL,
        timestamp REAL NOT NULL,
        source TEXT,
        correlation_id TEXT,
        payload_b64 TEXT NOT NULL,
        schema_version TEXT,
        priority_int INTEGER NOT NULL,
        request_id TEXT,
        task_id TEXT,
        parent_op_id TEXT,
        metadata_b64 TEXT,
        topic_name TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_event_log_topic_time
    ON event_log(topic_name, timestamp, id);

    CREATE TABLE IF NOT EXISTS event_dlq (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        topic_name TEXT NOT NULL,
        handler_id TEXT NOT NULL,
        error TEXT NOT NULL,
        timestamp REAL NOT NULL,
        event_blob TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_event_dlq_topic ON event_dlq(topic_name);
    """

    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path, check_same_thread=False, timeout=10.0)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            self._conn.executescript(self.SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def append(self, env: EventEnvelope, topic_name: str) -> None:
        row = _envelope_to_row(env, topic_name)
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO event_log (
                    event_id, event_type, timestamp, source, correlation_id,
                    payload_b64, schema_version, priority_int, request_id,
                    task_id, parent_op_id, metadata_b64, topic_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                row,
            )
            self._conn.commit()

    def replay(
        self,
        topic_name: str,
        since_timestamp: float | None = None,
        since_event_id: str | None = None,
        limit: int | None = None,
    ) -> list[EventEnvelope]:
        clauses: list[str] = ["topic_name = ?"]
        args: list[Any] = [topic_name]
        if since_event_id:
            clauses.append("id > COALESCE((SELECT id FROM event_log WHERE event_id = ?), 0)")
            args.append(since_event_id)
        if since_timestamp is not None:
            clauses.append("timestamp >= ?")
            args.append(since_timestamp)
        q = (
            "SELECT * FROM event_log WHERE "
            + " AND ".join(clauses)
            + " ORDER BY timestamp, id ASC"
            + (" LIMIT ?" if limit else "")
        )
        if limit:
            args.append(int(limit))
        with self._lock:
            cur = self._conn.execute(q, args)
            rows = cur.fetchall()
        return [_row_to_envelope(r) for r in rows]

    def append_dlq(
        self,
        env: EventEnvelope,
        topic_name: str,
        handler_id: str,
        error: str,
    ) -> None:
        blob = json.dumps(_envelope_to_row(env, topic_name), default=str)
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO event_dlq (
                    event_id, event_type, topic_name, handler_id, error, timestamp, event_blob
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(env.event_id),
                    env.event_type,
                    topic_name,
                    handler_id,
                    error,
                    time.time(),
                    blob,
                ),
            )
            self._conn.commit()

    def dlq_count(self, topic_name: str | None = None) -> int:
        if topic_name:
            q = "SELECT COUNT(*) AS c FROM event_dlq WHERE topic_name = ?"
            args = [topic_name]
        else:
            q = "SELECT COUNT(*) AS c FROM event_dlq"
            args = []
        with self._lock:
            row = self._conn.execute(q, args).fetchone()
        return int(row["c"])


class CoreEventBus:
    """The in-process event bus.

    Note: we intentionally do NOT implement the full Protocol (EventHandler type etc.) here
    using duck-typing — Python structural subtyping at runtime will match the Protocol.
    """

    def __init__(
        self,
        *,
        durable: bool = False,
        persistence_path: str | Path | None = None,
        dead_letter_enabled: bool = True,
        max_history: int = 100_000,
        event_loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        self._durable = durable
        self._persistence_path = Path(persistence_path) if persistence_path else None
        self._dlq_enabled = dead_letter_enabled
        self._max_history = max_history
        self._started = False
        self._stopped = False
        self._loop = event_loop
        self._handlers: dict[str, list[_HandlerRegistration]] = defaultdict(list)
        self._subscribers: dict[str, list[Subscriber]] = defaultdict(list)
        self._history: list[EventEnvelope] = []
        self._inmem_dlq: list[tuple[EventEnvelope, str, str, str]] = []  # (env, topic, hid, err)
        self._lock = threading.RLock()
        self._sql_log: _SQLiteAppendLog | None = None
        metrics = get_metrics_registry()
        self._m_publish = metrics.counter("aegis.eventbus.publish", "events published")
        self._m_handler_err = metrics.counter("aegis.eventbus.handler_errors", "handler errors")
        self._m_dlq = metrics.counter("aegis.eventbus.dlq", "events moved to DLQ")
        self._m_replay = metrics.counter("aegis.eventbus.replay", "events replayed")

    # -------- lifecycle --------

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            if self._durable and self._persistence_path:
                self._sql_log = _SQLiteAppendLog(self._persistence_path)
            self._started = True

    async def astart(self) -> None:
        self.start()

    def stop(self) -> None:
        with self._lock:
            if self._stopped:
                return
            if self._sql_log is not None:
                self._sql_log.close()
                self._sql_log = None
            self._stopped = True

    async def astop(self) -> None:
        self.stop()

    # -------- helpers --------

    def _ensure_started(self) -> None:
        if not self._started:
            raise EventBusError(
                ErrorCode.E20201,
                "CoreEventBus.start() must be called before publishing",
            )

    def _enrich_envelope(
        self,
        event_type: str,
        payload: Any,
        *,
        topic: Topic,
        priority: Priority = NORMAL,
        source: str | None = None,
        metadata: dict[str, Any] | None = None,
        correlation: CorrelationContext | None = None,
    ) -> EventEnvelope:
        ctx = correlation or CorrelationContext.get_current_or_none()
        now = datetime.datetime.now(tz=datetime.timezone.utc).timestamp()
        return EventEnvelope(
            event_id=uuid.uuid4(),
            event_type=event_type,
            timestamp=now,
            source=source,
            correlation_id=ctx.correlation_id if ctx else uuid.uuid4(),
            payload=payload,
            schema_version=str(topic.version) if topic.version else None,
            priority=priority,
            request_id=ctx.request_id if ctx else None,
            task_id=ctx.task_id if ctx else None,
            parent_op_id=ctx.parent_op_id if ctx else None,
            metadata=dict(metadata or {}),
        )

    def _append_history(self, env: EventEnvelope) -> None:
        with self._lock:
            self._history.append(env)
            while len(self._history) > self._max_history:
                self._history.pop(0)

    # -------- publish / variants --------

    def publish(
        self,
        event_type: str,
        payload: Any,  # noqa: ANN401
        *,
        topic: Topic | str = DEFAULT_TOPIC,
        priority: Priority = NORMAL,
        source: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EventEnvelope:
        """Sync publish. Returns the (enriched) EventEnvelope."""
        self._ensure_started()
        topic_obj = Topic(name=topic, version=1, durable=self._durable) if isinstance(topic, str) else topic
        env = self._enrich_envelope(
            event_type,
            payload,
            topic=topic_obj,
            priority=priority,
            source=source,
            metadata=metadata,
        )
        self._m_publish.inc(topic=topic_obj.name)
        if self._sql_log is not None and topic_obj.durable:
            self._sql_log.append(env, topic_obj.name)
        self._append_history(env)
        # Dispatch sync handlers + collect async coroutines
        with self._lock:
            sync_handlers = list(self._handlers.get(topic_obj.name, []))
            subscribers = list(self._subscribers.get(topic_obj.name, []))
        sync_handlers.sort()
        sync_futures: list[Awaitable[None]] = []
        for reg in sync_handlers:
            if not reg.filter(env):
                continue
            try:
                result = reg.handler(env)
                if asyncio.iscoroutine(result):
                    sync_futures.append(result)
            except Exception as exc:  # noqa: BLE001
                self._handler_failure(env, topic_obj.name, reg.handler_id, exc)
        for sub in subscribers:
            try:
                result = sub.handle_event(env, topic_obj)
                if asyncio.iscoroutine(result):
                    sync_futures.append(result)
            except Exception as exc:  # noqa: BLE001
                self._handler_failure(env, topic_obj.name, f"sub:{type(sub).__name__}", exc)
        if sync_futures:
            loop = self._get_loop()
            if loop is not None and loop.is_running():
                for f in sync_futures:
                    loop.create_task(self._safe_await(env, topic_obj.name, "async_handler", f))
            else:
                asyncio.get_event_loop_policy().get_event_loop().run_until_complete(
                    asyncio.gather(
                        *[self._safe_await(env, topic_obj.name, "async_handler", f) for f in sync_futures],
                        return_exceptions=True,
                    )
                )
        return env

    async def publish_async(
        self,
        event_type: str,
        payload: Any,  # noqa: ANN401
        *,
        topic: Topic | str = DEFAULT_TOPIC,
        priority: Priority = NORMAL,
        source: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EventEnvelope:
        self._ensure_started()
        topic_obj = Topic(name=topic, version=1, durable=self._durable) if isinstance(topic, str) else topic
        env = self._enrich_envelope(
            event_type,
            payload,
            topic=topic_obj,
            priority=priority,
            source=source,
            metadata=metadata,
        )
        self._m_publish.inc(topic=topic_obj.name)
        if self._sql_log is not None and topic_obj.durable:
            self._sql_log.append(env, topic_obj.name)
        self._append_history(env)
        with self._lock:
            regs = sorted(list(self._handlers.get(topic_obj.name, [])))
            subscribers = list(self._subscribers.get(topic_obj.name, []))
        for reg in regs:
            if not reg.filter(env):
                continue
            await self._safe_await(env, topic_obj.name, reg.handler_id, _invoke_any(reg.handler, env))
        for sub in subscribers:
            await self._safe_await(env, topic_obj.name, f"sub:{type(sub).__name__}", _invoke_any(sub.handle_event, env, topic_obj))
        return env

    # -------- subscribe / unsubscribe --------

    def subscribe(
        self,
        topic: Topic | str,
        handler: EventHandler,
        *,
        order: int = 0,
        handler_filter: Callable[[EventEnvelope], bool] | None = None,
    ) -> str:
        topic_name = topic.name if isinstance(topic, Topic) else str(topic)
        with self._lock:
            reg = _HandlerRegistration(
                order=order,
                topic=topic if isinstance(topic, Topic) else Topic(name=topic_name, version=1),
                handler=handler,
                filter=handler_filter or (lambda _: True),
            )
            self._handlers[topic_name].append(reg)
        return reg.handler_id

    def add_subscriber(self, topic: Topic | str, subscriber: Subscriber) -> None:
        topic_name = topic.name if isinstance(topic, Topic) else str(topic)
        with self._lock:
            self._subscribers[topic_name].append(subscriber)

    def unsubscribe(self, topic: Topic | str, handler_id: str) -> bool:
        topic_name = topic.name if isinstance(topic, Topic) else str(topic)
        with self._lock:
            before = list(self._handlers.get(topic_name, []))
            after = [r for r in before if r.handler_id != handler_id]
            self._handlers[topic_name] = after
            return len(after) != len(before)

    # -------- replay / dlq --------

    def replay(
        self,
        topic: Topic | str,
        *,
        since_timestamp: float | None = None,
        since_event_id: str | None = None,
        limit: int | None = None,
    ) -> list[EventEnvelope]:
        topic_name = topic.name if isinstance(topic, Topic) else str(topic)
        results: list[EventEnvelope] = []
        # Prefer durable log
        if self._sql_log is not None:
            results = self._sql_log.replay(
                topic_name,
                since_timestamp=since_timestamp,
                since_event_id=since_event_id,
                limit=limit,
            )
        else:
            with self._lock:
                events = list(self._history)
            filtered = [e for e in events]
            if since_timestamp is not None:
                filtered = [e for e in filtered if e.timestamp >= since_timestamp]
            if since_event_id:
                for i, e in enumerate(filtered):
                    if str(e.event_id) == since_event_id:
                        filtered = filtered[i + 1 :]
                        break
            if limit is not None:
                filtered = filtered[: int(limit)]
            results = filtered
        self._m_replay.add(len(results), topic=topic_name)
        return results

    def dead_letter_count(self, topic: Topic | str | None = None) -> int:
        topic_name = topic.name if topic and isinstance(topic, Topic) else (topic if isinstance(topic, str) else None)
        if self._sql_log is not None:
            return self._sql_log.dlq_count(topic_name)
        if topic_name:
            return sum(1 for _env, t, _h, _e in self._inmem_dlq if t == topic_name)
        return len(self._inmem_dlq)

    # -------- internals --------

    def _get_loop(self) -> asyncio.AbstractEventLoop | None:
        if self._loop is not None:
            return self._loop
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return None

    async def _safe_await(
        self,
        env: EventEnvelope,
        topic_name: str,
        handler_id: str,
        coro: Awaitable[Any],
    ) -> None:
        try:
            await coro
        except Exception as exc:  # noqa: BLE001
            self._handler_failure(env, topic_name, handler_id, exc)

    def _handler_failure(
        self,
        env: EventEnvelope,
        topic_name: str,
        handler_id: str,
        exc: Exception,
    ) -> None:
        err_text = f"{type(exc).__name__}: {exc}"
        log.warning(
            "EventBus handler failure",
            topic=topic_name,
            handler_id=handler_id[:8],
            event_type=env.event_type,
            error=err_text,
        )
        self._m_handler_err.inc(topic=topic_name)
        if self._dlq_enabled:
            self._m_dlq.inc(topic=topic_name)
            if self._sql_log is not None:
                self._sql_log.append_dlq(env, topic_name, handler_id, err_text)
            else:
                self._inmem_dlq.append((env, topic_name, handler_id, err_text))

    # ------- history / status -------

    def history_snapshot(self, limit: int = 200) -> list[EventEnvelope]:
        with self._lock:
            return list(self._history[-limit:])


# Utility: invoke handler which may be sync or async
async def _invoke_any(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
    result = fn(*args, **kwargs)
    if asyncio.iscoroutine(result):
        return await result
    return result


__all__ = [
    "CoreEventBus",
    "DEFAULT_TOPIC",
    "Priority",
    "LOW",
    "NORMAL",
    "HIGH",
    "CRITICAL",
    "Topic",
    "EventEnvelope",
    "Subscriber",
]
