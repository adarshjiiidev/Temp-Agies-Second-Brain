"""AgentMoe — BaseTool ABC.

Defines the contract every AgentMoe tool must satisfy.

Key design decisions:
  1. Tools are thin facades — they validate, then route to L5 via CapabilityInvoker.
     No tool should ever directly call subprocess.run() or os.system().
  2. Every tool must declare its RiskLevel so the L5 PolicyEngine can make
     an informed decision before execution.
  3. Dry-run MUST return a description of what would happen, never a side effect.
  4. All tool results carry an optional audit_ref linking to the L5 AuditChain.

Import safety: stdlib + agentmoe.config + agentmoe.observability (no L5 direct imports).
"""

from __future__ import annotations

import abc
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


__all__ = [
    "ToolRiskLevel",
    "ToolResult",
    "ToolInvokeError",
    "BaseTool",
]


# ---------------------------------------------------------------------------
# Risk classification (maps to L5 RiskLevel)
# ---------------------------------------------------------------------------

class ToolRiskLevel(str, Enum):
    """Risk classification of a tool operation.

    Maps to the L5 execution engine's RiskLevel:
        LOW      → generally safe, reversible, no system modification
        MEDIUM   → modifies local state (files in workspace, local git)
        HIGH     → network access, shell execution, external API calls
        CRITICAL → destructive/irreversible, system-wide, requires explicit approval
    """
    LOW      = "LOW"
    MEDIUM   = "MEDIUM"
    HIGH     = "HIGH"
    CRITICAL = "CRITICAL"


# ---------------------------------------------------------------------------
# Tool result
# ---------------------------------------------------------------------------

@dataclass
class ToolResult:
    """Result of a BaseTool.invoke() call.

    Attributes:
        success:        Whether the operation succeeded.
        output:         Structured or text output from the operation.
        dry_run:        True if this was a dry-run (no side effects occurred).
        audit_ref:      L5 AuditChain entry ID (None if not routed through L5).
        span_id:        AgentMoe observability span ID.
        error_type:     Exception class name if success=False.
        error_message:  Short human-readable error (no secrets).
        metadata:       Arbitrary safe key→value pairs.
    """
    success:       bool
    output:        Any                 = None
    dry_run:       bool                = False
    audit_ref:     Optional[str]       = None
    span_id:       Optional[str]       = None
    error_type:    Optional[str]       = None
    error_message: Optional[str]       = None
    metadata:      dict[str, Any]      = field(default_factory=dict)

    @classmethod
    def ok(
        cls,
        output: Any = None,
        *,
        audit_ref: Optional[str] = None,
        span_id: Optional[str] = None,
        dry_run: bool = False,
        **metadata: Any,
    ) -> "ToolResult":
        return cls(
            success=True,
            output=output,
            audit_ref=audit_ref,
            span_id=span_id,
            dry_run=dry_run,
            metadata=metadata,
        )

    @classmethod
    def err(
        cls,
        error_type: str,
        error_message: str,
        *,
        span_id: Optional[str] = None,
        **metadata: Any,
    ) -> "ToolResult":
        return cls(
            success=False,
            error_type=error_type,
            error_message=error_message[:500],  # truncate; never include secrets
            span_id=span_id,
            metadata=metadata,
        )


class ToolInvokeError(Exception):
    """Raised when a tool cannot execute (as opposed to executing but failing)."""
    def __init__(self, message: str, error_type: str = "ToolInvokeError") -> None:
        super().__init__(message)
        self.error_type = error_type


# ---------------------------------------------------------------------------
# BaseTool ABC
# ---------------------------------------------------------------------------

class BaseTool(abc.ABC):
    """Abstract base class for every AgentMoe tool.

    Subclasses must implement:
        - name (property)       : unique tool identifier, e.g. "filesystem.read"
        - description (property): human-readable description
        - default_risk_level    : ToolRiskLevel for this tool's default operation
        - supports_dry_run      : whether dry_run=True is meaningfully supported
        - invoke()              : the actual implementation

    Subclasses MUST NOT:
        - Call subprocess.run(), os.system(), or any OS primitive directly.
        - Skip routing through CapabilityInvoker → L5 for side-effecting operations.
        - Log or include API keys, file contents, or passwords in ToolResult.

    Subclasses SHOULD:
        - Call self._validate_inputs() before any work.
        - Use SpanBuilder to emit an ExecutionSpan.
        - Return ToolResult.err() for expected failure cases.
        - Raise ToolInvokeError only for configuration/setup failures.
    """

    # --- subclass must set these ------------------------------------------

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Unique dot-namespaced tool identifier, e.g. 'filesystem.read'."""

    @property
    @abc.abstractmethod
    def description(self) -> str:
        """One-sentence human-readable description."""

    @property
    @abc.abstractmethod
    def default_risk_level(self) -> ToolRiskLevel:
        """Default risk level for this tool's primary operation."""

    @property
    def supports_dry_run(self) -> bool:
        """Whether dry_run=True produces a meaningful description of intent."""
        return False

    @property
    def is_idempotent(self) -> bool:
        """True if repeated calls with the same args produce the same result."""
        return False

    @property
    def requires_network(self) -> bool:
        """True if the tool makes external network calls."""
        return False

    # --- mandatory implementation -----------------------------------------

    @abc.abstractmethod
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
        """Execute the tool.

        Args:
            parameters:     Tool-specific input dictionary.
            worker_id:      ID of the calling worker (for observability).
            mission_id:     Top-level mission ID (for observability + audit).
            parent_span_id: Parent span for trace linking.
            dry_run:        If True, describe what would happen without doing it.
            user_confirmed: If True, the user has explicitly approved this action.
                            Required for CRITICAL operations and some HIGH ones.

        Returns:
            ToolResult — never raises for expected error conditions.

        Raises:
            ToolInvokeError: for configuration/setup failures (not runtime errors).
        """

    # --- helpers available to subclasses ----------------------------------

    def _new_span_id(self) -> str:
        return str(uuid.uuid4())

    def _truncate_for_log(self, value: Any, max_len: int = 200) -> str:
        """Safely truncate a value for inclusion in logs (no secrets rule applies)."""
        s = str(value)
        if len(s) > max_len:
            return s[:max_len] + f"…[truncated {len(s) - max_len} chars]"
        return s

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} risk={self.default_risk_level.value}>"
