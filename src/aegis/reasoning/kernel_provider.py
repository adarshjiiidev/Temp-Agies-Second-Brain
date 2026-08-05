"""Reasoning subsystem — KernelReasoningProvider.

Production implementation of ReasoningProvider that routes AI reasoning calls
through the L3 AIKernel using structured output parsing.

Architecture notes:
  - This module sits at the boundary of L6→L3. It may only import from
    l3_intelligence (downward) and aegis.reasoning (lateral, same new layer).
  - The AIKernel is injected at construction time (caller owns lifecycle).
  - Prompt templates are loaded from the PromptLibrary (src/aegis/prompts/).
  - All outputs are validated via L3 structured.py before returning.
  - If the kernel call fails for any reason, raises ReasoningUnavailableError
    so callers can fall back to their deterministic path.

Import safety: stdlib + pydantic + l3_intelligence + aegis.reasoning + aegis.prompts.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Type, TypeVar

from pydantic import BaseModel, ValidationError

from aegis.reasoning.provider import ReasoningProvider, ReasoningUnavailableError

logger = logging.getLogger(__name__)

__all__ = ["KernelReasoningProvider"]

T = TypeVar("T", bound=BaseModel)


class KernelReasoningProvider(ReasoningProvider):
    """Production reasoning provider backed by the L3 AIKernel.

    Usage::

        kernel = AIKernel(registry=registry, accounting=accounting)
        provider = KernelReasoningProvider(kernel=kernel, prompt_library=library)

        # Inject into L6 planning modules
        planner = PlannerService(reasoning_provider=provider)

    The provider is a thin adapter:
      1. Look up the prompt template from the library.
      2. Render the template with ``variables``.
      3. Call ``kernel.infer()`` with the rendered prompt + schema.
      4. Validate and return the structured result.
    """

    def __init__(
        self,
        kernel: object,             # AIKernel — typed as object to avoid circular import
        prompt_library: object,     # PromptLibrary
        *,
        logger_: logging.Logger | None = None,
        default_task_type: str = "chat",
    ) -> None:
        """
        Args:
            kernel:          Configured AIKernel instance (L3).
            prompt_library:  PromptLibrary instance (src/aegis/prompts).
            logger_:         Optional logger.
            default_task_type: L3 TaskType for routing (default: 'chat').
        """
        self._kernel = kernel
        self._library = prompt_library
        self._log = logger_ or logger
        self._task_type = default_task_type

    # ------------------------------------------------------------------
    # ReasoningProvider implementation
    # ------------------------------------------------------------------

    @property
    def is_available(self) -> bool:
        """True if the kernel has at least one registered model."""
        try:
            # Duck-typed: AIKernel exposes .has_models()
            return bool(self._kernel.has_models())  # type: ignore[attr-defined]
        except Exception:
            return False

    async def reason(
        self,
        prompt_id: str,
        variables: dict,
        output_schema: Type[T],
    ) -> T:
        """Route a reasoning request through the L3 AIKernel.

        Raises:
            ReasoningUnavailableError: Kernel unavailable or inference failed.
            ValidationError:           LLM output failed schema validation.
        """
        t0 = time.monotonic()

        # ── 1. Load prompt template ──────────────────────────────────
        try:
            template = self._library.get(prompt_id)  # type: ignore[attr-defined]
        except Exception as exc:
            raise ReasoningUnavailableError(
                f"Prompt template {prompt_id!r} not found: {exc}"
            ) from exc

        # ── 2. Render prompt ─────────────────────────────────────────
        schema_json = output_schema.model_json_schema()
        try:
            prompt_text = template.render(
                {**variables, "schema": json.dumps(schema_json, indent=2)}
            )
        except Exception as exc:
            raise ReasoningUnavailableError(
                f"Failed to render prompt {prompt_id!r}: {exc}"
            ) from exc

        # ── 3. Call kernel ───────────────────────────────────────────
        try:
            raw_text: str = await self._kernel.infer_text(  # type: ignore[attr-defined]
                prompt=prompt_text,
                task_type=self._task_type,
            )
        except Exception as exc:
            latency = (time.monotonic() - t0) * 1000
            self._log.warning(
                "KernelReasoningProvider: kernel.infer_text failed for "
                "prompt_id=%r after %.0fms: %s", prompt_id, latency, exc
            )
            raise ReasoningUnavailableError(
                f"Kernel inference failed for {prompt_id!r}: {exc}"
            ) from exc

        # ── 4. Parse and validate structured output ──────────────────
        try:
            # Extract JSON block from LLM response
            json_str = _extract_json(raw_text)
            result = output_schema.model_validate_json(json_str)
        except (ValueError, ValidationError) as exc:
            latency = (time.monotonic() - t0) * 1000
            self._log.warning(
                "KernelReasoningProvider: output validation failed for "
                "prompt_id=%r after %.0fms: %s", prompt_id, latency, exc
            )
            raise  # Let ValidationError propagate; caller may fall back

        latency = (time.monotonic() - t0) * 1000
        self._log.debug(
            "KernelReasoningProvider: prompt_id=%r completed in %.0fms",
            prompt_id, latency
        )
        return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> str:
    """Extract the first JSON object or array from ``text``.

    LLMs often wrap JSON in markdown code fences (```json ... ```) or
    include preamble text.  This function strips that wrapping.
    """
    # Strip markdown code fences
    for fence in ("```json", "```JSON", "```"):
        if fence in text:
            start = text.index(fence) + len(fence)
            end_fence = text.find("```", start)
            if end_fence != -1:
                text = text[start:end_fence].strip()
                break

    # Find first { or [
    for i, ch in enumerate(text):
        if ch in ("{", "["):
            return text[i:]

    # Last resort: return as-is and let json.loads raise
    return text.strip()
