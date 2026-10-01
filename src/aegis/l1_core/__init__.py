"""L1 Core — Layer 1 per architecture.
Exports runtime, supervisor, interfaces, errors, health, DI.
L1 code MAY NOT import from L2 or above — see import-linter contracts in pyproject.toml."""

from aegis.l1_core import (
    di,  # noqa: F401
    errors,  # noqa: F401
    health,  # noqa: F401
    interfaces,  # noqa: F401
)
from aegis.l1_core.runtime import CoreRuntime, RuntimeState
from aegis.l1_core.supervisor import Supervisor

__all__ = ["CoreRuntime", "RuntimeState", "Supervisor"]
