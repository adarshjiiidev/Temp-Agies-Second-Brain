"""Prompt03 §5 provider-neutral provider abstraction.

Base classes and registry for LLM provider adapters. No network calls,
no concrete provider-specific logic, no kernel/router/contract imports.
All provider implementations subclass BaseProvider or conform to the
L1 LLMProvider Protocol directly.

P07.5 additions:
    BaseProvider.health_check() — async health probe (default: UNKNOWN).
    BaseProvider.discover_models() — async model list from provider (default: available_models()).
    ProviderRegistry.register_force() — overwrite-safe registration for runtime reloads.
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
    ModelHealth,
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

    def register_force(self, provider_id: str, provider: LLMProvider) -> None:
        """Register, overwriting any existing registration.

        Use for runtime provider reload / hot-swap (e.g. Ollama model refresh).
        """
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

    def list_providers(self) -> list[LLMProvider]:
        """Return all registered provider instances."""
        return list(self._providers.values())


class BaseProvider:
    """Convenience base class implementing the LLMProvider Protocol.

    Subclasses MUST override:
      - provider_id: str class attribute
      - async chat(messages, params) -> ChatResult
      - async chat_stream(messages, params) -> AsyncIterator[StreamChunk]

    Subclasses SHOULD override (P07.5):
      - async health_check() -> ModelHealth   (default: UNKNOWN)
      - async discover_models() -> list[ModelSpec]  (default: available_models())
    """

    provider_id: str = ""

    def __init__(self, models: list[ModelSpec] | None = None) -> None:
        self._models: list[ModelSpec] = list(models or [])

    def available_models(self) -> list[ModelSpec]:
        return list(self._models)

    async def health_check(self) -> ModelHealth:
        """Probe provider availability and return normalized health status.

        Default implementation returns UNKNOWN (no-op).
        Override in concrete providers that support health probing.

        Returns:
            ModelHealth.HEALTHY  — provider is reachable and responding.
            ModelHealth.DEGRADED — provider responds but with errors/latency.
            ModelHealth.DOWN     — provider is unreachable or returns 5xx.
            ModelHealth.UNKNOWN  — health not probed / not supported.
        """
        return ModelHealth.UNKNOWN

    async def discover_models(self) -> list[ModelSpec]:
        """Discover available models from the provider at runtime.

        Default implementation returns the static ``available_models()`` list.
        Override in providers that support dynamic model enumeration (e.g. Ollama).

        Returns:
            List of ModelSpec instances describing available models.
        """
        return self.available_models()

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
