"""Deterministic fake LLM provider for tests.

FakeProvider is a fully controllable mock of the LLMProvider Protocol.
No network calls. Configurable response content, token counts, errors,
latency (zero by default), and stream events.

Design rules:
  - Zero external dependencies (stdlib + L1 interfaces only).
  - Configurable via simple constructor args or call_responses list.
  - Can simulate: success, auth failure, rate limit, provider unavailable,
    stream partial delivery, stream cancellation.
  - Thread-safe for use in async tests with multiple concurrent callers.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Iterable
from uuid import UUID

from aegis.l1_core.interfaces.llm import (
    ChatMessage,
    ChatParams,
    ChatResult,
    ModelSpec,
    StreamChunk,
)


# ---------------------------------------------------------------------------
# Configurable per-call response descriptor
# ---------------------------------------------------------------------------


@dataclass
class FakeResponse:
    """Descriptor for one call-response in the FakeProvider queue.

    If ``error`` is set, that exception is raised instead of returning content.
    If ``content`` is set, a successful ChatResult is returned.
    """

    content: str = "Fake response."
    tokens_in: int = 10
    tokens_out: int = 8
    latency_seconds: float = 0.0
    error: Exception | None = None
    # For streaming: list of content chunks to emit in order.
    stream_chunks: list[str] | None = None


# Default response used when response_queue is exhausted.
_DEFAULT_RESPONSE = FakeResponse()


class FakeProvider:
    """Deterministic fake LLMProvider for integration tests.

    Usage::

        provider = FakeProvider(responses=[
            FakeResponse(content="Hello!"),
            FakeResponse(error=AIAuthenticationError("key invalid")),
        ])

    Calls dequeue from `responses`. When exhausted, `default_response` is used.
    """

    provider_id: str = "fake"

    def __init__(
        self,
        provider_id: str = "fake",
        responses: list[FakeResponse] | None = None,
        default_response: FakeResponse | None = None,
        model_ids: list[str] | None = None,
    ) -> None:
        self.provider_id = provider_id
        self._responses: list[FakeResponse] = list(responses or [])
        self._default_response: FakeResponse = default_response or _DEFAULT_RESPONSE
        self._model_ids = model_ids or ["fake-model"]
        self._call_count: int = 0
        self._call_log: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # LLMProvider Protocol implementation
    # ------------------------------------------------------------------

    def available_models(self) -> list[ModelSpec]:
        return [ModelSpec(model_id=m, provider_id=self.provider_id) for m in self._model_ids]

    async def chat(
        self,
        messages: Iterable[ChatMessage],
        params: ChatParams,
    ) -> ChatResult:
        resp = self._next_response()
        msgs = list(messages)
        self._call_log.append(
            {
                "call_id": str(uuid.uuid4()),
                "messages": msgs,
                "params": params,
                "timestamp": time.time(),
            }
        )
        self._call_count += 1

        if resp.latency_seconds > 0:
            await asyncio.sleep(resp.latency_seconds)

        if resp.error is not None:
            raise resp.error

        return ChatResult(
            content=resp.content,
            model=self._model_ids[0],
            tokens_in=resp.tokens_in,
            tokens_out=resp.tokens_out,
            finish_reason="stop",
            call_id=uuid.uuid4(),
        )

    async def chat_stream(
        self,
        messages: Iterable[ChatMessage],
        params: ChatParams,
    ) -> AsyncIterator[StreamChunk]:
        resp = self._next_response()
        msgs = list(messages)
        self._call_log.append(
            {
                "call_id": str(uuid.uuid4()),
                "messages": msgs,
                "params": params,
                "timestamp": time.time(),
                "stream": True,
            }
        )
        self._call_count += 1

        if resp.latency_seconds > 0:
            await asyncio.sleep(resp.latency_seconds)

        if resp.error is not None:
            raise resp.error

        async def _iter() -> AsyncIterator[StreamChunk]:
            chunks = resp.stream_chunks or [resp.content]
            for i, chunk in enumerate(chunks):
                yield StreamChunk(
                    delta=chunk,
                    finish_reason="stop" if i == len(chunks) - 1 else None,
                )

        return _iter()

    # ------------------------------------------------------------------
    # Test helpers
    # ------------------------------------------------------------------

    def call_count(self) -> int:
        return self._call_count

    def call_log(self) -> list[dict[str, Any]]:
        return list(self._call_log)

    def reset(self) -> None:
        self._call_count = 0
        self._call_log.clear()
        self._responses.clear()

    def push_response(self, resp: FakeResponse) -> None:
        """Append a response to the end of the queue."""
        self._responses.append(resp)

    def _next_response(self) -> FakeResponse:
        if self._responses:
            return self._responses.pop(0)
        return self._default_response


__all__ = ["FakeProvider", "FakeResponse"]
