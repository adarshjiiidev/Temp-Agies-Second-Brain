"""AgentMoe — TerminalTool.

Linux-first terminal execution tool for AgentMoe workers.

Routes to L5 ShellExecutor via CapabilityInvoker. Adds:
  - InjectionGuard (argv validation, metacharacter detection)
  - Streaming-compatible output capture (buffered with configurable limit)
  - Timeout enforcement
  - Environment isolation (allowlisted passthrough)
  - Linux-first defaults

SECURITY:
  - shell=True is NEVER used. Commands are always argv lists.
  - Environment is constructed from allowlist + explicit additions.
  - HIGH-risk commands require user_confirmed=True.
  - Streaming output is truncated at max_output_bytes to prevent runaway.

Import safety: agentmoe.core + agentmoe.security (no L5 direct imports).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from aegis.agentmoe.core.tool import BaseTool, ToolResult, ToolRiskLevel
from aegis.agentmoe.security.injection_guard import InjectionGuard, InjectionGuardError
from aegis.agentmoe.observability.span import SpanBuilder, SpanKind

logger = logging.getLogger(__name__)

__all__ = ["TerminalTool"]

# Default safe environment passthrough (SAFETY constant — not config)
_SAFE_ENV_PASSTHROUGH = frozenset({
    "PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL",
    "TERM", "COLORTERM", "DISPLAY", "WAYLAND_DISPLAY",
    "XDG_RUNTIME_DIR", "XDG_SESSION_TYPE",
})


class TerminalTool(BaseTool):
    """AgentMoe terminal tool — Linux-first shell execution.

    Usage::

        tool = TerminalTool(invoker=capability_invoker)
        result = await tool.invoke(
            parameters={
                "argv": ["python", "-m", "pytest", "tests/", "-q"],
                "cwd": "/workspace",
                "timeout": 60,
            },
            worker_id="...",
            mission_id="...",
        )
    """

    @property
    def name(self) -> str:
        return "terminal"

    @property
    def description(self) -> str:
        return (
            "Execute a command in a controlled terminal environment. "
            "Commands must be argv lists (no shell strings). "
            "HIGH-risk commands require user_confirmed=True."
        )

    @property
    def default_risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.HIGH

    @property
    def supports_dry_run(self) -> bool:
        return True

    def __init__(
        self,
        *,
        invoker: Any,
        default_timeout: float = 60.0,
        max_timeout: float = 600.0,
        max_output_bytes: int = 1 * 1024 * 1024,
        env_passthrough: frozenset[str] = _SAFE_ENV_PASSTHROUGH,
    ) -> None:
        self._invoker         = invoker
        self._default_timeout = default_timeout
        self._max_timeout     = max_timeout
        self._max_output      = max_output_bytes
        self._env_passthrough = env_passthrough
        self._guard           = InjectionGuard(allow_high_risk=False)

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
        span = SpanBuilder(
            kind=SpanKind.TOOL,
            name="terminal.exec",
            worker_id=worker_id,
            mission_id=mission_id,
            parent_id=parent_span_id,
            tool=self.name,
        )

        # 1. Extract argv
        argv = parameters.get("argv") or parameters.get("cmd")
        if not argv:
            return ToolResult.err("MissingParameter", "'argv' is required (list of strings)")

        # 2. Injection guard
        try:
            argv = self._guard.validate_argv(argv, user_confirmed=user_confirmed)
        except InjectionGuardError as exc:
            span.denied(str(exc), risk_level="HIGH")
            return ToolResult.err("InjectionGuardError", str(exc))

        # 3. Env validation
        extra_env = parameters.get("env") or {}
        try:
            extra_env = self._guard.validate_env(extra_env)
        except Exception as exc:
            return ToolResult.err("EnvValidationError", str(exc))

        # 4. Timeout
        timeout = float(parameters.get("timeout") or self._default_timeout)
        timeout = min(timeout, self._max_timeout)

        # 5. Dry-run
        if dry_run:
            return ToolResult.ok(
                {"dry_run_description": f"Would execute: {argv!r} (timeout={timeout}s)"},
                dry_run=True,
            )

        # 6. Build L5 action parameters
        cwd = parameters.get("cwd") or str(__import__("pathlib").Path.home() / "workspace")
        l5_params = {
            "cmd":     argv,
            "cwd":     cwd,
            "timeout": timeout,
            "env":     extra_env,
            "max_output_bytes": self._max_output,
        }

        # 7. Route to L5
        try:
            result = await self._invoker.invoke_action(
                action_kind="SHELL_EXEC",
                parameters=l5_params,
                worker_id=worker_id,
                mission_id=mission_id,
                user_confirmed=user_confirmed,
            )
        except Exception as exc:
            logger.exception("TerminalTool: L5 invocation failed")
            span.failed(exc, risk_level="HIGH")
            return ToolResult.err(type(exc).__name__, str(exc)[:300])

        output = getattr(result, "output", {}) or {}
        span.success(audit_ref=getattr(result, "audit_id", None), risk_level="HIGH")
        return ToolResult.ok(
            output={
                "stdout":      output.get("stdout", ""),
                "stderr":      output.get("stderr", ""),
                "returncode":  output.get("returncode", -1),
                "truncated":   output.get("truncated", False),
            },
            audit_ref=getattr(result, "audit_id", None),
        )
