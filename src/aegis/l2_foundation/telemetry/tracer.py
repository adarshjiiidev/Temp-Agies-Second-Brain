"""L2 Tracer skeleton (OTel-compatible Protocol surface).
Prompt 02 scope: no vendor export, no span batching, no network.
Keeps the correct public API surface so future prompts can plug OTel SDK without call-site changes.
"""
from __future__ import annotations

import contextlib
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Iterator
from uuid import UUID

from aegis.l2_foundation.telemetry.context import CorrelationContext


@dataclass
class Span:
    span_id: UUID
    trace_id: UUID
    parent_span_id: UUID | None
    name: str
    kind: str = "internal"
    start_time: float = field(default_factory=lambda: time.time())
    end_time: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)
    status: str = "UNSET"  # UNSET | OK | ERROR

    def is_recording(self) -> bool:  # Prompt 02: always record locally; no sampler
        return True

    def set_attribute(self, key: str, value: Any) -> None:  # noqa: ANN401
        if self.is_recording():
            self.attributes[key] = value

    def add_event(self, name: str, **attrs: Any) -> None:  # noqa: ANN401
        if self.is_recording():
            self.events.append({"name": name, "time": time.time(), "attrs": dict(attrs)})

    def set_status(self, status: str) -> None:
        if status in ("UNSET", "OK", "ERROR"):
            self.status = status

    def record_exception(self, exc: BaseException) -> None:
        self.set_status("ERROR")
        self.add_event(
            "exception",
            type=type(exc).__name__,
            message=str(exc),
        )

    def end(self) -> None:
        if self.end_time is None:
            self.end_time = time.time()


class Tracer:
    """Prompt 02 in-memory tracer. Spans kept in ring buffer (cap=1024) for debugging only;
    no export. Future subsystems can add OTel SpanExporter without touching this API."""

    def __init__(self, name: str, version: str = "0.1.0", *, ring_capacity: int = 1024) -> None:
        self.name = name
        self.version = version
        self._cap = max(1, ring_capacity)
        self._ring: list[Span] = []
        self._lock = threading.RLock()

    def start_span(
        self,
        name: str,
        *,
        kind: str = "internal",
        trace_id: UUID | None = None,
        parent_span_id: UUID | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> Span:
        ctx = CorrelationContext.get_current_or_none()
        if ctx is not None:
            trace_id = trace_id or ctx.correlation_id
        else:
            trace_id = trace_id or uuid.uuid4()
        span = Span(
            span_id=uuid.uuid4(),
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            name=name,
            kind=kind,
            attributes=dict(attributes or {}),
        )
        return span

    @contextlib.contextmanager
    def span(self, name: str, **kwargs: Any) -> Iterator[Span]:  # noqa: ANN401
        span = self.start_span(name, **kwargs)
        try:
            yield span
        except BaseException as exc:  # noqa: BLE001
            span.record_exception(exc)
            raise
        finally:
            span.end()
            self._store(span)

    def _store(self, span: Span) -> None:
        with self._lock:
            if len(self._ring) >= self._cap:
                self._ring.pop(0)
            self._ring.append(span)

    def recent_spans(self, limit: int = 50) -> list[Span]:
        with self._lock:
            return list(self._ring[-limit:])


_GLOBAL_TRACER: Tracer | None = None
_GLOBAL_TRACER_LOCK = threading.Lock()


def get_tracer(name: str = "aegis", version: str = "0.1.0") -> Tracer:
    global _GLOBAL_TRACER
    if _GLOBAL_TRACER is None:
        with _GLOBAL_TRACER_LOCK:
            if _GLOBAL_TRACER is None:
                _GLOBAL_TRACER = Tracer(name=name, version=version)
    return _GLOBAL_TRACER
