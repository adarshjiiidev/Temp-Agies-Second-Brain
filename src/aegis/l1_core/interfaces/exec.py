"""L1 Forward-declared Execution Kernel interfaces.
Prompt 02: Protocols ONLY. Concrete implementations in Prompt 05."""
from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable
from uuid import UUID


class ActionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"  # e.g. NEEDS_APPROVAL


@dataclass(frozen=True)
class Action:
    """Typed side-effecting action descriptor. Always SVRC-gated in Prompt 05+."""

    action_id: UUID
    action_type: str
    verb: str
    resource: str
    input: dict[str, Any] = field(default_factory=dict)
    correlation_id: UUID | None = None
    reason: str | None = None
    subject: str = "system:core_runtime"


@dataclass(frozen=True)
class ActionResult:
    action_id: UUID
    status: ActionStatus
    output: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    latency_ms: int = 0
    audit_trail: list[str] = field(default_factory=list)


@runtime_checkable
class Executor(Protocol):
    """Every executor (CLI/FS/Process/Git/...) implements this Protocol."""

    @property  # type: ignore[override,unused-ignore]
    @abstractmethod
    def executor_id(self) -> str: ...

    @abstractmethod
    async def execute(self, action: Action) -> ActionResult: ...  # pragma: no cover

    @abstractmethod
    async def cancel(self, action_id: UUID) -> bool: ...  # pragma: no cover
