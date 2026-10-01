"""AgentMoe — ToolFabric.

The ToolFabric is the single point of entry for all tool invocations.

It:
  1. Maintains a registry of all available BaseTool instances.
  2. Routes every invocation through CapabilityInvoker → L5 pipeline.
  3. Emits ExecutionSpans for every call.
  4. Enforces worker tool_grants before invoking.
  5. Collects and stores spans for later retrieval.

Architecture::

    caller (worker / L6 planner)
         │
         ▼
    ToolFabric.invoke(tool_name, parameters, ...)
         │
         ▼
    [tool_grants check]
         │
         ▼
    BaseTool.invoke()
         │   (tool delegates to CapabilityInvoker internally)
         ▼
    CapabilityInvoker → L5 ExecutionPipeline
         │
         ▼
    Permission → Risk → Policy → Executor → Sandbox → Audit → Verify

Import safety: stdlib + agentmoe.core.* + agentmoe.observability (no direct L5 imports).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, FrozenSet, Optional

from aegis.agentmoe.core.tool import BaseTool, ToolInvokeError, ToolResult
from aegis.agentmoe.observability.span import ExecutionSpan, SpanBuilder, SpanKind, SpanStatus

logger = logging.getLogger(__name__)

__all__ = ["ToolFabric", "ToolNotFoundError", "ToolNotGrantedError"]


class ToolNotFoundError(Exception):
    """Tool name not registered in ToolFabric."""


class ToolNotGrantedError(Exception):
    """Worker does not have this tool in its tool_grants."""


class ToolFabric:
    """Registry and dispatcher for all AgentMoe tools.

    Usage::

        fabric = ToolFabric()
        fabric.register(FilesystemTool())
        fabric.register(TerminalTool())

        result = await fabric.invoke(
            tool_name="filesystem.read",
            parameters={"path": "/workspace/README.md"},
            worker_id=worker.worker_id,
            mission_id=session.mission_id,
            tool_grants=worker.tool_grants,
        )
    """

    def __init__(
        self,
        *,
        span_handler: Optional[Callable[[ExecutionSpan], None]] = None,
    ) -> None:
        """
        Args:
            span_handler: Optional callback invoked with every finished span.
                          Use for logging, metrics emission, or audit routing.
        """
        self._tools: dict[str, BaseTool] = {}
        self._span_handler = span_handler
        self._spans: list[ExecutionSpan] = []
        self._lock = asyncio.Lock()

    # -- registration -------------------------------------------------------

    def register(self, tool: BaseTool) -> None:
        """Register a tool. Duplicate names overwrite (last wins)."""
        if not isinstance(tool, BaseTool):
            raise TypeError(f"Expected BaseTool, got {type(tool)}")
        self._tools[tool.name] = tool
        logger.debug("ToolFabric: registered tool %r (risk=%s)", tool.name, tool.default_risk_level.value)

    def unregister(self, tool_name: str) -> None:
        """Remove a tool from the registry."""
        self._tools.pop(tool_name, None)

    def list_tools(self) -> list[dict[str, Any]]:
        """Return a list of tool descriptors (name, description, risk, idempotent)."""
        return [
            {
                "name":         t.name,
                "description":  t.description,
                "risk_level":   t.default_risk_level.value,
                "dry_run":      t.supports_dry_run,
                "idempotent":   t.is_idempotent,
                "network":      t.requires_network,
            }
            for t in self._tools.values()
        ]

    def get_tool(self, tool_name: str) -> BaseTool:
        """Retrieve a registered tool by name."""
        if tool_name not in self._tools:
            raise ToolNotFoundError(f"Tool {tool_name!r} is not registered in ToolFabric")
        return self._tools[tool_name]

    # -- invocation ---------------------------------------------------------

    async def invoke(
        self,
        *,
        tool_name: str,
        parameters: dict[str, Any],
        worker_id: str,
        mission_id: str,
        tool_grants: FrozenSet[str] = frozenset(),
        parent_span_id: Optional[str] = None,
        dry_run: bool = False,
        user_confirmed: bool = False,
    ) -> ToolResult:
        """Invoke a registered tool.

        Args:
            tool_name:      Registered tool name, e.g. "filesystem.read".
            parameters:     Tool-specific parameter dict.
            worker_id:      ID of the calling worker.
            mission_id:     Top-level mission ID.
            tool_grants:    Frozenset of tool names the worker is allowed to use.
                            Use frozenset({"*"}) to grant all tools (elevated privilege).
            parent_span_id: Parent span for trace linkage.
            dry_run:        If True, do not execute side effects.
            user_confirmed: If True, the user has explicitly approved this.

        Returns:
            ToolResult — never raises for expected tool failures.

        Raises:
            ToolNotFoundError: Tool not registered.
            ToolNotGrantedError: Worker lacks grant for this tool.
        """
        # 1. Resolve tool
        if tool_name not in self._tools:
            raise ToolNotFoundError(f"Tool {tool_name!r} not registered")
        tool = self._tools[tool_name]

        # 2. Enforce tool_grants
        if not self._is_granted(tool_name, tool_grants):
            raise ToolNotGrantedError(
                f"Worker {worker_id!r} does not have grant for tool {tool_name!r}"
            )

        # 3. Build span
        builder = SpanBuilder(
            kind=SpanKind.TOOL,
            name=tool_name,
            worker_id=worker_id,
            mission_id=mission_id,
            parent_id=parent_span_id,
            tool=tool_name,
        )

        # 4. Invoke
        try:
            result = await tool.invoke(
                parameters=parameters,
                worker_id=worker_id,
                mission_id=mission_id,
                parent_span_id=parent_span_id,
                dry_run=dry_run,
                user_confirmed=user_confirmed,
            )
        except ToolInvokeError as exc:
            builder.failed(exc, risk_level=tool.default_risk_level.value)
            span = builder.build()
            self._emit_span(span)
            return ToolResult.err(
                exc.error_type,
                str(exc),
                span_id=span.span_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("ToolFabric: unexpected error invoking %r", tool_name)
            builder.failed(exc, risk_level=tool.default_risk_level.value)
            span = builder.build()
            self._emit_span(span)
            return ToolResult.err(
                type(exc).__name__,
                f"Unexpected error: {exc!s}"[:300],
                span_id=span.span_id,
            )

        # 5. Finalise span
        if result.success:
            builder.success(
                audit_ref=result.audit_ref,
                risk_level=tool.default_risk_level.value,
            )
        else:
            builder.failed(
                Exception(result.error_message or ""),
                risk_level=tool.default_risk_level.value,
            )
        span = builder.build()
        # Attach span_id to result
        result.span_id = span.span_id
        self._emit_span(span)
        return result

    # -- span access --------------------------------------------------------

    def get_spans(
        self,
        *,
        mission_id: Optional[str] = None,
        worker_id: Optional[str] = None,
        status: Optional[SpanStatus] = None,
    ) -> list[ExecutionSpan]:
        """Return recorded spans, optionally filtered."""
        spans = self._spans
        if mission_id:
            spans = [s for s in spans if s.mission_id == mission_id]
        if worker_id:
            spans = [s for s in spans if s.worker_id == worker_id]
        if status:
            spans = [s for s in spans if s.status == status]
        return list(spans)

    def clear_spans(self) -> None:
        """Clear recorded span history (e.g. after a session ends)."""
        self._spans.clear()

    # -- internals ----------------------------------------------------------

    @staticmethod
    def _is_granted(tool_name: str, grants: FrozenSet[str]) -> bool:
        """Return True if tool_name is in grants or grants contains '*'."""
        return "*" in grants or tool_name in grants

    def _emit_span(self, span: ExecutionSpan) -> None:
        self._spans.append(span)
        if self._span_handler:
            try:
                self._span_handler(span)
            except Exception:  # noqa: BLE001
                logger.warning("ToolFabric: span_handler raised (ignored)")
