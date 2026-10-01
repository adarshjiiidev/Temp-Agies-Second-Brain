"""L5 Execution Engine — Audit Chain.

Append-only, SHA-256 hash-chained SQLite audit log.

Every entry is linked to the previous entry's hash.  Tampering with any
entry breaks the chain and is detectable by AuditVerifier.

Invariants:
  - Entries are append-only (no UPDATE, no DELETE)
  - Each entry stores SHA-256(prev_hash + entry_fields)
  - The sequence number is monotonically increasing
  - The AuditChain is the ONLY writer to its SQLite file

Import safety: aiosqlite + stdlib + l5_execution.types/contracts ONLY.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any

import aiosqlite

from aegis.l5_execution.contracts import AuditEntryModel
from aegis.l5_execution.exceptions import AuditIntegrityError
from aegis.l5_execution.types import AuditStage

__all__ = ["AuditChain"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_entries (
    sequence    INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id    TEXT NOT NULL UNIQUE,
    timestamp   REAL NOT NULL,
    stage       TEXT NOT NULL,
    action_id   TEXT NOT NULL,
    actor       TEXT NOT NULL,
    verb        TEXT NOT NULL,
    resource    TEXT NOT NULL,
    decision    TEXT NOT NULL,
    result      TEXT NOT NULL,
    details     TEXT NOT NULL DEFAULT '{}',
    prev_hash   TEXT NOT NULL,
    entry_hash  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_entries(action_id);
CREATE INDEX IF NOT EXISTS idx_audit_stage  ON audit_entries(stage);
CREATE INDEX IF NOT EXISTS idx_audit_time   ON audit_entries(timestamp);
"""

# Sentinel hash for the first entry in the chain
_GENESIS_HASH = "0" * 64


def _compute_hash(prev_hash: str, fields: dict[str, Any]) -> str:
    """Compute SHA-256(prev_hash + canonical JSON of fields)."""
    canonical = json.dumps(fields, sort_keys=True, separators=(",", ":"))
    data = prev_hash + canonical
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


