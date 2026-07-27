"""Groq cloud provider adapter — Prompt 03 §10.3.

Connects to api.groq.com/openai/v1 (OpenAI-compatible endpoint).
Groq specializes in extremely low first-token latency on open models
(Llama, Gemma, Mistral). Best for planning loops and structured extraction.

Deployment: CLOUD. Suitable for P2/P3 data.

Dependencies: httpx (async HTTP).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any, Iterable

from aegis.l1_core.interfaces.llm import (
    CapabilityFlag,
    ChatMessage,
    ChatParams,
    ChatResult,
    ModelHealth,
    ModelSpec,
    Modality,
    StreamChunk,
)
from aegis.l3_intelligence.ai_kernel.providers.base import BaseProvider

try:
    import httpx
except ImportError as _httpx_err:  # pragma: no cover
    raise ImportError(
        "GroqProvider requires 'httpx'. Install with: pip install httpx"
    ) from _httpx_err


_BASE_URL = "https://api.groq.com/openai/v1"
_DEFAULT_TIMEOUT = 60.0


def _normalize_finish_reason(reason: str | None) -> str:
    mapping = {
        "stop": "stop",
        "length": "length",
        "tool_calls": "tool_calls",
    }
    return mapping.get(reason or "", "stop")


class GroqProvider(BaseProvider):
    """Groq cloud LLM provider.

    Args:
        api_key: Groq API key. Falls back to ``GROQ_API_KEY`` env var.
        default_model: Model id used when not specified in params.
        timeout: HTTP timeout in seconds.
    """

    def __init__(
        self,
        api_key: str | None = None,
        default_model: str = "llama3-8b-8192",
        model_ids: list[str] | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        import os
        self._api_key = api_key or os.environ.get("GROQ_API_KEY", "")
        self._default_model = default_model
        self._model_ids = model_ids or [default_model]
        self._timeout = timeout
        self._headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    @property
    def provider_id(self) -> str:
        return "groq"

    def available_models(self) -> list[ModelSpec]:
        return [
            ModelSpec(
                model_id=m,
                provider="groq",
                family="groq",
                context_window=8192,
                output_limit=4096,
                modality={Modality.TEXT},
                capabilities={
                    CapabilityFlag.JSON_MODE,
                    CapabilityFlag.FUNCTION_CALLING,
                    CapabilityFlag.STREAMING,
                },
                health=ModelHealth.UNKNOWN,
            )
            for m in self._model_ids
        ]

    async def chat(
        self, messages: Iterable[ChatMessage], params: ChatParams
    ) -> ChatResult:
        payload = self._build_payload(list(messages), params, stream=False)
        model = payload["model"]

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.post(
                    f"{_BASE_URL}/chat/completions",
                    headers=self._headers,
                    json=payload,
                )
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                self._raise_from_http(exc)
            except httpx.RequestError as exc:
                from aegis.l1_core.errors.base import AIProviderUnavailableError
                from aegis.l1_core.errors import ErrorCode
                raise AIProviderUnavailableError(
                    ErrorCode.AI_PROVIDER_UNAVAILABLE,
                    f"Groq network error: {exc}",
                ) from exc

        data = resp.json()
        choice = data["choices"][0]
        usage = data.get("usage", {})
        return ChatResult(
            content=choice["message"].get("content") or "",
            model=data.get("model", model),
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
            finish_reason=_normalize_finish_reason(choice.get("finish_reason")),
            call_id=uuid.uuid4(),
            tool_calls=choice["message"].get("tool_calls"),
            raw=data,
        )

    async def chat_stream(
        self, messages: Iterable[ChatMessage], params: ChatParams
    ) -> AsyncIterator[StreamChunk]:
        payload = self._build_payload(list(messages), params, stream=True)

        async def _iter() -> AsyncIterator[StreamChunk]:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                try:
                    async with client.stream(
                        "POST",
                        f"{_BASE_URL}/chat/completions",
                        headers=self._headers,
                        json=payload,
                    ) as resp:
                        resp.raise_for_status()
                        async for line in resp.aiter_lines():
                            if not line.startswith("data: "):
                                continue
                            raw = line[6:].strip()
                            if raw == "[DONE]":
                                break
                            try:
                                data = json.loads(raw)
                            except json.JSONDecodeError:
                                continue
                            choices = data.get("choices", [])
                            if not choices:
                                continue
                            delta = choices[0].get("delta", {})
                            finish = choices[0].get("finish_reason")
                            yield StreamChunk(
                                delta=delta.get("content"),
                                finish_reason=_normalize_finish_reason(finish) if finish else None,
                                raw=data,
                            )
                except httpx.HTTPStatusError as exc:
                    self._raise_from_http(exc)
                except httpx.RequestError as exc:
                    from aegis.l1_core.errors.base import AIProviderUnavailableError
                    from aegis.l1_core.errors import ErrorCode
                    raise AIProviderUnavailableError(
                        ErrorCode.AI_PROVIDER_UNAVAILABLE,
                        f"Groq stream error: {exc}",
                    ) from exc

        return _iter()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_payload(
        self, messages: list[ChatMessage], params: ChatParams, *, stream: bool
    ) -> dict[str, Any]:
        model = (params.extra or {}).get("model") or self._default_model
        msgs = [
            {"role": m.role, "content": str(m.content) if m.content is not None else ""}
            for m in messages
        ]
        payload: dict[str, Any] = {
            "model": model,
            "messages": msgs,
            "stream": stream,
        }
        if params.max_tokens is not None:
            payload["max_tokens"] = params.max_tokens
        if params.temperature is not None:
            payload["temperature"] = params.temperature
        if params.response_format is not None:
            payload["response_format"] = params.response_format
        if params.tools:
            payload["tools"] = params.tools
        return payload

    def _raise_from_http(self, exc: httpx.HTTPStatusError) -> None:
        from aegis.l1_core.errors.base import (
            AIAuthenticationError,
            AIRateLimitError,
            AIProviderUnavailableError,
            AIInvalidRequestError,
        )
        from aegis.l1_core.errors import ErrorCode

        status = exc.response.status_code
        if status in (401, 403):
            raise AIAuthenticationError(
                ErrorCode.AI_AUTHENTICATION_FAILED,
                f"Groq auth error: {status}",
            ) from exc
        if status == 429:
            raise AIRateLimitError(
                ErrorCode.AI_RATE_LIMITED, f"Groq rate limit: {status}"
            ) from exc
        if status >= 500:
            raise AIProviderUnavailableError(
                ErrorCode.AI_PROVIDER_UNAVAILABLE, f"Groq server error: {status}"
            ) from exc
        raise AIInvalidRequestError(
            ErrorCode.AI_INVALID_REQUEST, f"Groq rejected request: {status}"
        ) from exc


__all__ = ["GroqProvider"]
