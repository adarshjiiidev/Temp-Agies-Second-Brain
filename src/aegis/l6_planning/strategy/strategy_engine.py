"""L6 Planning Engine — Strategy Engine.

Selects and applies a PlanningStrategy based on mission context,
user preferences, and constraints.

Import safety: stdlib + pydantic + l6_planning internal only.
"""

from __future__ import annotations

from typing import Any

from aegis.l6_planning.planning.mission import Mission
from aegis.l6_planning.types import ConstraintKind, IntentDomain, PlanningStrategy

__all__ = ["StrategyEngine"]


# Domain → preferred default strategy
_DOMAIN_STRATEGY: dict[IntentDomain, PlanningStrategy] = {
    IntentDomain.CODING: PlanningStrategy.DEVELOPER_MODE,
    IntentDomain.RESEARCH: PlanningStrategy.RESEARCH_MODE,
    IntentDomain.BROWSER: PlanningStrategy.BALANCED,
    IntentDomain.FILESYSTEM: PlanningStrategy.FASTEST,
    IntentDomain.TERMINAL: PlanningStrategy.FASTEST,
    IntentDomain.FINANCE: PlanningStrategy.HIGHEST_QUALITY,
    IntentDomain.AUTOMATION: PlanningStrategy.BALANCED,
    IntentDomain.VISION: PlanningStrategy.BALANCED,
    IntentDomain.VOICE: PlanningStrategy.BALANCED,
    IntentDomain.PLANNING: PlanningStrategy.BALANCED,
    IntentDomain.MIXED: PlanningStrategy.BALANCED,
    IntentDomain.UNKNOWN: PlanningStrategy.BALANCED,
}


class StrategyEngine:
    """Selects and applies a PlanningStrategy for a Mission.

    Selection priority:
    1. Explicit user/caller strategy override
    2. Privacy or offline constraint → PRIVACY_FIRST / OFFLINE_FIRST
    3. Domain-based default
    4. BALANCED fallback

    Usage::

        engine = StrategyEngine()
        strategy = engine.select_strategy(mission)
        # PlanningStrategy.DEVELOPER_MODE  (for coding missions)
    """

    def select_strategy(
        self,
        mission: Mission,
        user_preference: PlanningStrategy | None = None,
        context: dict[str, Any] | None = None,
    ) -> PlanningStrategy:
        """Select the most appropriate PlanningStrategy for the mission.

        Args:
            mission: The Mission being planned.
            user_preference: Explicit user strategy preference (highest priority).
            context: Optional hints (e.g., battery_low, deadline_urgent).

        Returns:
            Selected PlanningStrategy.
        """
        # 1. Explicit user override
        if user_preference is not None:
            return user_preference

        # 2. Hard constraint overrides
        for constraint in mission.constraints:
            if constraint.hard:
                if constraint.kind is ConstraintKind.PRIVACY:
                    return PlanningStrategy.PRIVACY_FIRST
                if constraint.kind is ConstraintKind.OFFLINE:
                    return PlanningStrategy.OFFLINE_FIRST

        # 3. Intent-level overrides
        if mission.parsed_intent.requires_local_only:
            return PlanningStrategy.OFFLINE_FIRST

        # 4. Context hints
        if context:
            if context.get("battery_low"):
                return PlanningStrategy.ENERGY_SAVING
            if context.get("deadline_urgent"):
                return PlanningStrategy.FASTEST
            if context.get("cost_sensitive"):
                return PlanningStrategy.CHEAPEST

        # 5. Mission-level strategy if set explicitly
        if mission.strategy is not PlanningStrategy.BALANCED:
            return mission.strategy

        # 6. Domain default
        return _DOMAIN_STRATEGY.get(mission.parsed_intent.domain, PlanningStrategy.BALANCED)

    def describe_strategy(self, strategy: PlanningStrategy) -> str:
        """Return a human-readable description of the strategy."""
        return strategy.description
