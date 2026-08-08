"""P07 Privacy — ZoneRegistry and zone-aware filtering.

A PrivacyZone wraps a PrivacyZonePolicy with a name and optional scope
metadata. The ZoneRegistry holds all active zones and exposes a single
``allows(node)`` entry-point that scanners and the observer call FIRST
before passing any data to EnvironmentStore.

Import safety: l4_memory.policies + l4_memory.p07.model.types + stdlib ONLY.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aegis.l4_memory.policies import PrivacyZonePolicy
from aegis.l4_memory.p07.model.types import EnvNode


__all__ = ["PrivacyZone", "ZoneRegistry", "ZoneCheckResult"]


@dataclass(frozen=True)
class PrivacyZone:
    """A named privacy zone backed by a PrivacyZonePolicy.

    Attributes:
        name:     Unique name for display / audit.
        policy:   The policy that defines what is blocked.
        scope:    Optional scope tag (e.g. ``"observer"``, ``"app_scanner"``).
    """
    name: str
    policy: PrivacyZonePolicy
    scope: str = "global"     # Which component(s) this zone applies to


@dataclass
class ZoneCheckResult:
    """Result of a multi-zone allowance check."""
    allowed: bool
    blocking_zone: str | None = None  # Name of the first zone that blocked
    effective_privacy_tier: str = "P2"


class ZoneRegistry:
    """Registry of active PrivacyZones.

    Usage::

        registry = ZoneRegistry()
        registry.add(PrivacyZone(
            name="ssh_zone",
            policy=PrivacyZonePolicy(
                blocked_path_prefixes=["~/.ssh"],
                min_privacy_tier="P0",
            ),
        ))
        result = registry.check_node(node)
        if not result.allowed:
            return  # drop — do not store

    All checks are deterministic. No AI is involved.
    """

    def __init__(self) -> None:
        self._zones: dict[str, PrivacyZone] = {}

    # ------------------------------------------------------------------
    # Zone management
    # ------------------------------------------------------------------

    def add(self, zone: PrivacyZone) -> None:
        """Register a privacy zone. Replaces existing zone with same name."""
        self._zones[zone.name] = zone

    def remove(self, name: str) -> None:
        """Unregister a privacy zone by name."""
        self._zones.pop(name, None)

    def clear(self) -> None:
        """Remove all zones (opt-out / reset)."""
        self._zones.clear()

    @property
    def zone_names(self) -> list[str]:
        return list(self._zones.keys())

    # ------------------------------------------------------------------
    # Check helpers — called FIRST at every ingestion boundary
    # ------------------------------------------------------------------

    def check_node(self, node: EnvNode) -> ZoneCheckResult:
        """Check an EnvNode against all registered zones.

        Returns a ZoneCheckResult. If any enabled zone blocks the node,
        ``allowed=False`` is returned with the name of the blocking zone.

        The effective_privacy_tier is the most protective tier from all
        matching zones (lowest ordinal wins).
        """
        effective_tier = "P2"
        _tier_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}

        for zone in self._zones.values():
            if not zone.policy.enabled:
                continue
            # Path check
            if node.source_path and not zone.policy.allows_path(node.source_path):
                return ZoneCheckResult(
                    allowed=False,
                    blocking_zone=zone.name,
                    effective_privacy_tier="P0",
                )
            # App name check
            if not zone.policy.allows_app(node.label):
                return ZoneCheckResult(
                    allowed=False,
                    blocking_zone=zone.name,
                    effective_privacy_tier="P0",
                )
            # Update effective tier (most protective wins)
            candidate = zone.policy.effective_privacy_tier(effective_tier)
            if _tier_order.get(candidate, 2) < _tier_order.get(effective_tier, 2):
                effective_tier = candidate

        return ZoneCheckResult(
            allowed=True,
            blocking_zone=None,
            effective_privacy_tier=effective_tier,
        )

    def check_path(self, path: str) -> bool:
        """Quick path-only check. Returns False if any zone blocks the path."""
        for zone in self._zones.values():
            if zone.policy.enabled and not zone.policy.allows_path(path):
                return False
        return True

    def check_app(self, app_name: str) -> bool:
        """Quick app-name check. Returns False if any zone blocks the app."""
        for zone in self._zones.values():
            if zone.policy.enabled and not zone.policy.allows_app(app_name):
                return False
        return True

    def effective_tier_for_path(self, path: str, default: str = "P2") -> str:
        """Return the most protective tier from all zones for a given path."""
        _tier_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
        tier = default
        for zone in self._zones.values():
            candidate = zone.policy.effective_privacy_tier(tier)
            if _tier_order.get(candidate, 2) < _tier_order.get(tier, 2):
                tier = candidate
        return tier

    def __len__(self) -> int:
        return len(self._zones)
