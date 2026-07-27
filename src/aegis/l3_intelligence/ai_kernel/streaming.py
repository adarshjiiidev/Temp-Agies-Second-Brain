"""L3 AI Kernel streaming primitives (Prompt 03 §20).

Provider-neutral streaming infrastructure: token/chunk events, incremental
delivery, cancellation, completion/error signalling, and usage metadata.

This module is intentionally primitive — it imports ONLY from types.py, stdlib,
and Pydantic. Provider adapters, router, and kernel import from here, never the
reverse. No circular-import risk by design.

Async queue + async iteration integrates conceptually with Core Runtime's
event/context infrastructure, but no direct EventBus import is made.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from aegis.l3_intelligence.ai_kernel.types import StreamEventType, TokenUsage

# ---------------------------------------------------------------------------
# StreamEvent — frozen Pydantic model for every emitted chunk.
# ---------------------------------------------------------------------------


class StreamEvent(BaseModel):
    """Immutable streaming event (§20). One event per chunk / state transition.

    Provider adapters translate their native SSE / chunk objects into this
    normalized shape. Consumers (kernel, agent loop, CLI UI) iterate over
    StreamEvent instances via StreamEventEmitter.events() or merge_streams().
    """

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    event_type: StreamEventType
    delta: str | None = None
    index: int = 0
    tool_call_id: str | None = None
    tool_name: str | None = None
    tool_arguments_delta: str | None = None
    usage: TokenUsage | None = None
    error: str | None = None
    error_category: str | None = None
    correlation_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Sentinel used internally to signal end-of-stream on the async queue.
# ---------------------------------------------------------------------------


class _EndOfStream:
    pass


_END = _EndOfStream()


# ---------------------------------------------------------------------------
# StreamEventEmitter — producer side of the streaming pipeline.
# ---------------------------------------------------------------------------


class StreamEventEmitter:
    """Async event emitter + buffered queue for a single stream.

    Typical lifecycle:
        emitter = StreamEventEmitter()
        async for chunk in provider_native_stream():
            await emitter.emit_text(chunk.text)
        await emitter.finalize(usage=final_usage)

    Consumer side:
        async for event in emitter.events():
            print(event.delta or "")

    Cancellation:
        consumer cancels the async for → emitter detects and propagates
        OR producer calls emitter.cancel() → consumer sees CANCELLED event.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[StreamEvent | _EndOfStream] = asyncio.Queue()
        self._closed: bool = False
        self.done_event: asyncio.Event = asyncio.Event()
        self._cancelled: bool = False

    # ------------------------------------------------------------------
    # Producer API
    # ------------------------------------------------------------------

    async def emit(self, event: StreamEvent) -> None:
        """Emit a pre-constructed StreamEvent.

        Raises RuntimeError if emitter is already closed.
        """
        if self._closed:
            raise RuntimeError("StreamEventEmitter is closed; cannot emit new events")
        await self._queue.put(event)

    async def emit_text(self, delta: str, *, index: int = 0) -> None:
        """Shortcut: emit a CONTENT_DELTA event with the given text chunk."""
        await self.emit(
            StreamEvent(
                event_type=StreamEventType.CONTENT_DELTA,
                delta=delta,
                index=index,
            )
        )

    async def finalize(self, usage: TokenUsage | None = None) -> None:
        """Terminate stream successfully: emit optional USAGE + COMPLETION then close.

        No-op if emitter already closed.
        """
        if self._closed:
            return
        if usage is not None:
            await self.emit(StreamEvent(event_type=StreamEventType.USAGE, usage=usage))
        await self.emit(StreamEvent(event_type=StreamEventType.COMPLETION))
        self.close()

    async def fail(self, error: str, category: str = "retryable") -> None:
        """Terminate stream with an error: emit ERROR event then close.

        Default category = "retryable" (matches FailureCategory.RETRYABLE.value).
        No-op if emitter already closed.
        """
        if self._closed:
            return
        await self.emit(
            StreamEvent(
                event_type=StreamEventType.ERROR,
                error=error,
                error_category=category,
            )
        )
        self.close()

    async def cancel(self) -> None:
        """Mark stream cancelled: emit CANCELLED event then close.

        No-op if emitter already closed.
        """
        if self._closed:
            return
        self._cancelled = True
        await self.emit(StreamEvent(event_type=StreamEventType.CANCELLED))
        self.close()

    def close(self) -> None:
        """Close emitter: no further events accepted; consumers will exit loop.

        Idempotent: safe to call multiple times.
        """
        if not self._closed:
            self._closed = True
            self._queue.put_nowait(_END)
            self.done_event.set()

    # ------------------------------------------------------------------
    # Consumer API
    # ------------------------------------------------------------------

    async def events(self, *, propagate_errors: bool = True) -> AsyncIterator[StreamEvent]:
        """Async iteration over emitted StreamEvent instances.

        Args:
            propagate_errors: If True (default), when an ERROR event is
                encountered it is yielded first, then re-raised as a
                RuntimeError wrapping the error message + category so that
                callers using ``async for`` see the failure immediately.
                If False, ERROR events are yielded as ordinary events and
                iteration continues.

        Cancellation support:
            If the caller's task is cancelled (asyncio.CancelledError) while
            waiting for the next event, the emitter attempts to emit a
            CANCELLED event (if not already closed) before re-raising.
        """
        try:
            while True:
                item = await self._queue.get()
                if isinstance(item, _EndOfStream):
                    return
                yield item
                if propagate_errors and item.event_type is StreamEventType.ERROR:
                    category = item.error_category or "unknown"
                    message = item.error or "Stream error"
                    raise RuntimeError(f"[{category}] {message}")
        except asyncio.CancelledError:
            if not self._closed:
                self._cancelled = True
                try:
                    self._queue.put_nowait(
                        StreamEvent(event_type=StreamEventType.CANCELLED)
                    )
                    self._queue.put_nowait(_END)
                except Exception:
                    pass
                self._closed = True
                self.done_event.set()
            raise


