"""P07 Privacy — PrivacyZoneService.

Cohesive orchestration API over ZoneRegistry + PrivacyZonePolicy.

The PrivacyZoneService is the canonical entry point for:
  - Adding, updating, removing, and listing privacy zones
  - Performing path checks with deterministic platform-aware normalization
  - Nested zone containment queries
  - Configuration export / import (serializable dict)

Architecture::

    PrivacyZoneService
            │
            ▼
        ZoneRegistry
            │
            ▼
    Privacy enforcement (check_node / check_path / check_app)

Design principles:
  - The service is an API / orchestration layer.
  - It does NOT duplicate enforcement (ZoneRegistry does that).
  - All path normalization is deterministic and explicitly documented.
  - Nested zone semantics are explicitly defined.
  - Export/import are round-trip lossless (no information is discarded).

PATH NORMALIZATION POLICY (documented explicitly):
  1. ``~`` is expanded to the home directory (os.path.expanduser).
  2. The result is normalized (os.path.normpath — removes ./, ../ etc.).
  3. On Windows (os.name == 'nt'), comparison is case-insensitive
     (os.path.normcase is applied to both sides of the comparison).
  4. On Unix (os.name == 'posix'), comparison is case-sensitive.
  5. Symlinks are NOT resolved (no os.path.realpath) to avoid leaking
     symlink targets into the privacy model unexpectedly.
  6. Separators are normalized to the platform default (os.sep).

NESTED ZONE POLICY:
  - Each zone is independent. A child zone (/private/project/secrets) does
    NOT automatically inherit or override a parent zone (/private).
  - Adding a parent zone does NOT add child zones.
  - Removing a parent zone does NOT remove child zones (they remain active).
  - This is explicit and deterministic: no implicit inheritance.
  - Callers that want parent-implies-child semantics must add both zones.
  - The service provides ``get_covering_zones(path)`` to list all zones
    that cover a given path (useful for audit).

IMPORT / EXPORT FORMAT:
  - ``export_configuration()`` returns a plain Python dict (serializable via
    json.dumps without extra encoders).
  - ``import_configuration(data)`` merges imported zones with existing ones.
  - Duplicate zone names in imported data overwrite existing zones.
  - ``import_configuration`` is atomic: all zones are validated before any
    are applied. Validation failure raises ValueError with zone name.

Import safety: l4_memory.p07.privacy.* + l4_memory.policies + stdlib ONLY.
"""

from __future__ import annotations

import os
import os.path
import logging
from dataclasses import dataclass
from typing import Any

from aegis.l4_memory.policies import PrivacyZonePolicy
from aegis.l4_memory.p07.privacy.zones import PrivacyZone, ZoneCheckResult, ZoneRegistry
from aegis.l4_memory.p07.model.types import EnvNode

__all__ = ["PrivacyZoneService", "ZoneSummary", "PrivacyZoneServiceConfig"]

logger = logging.getLogger(__name__)

_TIER_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
_VALID_TIERS = frozenset(_TIER_ORDER.keys())


@dataclass(frozen=True)
class ZoneSummary:
    """Structured summary of a registered privacy zone."""
    name: str
    enabled: bool
    scope: str
    blocked_path_prefixes: tuple[str, ...]
    blocked_app_names: tuple[str, ...]
    min_privacy_tier: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "scope": self.scope,
            "blocked_path_prefixes": list(self.blocked_path_prefixes),
            "blocked_app_names": list(self.blocked_app_names),
            "min_privacy_tier": self.min_privacy_tier,
        }


@dataclass(frozen=True)
class PrivacyZoneServiceConfig:
    """Configuration for PrivacyZoneService.

    Attributes:
        normalize_paths: If True (default), apply the documented path
                         normalization policy (expanduser + normpath +
                         normcase on Windows).
        allow_overwrite: If True (default), add_zone() with an existing name
                         replaces the zone. If False, raises ValueError on
                         duplicate names.
    """
    normalize_paths: bool = True
    allow_overwrite: bool = True


