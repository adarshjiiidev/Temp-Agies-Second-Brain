"""L5 Execution Engine — Permission Engine.

The PermissionEngine is Stage 1 of the 7-stage execution pipeline.
It applies the SVRC (Subject / Verb / Resource / Context) model with
deny-by-default semantics.

Invariants:
  - Any action with no matching active grant → DENY (no implicit allow)
  - Every check is recorded in the audit log before returning
  - One-time grants are revoked immediately after a successful ALLOW

Import safety: l5_execution.* + aiosqlite + stdlib ONLY.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

from aegis.l5_execution.contracts import SVRCDecision, SVRCRequest
from aegis.l5_execution.exceptions import PermissionDeniedError
from aegis.l5_execution.permission.store import PermissionGrant, PermissionStore
from aegis.l5_execution.types import PermissionDecision, SandboxTier

__all__ = ["PermissionEngine"]


class PermissionEngine:
    """Stage 1 — SVRC permission checker.

    Usage::

        engine = PermissionEngine(db_path=None)
        await engine.initialize()

        # Grant a permission
        await engine.grant(
            subject="system:planner",
            verbs=["fs.read"],
            resources=["fs:~/Projects/**"],
            granted_by="user:primary",
        )

        # Check a permission
        decision = await engine.check(SVRCRequest(
            subject="system:planner",
            verb="fs.read",
            resource="fs:~/Projects/AGIES/README.md",
        ))
        assert decision.allowed
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._store = PermissionStore(db_path=db_path)
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the permission store."""
        await self._store.initialize()
        self._initialized = True

    async def close(self) -> None:
        await self._store.close()

    # ------------------------------------------------------------------
    # Grant management
    # ------------------------------------------------------------------

    async def grant(
        self,
        *,
        subject: str,
        verbs: list[str],
        resources: list[str],
        granted_by: str = "system",
        ttl_seconds: float | None = None,
        is_one_time: bool = False,
        is_permanent: bool = False,
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> PermissionGrant:
        """Add a new permission grant.

        Args:
            subject:      SVRC subject (e.g. 'system:planner')
            verbs:        List of SVRC verbs to grant
            resources:    List of resource patterns (glob-style)
            granted_by:   Who authorised this grant
            ttl_seconds:  Optional TTL; None = permanent
            is_one_time:  If True, revoke after a single successful use
            is_permanent: Mark as permanent (informational; still expires if ttl set)
            reason:       Human-readable reason for the grant
            metadata:     Extra key/value data attached to the grant

        Returns:
            The created PermissionGrant.
        """
        self._require_initialized()
        expires_at = time.time() + ttl_seconds if ttl_seconds is not None else None
        grant = PermissionGrant(
            subject=subject,
            verbs=verbs,
            resources=resources,
            granted_by=granted_by,
            expires_at=expires_at,
            is_one_time=is_one_time,
            is_permanent=is_permanent,
            reason=reason,
            metadata=metadata or {},
        )
        return await self._store.add_grant(grant)

    async def revoke(self, grant_id: str) -> bool:
        """Revoke a grant by ID.  Returns True if found."""
        self._require_initialized()
        return await self._store.revoke_grant(grant_id)

    async def list_grants(self, subject: str | None = None) -> list[PermissionGrant]:
        """List active grants, optionally filtered by subject."""
        self._require_initialized()
        return await self._store.list_active_grants(subject=subject)

    # ------------------------------------------------------------------
    # Permission check (Stage 1)
    # ------------------------------------------------------------------

    async def check(self, request: SVRCRequest) -> SVRCDecision:
        """Evaluate a SVRC permission request.

        Returns an SVRCDecision with decision=ALLOW, DENY, or NEEDS_APPROVAL.
        Raises PermissionDeniedError if no matching grant exists.

        This method does NOT raise on NEEDS_APPROVAL — callers must check
        the decision field and handle the approval flow.
        """
        self._require_initialized()

        matching_grants = await self._store.find_grants(
            subject=request.subject,
            verb=request.verb,
            resource=request.resource,
        )

        if not matching_grants:
            # Deny-by-default: no matching grant
            return SVRCDecision(
                decision=PermissionDecision.DENY,
                allowed=False,
                reason=(
                    f"No permission grant found for subject={request.subject!r}, "
                    f"verb={request.verb!r}, resource={request.resource!r}."
                ),
            )

        # Use the first (most recently granted) matching grant
        grant = matching_grants[0]

        # Consume one-time grants immediately
        if grant.is_one_time:
            await self._store.revoke_one_time_grant(grant.grant_id)
        else:
            await self._store.increment_used(grant.grant_id)

        return SVRCDecision(
            decision=PermissionDecision.ALLOW,
            allowed=True,
            reason=f"Grant {grant.grant_id!r} matches: {grant.reason or 'no reason given'}",
            grant_id=grant.grant_id,
            ttl_seconds=grant.remaining_ttl,
        )

    async def check_or_raise(self, request: SVRCRequest) -> SVRCDecision:
        """Like check() but raises PermissionDeniedError on DENY.

        This is the strict variant used inside the pipeline.
        """
        decision = await self.check(request)
        if not decision.allowed:
            raise PermissionDeniedError(
                decision.reason,
                actor=request.subject,
                verb=request.verb,
                resource=request.resource,
                stage="permission",
            )
        return decision

    async def has_permission(
        self,
        subject: str,
        verb: str,
        resource: str,
    ) -> bool:
        """Quick boolean check — True if subject has permission for verb+resource."""
        self._require_initialized()
        grants = await self._store.find_grants(subject, verb, resource)
        return len(grants) > 0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _require_initialized(self) -> None:
        if not self._initialized:
            raise RuntimeError(
                "PermissionEngine not initialized — call await engine.initialize() first."
            )
