"""P07 Observer — Event types.

Coarse-grained typed events recorded by the behavior observer.
All events are opt-in and privacy-zone filtered before storage.

Import safety: stdlib ONLY.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID


__all__ = ["EventKind", "ObservedEvent"]


class EventKind(str, Enum):
    """Coarse event types recorded by the synthetic observer."""
    APP_OPEN      = "app_open"      # Application launched by AEGIS or observed
    APP_CLOSE     = "app_close"     # Application closed
    FILE_TOUCH    = "file_touch"    # File read/written via an AEGIS action
    CMD_RUN       = "cmd_run"       # CLI command executed via AEGIS
    PROJECT_OPEN  = "project_open"  # Project root accessed
    TOOL_USE      = "tool_use"      # A tool/CLI invoked
    SEARCH_QUERY  = "search_query"  # Search query issued


@dataclass
class ObservedEvent:
    """A single coarse-grained observation event.

    Attributes:
        kind:         Type of event.
        subject:      What was acted on (app name, file path, command, etc.).
        session_id:   The observer session this event belongs to.
        timestamp:    Unix timestamp of the event.
        context:      Additional key/value context (bounded dict).
        privacy_tier: Privacy tier assigned after zone check.
        id:           UUID for deduplication.
    """
    kind: EventKind
    subject: str
    session_id: str
    timestamp: float = field(default_factory=time.time)
    context: dict = field(default_factory=dict)
    privacy_tier: str = "P2"
    id: UUID = field(default_factory=uuid.uuid4)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "kind": self.kind.value,
            "subject": self.subject,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "privacy_tier": self.privacy_tier,
            "context": self.context,
        }