# ---------------------------------------------------------------------------
# Helper: merge multiple stream sources into a single async iterator.
# ---------------------------------------------------------------------------


async def merge_streams(
    sources: list[AsyncIterator[StreamEvent]],
    *,
    propagate_errors: bool = False,
) -> AsyncIterator[StreamEvent]:
    """Merge several stream event iterators into one, preserving arrival order.

    Each source is consumed concurrently. Events from any source are yielded as
    soon as they arrive. When all sources are exhausted, the merged iterator
    terminates.

    Args:
        sources: Non-empty list of async iterators yielding StreamEvent.
        propagate_errors: If True, ERROR events raise after yield. Default False
            for merge: one source failing should not necessarily kill others.

    If a source raises CancelledError or any other exception, it is treated as
    terminated; remaining sources continue unless propagate_errors demands
    re-raising.
    """
    if not sources:
        return

    async def _wrap_one(
        source: AsyncIterator[StreamEvent],
        out_queue: asyncio.Queue[StreamEvent],
        finished: asyncio.Event,
    ) -> None:
        try:
            async for event in source:
                await out_queue.put(event)
                if propagate_errors and event.event_type is StreamEventType.ERROR:
                    category = event.error_category or "unknown"
                    message = event.error or "Stream error"
                    raise RuntimeError(f"[{category}] {message}")
        except asyncio.CancelledError:
            raise
        except Exception:
            if propagate_errors:
                raise
        finally:
            finished.set()

    queue: asyncio.Queue[StreamEvent] = asyncio.Queue()
    finished_events: list[asyncio.Event] = [asyncio.Event() for _ in sources]

    tasks: list[asyncio.Task[None]] = [
        asyncio.create_task(_wrap_one(src, queue, finished_events[i]))
        for i, src in enumerate(sources)
    ]

    try:
        while True:
            all_done = all(ev.is_set() for ev in finished_events)
            if all_done and queue.empty():
                return
            try:
                item = await asyncio.wait_for(
                    queue.get(),
                    timeout=0.05 if not all_done else None,
                )
            except TimeoutError:
                continue
            yield item
    finally:
        for t in tasks:
            if not t.done():
                t.cancel()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if (
                isinstance(r, BaseException)
                and not isinstance(r, asyncio.CancelledError)
                and propagate_errors
            ):
                raise r


# ---------------------------------------------------------------------------
# Helper: collect an entire stream into (text, events, usage).
# ---------------------------------------------------------------------------


async def collect_stream(
    source: AsyncIterator[StreamEvent],
    *,
    timeout: float | None = None,
) -> tuple[str, list[StreamEvent], TokenUsage | None]:
    """Aggregate a StreamEvent stream to a synchronous result tuple.

    Args:
        source: AsyncIterator yielding StreamEvent (e.g. emitter.events()
            or merge_streams(...)).
        timeout: Optional overall wall-time limit in seconds. If the stream
            does not complete within this duration, TimeoutError is raised
            (already-collected events are not returned — wrap the call if
            you need partial results on timeout).

    Returns:
        (full_text: str, events: list[StreamEvent], usage: TokenUsage | None)

        - ``full_text``: concatenation of every ``event.delta`` from
          ``CONTENT_DELTA / CONTENT_START / CONTENT_END`` events (in order).
        - ``events``: all events in emission order, including non-content.
        - ``usage``: the ``.usage`` from the last ``USAGE`` event seen, or None.
    """

    text_parts: list[str] = []
    all_events: list[StreamEvent] = []
    last_usage: TokenUsage | None = None

    async def _inner() -> None:
        nonlocal last_usage
        async for event in source:
            all_events.append(event)
            if event.delta is not None and event.event_type in {
                StreamEventType.CONTENT_DELTA,
                StreamEventType.CONTENT_START,
                StreamEventType.CONTENT_END,
            }:
                text_parts.append(event.delta)
            if event.usage is not None and event.event_type is StreamEventType.USAGE:
                last_usage = event.usage

    if timeout is not None:
        await asyncio.wait_for(_inner(), timeout=timeout)
    else:
        await _inner()

    full_text = "".join(text_parts)
    return full_text, all_events, last_usage


__all__ = [
    "StreamEvent",
    "StreamEventEmitter",
    "collect_stream",
    "merge_streams",
]
