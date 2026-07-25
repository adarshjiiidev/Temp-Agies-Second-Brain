"""L1 Forward-declared AI provider interfaces.
Prompt 02: Protocol signatures ONLY — absolutely no concrete code here.
Implementations live in L3 ai_kernel.providers.{ollama,openrouter,groq,vllm} and ship in Prompt 03.
The code in this file CANNOT reference concrete provider names. It does not."""
from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Iterable, Protocol, runtime_checkable
from uuid import UUID


class Modality(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    TOOL_USE = "tool_use"


class CapabilityFlag(str, Enum):
    JSON_MODE = "json_mode"
    FUNCTION_CALLING = "function_calling"
    STREAMING = "streaming"
    VISION = "vision"


class ModelHealth(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ModelSpec:
    """Cross-provider normalized model catalog entry."""

    model_id: str
    provider: str
    family: str
    context_window: int
    output_limit: int
    modality: set[Modality]
    capabilities: set[CapabilityFlag]
    cost_per_input_1k: float = 0.0
    cost_per_output_1k: float = 0.0
    typical_latency_first_ms: int = 0
    typical_throughput_tps: int = 0
    supported_privacy_tiers: set[str] = field(default_factory=lambda: {"P0", "P1", "P2", "P3"})
    health: ModelHealth = ModelHealth.UNKNOWN
    last_health_check: float = 0.0


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: Any = None
    name: str | None = None
    tool_calls: list[Any] | None = None
    tool_call_id: str | None = None


@dataclass(frozen=True)
class ChatParams:
    max_tokens: int | None = None
    temperature: float | None = None
    response_format: dict[str, Any] | None = None
    tools: list[dict[str, Any]] | None = None
    timeout_seconds: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChatResult:
    content: str
    model: str
    tokens_in: int
    tokens_out: int
    finish_reason: str
    call_id: UUID
    tool_calls: list[Any] | None = None
    raw: Any = None


@dataclass(frozen=True)
class StreamChunk:
    delta: str | None = None
    finish_reason: str | None = None
    tool_call_delta: Any = None
    raw: Any = None


@dataclass(frozen=True)
class EmbeddingModelSpec:
    model_id: str
    provider: str
    embedding_dim: int
    cost_per_1k: float = 0.0


@runtime_checkable
class LLMProvider(Protocol):
    """Provider-agnostic LLM interface. Every provider plugin implements this."""

    @property  # type: ignore[override,unused-ignore]
    @abstractmethod
    def provider_id(self) -> str: ...

    @abstractmethod
    def available_models(self) -> list[ModelSpec]: ...

    @abstractmethod
    async def chat(
        self, messages: Iterable[ChatMessage], params: ChatParams
    ) -> ChatResult: ...  # pragma: no cover

    @abstractmethod
    async def chat_stream(
        self, messages: Iterable[ChatMessage], params: ChatParams
    ) -> AsyncIterator[StreamChunk]:  # pragma: no cover
        yield StreamChunk()  # type: ignore[misc]


@runtime_checkable
class EmbeddingProvider(Protocol):
    @property  # type: ignore[override,unused-ignore]
    @abstractmethod
    def provider_id(self) -> str: ...

    @property  # type: ignore[override,unused-ignore]
    @abstractmethod
    def embedding_dim(self) -> int: ...

    @abstractmethod
    def available_models(self) -> list[EmbeddingModelSpec]: ...  # pragma: no cover

    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> list[list[float]]: ...  # pragma: no cover
