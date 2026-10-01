"""L5 Execution Engine — Temporary Workspace.

A scoped scratch directory for T2/T3 sandbox operations.
Auto-cleanup on context exit.  All paths inside the workspace are
validated to prevent path traversal.

Import safety: stdlib only.
"""

from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path

from aegis.l5_execution.exceptions import ResourceScopeError

__all__ = ["TempWorkspace"]


class TempWorkspace:
    """A scoped temporary directory for sandbox operations.

    Usage::

        async with TempWorkspace.create("git-clone") as ws:
            ws.validate_path("output/result.txt")  # OK
            ws.validate_path("../../etc/passwd")    # raises ResourceScopeError
            dest = ws.path / "output" / "result.txt"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text("hello")
        # workspace is deleted here
    """

    def __init__(self, path: Path, name: str = "") -> None:
        self._path = path
        self._name = name or path.name

    @property
    def path(self) -> Path:
        return self._path

    @property
    def name(self) -> str:
        return self._name

    @classmethod
    def create(cls, prefix: str = "aegis-sandbox") -> "TempWorkspace":
        """Create a new temporary workspace directory."""
        base = tempfile.mkdtemp(prefix=f"{prefix}-{uuid.uuid4().hex[:8]}-")
        return cls(path=Path(base), name=prefix)

    def validate_path(self, relative: str) -> Path:
        """Validate that ``relative`` stays inside the workspace.

        Returns the resolved absolute path.
        Raises ResourceScopeError on path traversal attempts.
        """
        try:
            resolved = (self._path / relative).resolve()
        except Exception as exc:
            raise ResourceScopeError(
                f"Path resolution failed for {relative!r}: {exc}",
                stage="sandbox",
            ) from exc

        try:
            resolved.relative_to(self._path.resolve())
        except ValueError:
            raise ResourceScopeError(
                f"Path traversal detected: {relative!r} escapes workspace {self._path!r}",
                stage="sandbox",
            )

        return resolved

    def cleanup(self) -> None:
        """Remove the workspace directory tree."""
        if self._path.exists():
            shutil.rmtree(self._path, ignore_errors=True)

    def __enter__(self) -> "TempWorkspace":
        return self

    def __exit__(self, *args: object) -> None:
        self.cleanup()

    def __repr__(self) -> str:
        return f"TempWorkspace(name={self._name!r}, path={self._path!r})"
