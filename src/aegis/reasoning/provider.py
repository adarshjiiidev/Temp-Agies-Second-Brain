"""Reasoning subsystem — ReasoningProvider abstract base class.

This is the hard boundary between deterministic infrastructure code and AI
reasoning.  Every layer that needs to "think" goes through this interface.

Design goals:
  1. Single injection point:  callers depend only on this ABC.
  2. Swappable:               tests inject MockReasoningProvider;
                              production injects KernelReasoningProvider.
  3. Offline-safe:            providers may raise ReasoningUnavailableError
                              when no LLM is reachable; callers must handle it
                              by invoking their deterministic fallback.
  4. Typed outputs:           ``reason()`` always returns a validated Pydantic
                              model — never raw text.

Import safety: stdlib + pydantic + aegis.reasoning.types only.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypeVar, Type

from pydantic import BaseModel

__all__ = [
    "ReasoningProvider",
    "ReasoningUnavailableError",
]

T = TypeVar("T", bound=BaseModel)


# ---------------------------------------------------------------------------
# Sentinel exception — callers catch this to trigger deterministic fallback
# ---------------------------------------------------------------------------

class ReasoningUnavailableError(RuntimeError):
    """Raised when no LLM is reachable or the provider is not configured.

    Callers MUST catch this and fall back to their deterministic path.
    It is NOT an AegisError because it is expected/recoverable.
    """


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------

class ReasoningProvider(ABC):
    """Abstract reasoning provider.

    Usage::

        # In a planning module:
        try:
            result: IntentAnalysis = await self._reasoning.reason(
                PromptId.INTENT_ANALYSIS,
                {"goal_text": goal, "context_json": "{}"},
                IntentAnalysis,
            )
        except ReasoningUnavailableError:
            result = self._deterministic_intent_parse(goal)
    """

    @abstractmethod
    async def reason(
        self,
        prompt_id: str,
        variables: dict,
        output_schema: Type[T],
    ) -> T:
        """Call the AI with ``prompt_id`` and return a validated ``output_schema`` instance.

        Args:
            prompt_id:     Identifier of the prompt template (see ``PromptId``).
            variables:     Template variable substitutions (str keys, JSON-safe values).
            output_schema: Pydantic model class the result must conform to.

        Returns:
            A validated instance of ``output_schema``.

        Raises:
            ReasoningUnavailableError: No LLM is reachable; caller should use fallback.
            ValidationError:           LLM returned output that failed schema validation.
        """

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """True if this provider can currently make AI calls."""

    @property
    def name(self) -> str:
        """Human-readable name for logging/tracing."""
        return self.__class__.__name__
