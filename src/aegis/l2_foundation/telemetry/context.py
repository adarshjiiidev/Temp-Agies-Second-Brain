"""L2 Correlation Context propagation.
Prompt 02 §9: single operation must be traceable across Request → Planning → Tool Invocation → Execution → Result.
Uses contextvars (NOT global mutable state) for safe async propagation.
Carries: Correlation ID, Request ID, Task ID, Parent Operation ID, arbitrary metadata."""

from __future__ import annotations

import contextlib
import contextvars
import uuid
from collections.abc import Iterator
from contextvars import Token
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

# One contextvar for the whole package — propagation guaranteed by PEP-567 / asyncio.
_CV: contextvars.ContextVar[CorrelationContext | None] = contextvars.ContextVar(
    "aegis.correlation", default=None
)


@dataclass(frozen=True)
class CorrelationContext:
    """Immutable correlation context. New values obtained via .fork(...) or CorrelationContext.new()."""

    correlation_id: UUID
    request_id: UUID | None = None
    task_id: UUID | None = None
    parent_op_id: UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def new(
        cls,
        *,
        correlation_id: UUID | None = None,
        request_id: UUID | None = None,
        task_id: UUID | None = None,
        parent_op_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CorrelationContext:
        return cls(
            correlation_id=correlation_id or uuid.uuid4(),
            request_id=request_id,
            task_id=task_id,
            parent_op_id=parent_op_id,
            metadata=dict(metadata or {}),
        )

    def fork(
        self,
        *,
        new_task_id: bool = False,
        new_request_id: bool = False,
        parent_op_id: UUID | None = None,
        extra_metadata: dict[str, Any] | None = None,
        new_correlation_id: bool = False,
    ) -> CorrelationContext:
        """Fork the context for a child operation; inherits unless overridden."""
        merged = {**self.metadata, **(extra_metadata or {})}
        return CorrelationContext(
            correlation_id=uuid.uuid4() if new_correlation_id else self.correlation_id,
            request_id=uuid.uuid4() if new_request_id else self.request_id,
            task_id=uuid.uuid4() if new_task_id else self.task_id,
            parent_op_id=parent_op_id or (self.task_id if not new_task_id else self.task_id),
            metadata=merged,
        )

    def as_dict(self, *, stringify: bool = True) -> dict[str, Any]:
        f = str if stringify else (lambda x: x)
        d: dict[str, Any] = {"correlation_id": f(self.correlation_id)}
        if self.request_id is not None:
            d["request_id"] = f(self.request_id)
        if self.task_id is not None:
            d["task_id"] = f(self.task_id)
        if self.parent_op_id is not None:
            d["parent_op_id"] = f(self.parent_op_id)
        if self.metadata:
            d["meta"] = dict(self.metadata)
        return d

    # -------- ContextVar-based current-context helpers --------

    @classmethod
    def current(cls) -> CorrelationContext:
        """Return current context or create a new root context (never returns None)."""
        ctx = _CV.get()
        if ctx is None:
            ctx = cls.new()
            _CV.set(ctx)
        return ctx

    @classmethod
    def get_current_or_none(cls) -> CorrelationContext | None:
        return _CV.get()

    @contextlib.contextmanager
    def enter(self) -> Iterator[CorrelationContext]:
        """Use this context as the current for the enclosed block. Restores previous on exit."""
        token: Token[CorrelationContext | None] = _CV.set(self)
        try:
            yield self
        finally:
            _CV.reset(token)


# Convenience: enter a fresh root or forked child context
@contextlib.contextmanager
def new_correlation(
    *,
    inherit: bool = False,
    metadata: dict[str, Any] | None = None,
) -> Iterator[CorrelationContext]:
    if inherit:
        parent = CorrelationContext.get_current_or_none()
        ctx = (
            parent.fork(extra_metadata=metadata)
            if parent
            else CorrelationContext.new(metadata=metadata)
        )
    else:
        ctx = CorrelationContext.new(metadata=metadata)
    with ctx.enter() as entered:
        yield entered
