"""L5 Execution Engine — Browser Executor Stub.

Full implementation planned for Prompt 10 (Browser OS + Web Learning).
This stub registers the action kinds in the registry so the pipeline
can produce clear "not yet available" errors instead of ExecutorNotFoundError.
"""

from __future__ import annotations

from aegis.l5_execution.executors.base import StubExecutor
from aegis.l5_execution.types import ActionKind

__all__ = ["BrowserExecutor"]

BrowserExecutor = StubExecutor(
    name="browser",
    handles=[
        ActionKind.BROWSER_NAVIGATE,
        ActionKind.BROWSER_READ,
        ActionKind.BROWSER_FILL,
        ActionKind.BROWSER_CLICK,
        ActionKind.BROWSER_DOWNLOAD,
    ],
    milestone="Prompt 10 (Browser OS + Web Learning)",
)