class AuditChain:
    """Append-only hash-chained audit log.

    Usage::

        chain = AuditChain(db_path=None)  # in-memory for tests
        await chain.initialize()

        entry_id = await chain.append(
            stage=AuditStage.PERMISSION,
            action_id="...",
            actor="system:planner",
            verb="fs.write",
            resource="fs:~/notes.md",
            decision="ALLOW",
            result="SUCCESS",
            details={"grant_id": "..."},
        )
        await chain.close()
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = str(db_path) if db_path else ":memory:"
        self._conn: aiosqlite.Connection | None = None
        self._last_hash: str = _GENESIS_HASH
        self._sequence: int = 0

    async def initialize(self) -> None:
        """Open the database, apply schema, and load chain tail."""
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(_SCHEMA)
        await self._conn.commit()
        # Restore the last hash from DB (for crash recovery)
        await self._restore_chain_tail()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def append(
        self,
        *,
        stage: AuditStage,
        action_id: str,
        actor: str,
        verb: str,
        resource: str,
        decision: str,
        result: str,
        details: dict[str, Any] | None = None,
    ) -> str:
        """Append a new entry to the audit chain.

        Returns:
            The entry_id (UUID string) of the created entry.
        """
        conn = self._require_conn()

        entry_id = str(uuid.uuid4())
        ts = time.time()
        details_dict = details or {}

        fields = {
            "entry_id": entry_id,
            "timestamp": ts,
            "stage": stage.value,
            "action_id": action_id,
            "actor": actor,
            "verb": verb,
            "resource": resource,
            "decision": decision,
            "result": result,
            "details": details_dict,
        }
        entry_hash = _compute_hash(self._last_hash, fields)

        await conn.execute(
            """
            INSERT INTO audit_entries
              (entry_id, timestamp, stage, action_id, actor, verb, resource,
               decision, result, details, prev_hash, entry_hash)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                entry_id,
                ts,
                stage.value,
                str(action_id),
                actor,
                verb,
                resource,
                decision,
                result,
                json.dumps(details_dict),
                self._last_hash,
                entry_hash,
            ),
        )
        await conn.commit()

        self._last_hash = entry_hash
        self._sequence += 1
        return entry_id

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_entries_for_action(self, action_id: str) -> list[AuditEntryModel]:
        """Return all audit entries for a given action_id, in sequence order."""
        conn = self._require_conn()
        cursor = await conn.execute(
            "SELECT * FROM audit_entries WHERE action_id=? ORDER BY sequence ASC",
            (str(action_id),),
        )
        rows = await cursor.fetchall()
        return [self._row_to_model(row) for row in rows]

    async def get_recent(self, limit: int = 100) -> list[AuditEntryModel]:
        """Return the most recent N entries."""
        conn = self._require_conn()
        cursor = await conn.execute(
            "SELECT * FROM audit_entries ORDER BY sequence DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [self._row_to_model(row) for row in reversed(rows)]

    async def count(self) -> int:
        """Return total number of entries in the chain."""
        conn = self._require_conn()
        cursor = await conn.execute("SELECT COUNT(*) FROM audit_entries")
        row = await cursor.fetchone()
        return int(row[0]) if row else 0

    # ------------------------------------------------------------------
    # Verification (quick check — full check in AuditVerifier)
    # ------------------------------------------------------------------

    async def verify_last_n(self, n: int = 100) -> bool:
        """Quickly verify the hash chain for the last N entries.

        Returns True if the chain is intact.
        Raises AuditIntegrityError on the first detected violation.
        """
        conn = self._require_conn()
        cursor = await conn.execute(
            "SELECT * FROM audit_entries ORDER BY sequence ASC"
        )
        rows = await cursor.fetchall()

        if not rows:
            return True

        # Only verify last n
        rows = rows[-n:] if len(rows) > n else rows
        prev_hash = rows[0]["prev_hash"]

        for row in rows:
            model = self._row_to_model(row)
            fields = {
                "entry_id": model.entry_id,
                "timestamp": model.timestamp,
                "stage": model.stage.value,
                "action_id": model.action_id,
                "actor": model.actor,
                "verb": model.verb,
                "resource": model.resource,
                "decision": model.decision,
                "result": model.result,
                "details": model.details,
            }
            expected = _compute_hash(prev_hash, fields)
            if expected != model.entry_hash:
                raise AuditIntegrityError(
                    f"Hash mismatch at entry {model.entry_id!r} (seq={model.sequence}). "
                    f"Chain integrity violation detected.",
                    entry_id=model.entry_id,
                    expected_hash=expected,
                    actual_hash=model.entry_hash,
                )
            prev_hash = model.entry_hash

        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _restore_chain_tail(self) -> None:
        """Load the last entry's hash from DB after restart."""
        conn = self._require_conn()
        cursor = await conn.execute(
            "SELECT entry_hash, sequence FROM audit_entries ORDER BY sequence DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        if row:
            self._last_hash = row["entry_hash"]
            self._sequence = int(row["sequence"])

    def _require_conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError(
                "AuditChain not initialized — call await chain.initialize() first."
            )
        return self._conn

    @staticmethod
    def _row_to_model(row: aiosqlite.Row) -> AuditEntryModel:
        return AuditEntryModel(
            entry_id=row["entry_id"],
            timestamp=float(row["timestamp"]),
            stage=AuditStage(row["stage"]),
            action_id=row["action_id"],
            actor=row["actor"],
            verb=row["verb"],
            resource=row["resource"],
            decision=row["decision"],
            result=row["result"],
            details=json.loads(row["details"]),
            prev_hash=row["prev_hash"],
            entry_hash=row["entry_hash"],
            sequence=int(row["sequence"]),
        )
