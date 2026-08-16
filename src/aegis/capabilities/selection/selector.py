"""Capabilities selection — CapabilitySelector.

Selects the best capabilities for a task using:
1. AI path: calls a reasoning_provider.reason() call with structured output.
2. Deterministic fallback: filter + rank by ranking_score().

The AI proposes; deterministic validation confirms.

INVARIANT: selected_ids must all exist in the registry and be usable.
If the AI proposes an invalid or disabled capability, it is silently
removed and replaced with deterministic alternatives.

Import safety: stdlib + aegis.capabilities.model + aegis.capabilities.selection.schemas
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

from aegis.capabilities.model.capability import CapabilityRecord, TrustState
from aegis.capabilities.model.health import HealthStatus
from aegis.capabilities.selection.schemas import (
    CapabilityConstraints,
    CapabilitySelectionInput,
    CapabilitySelectionOutput,
)

logger = logging.getLogger(__name__)

__all__ = ["CapabilitySelector", "ReasoningProvider"]

# Minimum score threshold to include in fallback selection
_MIN_SCORE_THRESHOLD = 0.1
_MAX_CANDIDATES_FOR_AI = 20


@runtime_checkable
class ReasoningProvider(Protocol):
    """Minimal interface the selector needs from a reasoning provider."""

    def reason(
        self,
        prompt_id: str,
        inputs: dict[str, Any],
        output_schema: type,
    ) -> Any:
        """Reason and return structured output matching output_schema."""
        ...


class CapabilitySelector:
    """Selects capabilities for a task goal.

    Tries AI reasoning first; falls back to deterministic scoring
    if no provider is available or if the AI output is invalid.

    Usage::

        selector = CapabilitySelector(reasoning_provider=my_provider)
        result = selector.select(
            goal="commit my changes to git",
            candidates=[cap_git, cap_shell],
            constraints=CapabilityConstraints(online_allowed=False),
        )
        # result.selected_ids = ["cli:git"]
        # result.selection_method = "ai" or "deterministic"
    """

    PROMPT_ID = "capability_selection_v1"

    def __init__(
        self,
        reasoning_provider: ReasoningProvider | None = None,
    ) -> None:
        self._provider = reasoning_provider

    def select(
        self,
        goal: str,
        candidates: list[CapabilityRecord],
        constraints: CapabilityConstraints | None = None,
    ) -> CapabilitySelectionOutput:
        """Select capabilities for the given goal.

        Args:
            goal:        Natural language task description.
            candidates:  List of CapabilityRecord objects to choose from.
            constraints: Optional selection constraints.

        Returns:
            CapabilitySelectionOutput with selected_ids and metadata.
        """
        if constraints is None:
            constraints = CapabilityConstraints()

        # Apply constraint filters first
        filtered = self._apply_constraints(candidates, constraints)

        if not filtered:
            logger.warning("CapabilitySelector: no candidates after constraint filtering")
            return CapabilitySelectionOutput(
                selected_ids=[],
                rationale="No capabilities matched the given constraints",
                confidence=0.0,
                selection_method="deterministic",
                warnings=["No matching capabilities available"],
            )

        # Limit to top N for AI context window
        top_candidates = sorted(filtered, key=lambda c: c.ranking_score(), reverse=True)
        ai_input = top_candidates[:_MAX_CANDIDATES_FOR_AI]

        # Try AI path
        if self._provider is not None:
            result = self._try_ai_selection(goal, ai_input, filtered, constraints)
            if result is not None:
                return result

        # Deterministic fallback
        return self._deterministic_select(goal, filtered)

    # ------------------------------------------------------------------ #
    # AI path
    # ------------------------------------------------------------------ #

    def _try_ai_selection(
        self,
        goal: str,
        candidates: list[CapabilityRecord],
        all_candidates: list[CapabilityRecord],
        constraints: CapabilityConstraints,
    ) -> CapabilitySelectionOutput | None:
        """Attempt AI-driven selection. Returns None if AI fails."""
        try:
            cap_summaries = [self._summarize(c) for c in candidates]
            sel_input = CapabilitySelectionInput(
                goal_text=goal,
                available_capabilities=cap_summaries,
                constraints=constraints,
            )
            raw = self._provider.reason(  # type: ignore[union-attr]
                self.PROMPT_ID,
                {"selection_input": sel_input.model_dump()},
                CapabilitySelectionOutput,
            )
            if not isinstance(raw, CapabilitySelectionOutput):
                logger.warning("CapabilitySelector: AI returned unexpected type %s", type(raw))
                return None

            # Validate: remove IDs that don't exist or aren't usable
            valid_ids = {c.capability_id for c in all_candidates if c.is_usable}
            warnings = list(raw.warnings)
            validated_ids = []
            for cid in raw.selected_ids:
                if cid in valid_ids:
                    validated_ids.append(cid)
                else:
                    warnings.append(
                        f"AI proposed {cid!r} which is not available — removed"
                    )
            fallback_ids = [
                cid for cid in raw.fallback_ids if cid in valid_ids
            ]

            if not validated_ids:
                logger.warning(
                    "CapabilitySelector: AI selection had no valid IDs — falling back"
                )
                return None

            logger.info(
                "CapabilitySelector: AI selected %d capabilities for %r",
                len(validated_ids), goal[:60],
            )
            return CapabilitySelectionOutput(
                selected_ids=validated_ids,
                rationale=raw.rationale,
                confidence=raw.confidence,
                fallback_ids=fallback_ids,
                selection_method="ai",
                warnings=warnings,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("CapabilitySelector: AI selection failed: %s", exc)
            return None

    # ------------------------------------------------------------------ #
    # Deterministic fallback
    # ------------------------------------------------------------------ #

    def _deterministic_select(
        self,
        goal: str,
        candidates: list[CapabilityRecord],
    ) -> CapabilitySelectionOutput:
        """Score and rank candidates, return top result(s)."""
        goal_lower = goal.lower()
        scored: list[tuple[CapabilityRecord, float]] = []

        for cap in candidates:
            score = cap.ranking_score()
            # Keyword boost
            text = f"{cap.name} {cap.description}".lower()
            words = [w for w in goal_lower.split() if len(w) > 3]
            if words:
                hits = sum(1 for w in words if w in text)
                score += (hits / len(words)) * 0.1
            if score >= _MIN_SCORE_THRESHOLD:
                scored.append((cap, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        if not scored:
            return CapabilitySelectionOutput(
                selected_ids=[],
                rationale="No capabilities met the minimum score threshold",
                confidence=0.0,
                selection_method="deterministic",
                warnings=["No sufficiently reliable capabilities available"],
            )

        # Primary = top 1, fallback = next 2
        primary = [cap.capability_id for cap, _ in scored[:1]]
        fallback = [cap.capability_id for cap, _ in scored[1:3]]

        return CapabilitySelectionOutput(
            selected_ids=primary,
            rationale=(
                f"Deterministic selection: top-ranked capability by score "
                f"({scored[0][1]:.2f}) for goal: {goal[:80]!r}"
            ),
            confidence=min(scored[0][1], 1.0),
            fallback_ids=fallback,
            selection_method="deterministic",
        )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _apply_constraints(
        self,
        candidates: list[CapabilityRecord],
        constraints: CapabilityConstraints,
    ) -> list[CapabilityRecord]:
        """Filter candidates against constraints."""
        result = []
        tier_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
        max_tier = tier_order.get(constraints.max_privacy_tier, 3)

        for cap in candidates:
            if not cap.is_usable:
                continue
            if cap.capability_id in constraints.excluded_ids:
                continue
            if not constraints.online_allowed and cap.online_required:
                continue
            if constraints.required_category and cap.category.value != constraints.required_category:
                continue
            cap_tier = tier_order.get(cap.privacy_tier, 3)
            if cap_tier < max_tier:
                # Capability is more sensitive than allowed
                continue
            result.append(cap)
        return result

    def _summarize(self, cap: CapabilityRecord) -> dict[str, Any]:
        """Compact summary of a capability for AI context."""
        return {
            "id": cap.capability_id,
            "name": cap.name,
            "description": cap.description,
            "category": cap.category.value,
            "success_rate": round(cap.metrics.success_rate, 2),
            "health": cap.health.status.value,
            "online_required": cap.online_required,
            "privacy_tier": cap.privacy_tier,
            "trust": cap.trust_state.value,
            "ranking_score": round(cap.ranking_score(), 3),
        }
