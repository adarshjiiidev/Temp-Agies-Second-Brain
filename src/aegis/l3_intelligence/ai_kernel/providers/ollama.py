"""Ollama local provider adapter — Prompt 03 §10.1.

Connects to a local Ollama server (default: http://localhost:11434).
Uses OpenAI-compatible /api/chat endpoint with NDJSON streaming.
Deployment: LOCAL. Cost: $0. Satisfies P0/P1/P2/P3 privacy tiers.

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
        "OllamaProvider requires 'httpx'. Install with: pip install httpx"
    ) from _httpx_err


_DEFAULT_BASE_URL = "http://localhost:11434"
_DEFAULT_TIMEOUT = 120.0


def _normalize_finish_reason(reason: str | None) -> str:
    mapping = {"stop": "stop", "length": "length", "": "stop"}
    return mapping.get(reason or "", "stop")


class OllamaProvider(BaseProvider):
    """Ollama local LLM provider.

    Args:
        base_url: Ollama server base URL (default: http://localhost:11434).
        model_ids: List of model ids to advertise. Defaults to ["llama3"].
        timeout: Default HTTP timeout in seconds.
    """

    provider_id: str = "ollama"

    def __init__(
        self,
        base_url: str = _DEFAULT_BASE_URL,
        model_ids: list[str] | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._model_ids: list[str] = model_ids or ["llama3"]

    # ------------------------------------------------------------------
    # LLMProvider Protocol
    # ------------------------------------------------------------------

    @property
    def provider_id(self) -> str:  # type: ignore[override]
        return "ollama"

    def available_models(self) -> list[ModelSpec]:
        return [
            ModelSpec(
                model_id=m,
                provider="ollama",
                family="ollama",
                context_window=8192,
                output_limit=4096,
                modality={Modality.TEXT},
                capabilities={CapabilityFlag.STREAMING},
                cost_per_input_1k=0.0,
                cost_per_output_1k=0.0,
                health=ModelHealth.UNKNOWN,
            )
            for m in self._model_ids
        ]

    async def chat(
        self, messages: Iterable[ChatMessage], params: ChatParams
    ) -> ChatResult:
        msgs = self._build_messages(list(messages))
        payload = self._build_payload(msgs, params, stream=False)
        model = payload.get("model", self._model_ids[0])

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.post(
                    f"{self._base_url}/api/chat",
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
                    f"Ollama network error: {exc}",
                ) from exc

        data = resp.json()
        msg = data.get("message", {})
        usage = data.get("eval_count", 0)
        prompt_eval = data.get("prompt_eval_count", 0)
        return ChatResult(
            content=msg.get("content", ""),
            model=model,
            tokens_in=prompt_eval,
            tokens_out=usage,
            finish_reason=_normalize_finish_reason(data.get("done_reason")),
            call_id=uuid.uuid4(),
            raw=data,
        )

    async def chat_stream(
        self, messages: Iterable[ChatMessage], params: ChatParams
    ) -> AsyncIterator[StreamChunk]:
        msgs = self._build_messages(list(messages))
        payload = self._build_payload(msgs, params, stream=True)

        async def _iter() -> AsyncIterator[StreamChunk]:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                try:
                    async with client.stream(
                        "POST", f"{self._base_url}/api/chat", json=payload
                    ) as resp:
                        resp.raise_for_status()
                        async for line in resp.aiter_lines():
                            if not line.strip():
                                continue
                            try:
                                data = json.loads(line)
                            except json.JSONDecodeError:
                                continue
                            msg = data.get("message", {})
                            done = data.get("done", False)
                            yield StreamChunk(
                                delta=msg.get("content"),
                                finish_reason="stop" if done else None,
                                raw=data,
                            )
                            if done:
                                break
                except httpx.HTTPStatusError as exc:
                    self._raise_from_http(exc)
                except httpx.RequestError as exc:
                    from aegis.l1_core.errors.base import AIProviderUnavailableError
                    from aegis.l1_core.errors import ErrorCode
                    raise AIProviderUnavailableError(
                        ErrorCode.AI_PROVIDER_UNAVAILABLE,
                        f"Ollama stream network error: {exc}",
                    ) from exc

        return _iter()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_messages(self, messages: list[ChatMessage]) -> list[dict[str, Any]]:
        result = []
        for msg in messages:
            d: dict[str, Any] = {"role": msg.role}
            if msg.content is not None:
                d["content"] = str(msg.content)
            result.append(d)
        return result

    def _build_payload(
        self, messages: list[dict], params: ChatParams, *, stream: bool
    ) -> dict[str, Any]:
        model = (params.extra or {}).get("model") or self._model_ids[0]
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
        }
        options: dict[str, Any] = {}
        if params.max_tokens is not None:
            options["num_predict"] = params.max_tokens
        if params.temperature is not None:
            options["temperature"] = params.temperature
        if options:
            payload["options"] = options
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
                ErrorCode.AI_AUTHENTICATION_FAILED, f"Ollama auth: {status}"
            ) from exc
        if status == 429:
            raise AIRateLimitError(
                ErrorCode.AI_RATE_LIMITED, f"Ollama rate limit: {status}"
            ) from exc
        if status >= 500:
            raise AIProviderUnavailableError(
                ErrorCode.AI_PROVIDER_UNAVAILABLE, f"Ollama server error: {status}"
            ) from exc
        raise AIInvalidRequestError(
            ErrorCode.AI_INVALID_REQUEST, f"Ollama rejected request: {status}"
        ) from exc


__all__ = ["OllamaProvider"]
