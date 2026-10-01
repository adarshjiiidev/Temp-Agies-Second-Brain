"""P07 Model — core types for environment graph nodes and edges.

Import safety: l4_memory.types + stdlib ONLY.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


__all__ = [
    "EnvNodeKind",
    "EnvEdgeKind",
    "ScannerState",
    "ObserverState",
    "CandidateStatus",
    "EnvNode",
    "EnvEdge",
    "ScanResult",
]


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class EnvNodeKind(str, Enum):
    """Environment graph node type.

    Mirrors EntityKind additions added in P07 but kept as a local enum
    to avoid coupling model/ to the L4 types module directly.
    The persistence layer maps these to EntityKind on write.
    """
    APPLICATION = "application"
    PROJECT = "project"
    REPOSITORY = "repository"
    TOOL = "tool"
    DEV_ENVIRONMENT = "dev_environment"
    DEVICE = "device"
    ACCOUNT = "account"
    WORKSPACE = "workspace"
    TECHNOLOGY = "technology"


class EnvEdgeKind(str, Enum):
    """Environment graph edge (relationship) type."""
    USES = "uses"
    CONTAINS = "contains"
    DEPENDS_ON = "depends_on"
    RUNS_ON = "runs_on"
    DEPLOYS_THROUGH = "deploys_through"
    MANAGES = "manages"
    RELATED_TO = "related_to"
    VERSION_OF = "version_of"


class ScannerState(str, Enum):
    """Lifecycle state of a scanner run."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    DONE = "done"
    FAILED = "failed"
    DISABLED = "disabled"


class ObserverState(str, Enum):
    """Lifecycle state of the behavior observer."""
    STOPPED = "stopped"      # Not running; no records being written
    RUNNING = "running"      # Active; writing events
    PAUSED = "paused"        # Temporarily suspended; no new events
    DRAINING = "draining"    # Shutting down; purging transient records


class CandidateStatus(str, Enum):
    """Status of an inference candidate (workflow or preference).

    Candidates NEVER auto-promote — they remain PENDING_REVIEW until
    explicit user action.
    """
    PENDING_REVIEW = "pending_review"   # Created; awaiting user decision
    ACCEPTED = "accepted"               # User promoted to active memory tier
    REJECTED = "rejected"               # User dismissed; stays rejected
    EXPIRED = "expired"                 # TTL elapsed; auto-purged


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EnvNode:
    """A single node in the environment model graph.

    All fields are plain Python types to keep model/ stdlib-only.
    The persistence layer serializes these into KGEntity records.
    """
    key: str                            # Stable unique key (e.g. "app:notepad.exe")
    kind: EnvNodeKind
    label: str                          # Human-readable display name
    namespace: str = "p07_env"
    privacy_tier: str = "P2"
    attributes: dict[str, Any] = field(default_factory=dict)
    source_path: str | None = None      # Where this was discovered (for zone checks)
    scanned_at: float = 0.0             # Unix timestamp of last scan
    version: str | None = None          # Version string if known


@dataclass(frozen=True)
class EnvEdge:
    """A directed relationship between two EnvNodes."""
    subject_key: str
    object_key: str
    kind: EnvEdgeKind
    confidence: float = 0.7
    privacy_tier: str = "P2"
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScanResult:
    """Output of a single scanner run.

    Attributes:
        scanner_name:  Which scanner produced this result.
        nodes:         New or updated environment nodes discovered.
        edges:         Relationships inferred between nodes.
        truncated:     True if the scan hit max_results or max_seconds cap.
        duration_s:    Wall-clock time of the scan in seconds.
        error:         Non-None if the scan raised a recoverable error.
    """
    scanner_name: str
    nodes: list[EnvNode] = field(default_factory=list)
    edges: list[EnvEdge] = field(default_factory=list)
    truncated: bool = False
    duration_s: float = 0.0
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None
