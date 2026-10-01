"""Capabilities invocation — CapabilityInvoker.

Bridges capability selection to the L5 execution pipeline.

CRITICAL INVARIANT: ALL side effects go through L5.
No capability may be directly executed without passing through:
  Permission → Risk → Policy → Sandbox → Executor → Audit → Verify

This file creates the appropriate L5 Action from a CapabilityRecord's
ImplementationRef, then submits it to an ExecutionPipeline.

Import safety: stdlib + aegis.capabilities.model + aegis.l5_execution.types/contracts
(No direct import of L6 — this is L5-layer code).
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Protocol, runtime_checkable

from aegis.capabilities.model.capability import CapabilityRecord, TrustState
from aegis.capabilities.model.composition import (
    BuiltinRef,
    CompositeRef,
    ExternalAgentRef,
    ImplementationType,
    MCPToolRef,
)
from aegis.capabilities.model.health import CapabilityHealth, HealthStatus
from aegis.capabilities.model.metrics import CapabilityMetrics

logger = logging.getLogger(__name__)

__all__ = ["CapabilityInvoker", "InvocationResult"]


# ---------------------------------------------------------------------------
# Minimal protocol for the L5 execution pipeline
# ---------------------------------------------------------------------------

@runtime_checkable
class ExecutionPipeline(Protocol):
    """Minimal protocol for the L5 ExecutionPipeline needed by the invoker."""

    async def run_action(self, action: Any) -> Any:
        """Run an L5 Action and return an ActionResult."""
        ...


# ---------------------------------------------------------------------------
# Invocation result
# ---------------------------------------------------------------------------

class InvocationResult:
    """Result of a CapabilityInvoker.invoke() call."""

    def __init__(
        self,
        capability_id: str,
        success: bool,
        output: Any = None,
        error: str | None = None,
        latency_ms: float | None = None,
        action_result: Any = None,
    ) -> None:
        self.capability_id = capability_id
        self.success = success
        self.output = output
        self.error = error
        self.latency_ms = latency_ms
        self.action_result = action_result   # Raw L5 ActionResult


# ---------------------------------------------------------------------------
# CapabilityInvoker
# ---------------------------------------------------------------------------

class CapabilityInvoker:
    """Translates a CapabilityRecord into an L5 Action and executes it.

    Usage::

        invoker = CapabilityInvoker(registry, pipeline)
        result = await invoker.invoke(
            capability_id="builtin:fs.read",
            inputs={"path": "/tmp/foo.txt"},
            subject="system:planner",
        )
        assert result.success
    """

    def __init__(
        self,
        registry: Any,   # CapabilityRegistry (avoid circular import)
        pipeline: ExecutionPipeline,
    ) -> None:
        self._registry = registry
        self._pipeline = pipeline

    async def invoke(
        self,
        capability_id: str,
        inputs: dict[str, Any],
        *,
        subject: str = "system:planner",
        goal_context: str = "",
        user_confirmed: bool = False,
    ) -> InvocationResult:
        """Invoke a capability through the L5 pipeline.

        Args:
            capability_id:  ID of the capability to invoke.
            inputs:         Input parameters for the capability.
            subject:        SVRC subject string (who is calling).
            goal_context:   Human-readable context for audit logging.
            user_confirmed: Whether the user has explicitly approved.

        Returns:
            InvocationResult with success/failure and output.
        """
        # --- Capability lookup ---
        record: CapabilityRecord | None = self._registry.get(capability_id)
        if record is None:
            return InvocationResult(
                capability_id=capability_id,
                success=False,
                error=f"Capability {capability_id!r} not found in registry",
            )

        # --- Pre-invocation guard ---
        if not record.enabled:
            return InvocationResult(
                capability_id=capability_id,
                success=False,
                error=f"Capability {capability_id!r} is disabled",
            )

        if record.trust_state == TrustState.UNVERIFIED:
            return InvocationResult(
                capability_id=capability_id,
                success=False,
                error=(
                    f"Capability {capability_id!r} is UNVERIFIED and cannot be executed. "
                    f"Elevate trust_state to VERIFIED or TRUSTED first."
                ),
            )

        if record.trust_state == TrustState.DISABLED:
            return InvocationResult(
                capability_id=capability_id,
                success=False,
                error=f"Capability {capability_id!r} trust_state is DISABLED",
            )

        # --- Build L5 Action from ImplementationRef ---
        start = time.monotonic()
        try:
            action = self._build_action(record, inputs, subject, goal_context, user_confirmed)
        except Exception as exc:  # noqa: BLE001
            return InvocationResult(
                capability_id=capability_id,
                success=False,
                error=f"Failed to build action for {capability_id!r}: {exc}",
            )

        # --- Submit to L5 pipeline (ALWAYS goes through L5) ---
        try:
            action_result = await self._pipeline.run_action(action)
        except Exception as exc:  # noqa: BLE001
            latency = (time.monotonic() - start) * 1000
            self._update_record_on_failure(record, str(exc), latency)
            return InvocationResult(
                capability_id=capability_id,
                success=False,
                error=str(exc),
                latency_ms=latency,
            )

        # --- Extract result ---
        latency = (time.monotonic() - start) * 1000
        success = getattr(action_result, "status", None) in (
            "completed", "COMPLETED", None  # None = caller checks result
        )
        # Treat APPROVAL_REQUIRED as not a failure (it needs user interaction)
        if getattr(action_result, "status", None) in ("APPROVAL_REQUIRED", "approval_required"):
            success = False  # Not successful yet but not an error

        error_msg = getattr(action_result, "error", None)
        output = getattr(action_result, "output", None)

        # --- Update registry health & metrics ---
        self._update_record_on_result(record, success, latency, error_msg)

        logger.info(
            "CapabilityInvoker: %r %s in %.1fms",
            capability_id, "OK" if success else "FAILED", latency,
        )

        return InvocationResult(
            capability_id=capability_id,
            success=success,
            output=output,
            error=error_msg,
            latency_ms=latency,
            action_result=action_result,
        )

    # ------------------------------------------------------------------ #
    # Action building
    # ------------------------------------------------------------------ #

    def _build_action(
        self,
        record: CapabilityRecord,
        inputs: dict[str, Any],
        subject: str,
        goal_context: str,
        user_confirmed: bool,
    ) -> Any:
        """Build an L5 Action from a CapabilityRecord's ImplementationRef."""
        from aegis.l5_execution.types import Action, ActionKind

        impl = record.implementation
        impl_type = impl.type

        if impl_type == ImplementationType.BUILTIN:
            # Map builtin action_kind to L5 ActionKind
            action_kind = self._resolve_action_kind(impl.action_kind)
            return Action(
                action_id=uuid.uuid4(),
                kind=action_kind,
                actor=subject,
                resource=f"capability:{record.capability_id}",
                parameters=inputs,
                context={
                    "capability_id": record.capability_id,
                    "goal_context": goal_context,
                },
                user_confirmed=user_confirmed,
            )

        elif impl_type == ImplementationType.MCP_TOOL:
            return Action(
                action_id=uuid.uuid4(),
                kind=ActionKind.MCP_INVOKE,
                actor=subject,
                resource=f"mcp:{impl.server_id}:{impl.tool_name}",
                parameters={
                    "server_id": impl.server_id,
                    "tool_name": impl.tool_name,
                    "tool_id": impl.tool_id,
                    "inputs": inputs,
                },
                context={
                    "capability_id": record.capability_id,
                    "goal_context": goal_context,
                },
                user_confirmed=user_confirmed,
            )

        elif impl_type == ImplementationType.EXTERNAL_AGENT:
            return Action(
                action_id=uuid.uuid4(),
                kind=ActionKind.EXTERNAL_AGENT,
                actor=subject,
                resource=f"agent:{impl.agent_id}",
                parameters={
                    "agent_id": impl.agent_id,
                    "agent_type": impl.agent_type,
                    "inputs": inputs,
                },
                context={
                    "capability_id": record.capability_id,
                    "goal_context": goal_context,
                },
                user_confirmed=user_confirmed,
            )

        elif impl_type == ImplementationType.COMPOSITE:
            raise NotImplementedError(
                "Composite capability invocation is handled by invoke_composite(), "
                "not _build_action(). Use invoke() which routes composites correctly."
            )

        raise ValueError(f"Unknown ImplementationType: {impl_type!r}")

    def _resolve_action_kind(self, action_kind_str: str) -> Any:
        """Convert a string action kind to L5 ActionKind enum value."""
        from aegis.l5_execution.types import ActionKind
        # Try direct lookup
        try:
            return ActionKind(action_kind_str)
        except ValueError:
            pass
        # Try attribute lookup by name (e.g. "fs.read" → FS_READ)
        normalized = action_kind_str.upper().replace(".", "_")
        if hasattr(ActionKind, normalized):
            return getattr(ActionKind, normalized)
        # Default to FS_READ as a safe fallback — will be blocked by policy
        logger.warning(
            "CapabilityInvoker: unknown action_kind %r — using SHELL_EXEC",
            action_kind_str,
        )
        return ActionKind.SHELL_EXEC

    # ------------------------------------------------------------------ #
    # Post-invocation updates
    # ------------------------------------------------------------------ #

    def _update_record_on_result(
        self,
        record: CapabilityRecord,
        success: bool,
        latency_ms: float,
        error: str | None,
    ) -> None:
        new_metrics = record.metrics.record_invocation(success=success, latency_ms=latency_ms)
        self._registry.update_metrics(record.capability_id, new_metrics)

        if success:
            new_health = record.health.record_success(latency_ms=latency_ms)
        else:
            new_health = record.health.record_failure(error or "unknown error")
        self._registry.update_health(record.capability_id, new_health)

    def _update_record_on_failure(
        self,
        record: CapabilityRecord,
        error: str,
        latency_ms: float,
    ) -> None:
        new_metrics = record.metrics.record_invocation(success=False, latency_ms=latency_ms)
        self._registry.update_metrics(record.capability_id, new_metrics)
        new_health = record.health.record_failure(error)
        self._registry.update_health(record.capability_id, new_health)
