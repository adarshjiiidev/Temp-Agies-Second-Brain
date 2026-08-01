"""L5 Execution Engine — VS Code Executor Stub.

Full implementation planned for Prompt 12 (Coding Intelligence).
"""

from __future__ import annotations

from aegis.l5_execution.executors.base import StubExecutor
from aegis.l5_execution.types import ActionKind

__all__ = ["VSCodeExecutor"]

VSCodeExecutor = StubExecutor(
    name="vscode",
    handles=[
        ActionKind.VSCODE_READ,
        ActionKind.VSCODE_SEARCH,
        ActionKind.VSCODE_DIAGNOSTICS,
        ActionKind.VSCODE_TASK,
    ],
    milestone="Prompt 12 (Coding Intelligence)",
)
