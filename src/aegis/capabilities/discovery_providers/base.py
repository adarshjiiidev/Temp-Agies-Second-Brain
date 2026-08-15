"""Capabilities discovery — CapabilityDiscoveryProvider ABC.

All discovery providers must implement this interface.

Design principles:
- Never raise: errors return empty list and log a warning.
- Respect the deadline: stop probing when time.monotonic() > deadline.
- Work offline: online_required declares whether the provider needs internet.
- Fast: individual probes should complete in < 500ms each.

Import safety: stdlib + aegis.capabilities.model only.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod

from aegis.capabilities.model.capability import CapabilityRecord

logger = logging.getLogger(__name__)

__all__ = ["CapabilityDiscoveryProvider"]


class CapabilityDiscoveryProvider(ABC):
    """Abstract base class for capability discovery backends.

    Each provider discovers a specific class of capabilities:
    - StaticRegistryProvider: builtin AEGIS capabilities (always available)
    - CLIDiscoveryProvider: CLI tools on PATH (git, docker, etc.)
    - LocalModelDiscoveryProvider: Ollama / LM Studio local model servers
    - MCPDiscoveryProvider: MCP server tool lists
    - PluginDiscoveryProvider: capabilities declared by L2 plugins

    Providers are run in parallel by the CapabilityRegistry.discover() method.
    Each provider runs synchronously in an executor thread pool.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable human-readable identifier for this provider."""

    @property
    def online_required(self) -> bool:
        """True if this provider requires internet access.
        Override in providers that make external network calls.
        """
        return False

    @abstractmethod
    def discover(self, deadline: float) -> list[CapabilityRecord]:
        """Discover capabilities and return CapabilityRecord objects.

        Args:
            deadline: time.monotonic() value — stop probing when exceeded.

        Returns:
            List of discovered capability records (may be empty).
            Never raises — return empty list on any error.
        """

    def safe_discover(self, deadline: float) -> list[CapabilityRecord]:
        """Wrapper that catches all exceptions and logs them.

        Callers should use this instead of discover() directly so that
        a crashing provider does not abort the entire discovery run.
        """
        try:
            return self.discover(deadline)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "CapabilityDiscoveryProvider[%s]: discover() raised unexpectedly: %s",
                self.name, exc,
            )
            return []