class PrivacyZoneService:
    """Orchestration service over ZoneRegistry.

    Usage::

        svc = PrivacyZoneService()
        svc.add_zone(
            name="ssh_zone",
            blocked_paths=["~/.ssh"],
            min_tier="P0",
        )
        if not svc.check_path("~/.ssh/id_rsa"):
            # blocked — do not scan
            pass

        # Export for persistence
        cfg = svc.export_configuration()
        # Later: reconstruct
        svc2 = PrivacyZoneService()
        svc2.import_configuration(cfg)
    """

    def __init__(
        self,
        registry: ZoneRegistry | None = None,
        config: PrivacyZoneServiceConfig | None = None,
    ) -> None:
        self._registry = registry or ZoneRegistry()
        self._config = config or PrivacyZoneServiceConfig()

    # ------------------------------------------------------------------
    # Zone management
    # ------------------------------------------------------------------

    def add_zone(
        self,
        name: str,
        blocked_paths: list[str] | None = None,
        blocked_apps: list[str] | None = None,
        min_tier: str | None = None,
        scope: str = "global",
        enabled: bool = True,
    ) -> None:
        """Add or replace a privacy zone.

        Args:
            name:          Unique zone name. If already exists and
                           allow_overwrite=True, replaces it.
            blocked_paths: List of path prefixes to block. ``~`` is supported.
            blocked_apps:  List of app name substrings to block (case-insensitive).
            min_tier:      Minimum privacy tier floor (e.g. "P0"). If None, no floor.
            scope:         Scope tag for audit (default: "global").
            enabled:       Whether the zone is active (default: True).

        Raises:
            ValueError: If name already exists and allow_overwrite=False.
            ValueError: If min_tier is not a recognised tier string.
        """
        if not name or not isinstance(name, str):
            raise ValueError(f"Zone name must be a non-empty string, got: {name!r}")

        if min_tier is not None and min_tier not in _VALID_TIERS:
            raise ValueError(f"Invalid min_tier {min_tier!r}. Must be one of {sorted(_VALID_TIERS)}")

        if not self._config.allow_overwrite and name in self._registry.zone_names:
            raise ValueError(f"Zone {name!r} already exists and allow_overwrite=False")

        normalized_paths = (
            [self._normalize_path_prefix(p) for p in (blocked_paths or [])]
            if self._config.normalize_paths
            else list(blocked_paths or [])
        )

        policy = PrivacyZonePolicy(
            name=name,
            enabled=enabled,
            blocked_path_prefixes=normalized_paths,
            blocked_app_names=list(blocked_apps or []),
            min_privacy_tier=min_tier,
        )
        zone = PrivacyZone(name=name, policy=policy, scope=scope)
        self._registry.add(zone)
        logger.debug("PrivacyZoneService: added zone %r (scope=%s, enabled=%s)", name, scope, enabled)

    def remove_zone(self, name: str) -> bool:
        """Remove a zone by name. Returns True if it was present.

        NOTE: Removing a parent-path zone does NOT remove child-path zones.
        Both are independent. See module docstring for nested zone policy.
        """
        if name not in self._registry.zone_names:
            return False
        self._registry.remove(name)
        logger.debug("PrivacyZoneService: removed zone %r", name)
        return True

    def update_zone(
        self,
        name: str,
        *,
        blocked_paths: list[str] | None = None,
        blocked_apps: list[str] | None = None,
        min_tier: str | None = None,
        scope: str | None = None,
        enabled: bool | None = None,
    ) -> bool:
        """Update an existing zone. Unspecified fields remain unchanged.

        Returns True if the zone existed and was updated; False if not found.
        """
        existing = self._get_zone(name)
        if existing is None:
            return False

        new_paths = (
            [self._normalize_path_prefix(p) for p in blocked_paths]
            if blocked_paths is not None
            else list(existing.policy.blocked_path_prefixes)
        )
        new_apps = blocked_apps if blocked_apps is not None else list(existing.policy.blocked_app_names)
        new_min_tier = min_tier if min_tier is not None else existing.policy.min_privacy_tier
        new_enabled = enabled if enabled is not None else existing.policy.enabled
        new_scope = scope if scope is not None else existing.scope

        if new_min_tier is not None and new_min_tier not in _VALID_TIERS:
            raise ValueError(f"Invalid min_tier {new_min_tier!r}")

        policy = PrivacyZonePolicy(
            name=name,
            enabled=new_enabled,
            blocked_path_prefixes=new_paths,
            blocked_app_names=new_apps,
            min_privacy_tier=new_min_tier,
        )
        zone = PrivacyZone(name=name, policy=policy, scope=new_scope)
        self._registry.add(zone)
        logger.debug("PrivacyZoneService: updated zone %r", name)
        return True

    def list_zones(self) -> list[ZoneSummary]:
        """Return a structured list of all registered zones."""
        summaries = []
        for name in self._registry.zone_names:
            zone = self._get_zone(name)
            if zone is None:
                continue
            summaries.append(ZoneSummary(
                name=zone.name,
                enabled=zone.policy.enabled,
                scope=zone.scope,
                blocked_path_prefixes=tuple(zone.policy.blocked_path_prefixes),
                blocked_app_names=tuple(zone.policy.blocked_app_names),
                min_privacy_tier=zone.policy.min_privacy_tier,
            ))
        return summaries

    def zone_count(self) -> int:
        """Return the number of registered zones."""
        return len(self._registry)

    def clear_all_zones(self) -> int:
        """Remove all zones. Returns the count removed."""
        count = len(self._registry)
        self._registry.clear()
        return count

    # ------------------------------------------------------------------
    # Path / node / app checks
    # ------------------------------------------------------------------

    def check_path(self, path: str) -> bool:
        """Return True if the path is allowed by all active zones.

        Applies the documented path normalization policy before checking.
        """
        normalized = self._normalize_path(path) if self._config.normalize_paths else path
        return self._registry.check_path(normalized)

    def check_node(self, node: EnvNode) -> ZoneCheckResult:
        """Check an EnvNode against all zones. Returns ZoneCheckResult."""
        if node.source_path and self._config.normalize_paths:
            normalized_path = self._normalize_path(node.source_path)
            if normalized_path != node.source_path:
                # Build a temporary node with normalized path for checking
                from dataclasses import replace as dc_replace
                node = dc_replace(node, source_path=normalized_path)
        return self._registry.check_node(node)

    def check_app(self, app_name: str) -> bool:
        """Return True if the app name passes all active zones."""
        return self._registry.check_app(app_name)

    def get_covering_zones(self, path: str) -> list[str]:
        """Return names of all zones whose blocked prefixes cover this path.

        A zone 'covers' a path if the path starts with any of the zone's
        blocked_path_prefixes (after normalization).

        Useful for audit: which zones are affecting a given path?
        A zone covering a path does NOT necessarily block it — the zone
        must also be enabled.
        """
        normalized = self._normalize_path(path) if self._config.normalize_paths else path
        covering = []
        for name in self._registry.zone_names:
            zone = self._get_zone(name)
            if zone is None:
                continue
            for stored_prefix in zone.policy.blocked_path_prefixes:
                # stored_prefix is already normalized with trailing sep (from add_zone /
                # update_zone).  _paths_match_prefix adds trailing sep if missing so this
                # handles both normalise=True and normalise=False cases safely.
                if self._paths_match_prefix(normalized, stored_prefix):
                    covering.append(name)
                    break
        return covering

    def is_nested_under(self, child_path: str, parent_path: str) -> bool:
        """Return True if child_path is contained within parent_path.

        Uses the documented normalization policy.
        This is a pure utility method — it does NOT consult zones.
        """
        n_child = self._normalize_path(child_path) if self._config.normalize_paths else child_path
        n_parent = self._normalize_path(parent_path) if self._config.normalize_paths else parent_path
        return self._paths_match_prefix(n_child, n_parent)

    # ------------------------------------------------------------------
    # Export / import
    # ------------------------------------------------------------------

    def export_configuration(self) -> dict[str, Any]:
        """Export all zones as a serializable dict.

        The format is::

            {
                "version": 1,
                "zones": [
                    {
                        "name": "ssh_zone",
                        "enabled": true,
                        "scope": "global",
                        "blocked_path_prefixes": ["~/.ssh"],
                        "blocked_app_names": [],
                        "min_privacy_tier": "P0"
                    },
                    ...
                ]
            }

        This format is stable. All values are JSON-serializable (str / bool /
        list / None). No UUIDs or datetime objects.
        """
        return {
            "version": 1,
            "zones": [s.to_dict() for s in self.list_zones()],
        }

    def import_configuration(self, data: dict[str, Any]) -> int:
        """Import zones from a configuration dict (as returned by export).

        Validates ALL entries before applying any of them.
        On validation failure, raises ValueError with details and
        leaves the existing zones unchanged.

        Duplicate zone names in the import data overwrite existing zones.

        Args:
            data: Dict in the format produced by export_configuration().

        Returns:
            Number of zones imported.

        Raises:
            ValueError: If data format is invalid or any zone entry is malformed.
        """
        if not isinstance(data, dict):
            raise ValueError("import_configuration: expected a dict")
        version = data.get("version")
        if version != 1:
            raise ValueError(f"import_configuration: unsupported version {version!r}")
        zones_raw = data.get("zones")
        if not isinstance(zones_raw, list):
            raise ValueError("import_configuration: 'zones' must be a list")

        # Validate all entries first
        validated: list[dict] = []
        for idx, entry in enumerate(zones_raw):
            if not isinstance(entry, dict):
                raise ValueError(f"import_configuration: zone[{idx}] must be a dict")
            name = entry.get("name")
            if not name or not isinstance(name, str):
                raise ValueError(f"import_configuration: zone[{idx}] missing valid 'name'")
            min_tier = entry.get("min_privacy_tier")
            if min_tier is not None and min_tier not in _VALID_TIERS:
                raise ValueError(
                    f"import_configuration: zone {name!r} has invalid min_tier {min_tier!r}"
                )
            validated.append(entry)

        # Apply
        for entry in validated:
            self.add_zone(
                name=entry["name"],
                blocked_paths=entry.get("blocked_path_prefixes", []),
                blocked_apps=entry.get("blocked_app_names", []),
                min_tier=entry.get("min_privacy_tier"),
                scope=entry.get("scope", "global"),
                enabled=entry.get("enabled", True),
            )

        logger.info("PrivacyZoneService: imported %d zone(s)", len(validated))
        return len(validated)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_zone(self, name: str) -> PrivacyZone | None:
        """Retrieve a zone from the registry by name."""
        # ZoneRegistry stores zones in _zones dict; access via internal attr
        return self._registry._zones.get(name)  # noqa: SLF001

    @staticmethod
    def _normalize_path(path: str) -> str:
        """Apply the documented path normalization policy.

        Steps:
          1. Expand ~ to home directory.
          2. os.path.normpath (resolves ./ and ../).
          3. On Windows: os.path.normcase (case fold).
          4. Convert to forward slashes for consistent comparison,
             then back to platform separator.

        Symlinks are NOT resolved (os.path.realpath is not called).
        """
        if not path:
            return path
        expanded = os.path.expanduser(path)
        normed = os.path.normpath(expanded)
        # Platform case normalization (Windows: case-insensitive)
        return os.path.normcase(normed)

    @staticmethod
    def _normalize_path_prefix(path: str) -> str:
        """Normalize a path prefix for storage in a PrivacyZonePolicy.

        Same as _normalize_path, but also appends a trailing os.sep so that
        the underlying PrivacyZonePolicy.allows_path() startswith() check
        correctly handles directory boundaries.

        Example:
            /private  →  /private/    (blocks /private/foo but NOT /private_extra)
            ~/.ssh    →  /home/user/.ssh/

        The stored prefix is always a normalized directory path ending with sep,
        so the PrivacyZonePolicy's ``startswith(prefix)`` check is boundary-safe.
        """
        if not path:
            return path
        expanded = os.path.expanduser(path)
        normed = os.path.normpath(expanded)
        cased = os.path.normcase(normed)
        # Append trailing separator for boundary-safe startswith matching
        sep = os.sep
        if not cased.endswith(sep):
            cased = cased + sep
        return cased

    @staticmethod
    def _paths_match_prefix(path: str, prefix: str) -> bool:
        """Return True if path starts with prefix (platform-normalized).

        Handles trailing separator correctly so /private does not accidentally
        match /private_ext.
        """
        if not prefix:
            return True
        # Ensure prefix ends with separator for reliable prefix matching
        sep = os.sep
        if not prefix.endswith(sep):
            prefix_check = prefix + sep
        else:
            prefix_check = prefix
        return path.startswith(prefix_check) or path == prefix.rstrip(sep)

