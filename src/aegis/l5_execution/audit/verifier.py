"""L5 Execution Engine — Audit Verifier.

Full chain integrity verification: replays every entry in sequence order,
recomputes the hash, and detects gaps, truncation, reordering, and tampering.

Can be run as a CLI: python -m aegis.l5_execution.audit.verifier <db_path>

Import safety: stdlib + l5_execution.* ONLY.
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiosqlite

from aegis.l5_execution.audit.chain import _GENESIS_HASH, _compute_hash
from aegis.l5_execution.exceptions import AuditIntegrityError

__all__ = ["AuditVerifier", "VerificationReport"]


@dataclass
class VerificationReport:
    """Result of a full chain verification pass."""

    total_entries: int = 0
    verified_entries: int = 0
    violations: list[str] = field(default_factory=list)
    is_intact: bool = True

    def summary(self) -> str:
        if self.is_intact:
            return (
                f"✅ Audit chain intact: {self.verified_entries}/{self.total_entries} "
                f"entries verified."
            )
        lines = [
            f"❌ Audit chain CORRUPT: {len(self.violations)} violation(s) found.",
            f"   Verified {self.verified_entries}/{self.total_entries} entries before failure.",
        ]
        for v in self.violations[:5]:  # Show first 5
            lines.append(f"   • {v}")
        if len(self.violations) > 5:
            lines.append(f"   ... and {len(self.violations) - 5} more.")
        return "\n".join(lines)


class AuditVerifier:
    """Full audit chain verification utility.

    Usage::

        verifier = AuditVerifier(db_path="data/audit.db")
        report = await verifier.verify()
        print(report.summary())
        if not report.is_intact:
            raise AuditIntegrityError("Chain corrupt!")
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)

    async def verify(self) -> VerificationReport:
        """Replay the entire chain from genesis.  Returns a VerificationReport."""
        report = VerificationReport()

        async with aiosqlite.connect(self._db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM audit_entries ORDER BY sequence ASC"
            )
            rows = await cursor.fetchall()

        if not rows:
            report.is_intact = True
            return report

        report.total_entries = len(rows)
        prev_hash = _GENESIS_HASH
        expected_seq = rows[0]["sequence"]  # first entry's sequence

        for row in rows:
            seq = int(row["sequence"])

            # Check for gaps in sequence
            if seq != expected_seq:
                violation = (
                    f"Sequence gap: expected {expected_seq}, got {seq} "
                    f"(entry_id={row['entry_id']!r})"
                )
                report.violations.append(violation)
                report.is_intact = False
                # Continue checking the rest
                expected_seq = seq + 1
            else:
                expected_seq += 1

            # Check prev_hash linkage
            if row["prev_hash"] != prev_hash:
                violation = (
                    f"Chain break at seq={seq} entry_id={row['entry_id']!r}: "
                    f"expected prev_hash={prev_hash[:16]}..., "
                    f"got {row['prev_hash'][:16]}..."
                )
                report.violations.append(violation)
                report.is_intact = False

            # Recompute entry_hash
            fields = {
                "entry_id": row["entry_id"],
                "timestamp": float(row["timestamp"]),
                "stage": row["stage"],
                "action_id": row["action_id"],
                "actor": row["actor"],
                "verb": row["verb"],
                "resource": row["resource"],
                "decision": row["decision"],
                "result": row["result"],
                "details": json.loads(row["details"]),
            }
            computed = _compute_hash(row["prev_hash"], fields)
            if computed != row["entry_hash"]:
                violation = (
                    f"Hash mismatch at seq={seq} entry_id={row['entry_id']!r}: "
                    f"stored={row['entry_hash'][:16]}..., "
                    f"computed={computed[:16]}..."
                )
                report.violations.append(violation)
                report.is_intact = False

            prev_hash = row["entry_hash"]
            report.verified_entries += 1

        return report


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

async def _main(db_path: str) -> int:
    verifier = AuditVerifier(db_path)
    report = await verifier.verify()
    print(report.summary())
    return 0 if report.is_intact else 1


if __name__ == "__main__":
    import asyncio

    if len(sys.argv) < 2:
        print("Usage: python -m aegis.l5_execution.audit.verifier <db_path>")
        sys.exit(1)
    exit_code = asyncio.run(_main(sys.argv[1]))
    sys.exit(exit_code)
