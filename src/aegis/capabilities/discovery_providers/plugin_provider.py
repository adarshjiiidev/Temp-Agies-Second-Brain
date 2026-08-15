"""Capabilities discovery — PluginDiscoveryProvider.

Bridges the L2 PluginLoader to the P08 capability registry by reading
the capabilities list from each loaded plugin's PluginManifest.

Plugin-declared capabilities start as VERIFIED (plugin is loaded and
manifested) but below TRUSTED. They may be elevated via policy.

Import safety: stdlib + aegis.capabilities.model + aegis.l2_foundation.plugin_loader
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aegis.capabilities.discovery_providers.base import CapabilityDiscoveryProvider
from aegis.capabilities.model.capability import (
    CapabilityCategory,
    CapabilityRecord,
    ProvenanceSource,
    TrustState,
)
from aegis.capabilities.model.composition import BuiltinRef
from aegis.capabilities.model.health import CapabilityHealth, HealthStatus

if TYPE_CHECKING:
    from aegis.l2_foundation.plugin_loader.loader import PluginLoader

logger = logging.getLogger(__name__)

__all__ = ["PluginDiscoveryProvider"]


class PluginDiscoveryProvider(CapabilityDiscoveryProvider):
    """Discovers capabilities declared in L2 plugin manifests.

    For each loaded plugin, reads ``PluginManifest.capabilities`` (list of
    string capability verb declarations) and creates a CapabilityRecord for
    each. These capabilities wrap the plugin's own executor logic.

    The existing L2 plugin system is reused — no second plugin system.

    Usage::

        plugin_loader = PluginLoader()
        # ... plugins loaded ...
        provider = PluginDiscoveryProvider(plugin_loader)
        records = provider.safe_discover(deadline=...)
    """

    def __init__(self, plugin_loader: "PluginLoader | None" = None) -> None:
        self._loader = plugin_loader

    @property
    def name(self) -> str:
        return "plugin_discovery_provider"

    def discover(self, deadline: float) -> list[CapabilityRecord]:
        if self._loader is None:
            return []

        records: list[CapabilityRecord] = []
        try:
            plugins = self._loader.list_plugins()
        except Exception as exc:  # noqa: BLE001
            logger.warning("PluginDiscoveryProvider: failed to list plugins: %s", exc)
            return []

        for plugin_id, plugin_stub in plugins.items():
            manifest = plugin_stub.manifest
            if not manifest.capabilities:
                continue
            for verb in manifest.capabilities:
                cap_id = f"plugin:{plugin_id}:{verb}"
                record = CapabilityRecord(
                    capability_id=cap_id,
                    name=f"[Plugin:{plugin_id}] {verb}",
                    description=(
                        f"Capability '{verb}' provided by plugin '{manifest.display_name or plugin_id}'"
                    ),
                    category=CapabilityCategory.CUSTOM,
                    version=manifest.version,
                    provider_id=f"plugin:{plugin_id}",
                    provenance=ProvenanceSource.PLUGIN,
                    trust_state=TrustState.VERIFIED,
                    implementation=BuiltinRef(
                        executor_name=f"plugin_{plugin_id}_executor",
                        action_kind=verb,
                        module_path=manifest.entry_point,
                    ),
                    health=CapabilityHealth(status=HealthStatus.UNKNOWN),
                    enabled=True,
                )
                records.append(record)
                logger.debug(
                    "PluginDiscoveryProvider: registered plugin capability %r", cap_id
                )

        return records
