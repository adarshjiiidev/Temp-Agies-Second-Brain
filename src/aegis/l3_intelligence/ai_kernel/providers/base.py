"""Prompt03 §5 provider-neutral provider abstraction.

Base classes and registry for LLM provider adapters. No network calls,
no concrete provider-specific logic, no kernel/router/contract imports.
All provider implementations subclass BaseProvider or conform to the
L1 LLMProvider Protocol directly.
"""

from __future__ import annotations

import asyncio
import random
import uuid
from collections.abc import AsyncIterator, Iterable
from uuid import UUID

from aegis.l1_core.interfaces.llm import (
    ChatMessage,
    ChatParams,
    ChatResult,
    LLMProvider,
    ModelSpec,
    StreamChunk,
)


class ProviderRegistry:
    """Simple in-memory registry mapping provider_id -> LLMProvider instance."""

    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}

    def register(self, provider_id: str, provider: LLMProvider) -> None:
        if provider_id in self._providers:
            raise ValueError(f"Provider '{provider_id}' is already registered")
        self._providers[provider_id] = provider

    def unregister(self, provider_id: str) -> bool:
        if provider_id in self._providers:
            del self._providers[provider_id]
            return True
        return False

    def get(self, provider_id: str) -> LLMProvider | None:
        return self._providers.get(provider_id)

    def list_provider_ids(self) -> list[str]:
        return list(self._providers.keys())


class BaseProvider:
    """Convenience base class implementing the LLMProvider Protocol.

    Subclasses MUST override:
      - provider_id: str class attribute
      - async chat(messages, params) -> ChatResult
      - async chat_stream(messages, params) -> AsyncIterator[StreamChunk]
    """

    provider_id: str = ""

    def __init__(self, models: list[ModelSpec] | None = None) -> None:
        self._models: list[ModelSpec] = list(models or [])

    def available_models(self) -> list[ModelSpec]:
        return list(self._models)

    async def chat(
        self, messages: Iterable[ChatMessage], params: ChatParams
    ) -> ChatResult:
        raise NotImplementedError

    async def chat_stream(
        self, messages: Iterable[ChatMessage], params: ChatParams
    ) -> AsyncIterator[StreamChunk]:
        raise NotImplementedError
        yield StreamChunk()

    def _normalize_messages(self, messages: Iterable[ChatMessage]) -> list[ChatMessage]:
        return list(messages)

    def _build_call_id(self) -> UUID:
        return uuid.uuid4()

    def _count_tokens_fallback(self, messages: Iterable[ChatMessage]) -> int:
        total_chars = 0
        for msg in messages:
            content = msg.content
            if content is None:
                continue
            if isinstance(content, str):
                total_chars += len(content)
            else:
                total_chars += len(str(content))
        return max(1, int(total_chars / 3.5))
