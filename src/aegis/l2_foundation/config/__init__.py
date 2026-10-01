"""L2 Configuration subsystem.
Layered precedence (Prompt 01 §05): Defaults → Config File → Env Vars → Runtime Overrides.
Snapshots are immutable once validated; secret:// references never resolve to plaintext in logs."""

from aegis.l2_foundation.config.loader import (
    ConfigLoader,
    ImmutableConfigSnapshot,
    load_config,
)

__all__ = [
    "ConfigLoader",
    "ImmutableConfigSnapshot",
    "load_config",
]
