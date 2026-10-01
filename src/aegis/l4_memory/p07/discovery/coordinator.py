"""P07 Discovery — ScanningCoordinator.

Orchestrates multiple environment scanners under:
  - Explicit consent (ConsentGate)
  - Privacy zone filtering (ZoneRegistry)
  - Optional EnvironmentStore persistence

The coordinator guarantees:
  1. Scanning is completely blocked without explicit consent.
  2. Privacy zone filter runs BEFORE any data reaches the store.
  3. All scanner runs are bounded (max_seconds, max_results).
  4. Results are returned even in dry_run mode (no persistence).

Import safety: l4_memory.p07.* + stdlib ONLY.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from aegis.l4_memory.p07.discovery.consent import ConsentGate, ConsentScope
from aegis.l4_memory.p07.model.scheduler import FreshnessScheduler
from aegis.l4_memory.p07.model.types import EnvNode, ScanResult
from aegis.l4_memory.p07.privacy.zones import ZoneRegistry
from aegis.l4_memory.p07.scanners.base import ScannerBase

logger = logging.getLogger(__name__)

__all__ = ["ScanningCoordinator", "DiscoveryResult"]


@dataclass
class DiscoveryResult:
    """Result of a full discovery run.

    Attributes:
        scan_results:      Per-scanner ScanResult objects.
        total_nodes:       Total nodes discovered across all scanners.
        total_filtered:    Nodes dropped by privacy zone filter.
        persisted_nodes:   Nodes actually written to the store (0 if dry_run).
        consent_denied:    True if the run was blocked due to missing consent.
        errors:            Any non-fatal errors from individual scanners.
    """
    scan_results: list[ScanResult] = field(default_factory=list)
    total_nodes: int = 0
    total_filtered: int = 0
    persisted_nodes: int = 0
    consent_denied: bool = False
    errors: list[str] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        """True if discovery ran (consent granted) and had no fatal errors."""
        return not self.consent_denied


class ScanningCoordinator:
    """Orchestrates P07 environment scanners with consent + privacy gate.

    Usage::

        # Set up
        gate = ConsentGate()
        zones = ZoneRegistry()
        coordinator = ScanningCoordinator(
            consent_gate=gate,
            zone_registry=zones,
            scanners=[ApplicationScanner(), ProjectScanner()],
        )

        # Without consent → blocked
        result = await coordinator.run_discovery()
        assert result.consent_denied

        # Grant consent
        gate.grant(ConsentScope.ALL)
        result = await coordinator.run_discovery(env_store=store)
        assert result.total_nodes > 0

    The coordinator does NOT own scanner lifecycle — callers create and
    configure scanners before passing them in.
    """

    def __init__(
        self,
        consent_gate: ConsentGate,
        zone_registry: ZoneRegistry | None = None,
        scanners: list[ScannerBase] | None = None,
        freshness_scheduler: FreshnessScheduler | None = None,
        logger_: logging.Logger | None = None,
    ) -> None:
        self._consent = consent_gate
        self._zones = zone_registry or ZoneRegistry()
        self._scanners: list[ScannerBase] = list(scanners or [])
        self._scheduler = freshness_scheduler
        self._log = logger_ or logger
        self._env_store: Any = None  # Set by start() for scheduler rescans

    # ------------------------------------------------------------------
    # Scanner management
    # ------------------------------------------------------------------

    def add_scanner(self, scanner: ScannerBase) -> None:
        """Register a scanner with the coordinator."""
        self._scanners.append(scanner)

    def remove_scanner(self, name: str) -> bool:
        """Remove a scanner by name. Returns True if found and removed."""
        for i, s in enumerate(self._scanners):
            if s.name == name:
                del self._scanners[i]
                return True
        return False

    # ------------------------------------------------------------------
    # Lifecycle (optional — needed when FreshnessScheduler is attached)
    # ------------------------------------------------------------------

    async def start(self, env_store: Any = None) -> None:
        """Start the FreshnessScheduler background loop (if configured).

        Idempotent: no-op if no scheduler was provided or already running.

        Args:
            env_store: Optional EnvironmentStore passed to rescans triggered
                       by the scheduler.  If None, rescans run in dry-run mode.
        """
        if self._scheduler is None:
            return
        self._env_store = env_store
        # Register all current scanners with the freshness scheduler
        for scanner in self._scanners:
            async def _scan_fn(s=scanner, store=env_store) -> None:  # noqa: E731
                await self.run_discovery(env_store=store)
            self._scheduler.register(
                scanner.name,
                _scan_fn,
                ttl_seconds=86400.0,  # Default 24h TTL; override via scheduler.register()
            )
        await self._scheduler.start()
        self._log.info(
            "ScanningCoordinator: FreshnessScheduler started (%d scanner(s) registered)",
            len(self._scanners),
        )

    async def stop(self) -> None:
        """Stop the FreshnessScheduler background loop (if running).

        Idempotent: no-op if no scheduler was provided.
        """
        if self._scheduler is None:
            return
        await self._scheduler.stop()
        self._log.info("ScanningCoordinator: FreshnessScheduler stopped")

    @property
    def is_running(self) -> bool:
        """True if the background FreshnessScheduler is active."""
        return self._scheduler is not None and self._scheduler.is_running

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    async def run_discovery(
        self,
        env_store: Any = None,
        dry_run: bool = False,
    ) -> DiscoveryResult:
        """Run all registered scanners that have consent.

        Args:
            env_store: Optional EnvironmentStore for persistence.
                       If None or dry_run=True, nodes are discovered but not persisted.
            dry_run:   If True, scan but never write to the store.

        Returns:
            DiscoveryResult with aggregated statistics and scan results.
        """
        result = DiscoveryResult()

        # Consent gate check — all scanning blocked without any consent
        if not self._consent.has_any_consent:
            self._log.info(
                "ScanningCoordinator: discovery blocked — no consent granted. "
                "Call consent_gate.grant() to enable scanning."
            )
            result.consent_denied = True
            return result

        for scanner in self._scanners:
            # Map scanner name → consent scope
            scope = _scanner_name_to_scope(scanner.name)
            if not self._consent.is_allowed(scope):
                self._log.debug(
                    "ScanningCoordinator: scanner %r skipped (consent not granted for %s)",
                    scanner.name, scope.value
                )
                continue

            # Run scanner
            self._log.debug("ScanningCoordinator: running scanner %r", scanner.name)
            scan_result = await scanner.scan()
            result.scan_results.append(scan_result)

            if not scan_result.succeeded:
                result.errors.append(
                    f"{scanner.name}: {scan_result.error}"
                )
                continue

            # Privacy zone filter + optional persistence
            for node in scan_result.nodes:
                result.total_nodes += 1
                zone_check = self._zones.check_node(node)
                if not zone_check.allowed:
                    result.total_filtered += 1
                    self._log.debug(
                        "ScanningCoordinator: node %r blocked by privacy zone %r",
                        node.key, zone_check.blocking_zone
                    )
                    continue

                # Apply effective privacy tier from zone
                if zone_check.effective_privacy_tier != node.privacy_tier:
                    node = _apply_tier(node, zone_check.effective_privacy_tier)

                # Persist if store available and not dry_run
                if env_store is not None and not dry_run:
                    try:
                        await env_store.upsert_node(node, scanner_id=scanner.name)
                        result.persisted_nodes += 1
                    except Exception as exc:
                        self._log.warning(
                            "ScanningCoordinator: failed to persist node %r: %s",
                            node.key, exc
                        )

        return result

    @property
    def scanner_names(self) -> list[str]:
        return [s.name for s in self._scanners]

    @property
    def scanner_count(self) -> int:
        return len(self._scanners)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SCOPE_MAP: dict[str, ConsentScope] = {
    "app_scanner":      ConsentScope.APP_SCANNER,
    "project_scanner":  ConsentScope.PROJECT_SCANNER,
    "cli_scanner":      ConsentScope.CLI_SCANNER,
    "relation_scanner": ConsentScope.RELATION_SCANNER,
    "observer":         ConsentScope.OBSERVER,
}


def _scanner_name_to_scope(name: str) -> ConsentScope:
    """Map a scanner name to its ConsentScope (default: APP_SCANNER if unknown)."""
    return _SCOPE_MAP.get(name, ConsentScope.APP_SCANNER)


def _apply_tier(node: EnvNode, tier: str) -> EnvNode:
    """Return a copy of node with updated privacy_tier."""
    from dataclasses import replace
    return replace(node, privacy_tier=tier)
