"""L5 Execution Engine — MCPExecutor (P08 stub).

Handles ActionKind.MCP_INVOKE actions.

P08 security model:
- ALL MCP invocations must pass through L5 (this executor is the gate)
- The executor validates the tool exists and is not disabled
- In P08, actual MCP protocol communication is NOT implemented
- The executor returns a stub result documenting what would happen
- Full MCP transport (stdio/HTTP/SSE) is implemented in P09+

Full implementation path (P09+):
- STDIO: subprocess launch with protocol framing
- HTTP:  HTTP POST to MCP endpoint with JSON-RPC
- SSE:   HTTP POST + event stream for streaming tools

Import safety: stdlib + l5_execution.* only.
"""

from __future__ import annotations

import logging
from typing import Any

from aegis.l5_execution.contracts import ExecutorManifest, SandboxContext
from aegis.l5_execution.executors.base import BaseExecutor, ExecutorHealth
from aegis.l5_execution.types import Action, ActionKind, ActionResult, ExecutionStatus

logger = logging.getLogger(__name__)

__all__ = ["MCPExecutor"]


class MCPExecutor:
    """Stub executor for MCP_INVOKE and EXTERNAL_AGENT actions.

    P08 role: validates that the MCP tool is registered and not disabled,
    then returns a stub result. This ensures the audit chain records the
    attempt even before P09+ implements the actual transport layer.

    All invocations through this executor are AUDITED by L5.
    No MCP tool can bypass policy/permission/risk stages to reach this executor.
    """

    manifest = ExecutorManifest(
        name="mcp_executor",
        handles=[ActionKind.MCP_INVOKE, ActionKind.EXTERNAL_AGENT],
        is_stub=True,
        supports_rollback=False,
        description=(
            "MCP and external agent executor. "
            "Full MCP transport implementation is planned for P09+. "
            "P08: validates tool metadata, audits attempt, returns stub result."
        ),
    )

    def __init__(self, mcp_server_registry: Any = None) -> None:
        """
        Args:
            mcp_server_registry: Optional MCPServerRegistry to validate tools.
                                  If None, validation is skipped (test mode).
        """
        self._registry = mcp_server_registry

    async def execute(self, action: Action, sandbox: SandboxContext) -> ActionResult:
        """Validate and stub-execute an MCP or external agent action."""
        kind = action.kind

        if kind == ActionKind.MCP_INVOKE:
            return await self._handle_mcp(action, sandbox)
        elif kind == ActionKind.EXTERNAL_AGENT:
            return await self._handle_external_agent(action, sandbox)
        else:
            return ActionResult(
                action_id=action.action_id,
                status=ExecutionStatus.FAILED,
                error=f"MCPExecutor: unexpected action kind {kind!r}",
                error_code="E_MCP_WRONG_KIND",
                executor_name="mcp_executor",
            )

    async def _handle_mcp(self, action: Action, sandbox: SandboxContext) -> ActionResult:
        """Handle MCP_INVOKE action."""
        payload = action.parameters or {}
        server_id = payload.get("server_id", "")
        tool_name = payload.get("tool_name", "")
        tool_id = payload.get("tool_id", f"{server_id}:{tool_name}")
        inputs = payload.get("inputs", {})

        # Validate tool exists if registry is available
        if self._registry is not None:
            tool = self._registry.get_tool(tool_id)
            if tool is None:
                return ActionResult(
                    action_id=action.action_id,
                    status=ExecutionStatus.FAILED,
                    error=(
                        f"MCP tool {tool_id!r} is not registered. "
                        f"Register the server and its tools before invoking."
                    ),
                    error_code="E_MCP_TOOL_NOT_FOUND",
                    executor_name="mcp_executor",
                )
            if not tool.enabled:
                return ActionResult(
                    action_id=action.action_id,
                    status=ExecutionStatus.FAILED,
                    error=f"MCP tool {tool_id!r} is disabled",
                    error_code="E_MCP_TOOL_DISABLED",
                    executor_name="mcp_executor",
                )

        # P08 stub: return a clear result explaining what would happen
        logger.info(
            "MCPExecutor: MCP_INVOKE audit recorded for server=%r tool=%r (stub — P09+ transport)",
            server_id, tool_name,
        )
        return ActionResult(
            action_id=action.action_id,
            status=ExecutionStatus.FAILED,
            error=(
                f"MCPExecutor P08 stub: tool {tool_id!r} validated and audited. "
                f"Full MCP transport (HTTP/stdio/SSE) is implemented in P09+. "
                f"The invocation has been recorded in the audit chain."
            ),
            error_code="E_MCP_STUB_P08",
            executor_name="mcp_executor",
            output={
                "stub": True,
                "server_id": server_id,
                "tool_name": tool_name,
                "inputs_received": inputs,
                "planned_milestone": "P09",
            },
        )

    async def _handle_external_agent(self, action: Action, sandbox: SandboxContext) -> ActionResult:
        """Handle EXTERNAL_AGENT action."""
        payload = action.parameters or {}
        agent_id = payload.get("agent_id", "unknown")
        agent_type = payload.get("agent_type", "unknown")

        logger.info(
            "MCPExecutor: EXTERNAL_AGENT audit recorded for agent=%r type=%r (stub — P20+)",
            agent_id, agent_type,
        )
        return ActionResult(
            action_id=action.action_id,
            status=ExecutionStatus.FAILED,
            error=(
                f"ExternalAgent P08 stub: agent {agent_id!r} ({agent_type}) invocation audited. "
                f"Full external agent integration is planned for P20+."
            ),
            error_code="E_EXTERNAL_AGENT_STUB_P08",
            executor_name="mcp_executor",
            output={
                "stub": True,
                "agent_id": agent_id,
                "agent_type": agent_type,
                "planned_milestone": "P20",
            },
        )

    async def rollback(self, action: Action, result: ActionResult) -> dict[str, Any]:
        return {"supported": False, "reason": "MCP executor is a P08 stub — no rollback"}

    async def health(self) -> ExecutorHealth:
        return ExecutorHealth(
            name="mcp_executor",
            healthy=True,
            message="P08 stub — MCP transport available in P09+",
        )
