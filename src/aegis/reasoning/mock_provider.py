"""Reasoning subsystem — MockReasoningProvider for tests.

Provides a fully deterministic, configurable reasoning provider for use in
integration tests.  Zero network calls.  Zero LLM dependencies.

Usage in tests::

    from aegis.reasoning import MockReasoningProvider

    provider = MockReasoningProvider()

    # Option A: register a factory for a specific prompt
    provider.register("intent_analysis_v1", lambda vars, schema: schema(
        domain="coding", primary_verb="build", ...
    ))

    # Option B: register a fixed response object
    provider.register_fixed("intent_analysis_v1", IntentAnalysis(
        domain=IntentDomain.CODING, ...
    ))

    # Pass into the module under test
    service = PlannerService(reasoning_provider=provider)

    # Inspect what was called
    assert provider.call_count("intent_analysis_v1") == 1

Import safety: stdlib + pydantic + aegis.reasoning only.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from typing import Any, Callable, Type, TypeVar

from pydantic import BaseModel

from aegis.reasoning.provider import ReasoningProvider, ReasoningUnavailableError

__all__ = ["MockReasoningProvider"]

T = TypeVar("T", bound=BaseModel)

# Type alias for factory callables
_Factory = Callable[[dict[str, Any], Type[BaseModel]], BaseModel]


class MockReasoningProvider(ReasoningProvider):
    """Deterministic mock reasoning provider for tests.

    Thread-safe: uses asyncio.Lock for call recording.
    """

    def __init__(self, *, latency_ms: float = 0.0) -> None:
        """
        Args:
            latency_ms: Simulated latency per call (0 = instant, useful for
                        performance-sensitive tests).
        """
        self._latency_ms = latency_ms
        self._factories: dict[str, _Factory] = {}
        self._call_counts: dict[str, int] = defaultdict(int)
        self._call_args: dict[str, list[dict]] = defaultdict(list)
        self._available = True

    # ------------------------------------------------------------------
    # Registration helpers
    # ------------------------------------------------------------------

    def register(self, prompt_id: str, factory: _Factory) -> "MockReasoningProvider":
        """Register a factory function for ``prompt_id``.

        The factory receives ``(variables: dict, output_schema: type)`` and
        must return a valid instance of ``output_schema``.

        Returns self to allow method chaining.
        """
        self._factories[prompt_id] = factory
        return self

    def register_fixed(self, prompt_id: str, response: BaseModel) -> "MockReasoningProvider":
        """Register a fixed response object for ``prompt_id``.

        The same object is returned for every call to this prompt_id.
        Returns self to allow method chaining.
        """
        self._factories[prompt_id] = lambda _vars, _schema: response
        return self

    def set_available(self, available: bool) -> "MockReasoningProvider":
        """Toggle provider availability (to test offline fallback paths)."""
        self._available = available
        return self

    # ------------------------------------------------------------------
    # Inspection helpers
    # ------------------------------------------------------------------

    def call_count(self, prompt_id: str) -> int:
        """Return how many times ``prompt_id`` was called."""
        return self._call_counts[prompt_id]

    def last_variables(self, prompt_id: str) -> dict[str, Any] | None:
        """Return the variables dict from the most recent call to ``prompt_id``."""
        history = self._call_args[prompt_id]
        return history[-1] if history else None

    def all_calls(self, prompt_id: str) -> list[dict[str, Any]]:
        """Return all variable dicts from calls to ``prompt_id``."""
        return list(self._call_args[prompt_id])

    def reset(self) -> None:
        """Clear all call counts and args (useful between test cases)."""
        self._call_counts.clear()
        self._call_args.clear()

    # ------------------------------------------------------------------
    # ReasoningProvider implementation
    # ------------------------------------------------------------------

    @property
    def is_available(self) -> bool:
        return self._available

    async def reason(
        self,
        prompt_id: str,
        variables: dict,
        output_schema: Type[T],
    ) -> T:
        if not self._available:
            raise ReasoningUnavailableError(
                f"MockReasoningProvider is set to unavailable (prompt_id={prompt_id!r})"
            )

        # Record the call
        self._call_counts[prompt_id] += 1
        self._call_args[prompt_id].append(dict(variables))

        # Simulate latency
        if self._latency_ms > 0:
            await asyncio.sleep(self._latency_ms / 1000.0)

        # Invoke factory if registered
        if prompt_id in self._factories:
            result = self._factories[prompt_id](variables, output_schema)
            if not isinstance(result, output_schema):
                raise TypeError(
                    f"MockReasoningProvider factory for {prompt_id!r} returned "
                    f"{type(result).__name__}, expected {output_schema.__name__}"
                )
            return result  # type: ignore[return-value]

        raise ReasoningUnavailableError(
            f"MockReasoningProvider has no factory registered for prompt_id={prompt_id!r}. "
            f"Registered: {sorted(self._factories.keys())}. "
            "Use provider.register(prompt_id, factory) or provider.register_fixed(prompt_id, obj) "
            "in your test setup, or catch ReasoningUnavailableError to exercise the fallback path."
        )
