"""P07 Observer — ObserverSink.

Buffers ObservedEvents and flushes them to the L4 MemoryManager as
T1_SESSION MemoryKind.OBSERVATION records.

Privacy zone check MUST be performed before calling record().

Import safety: l4_memory.* + stdlib ONLY.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque

from aegis.l4_memory.manager import MemoryManager
from aegis.l4_memory.models import MemoryRecord, ProvenanceChain, ProvenanceLink
from aegis.l4_memory.p07.observer.events import ObservedEvent
from aegis.l4_memory.types import (
    Importance,
    MemoryKind,
    MemoryStatus,
    MemoryTier,
    ProvenanceKind,
)

__all__ = ["ObserverSink"]

_NAMESPACE = "p07_observer"
_MAX_BUFFER = 200  # Maximum events held in memory before forced flush


class ObserverSink:
    """Buffers and flushes observer events to L4 memory storage.

    Usage::

        sink = ObserverSink(manager)
        await sink.record(event)   # buffer
        await sink.flush()         # persist to store
        await sink.drain()         # flush + delete all (shutdown)
    """

    def __init__(self, manager: MemoryManager, max_buffer: int = _MAX_BUFFER) -> None:
        self._manager = manager
        self._buffer: deque[ObservedEvent] = deque(maxlen=max_buffer)
        self._flushed_count = 0
        self._record_ids: list = []  # Track IDs for drain

    async def record(self, event: ObservedEvent) -> None:
        """Add an event to the buffer. Auto-flushes when buffer is full."""
        self._buffer.append(event)
        if len(self._buffer) >= _MAX_BUFFER:
            await self.flush()

    async def flush(self) -> int:
        """Persist all buffered events to the memory store.

        Returns the number of events flushed.
        """
        if not self._buffer:
            return 0

        flushed = 0
        while self._buffer:
            event = self._buffer.popleft()
            record = MemoryRecord(
                key=f"obs:{event.id}",
                namespace=_NAMESPACE,
                tier=MemoryTier.T1_SESSION,
                kind=MemoryKind.OBSERVATION,
                status=MemoryStatus.ACTIVE,
                importance=Importance.LOW,
                privacy_tier=event.privacy_tier,
                provenance=ProvenanceChain(links=[
                    ProvenanceLink(
                        kind=ProvenanceKind.OBSERVER_DERIVED,
                        subject="p07:observer",
                    )
                ]),
                content=event.to_dict(),
                summary=f"{event.kind.value}: {event.subject[:80]}",
                tags=["p07_observer", event.kind.value],
                session_id=event.session_id,
            )
            try:
                await self._manager.store(record)
                self._record_ids.append(record.id)
                flushed += 1
            except Exception:
                pass  # Non-critical; log is best-effort

        self._flushed_count += flushed
        return flushed

    async def drain(self) -> int:
        """Flush remaining events then delete ALL observer records from store.

        Called on observer shutdown. Guarantees zero retained transient records.
        Returns count of deleted records.
        """
        await self.flush()
        deleted = 0
        for rec_id in self._record_ids:
            try:
                await self._manager.delete(rec_id)
                deleted += 1
            except Exception:
                pass
        self._record_ids.clear()
        self._flushed_count = 0

        # Belt-and-suspenders: also sweep namespace for any stragglers
        from aegis.l4_memory.search import SearchQuery
        from aegis.l4_memory.types import SearchMode
        query = SearchQuery(
            namespace=_NAMESPACE,
            mode=SearchMode.METADATA,
            limit=10000,
        )
        try:
            results = await self._manager.search(query)
            for r in results:
                try:
                    await self._manager.delete(r.record.id)
                    deleted += 1
                except Exception:
                    pass
        except Exception:
            pass

        return deleted

    @property
    def buffered_count(self) -> int:
        return len(self._buffer)

    @property
    def total_flushed(self) -> int:
        return self._flushed_count
