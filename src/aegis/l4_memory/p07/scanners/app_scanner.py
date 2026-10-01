"""P07 Scanners — ApplicationScanner.

Discovers installed applications via pluggable ApplicationDiscoveryProviders:
  - WindowsRegistryProvider: HKLM/HKCU Uninstall keys (Windows only)
  - PathToolProvider: shutil.which over common tool names (cross-platform)
  - CompositeProvider: combines multiple providers

Default providers are selected automatically based on platform, but can be
overridden via constructor injection for testing.

All operations are bounded by max_seconds + max_results.
Privacy zone checks must be performed by the caller (coordinator).

Import safety: l4_memory.p07.* + stdlib ONLY. No L5/L6/L3.
"""

from __future__ import annotations

import time

from aegis.l4_memory.p07.model.types import ScanResult
from aegis.l4_memory.p07.scanners.base import ScannerBase, ScannerConfig
from aegis.l4_memory.p07.scanners.providers import (
    ApplicationDiscoveryProvider,
    _COMMON_TOOLS,
    default_providers,
)

__all__ = ["ApplicationScanner"]


class ApplicationScanner(ScannerBase):
    """Discover installed applications using pluggable discovery providers.

    By default uses the platform-appropriate providers:
      - Windows: WindowsRegistryProvider + PathToolProvider
      - Linux/macOS: PathToolProvider

    For testing, inject a mock provider::

        scanner = ApplicationScanner(
            config=ScannerConfig(opt_in=True),
            providers=[MockProvider(nodes=[...])],
        )

    Produces EnvNode records of kind APPLICATION.
    """

    name = "app_scanner"

    def __init__(
        self,
        config: ScannerConfig | None = None,
        providers: list[ApplicationDiscoveryProvider] | None = None,
    ) -> None:
        """
        Args:
            config:    Scanner configuration. Defaults to ScannerConfig().
            providers: Discovery provider stack. Defaults to default_providers()
                       (platform-appropriate). Override for testing.
        """
        super().__init__(config)
        self._providers: list[ApplicationDiscoveryProvider] = (
            providers if providers is not None else default_providers()
        )

    async def _run(self, config: ScannerConfig, deadline: float) -> ScanResult:
        from aegis.l4_memory.p07.model.types import EnvNode

        all_nodes: list[EnvNode] = []
        seen_keys: set[str] = set()

        for provider in self._providers:
            if time.monotonic() > deadline or len(all_nodes) >= config.max_results:
                break
            remaining = config.max_results - len(all_nodes)
            new_nodes = provider.discover(
                deadline=deadline,
                max_results=remaining,
                privacy_tier=config.privacy_tier,
                existing_keys=seen_keys,
            )
            for node in new_nodes:
                seen_keys.add(node.key)
            all_nodes.extend(new_nodes)

        truncated = time.monotonic() > deadline or len(all_nodes) >= config.max_results
        return ScanResult(
            scanner_name=self.name,
            nodes=all_nodes[:config.max_results],
            truncated=truncated,
        )
