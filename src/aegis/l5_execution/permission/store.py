"""L5 Execution Engine — Permission Store.

SQLite-backed storage for permission grants.  Each grant records:
  - subject (SVRC Subject)
  - verbs   (list of SVRC Verbs covered)
  - resources (list of resource patterns covered, e.g. 'fs:~/Projects/**')
  - granted_by (who authorised this grant)
  - granted_at / expires_at (TTL support)
  - is_one_time (revoked after single use)
  - is_permanent (survives restarts)

Import safety: aiosqlite + stdlib + l5_execution.types/exceptions ONLY.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiosqlite

from aegis.l5_execution.exceptions import ExecutionEngineError

__all__ = ["PermissionGrant", "PermissionStore"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS permission_grants (
    grant_id        TEXT PRIMARY KEY,
    subject         TEXT NOT NULL,
    verbs           TEXT NOT NULL,          -- JSON list of verb strings
    resources       TEXT NOT NULL,          -- JSON list of resource patterns
    granted_by      TEXT NOT NULL,
    granted_at      REAL NOT NULL,
    expires_at      REAL,                   -- NULL = permanent
    is_one_time     INTEGER NOT NULL DEFAULT 0,
    is_permanent    INTEGER NOT NULL DEFAULT 0,
    reason          TEXT,
    used_count      INTEGER NOT NULL DEFAULT 0,
    revoked         INTEGER NOT NULL DEFAULT 0,
    revoked_at      REAL,
    metadata        TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_grants_subject ON permission_grants(subject);
CREATE INDEX IF NOT EXISTS idx_grants_revoked ON permission_grants(revoked);
CREATE INDEX IF NOT EXISTS idx_grants_expires ON permission_grants(expires_at);
"""


@dataclass
class PermissionGrant:
    """A stored permission grant record."""

    grant_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    subject: str = ""
    verbs: list[str] = field(default_factory=list)
    resources: list[str] = field(default_factory=list)
    granted_by: str = "system"
    granted_at: float = field(default_factory=time.time)
    expires_at: float | None = None
    is_one_time: bool = False
    is_permanent: bool = False
    reason: str = ""
    used_count: int = 0
    revoked: bool = False
    revoked_at: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        """True if the grant is currently valid."""
        if self.revoked:
            return False
        if self.expires_at is not None and time.time() > self.expires_at:
            return False
        return True

    @property
    def remaining_ttl(self) -> float | None:
        """Seconds until expiry, or None if permanent."""
        if self.expires_at is None:
            return None
        return max(0.0, self.expires_at - time.time())


