"""L5 Execution Engine — Sandbox Manager.

Stage 5: selects the appropriate sandbox tier and creates the SandboxContext
for the executor to use.  Tier is assigned by the Policy Engine decision;
the SandboxManager enforces resource limits and prepares workspaces.

Tier mapping:
  T0_NONE      → no isolation (trusted reads only)
  T1_AST       → T1ASTJail (in-process, no I/O)
  T2_SUBPROCESS → T2SubprocessSandbox (isolated process + workspace)
  T3_DOCKER    → T3DockerSandbox (container; requires Docker)
  T4_FIRECRACKER → not yet implemented; raises NotImplementedError

Import safety: stdlib + l5_execution.* ONLY.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aegis.l5_execution.contracts import PolicyDecision, SandboxContext
from aegis.l5_execution.sandbox.workspace import TempWorkspace
from aegis.l5_execution.types import Action, SandboxTier

__all__ = ["SandboxManager"]


class SandboxManager:
    """Stage 5 sandbox context builder.

    Usage::

        manager = SandboxManager()
        sandbox_ctx = manager.build_context(action, policy_decision)
        # Pass sandbox_ctx to executor.execute(action, sandbox_ctx)
    """

    def __init__(
        self,
        *,
        default_timeout_seconds: float = 30.0,
        docker_image: str = "python:3.12-slim",
    ) -> None:
        self._default_timeout = default_timeout_seconds
        self._docker_image = docker_image

    def build_context(
        self,
        action: Action,
        policy_decision: PolicyDecision,
        *,
        executor_timeout: float | None = None,
    ) -> SandboxContext:
        """Build a SandboxContext for the given action and policy decision.

        Returns a SandboxContext (frozen Pydantic model) ready to pass to
        the executor.  Does NOT start the sandbox — the executor owns that.
        """
        tier = policy_decision.required_sandbox_tier or self._infer_tier(action)

        timeout = executor_timeout or self._default_timeout

        # Build a workspace path for T2+ (the executor creates the actual dir)
        workspace_path: str | None = None
        if tier.ordinal >= SandboxTier.T2_SUBPROCESS.ordinal:
            # We create a workspace and encode the path; executor cleans it up
            ws = TempWorkspace.create(f"aegis-{action.kind.value.replace('.', '-')}")
            workspace_path = str(ws.path)

        # T4 Firecracker: stub
        if tier is SandboxTier.T4_FIRECRACKER:
            raise NotImplementedError(
                "T4 Firecracker sandbox is not yet implemented (planned for P08+). "
                "Use T3_DOCKER for CRITICAL risk actions."
            )

        return SandboxContext(
            tier=tier,
            workspace_path=workspace_path,
            timeout_seconds=timeout,
            max_memory_bytes=self._memory_limit_for_tier(tier),
            network_allowed=self._network_allowed_for_tier(tier, action),
            dry_run=action.dry_run,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _infer_tier(action: Action) -> SandboxTier:
        """Fallback tier inference when policy didn't set one."""
        verb = action.kind.value
        if verb.startswith("fs.read") or verb.startswith("git.status") \
                or verb.startswith("git.diff") or verb.startswith("git.log"):
            return SandboxTier.T0_NONE
        if verb.startswith("python.") or verb.startswith("python.eval"):
            return SandboxTier.T1_AST
        if verb.startswith("shell.") or verb.startswith("proc.") \
                or verb.startswith("git.") or verb.startswith("fs.write"):
            return SandboxTier.T2_SUBPROCESS
        if verb.startswith("docker."):
            return SandboxTier.T3_DOCKER
        return SandboxTier.T2_SUBPROCESS  # safe default

    @staticmethod
    def _memory_limit_for_tier(tier: SandboxTier) -> int | None:
        limits: dict[SandboxTier, int | None] = {
            SandboxTier.T0_NONE: None,
            SandboxTier.T1_AST: 64 * 1024 * 1024,       # 64 MB
            SandboxTier.T2_SUBPROCESS: 512 * 1024 * 1024, # 512 MB
            SandboxTier.T3_DOCKER: 256 * 1024 * 1024,    # 256 MB (set in Docker flags)
            SandboxTier.T4_FIRECRACKER: None,
        }
        return limits.get(tier)

    @staticmethod
    def _network_allowed_for_tier(tier: SandboxTier, action: Action) -> bool:
        """Network is off by default for T1/T2; available via explicit grant for T0/T3."""
        if tier in (SandboxTier.T1_AST, SandboxTier.T2_SUBPROCESS):
            return False
        if tier is SandboxTier.T3_DOCKER:
            return False  # container --network=none by default
        # T0: allow if action.kind is a net.* verb
        return action.kind.value.startswith("net.")
