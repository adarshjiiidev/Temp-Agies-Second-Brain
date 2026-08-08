"""P07 Observer — ObserverAudit.

Every observation (record or lifecycle event) produces an immutable audit
log entry. This ensures all observer activity is traceable even if the
observation data itself is ephemeral and purged on shutdown.

Import safety: stdlib ONLY.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID


__all__ = ["AuditEventKind", "ObserverAuditEntry", "ObserverAuditLog"]


class AuditEventKind(str, Enum):
    OBSERVER_STARTED  = "observer_started"
    OBSERVER_PAUSED   = "observer_paused"
    OBSERVER_RESUMED  = "observer_resumed"
    OBSERVER_STOPPED  = "observer_stopped"
    EVENT_RECORDED    = "event_recorded"
    EVENT_BLOCKED     = "event_blocked"     # Blocked by privacy zone
    SINK_FLUSHED      = "sink_flushed"
    SINK_DRAINED      = "sink_drained"
    CONSENT_GRANTED   = "consent_granted"
    CONSENT_REVOKED   = "consent_revoked"


@dataclass(frozen=True)
class ObserverAuditEntry:
    """Immutable record of an observer lifecycle or event action."""
    kind: AuditEventKind
    session_id: str
    timestamp: float = field(default_factory=time.time)
    id: UUID = field(default_factory=uuid.uuid4)
    detail: dict[str, Any] = field(default_factory=dict)


class ObserverAuditLog:
    """In-memory append-only audit log for the observer.

    The audit log is separate from the observation sink. It is NOT purged
    on observer shutdown — it is retained for the session lifetime so that
    lifecycle events (start/stop) remain auditable even after observations
    are drained.

    For production use, this should be persisted to a durable log (L2
    EventBus or L4 T3_SEMANTIC). In P07 it is in-memory only.
    """

    def __init__(self) -> None:
        self._entries: list[ObserverAuditEntry] = []

    def append(self, kind: AuditEventKind, session_id: str, **detail: Any) -> ObserverAuditEntry:
        entry = ObserverAuditEntry(kind=kind, session_id=session_id, detail=dict(detail))
        self._entries.append(entry)
        return entry

    @property
    def entries(self) -> list[ObserverAuditEntry]:
        return list(self._entries)

    def entries_for_session(self, session_id: str) -> list[ObserverAuditEntry]:
        return [e for e in self._entries if e.session_id == session_id]

    def __len__(self) -> int:
        return len(self._entries)
