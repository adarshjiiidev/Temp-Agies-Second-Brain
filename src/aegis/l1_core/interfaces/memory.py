"""L1 Forward-declared Memory Store interface.
Prompt 02: Protocol ONLY — concrete 9-tier implementation ships in Prompt 04 (Memory Engine)."""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable
from uuid import UUID


class MemoryTier(str, Enum):
    WORKING = "T0"
    SESSION = "T1"
    EPISODIC = "T2"
    SEMANTIC = "T3"
    PROCEDURAL = "T4"
    PERSONAL = "T5"
    ENVIRONMENTAL = "T6"
    PROJECT = "T7"
    SKILL = "T8"


@dataclass(frozen=True)
class MemoryRecord:
    record_id: UUID
    tier: MemoryTier
    key: str
    content: Any
    privacy_tier: str = "P2"
    confidence: float = 0.0
    provenance: dict[str, Any] = field(default_factory=dict)
    scope: str = "global"
    ttl_seconds: float | None = None
    is_draft: bool = True
    revision: int = 1


@runtime_checkable
class MemoryStore(Protocol):
    @abstractmethod
    async def write(self, record: MemoryRecord) -> None: ...  # pragma: no cover

    @abstractmethod
    async def read(self, tier: MemoryTier, key: str) -> MemoryRecord | None: ...  # pragma: no cover

    @abstractmethod
    async def query(
        self,
        *,
        tiers: list[MemoryTier] | None = None,
        text_query: str | None = None,
        limit: int = 50,
    ) -> list[MemoryRecord]: ...  # pragma: no cover

    @abstractmethod
    async def delete(self, tier: MemoryTier, key: str) -> bool: ...  # pragma: no cover
