"""AgentMoe — ExecutionSpan (structured observability).

Every tool invocation and worker execution emits an ExecutionSpan.
Spans are the primary observability primitive for AgentMoe.

Security rules:
  - NEVER include API keys, passwords, tokens, session cookies.
  - NEVER include file contents even if the operation returned them.
  - NEVER include raw command output (use truncated summary).
  - Provenance of the caller is recorded (worker_id, mission_id, parent_id).

Import safety: stdlib only (no AEGIS layer imports).
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


__all__ = [
    "SpanStatus",
    "SpanKind",
    "ExecutionSpan",
    "SpanBuilder",
]


class SpanStatus(str, Enum):
    """Outcome of a tool or worker invocation."""
    PENDING    = "pending"
    RUNNING    = "running"
    SUCCESS    = "success"
    FAILED     = "failed"
    CANCELLED  = "cancelled"
    TIMEOUT    = "timeout"
    DENIED     = "denied"      # policy/permission denial
    DEFERRED   = "deferred"    # needs_approval


class SpanKind(str, Enum):
    """What kind of operation does this span represent."""
    TOOL        = "tool"
    WORKER      = "worker"
    SWARM       = "swarm"
    MODEL_CALL  = "model_call"
    DELEGATION  = "delegation"
    CHECKPOINT  = "checkpoint"


@dataclass(frozen=True)
class ExecutionSpan:
    """Immutable record of one AgentMoe tool/worker execution.

    Fields:
        span_id:        Unique ID for this span.
        kind:           What kind of operation (tool/worker/swarm/...).
        name:           Human-readable name (e.g. "FilesystemTool.read").
        exec_id:        ID of the L5 ActionResult, if routed through L5.
        worker_id:      ID of the worker that triggered this span.
        mission_id:     Top-level mission or session ID.
        parent_id:      Parent span_id (None for root spans).
        tool:           Tool name or worker class name.
        model:          Model name used (None if not a model call).
        provider:       Provider name (None if not a model call).
        status:         Outcome.
        risk_level:     Risk level string from L5 ("LOW"/"MEDIUM"/"HIGH"/"CRITICAL").
        latency_ms:     Wall-clock milliseconds.
        input_tokens:   Tokens consumed (None if not a model call).
        output_tokens:  Tokens produced (None if not a model call).
        cost_usd:       Estimated cost in USD (None if unknown).
        error_type:     Exception class name if status=FAILED.
        error_summary:  Short error description (no secrets).
        audit_ref:      L5 audit chain entry ID, if applicable.
        metadata:       Arbitrary extra key→value (no secrets).
        started_at:     Unix timestamp when span started.
        finished_at:    Unix timestamp when span finished (None if still running).
    """

    span_id:      str
    kind:         SpanKind
    name:         str
    worker_id:    str
    mission_id:   str

    # optional linkage
    exec_id:      Optional[str]           = None
    parent_id:    Optional[str]           = None

    # what was invoked
    tool:         Optional[str]           = None
    model:        Optional[str]           = None
    provider:     Optional[str]           = None

    # outcome
    status:       SpanStatus              = SpanStatus.PENDING
    risk_level:   str                     = "UNKNOWN"

    # timing
    latency_ms:   Optional[float]         = None
    started_at:   float                   = field(default_factory=time.monotonic)
    finished_at:  Optional[float]         = None

    # token / cost accounting
    input_tokens:  Optional[int]          = None
    output_tokens: Optional[int]          = None
    cost_usd:      Optional[float]        = None

    # error info (no secrets)
    error_type:    Optional[str]          = None
    error_summary: Optional[str]          = None

    # L5 audit reference
    audit_ref:     Optional[str]          = None

    # arbitrary safe metadata (caller responsible for not putting secrets here)
    metadata:      dict[str, Any]         = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """Serialise to a log-safe dict."""
        return {
            "span_id":      self.span_id,
            "kind":         self.kind.value,
            "name":         self.name,
            "worker_id":    self.worker_id,
            "mission_id":   self.mission_id,
            "exec_id":      self.exec_id,
            "parent_id":    self.parent_id,
            "tool":         self.tool,
            "model":        self.model,
            "provider":     self.provider,
            "status":       self.status.value,
            "risk_level":   self.risk_level,
            "latency_ms":   self.latency_ms,
            "started_at":   self.started_at,
            "finished_at":  self.finished_at,
            "input_tokens": self.input_tokens,
            "output_tokens":self.output_tokens,
            "cost_usd":     self.cost_usd,
            "error_type":   self.error_type,
            "error_summary":self.error_summary,
            "audit_ref":    self.audit_ref,
            "metadata":     self.metadata,
        }


class SpanBuilder:
    """Mutable builder that produces an immutable ExecutionSpan when finished.

    Usage::

        builder = SpanBuilder(
            kind=SpanKind.TOOL,
            name="FilesystemTool.read",
            worker_id=session.worker_id,
            mission_id=session.mission_id,
        )
        try:
            result = do_work()
            builder.success(audit_ref=result.audit_id)
        except Exception as exc:
            builder.failed(exc)
        span = builder.build()
        emit_span(span)
    """

    def __init__(
        self,
        *,
        kind: SpanKind,
        name: str,
        worker_id: str,
        mission_id: str,
        parent_id: Optional[str] = None,
        tool: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> None:
        self._span_id   = str(uuid.uuid4())
        self._kind      = kind
        self._name      = name
        self._worker_id = worker_id
        self._mission_id = mission_id
        self._parent_id = parent_id
        self._tool      = tool
        self._model     = model
        self._provider  = provider
        self._started   = time.monotonic()
        self._status    = SpanStatus.RUNNING
        self._risk      = "UNKNOWN"
        self._exec_id: Optional[str]   = None
        self._error_type: Optional[str]  = None
        self._error_summary: Optional[str] = None
        self._audit_ref: Optional[str]  = None
        self._input_tokens: Optional[int]  = None
        self._output_tokens: Optional[int] = None
        self._cost_usd: Optional[float]    = None
        self._metadata: dict[str, Any]    = {}

    # -- outcome setters -------------------------------------------------------

    def success(
        self,
        *,
        audit_ref: Optional[str] = None,
        exec_id: Optional[str] = None,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        cost_usd: Optional[float] = None,
        risk_level: str = "UNKNOWN",
    ) -> "SpanBuilder":
        self._status = SpanStatus.SUCCESS
        self._audit_ref = audit_ref
        self._exec_id = exec_id
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens
        self._cost_usd = cost_usd
        self._risk = risk_level
        return self

    def failed(self, exc: Exception, *, risk_level: str = "UNKNOWN") -> "SpanBuilder":
        self._status = SpanStatus.FAILED
        self._error_type = type(exc).__name__
        # Truncate to 200 chars; never include stack trace (may contain paths/secrets)
        self._error_summary = str(exc)[:200]
        self._risk = risk_level
        return self

    def denied(self, reason: str = "", *, risk_level: str = "HIGH") -> "SpanBuilder":
        self._status = SpanStatus.DENIED
        self._error_summary = reason[:200]
        self._risk = risk_level
        return self

    def cancelled(self) -> "SpanBuilder":
        self._status = SpanStatus.CANCELLED
        return self

    def timeout(self) -> "SpanBuilder":
        self._status = SpanStatus.TIMEOUT
        return self

    def add_metadata(self, **kwargs: Any) -> "SpanBuilder":
        """Add log-safe key/value metadata. Caller must ensure no secrets."""
        self._metadata.update(kwargs)
        return self

    def build(self) -> ExecutionSpan:
        finished = time.monotonic()
        latency  = (finished - self._started) * 1000  # ms
        return ExecutionSpan(
            span_id      = self._span_id,
            kind         = self._kind,
            name         = self._name,
            worker_id    = self._worker_id,
            mission_id   = self._mission_id,
            exec_id      = self._exec_id,
            parent_id    = self._parent_id,
            tool         = self._tool,
            model        = self._model,
            provider     = self._provider,
            status       = self._status,
            risk_level   = self._risk,
            latency_ms   = latency,
            started_at   = self._started,
            finished_at  = finished,
            input_tokens = self._input_tokens,
            output_tokens= self._output_tokens,
            cost_usd     = self._cost_usd,
            error_type   = self._error_type,
            error_summary= self._error_summary,
            audit_ref    = self._audit_ref,
            metadata     = dict(self._metadata),
        )
