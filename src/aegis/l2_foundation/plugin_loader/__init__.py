"""L2 Plugin Loader skeleton — Prompt 02.
Manifest-based deny-by-default plugin loading. Sandbox tiers defined but actual sandbox
code / dynamic import gates deferred to Prompt 10+."""
from aegis.l2_foundation.plugin_loader.loader import (
    PluginLoader,
    PluginManifest,
    SandboxTier,
)

__all__ = ["PluginLoader", "PluginManifest", "SandboxTier"]