class PermissionStore:
    """Async SQLite-backed store for permission grants.

    In-memory mode (db_path=None) is fully supported for tests.

    Usage::

        store = PermissionStore(db_path=None)
        await store.initialize()
        grant = PermissionGrant(
            subject="system:planner",
            verbs=["fs.read", "fs.write"],
            resources=["fs:~/Projects/**"],
            granted_by="user:primary",
        )
        await store.add_grant(grant)
        matching = await store.find_grants("system:planner", "fs.write", "fs:~/Projects/foo.py")
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = str(db_path) if db_path else ":memory:"
        self._conn: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """Open the database and apply schema."""
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(_SCHEMA)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    def _require_conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise ExecutionEngineError(
                "PermissionStore not initialized — call await store.initialize() first."
            )
        return self._conn

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    async def add_grant(self, grant: PermissionGrant) -> PermissionGrant:
        """Persist a new permission grant."""
        conn = self._require_conn()
        await conn.execute(
            """
            INSERT INTO permission_grants
              (grant_id, subject, verbs, resources, granted_by, granted_at,
               expires_at, is_one_time, is_permanent, reason,
               used_count, revoked, revoked_at, metadata)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                grant.grant_id,
                grant.subject,
                json.dumps(grant.verbs),
                json.dumps(grant.resources),
                grant.granted_by,
                grant.granted_at,
                grant.expires_at,
                int(grant.is_one_time),
                int(grant.is_permanent),
                grant.reason,
                grant.used_count,
                int(grant.revoked),
                grant.revoked_at,
                json.dumps(grant.metadata),
            ),
        )
        await conn.commit()
        return grant

    async def revoke_grant(self, grant_id: str) -> bool:
        """Revoke a grant by ID.  Returns True if the grant was found."""
        conn = self._require_conn()
        cursor = await conn.execute(
            "UPDATE permission_grants SET revoked=1, revoked_at=? WHERE grant_id=?",
            (time.time(), grant_id),
        )
        await conn.commit()
        return cursor.rowcount > 0

    async def increment_used(self, grant_id: str) -> None:
        """Increment the usage counter for a grant."""
        conn = self._require_conn()
        await conn.execute(
            "UPDATE permission_grants SET used_count = used_count + 1 WHERE grant_id=?",
            (grant_id,),
        )
        await conn.commit()

    async def revoke_one_time_grant(self, grant_id: str) -> None:
        """Revoke a one-time grant after it has been consumed."""
        await self.revoke_grant(grant_id)

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def find_grants(
        self,
        subject: str,
        verb: str,
        resource: str,
    ) -> list[PermissionGrant]:
        """Find active grants matching a given SVRC triple.

        Resource matching is done in Python (glob-style) after fetching
        candidates by subject.  Verb matching also uses the verb_implies
        hierarchy.
        """
        from aegis.l5_execution.permission.verbs import verb_implies

        conn = self._require_conn()
        now = time.time()

        # Fetch all non-revoked, non-expired grants for this subject
        # (also include wildcard subjects)
        cursor = await conn.execute(
            """
            SELECT * FROM permission_grants
            WHERE revoked = 0
              AND (subject = ? OR subject = '*')
              AND (expires_at IS NULL OR expires_at > ?)
            ORDER BY granted_at DESC
            """,
            (subject, now),
        )
        rows = await cursor.fetchall()

        matching: list[PermissionGrant] = []
        for row in rows:
            grant = self._row_to_grant(row)
            # Check verb
            if not any(verb_implies(gv, verb) for gv in grant.verbs):
                continue
            # Check resource (simple prefix/glob — see _resource_matches)
            if not any(_resource_matches(gr, resource) for gr in grant.resources):
                continue
            matching.append(grant)

        return matching

    async def get_grant(self, grant_id: str) -> PermissionGrant | None:
        """Fetch a single grant by ID."""
        conn = self._require_conn()
        cursor = await conn.execute(
            "SELECT * FROM permission_grants WHERE grant_id=?", (grant_id,)
        )
        row = await cursor.fetchone()
        return self._row_to_grant(row) if row else None

    async def list_active_grants(self, subject: str | None = None) -> list[PermissionGrant]:
        """List all non-revoked, non-expired grants, optionally filtered by subject."""
        conn = self._require_conn()
        now = time.time()
        if subject:
            cursor = await conn.execute(
                """
                SELECT * FROM permission_grants
                WHERE revoked=0 AND subject=?
                  AND (expires_at IS NULL OR expires_at > ?)
                ORDER BY granted_at DESC
                """,
                (subject, now),
            )
        else:
            cursor = await conn.execute(
                """
                SELECT * FROM permission_grants
                WHERE revoked=0
                  AND (expires_at IS NULL OR expires_at > ?)
                ORDER BY granted_at DESC
                """,
                (now,),
            )
        rows = await cursor.fetchall()
        return [self._row_to_grant(r) for r in rows]

    async def expire_old_grants(self) -> int:
        """Mark expired grants as revoked.  Returns the count of expired grants."""
        conn = self._require_conn()
        cursor = await conn.execute(
            """
            UPDATE permission_grants
            SET revoked=1, revoked_at=?
            WHERE revoked=0 AND expires_at IS NOT NULL AND expires_at <= ?
            """,
            (time.time(), time.time()),
        )
        await conn.commit()
        return cursor.rowcount

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_grant(row: aiosqlite.Row) -> PermissionGrant:
        return PermissionGrant(
            grant_id=row["grant_id"],
            subject=row["subject"],
            verbs=json.loads(row["verbs"]),
            resources=json.loads(row["resources"]),
            granted_by=row["granted_by"],
            granted_at=float(row["granted_at"]),
            expires_at=float(row["expires_at"]) if row["expires_at"] is not None else None,
            is_one_time=bool(row["is_one_time"]),
            is_permanent=bool(row["is_permanent"]),
            reason=row["reason"] or "",
            used_count=int(row["used_count"]),
            revoked=bool(row["revoked"]),
            revoked_at=float(row["revoked_at"]) if row["revoked_at"] is not None else None,
            metadata=json.loads(row["metadata"]),
        )


def _resource_matches(pattern: str, resource: str) -> bool:
    """Simple glob-style resource matching.

    Patterns:
      '*'          matches everything
      'fs:*'       matches any filesystem resource
      'fs:~/Proj/**' matches any path under ~/Proj/
      Exact match  matches only that exact resource string
    """
    import fnmatch

    if pattern == "*":
        return True
    if pattern == resource:
        return True
    return fnmatch.fnmatch(resource, pattern)
