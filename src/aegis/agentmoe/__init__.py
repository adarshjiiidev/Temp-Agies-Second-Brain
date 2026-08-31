"""AgentMoe — AEGIS Execution/Capability Fabric.

AgentMoe gives AEGIS "hands and legs": tools, workers, browser, computer control,
research, coding, delegation, and swarms — all governed by AEGIS L5 security.

Architecture:
    L6 PlannerService
        → AgentMoe ToolFabric.invoke()
            → CapabilityInvoker (aegis.capabilities.invocation)
                → L5 ExecutionPipeline
                    → Permission → Risk → Policy → Executor → Sandbox → Audit

Public API::

    from aegis.agentmoe import ToolFabric, WorkerRuntime, AgentMoeConfig
    from aegis.agentmoe.tools.filesystem import FilesystemTool
    from aegis.agentmoe.tools.terminal import TerminalTool
    from aegis.agentmoe.tools.git import GitTool

MILESTONE: Phase 1+2+3+4 (Core + Security + Runtime + Tools)
"""

from aegis.agentmoe.core.tool import BaseTool, ToolResult, ToolRiskLevel, ToolInvokeError
from aegis.agentmoe.core.worker import BaseWorker, WorkerBudget, WorkerContext, WorkerResult, WorkerState
from aegis.agentmoe.core.fabric import ToolFabric, ToolNotFoundError, ToolNotGrantedError
from aegis.agentmoe.workers.runtime import WorkerRuntime, WorkerSpawnError
from aegis.agentmoe.config.settings import AgentMoeConfig
from aegis.agentmoe.observability.span import ExecutionSpan, SpanBuilder, SpanKind, SpanStatus

__all__ = [
    # Core contracts
    "BaseTool", "ToolResult", "ToolRiskLevel", "ToolInvokeError",
    "BaseWorker", "WorkerBudget", "WorkerContext", "WorkerResult", "WorkerState",
    # Fabric
    "ToolFabric", "ToolNotFoundError", "ToolNotGrantedError",
    # Runtime
    "WorkerRuntime", "WorkerSpawnError",
    # Config
    "AgentMoeConfig",
    # Observability
    "ExecutionSpan", "SpanBuilder", "SpanKind", "SpanStatus",
]
