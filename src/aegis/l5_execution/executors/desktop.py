"""L5 Execution Engine — Desktop Executor Stub.

Full implementation planned for Prompt 09 (Real Computer Control).
"""

from __future__ import annotations

from aegis.l5_execution.executors.base import StubExecutor
from aegis.l5_execution.types import ActionKind

__all__ = ["DesktopExecutor"]

DesktopExecutor = StubExecutor(
    name="desktop",
    handles=[
        ActionKind.DESKTOP_SCREENSHOT,
        ActionKind.DESKTOP_MOUSE,
        ActionKind.DESKTOP_KEYBOARD,
        ActionKind.DESKTOP_WINDOW,
    ],
    milestone="Prompt 09 (Real Computer Control)",
)
