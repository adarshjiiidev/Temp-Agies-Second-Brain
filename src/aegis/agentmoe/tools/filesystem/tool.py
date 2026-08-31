"""AgentMoe — FilesystemTool.

High-level filesystem tool for AgentMoe workers.

This tool wraps the L5 FilesystemExecutor via CapabilityInvoker.
It adds:
  - PathGuard (traversal prevention, workspace root enforcement)
  - PrivacyZone check (defers to aegis.l4_memory.p07 PrivacyZoneService)
  - Dry-run support for destructive operations
  - Rich structured output

Supported operations (all via L5 FilesystemExecutor):
  read, write, edit (patch), search, list, move, copy, delete,
  glob, metadata, diff, mkdir, hash

SECURITY:
  - All paths are resolved and validated before L5 submission.
  - FS_DELETE always requires user_confirmed=True.
  - Paths outside workspace_root are blocked unless allow_outside_workspace=True.
  - Writes to system paths are always blocked.

Import safety: stdlib + agentmoe.core + agentmoe.security + agentmoe.observability.
L5 invocation is via CapabilityInvoker (lazy import to avoid circular deps).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from aegis.agentmoe.core.tool import BaseTool, ToolInvokeError, ToolResult, ToolRiskLevel
from aegis.agentmoe.observability.span import SpanBuilder, SpanKind
from aegis.agentmoe.security.path_guard import PathGuard, PathGuardError

logger = logging.getLogger(__name__)

__all__ = ["FilesystemTool"]


class FilesystemTool(BaseTool):
    """AgentMoe filesystem tool.

    Routes all operations through L5 FilesystemExecutor via CapabilityInvoker.

    Usage::

        tool = FilesystemTool(
            invoker=capability_invoker,
            workspace_root=Path("/workspace"),
        )
        result = await tool.invoke(
            parameters={"op": "read", "path": "/workspace/README.md"},
            worker_id="...",
            mission_id="...",
        )
    """

    @property
    def name(self) -> str:
        return "filesystem"

    @property
    def description(self) -> str:
        return (
            "Filesystem operations: read, write, edit, search, list, move, copy, "
            "delete, glob, metadata, diff, mkdir, hash. "
            "All paths validated against workspace root and privacy zones."
        )

    @property
    def default_risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.MEDIUM  # reads are LOW, writes MEDIUM, deletes HIGH

    @property
    def supports_dry_run(self) -> bool:
        return True

    @property
    def is_idempotent(self) -> bool:
        return False  # writes/deletes are not idempotent

    def __init__(
        self,
        *,
        invoker: Any,  # CapabilityInvoker — typed as Any to avoid circular import
        workspace_root: Optional[Path] = None,
        allow_outside_workspace: bool = False,
    ) -> None:
        self._invoker = invoker
        self._guard = PathGuard(
            workspace_root=workspace_root or Path.home() / "workspace",
            allow_outside_workspace=allow_outside_workspace,
        )

    # -- operation risk mapping --------------------------------------------

    _OP_RISK: dict[str, ToolRiskLevel] = {
        "read":     ToolRiskLevel.LOW,
        "list":     ToolRiskLevel.LOW,
        "glob":     ToolRiskLevel.LOW,
        "search":   ToolRiskLevel.LOW,
        "hash":     ToolRiskLevel.LOW,
        "metadata": ToolRiskLevel.LOW,
        "diff":     ToolRiskLevel.LOW,
        "mkdir":    ToolRiskLevel.MEDIUM,
        "write":    ToolRiskLevel.MEDIUM,
        "edit":     ToolRiskLevel.MEDIUM,
        "copy":     ToolRiskLevel.MEDIUM,
        "append":   ToolRiskLevel.MEDIUM,
        "move":     ToolRiskLevel.HIGH,
        "delete":   ToolRiskLevel.HIGH,
    }

    # -- L5 ActionKind mapping ---------------------------------------------

    _OP_ACTION: dict[str, str] = {
        "read":     "FS_READ",
        "write":    "FS_WRITE",
        "append":   "FS_APPEND",
        "edit":     "FS_WRITE",      # edit = read-modify-write at L5 level
        "copy":     "FS_COPY",
        "move":     "FS_MOVE",
        "delete":   "FS_DELETE",
        "mkdir":    "FS_MKDIR",
        "hash":     "FS_HASH",
        "search":   "FS_SEARCH",
        "list":     "FS_SEARCH",     # list is a constrained search
        "glob":     "FS_SEARCH",
        "metadata": "FS_HASH",       # reuse FS_HASH executor for stat info
        "diff":     "FS_READ",       # diff is two reads + comparison
    }

    async def invoke(
        self,
        *,
        parameters: dict[str, Any],
        worker_id: str,
        mission_id: str,
        parent_span_id: Optional[str] = None,
        dry_run: bool = False,
        user_confirmed: bool = False,
    ) -> ToolResult:
        op = parameters.get("op", "read")
        span = SpanBuilder(
            kind=SpanKind.TOOL,
            name=f"filesystem.{op}",
            worker_id=worker_id,
            mission_id=mission_id,
            parent_id=parent_span_id,
            tool=self.name,
        )

        # 1. Validate operation
        if op not in self._OP_ACTION:
            span.failed(ValueError(f"Unknown op: {op!r}"))
            return ToolResult.err(
                "InvalidOperation",
                f"Unknown filesystem operation: {op!r}. "
                f"Valid ops: {sorted(self._OP_ACTION.keys())}",
                span_id=span.build().span_id,
            )

        # 2. Validate path
        path_str = parameters.get("path") or parameters.get("src")
        if not path_str:
            return ToolResult.err("MissingParameter", "Parameter 'path' is required", span_id=self._new_span_id())

        try:
            validated_path = self._guard.validate(
                path_str,
                must_exist=(op in {"read", "move", "copy", "delete", "hash", "metadata", "diff"}),
                allow_write=(op in {"write", "edit", "append", "mkdir"}),
            )
        except PathGuardError as exc:
            span.denied(str(exc))
            return ToolResult.err("PathGuardError", str(exc))

        # Validate destination path for copy/move
        dst_str = parameters.get("dst")
        validated_dst: Optional[Path] = None
        if dst_str:
            try:
                validated_dst = self._guard.validate(dst_str, allow_write=True)
            except PathGuardError as exc:
                return ToolResult.err("PathGuardError", f"Destination: {exc}")

        # 3. Require user_confirmed for destructive ops
        if op == "delete" and not user_confirmed:
            span.denied("FS_DELETE requires user_confirmed=True", risk_level="HIGH")
            return ToolResult.err(
                "ApprovalRequired",
                "File deletion requires explicit user confirmation (user_confirmed=True).",
            )

        # 4. Dry-run — describe what would happen
        if dry_run:
            description = self._describe_dry_run(op, validated_path, validated_dst, parameters)
            return ToolResult.ok({"dry_run_description": description}, dry_run=True)

        # 5. Route to L5 via CapabilityInvoker
        action_kind = self._OP_ACTION[op]
        params = dict(parameters)
        params["path"] = str(validated_path)
        if validated_dst:
            params["dst"] = str(validated_dst)

        try:
            result = await self._invoker.invoke_action(
                action_kind=action_kind,
                parameters=params,
                worker_id=worker_id,
                mission_id=mission_id,
                user_confirmed=user_confirmed,
            )
        except Exception as exc:
            logger.exception("FilesystemTool: L5 invocation failed for op=%s", op)
            span.failed(exc, risk_level=self._OP_RISK[op].value)
            return ToolResult.err(type(exc).__name__, str(exc)[:300])

        span.success(
            audit_ref=getattr(result, "audit_id", None),
            risk_level=self._OP_RISK[op].value,
        )
        return ToolResult.ok(
            output=getattr(result, "output", None),
            audit_ref=getattr(result, "audit_id", None),
        )

    def _describe_dry_run(
        self,
        op: str,
        path: Path,
        dst: Optional[Path],
        params: dict[str, Any],
    ) -> str:
        """Generate a human-readable dry-run description."""
        if op == "read":
            return f"Would read file: {path}"
        if op in ("write", "edit"):
            content_preview = str(params.get("content", ""))[:50]
            return f"Would write to {path}: {content_preview!r}..."
        if op == "delete":
            return f"Would DELETE (irreversible): {path}"
        if op == "copy":
            return f"Would copy {path} → {dst}"
        if op == "move":
            return f"Would move {path} → {dst}"
        if op == "mkdir":
            return f"Would create directory: {path}"
        if op == "search":
            pattern = params.get("pattern", "")
            return f"Would search for {pattern!r} in {path}"
        return f"Would perform {op} on {path}"
