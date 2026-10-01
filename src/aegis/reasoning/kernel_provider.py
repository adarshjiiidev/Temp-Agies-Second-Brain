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

        kernel = AIKernel(registry=registry, provider_registry=prov_registry, ...)
        library = PromptLibrary()
        provider = KernelReasoningProvider(kernel=kernel, prompt_library=library)

        # Inject into L6 planning modules
        planner = PlannerService(reasoning_provider=provider)

    The provider is a thin adapter:
      1. Look up the prompt template from the library.
      2. Render the template with ``variables``.
      3. Build an AIRequest with the rendered prompt + output schema.
      4. Call ``kernel.generate(request)`` — the real AIKernel API.
      5. Extract structured_output if available, else parse content JSON.
      6. Validate and return the structured result.

    If the kernel raises any exception or the output fails validation,
    ReasoningUnavailableError is raised so the caller can use its fallback.
    """

    def __init__(
        self,
        kernel: object,             # AIKernel — typed as object to avoid circular import
        prompt_library: object,     # PromptLibrary
        *,
        logger_: logging.Logger | None = None,
        default_task_type: str = "reason",
        privacy_tier: str = "P2",
    ) -> None:
        """
        Args:
            kernel:           Configured AIKernel instance (L3).
            prompt_library:   PromptLibrary instance (src/aegis/prompts).
            logger_:          Optional logger.
            default_task_type: L3 TaskType for routing (default: 'reason').
            privacy_tier:     Default privacy tier for requests ('P0'–'P3').
        """
        self._kernel = kernel
        self._library = prompt_library
        self._log = logger_ or logger
        self._task_type = default_task_type
        self._privacy_tier = privacy_tier

    # ------------------------------------------------------------------
    # ReasoningProvider implementation
    # ------------------------------------------------------------------

    @property
    def is_available(self) -> bool:
        """True if the kernel has at least one registered model.

        Checks the ModelRegistry directly via duck-typing to avoid
        circular imports. Falls back to False on any error.
        """
        try:
            # Duck-type: AIKernel._registry is a ModelRegistry with _models dict
            registry = self._kernel._registry  # type: ignore[attr-defined]
            return bool(registry._models)      # type: ignore[attr-defined]
        except Exception:
            return False

    async def reason(
        self,
        prompt_id: str,
        variables: dict,
        output_schema: Type[T],
    ) -> T:
        """Route a reasoning request through the L3 AIKernel.

        This method uses the REAL AIKernel.generate(AIRequest) → AIResponse
        contract — not the hypothetical has_models()/infer_text() interface.

        Flow:
          1. Load + render prompt template
          2. Build AIRequest with structured output schema
          3. Call kernel.generate()
          4. Extract validated structured output

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

        # ── 3. Build AIRequest using the real L3 contract ────────────
        try:
            from aegis.l3_intelligence.ai_kernel.contracts import (
                AIRequest,
                RoutingRequirements,
                StructuredOutputRequirements,
            )
            from aegis.l1_core.interfaces.llm import ChatMessage
            from aegis.l3_intelligence.ai_kernel.types import (
                PrivacyTier,
                TaskType,
            )

            # Map string task_type → TaskType enum (best-effort, default REASON)
            try:
                task_type_enum = TaskType(self._task_type)
            except (ValueError, KeyError):
                task_type_enum = TaskType.REASON

            # Map string privacy_tier → PrivacyTier enum (best-effort, default STANDARD)
            try:
                privacy_tier_enum = PrivacyTier(self._privacy_tier)
            except (ValueError, KeyError):
                privacy_tier_enum = PrivacyTier.STANDARD

            request = AIRequest(
                messages=[
                    ChatMessage(role="user", content=prompt_text)
                ],
                structured=StructuredOutputRequirements(
                    output_schema=output_schema,
                    max_retries=2,
                ),
                routing=RoutingRequirements(
                    task_type=task_type_enum,
                    privacy_tier=privacy_tier_enum,
                ),
            )
        except Exception as exc:
            raise ReasoningUnavailableError(
                f"Failed to build AIRequest for {prompt_id!r}: {exc}"
            ) from exc

        # ── 4. Call kernel.generate() ────────────────────────────────
        try:
            response = await self._kernel.generate(request)  # type: ignore[attr-defined]
            elapsed_ms = (time.monotonic() - t0) * 1000
        except Exception as exc:
            latency = (time.monotonic() - t0) * 1000
            self._log.warning(
                "KernelReasoningProvider: kernel.generate failed for "
                "prompt_id=%r after %.0fms: %s", prompt_id, latency, exc
            )
            raise ReasoningUnavailableError(
                f"Kernel inference failed for {prompt_id!r}: {exc}"
            ) from exc

        # ── 5. Extract structured output ─────────────────────────────
        # The kernel runs the structured output loop internally.
        # If structured_output is already parsed, use it directly.
        if response.structured_output is not None:
            obj = response.structured_output
            # Type check: ensure it's the right schema
            if isinstance(obj, output_schema):
                self._log.debug(
                    "KernelReasoningProvider: prompt_id=%r completed (structured) in %.0fms",
                    prompt_id, elapsed_ms
                )
                return obj  # type: ignore[return-value]
            # Try re-validation in case kernel returned a dict
            try:
                if isinstance(obj, dict):
                    result = output_schema.model_validate(obj)
                    return result  # type: ignore[return-value]
            except (ValueError, ValidationError):
                pass

        # ── 6. Fallback: parse content JSON ──────────────────────────
        try:
            json_str = _extract_json(response.content or "")
            result = output_schema.model_validate_json(json_str)
        except (ValueError, ValidationError) as exc:
            latency = (time.monotonic() - t0) * 1000
            self._log.warning(
                "KernelReasoningProvider: output validation failed for "
                "prompt_id=%r after %.0fms: %s", prompt_id, latency, exc
            )
            raise  # Let ValidationError propagate; caller may fall back

        self._log.debug(
            "KernelReasoningProvider: prompt_id=%r completed (content parse) in %.0fms",
            prompt_id, elapsed_ms
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
