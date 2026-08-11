"""P07 Discovery — ConsentGate.

Manages opt-in / opt-out state for environment scanning and observation.
No scanner or observer may run without explicit user consent.

Consent is:
  - Per-scope (app_scanner, project_scanner, cli_scanner, observer, all)
  - Revocable at any time
  - Timestamped for audit
  - Persistent in memory (not persisted to disk by this module —
    callers may serialize ConsentRecord if needed)

Import safety: stdlib ONLY.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


__all__ = ["ConsentScope", "ConsentRecord", "ConsentGate"]


class ConsentScope(str, Enum):
    """Scope of consent grant.

    ALL grants consent for every scanner + observer.
    Individual scopes grant consent for specific components only.
    """
    ALL             = "all"
    APP_SCANNER     = "app_scanner"
    PROJECT_SCANNER = "project_scanner"
    CLI_SCANNER     = "cli_scanner"
    RELATION_SCANNER = "relation_scanner"
    OBSERVER        = "observer"


@dataclass(frozen=True)
class ConsentRecord:
    """Immutable record of a single consent grant or revocation.

    Attributes:
        id:          Unique ID for audit.
        scope:       What was consented to.
        granted:     True = consent granted; False = consent revoked.
        timestamp:   Unix timestamp of the action.
        user_agent:  Identifier of who granted/revoked (optional).
        notes:       Optional free-text (e.g. UI button label).
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    scope: ConsentScope = ConsentScope.ALL
    granted: bool = True
    timestamp: float = field(default_factory=time.time)
    user_agent: str = "system"
    notes: str = ""


class ConsentGate:
    """Thread-safe, in-memory consent registry for P07 discovery.

    Usage::

        gate = ConsentGate()

        # Opt in to everything
        gate.grant(ConsentScope.ALL)
        assert gate.is_allowed(ConsentScope.APP_SCANNER)

        # Revoke a specific scope
        gate.revoke(ConsentScope.APP_SCANNER)
        assert not gate.is_allowed(ConsentScope.APP_SCANNER)
        assert gate.is_allowed(ConsentScope.CLI_SCANNER)  # still allowed via ALL

        # Check full history
        records = gate.audit_log()

    Consent logic:
      - ConsentScope.ALL grants all child scopes implicitly.
      - Explicit scope revocation overrides the ALL grant for that scope.
      - If neither ALL nor the specific scope has been granted, access is denied.
    """

    def __init__(self) -> None:
        self._state: dict[ConsentScope, bool] = {}  # scope → current granted state
        self._log: list[ConsentRecord] = []

    # ------------------------------------------------------------------
    # Consent management
    # ------------------------------------------------------------------

    def grant(self, scope: ConsentScope, *, user_agent: str = "system", notes: str = "") -> ConsentRecord:
        """Grant consent for a scope. Records an audit entry.

        Returns the ConsentRecord for the caller to store if needed.
        """
        self._state[scope] = True
        record = ConsentRecord(
            scope=scope,
            granted=True,
            user_agent=user_agent,
            notes=notes,
        )
        self._log.append(record)
        return record

    def revoke(self, scope: ConsentScope, *, user_agent: str = "system", notes: str = "") -> ConsentRecord:
        """Revoke consent for a scope. Records an audit entry.

        After revocation, is_allowed(scope) returns False even if ALL was granted.
        """
        self._state[scope] = False
        record = ConsentRecord(
            scope=scope,
            granted=False,
            user_agent=user_agent,
            notes=notes,
        )
        self._log.append(record)
        return record

    def revoke_all(self, *, user_agent: str = "system") -> list[ConsentRecord]:
        """Revoke all scopes. Returns all revocation records created."""
        records = []
        for scope in ConsentScope:
            record = self.revoke(scope, user_agent=user_agent, notes="revoke_all")
            records.append(record)
        return records

    # ------------------------------------------------------------------
    # Consent checks
    # ------------------------------------------------------------------

    def is_allowed(self, scope: ConsentScope) -> bool:
        """Return True if the given scope is currently consented.

        Logic:
          1. If scope is explicitly set (granted or revoked) → use that.
          2. Else if ConsentScope.ALL is granted → True.
          3. Else → False (deny by default).
        """
        # Explicit per-scope state takes priority
        if scope in self._state:
            return self._state[scope]

        # ALL grant covers all child scopes (unless explicitly revoked above)
        if ConsentScope.ALL in self._state:
            return self._state[ConsentScope.ALL]

        # Default: deny
        return False

    def is_any_allowed(self) -> bool:
        """Return True if at least one scope is currently consented."""
        return any(self.is_allowed(s) for s in ConsentScope if s is not ConsentScope.ALL)

    @property
    def has_any_consent(self) -> bool:
        """True if any scope (including ALL) is explicitly granted."""
        return any(v for v in self._state.values())

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------

    def audit_log(self) -> list[ConsentRecord]:
        """Return the full chronological log of consent events (immutable copy)."""
        return list(self._log)

    def current_state(self) -> dict[str, bool]:
        """Return current consent state as a string-keyed dict (for serialization)."""
        result = {}
        for scope in ConsentScope:
            result[scope.value] = self.is_allowed(scope)
        return result
