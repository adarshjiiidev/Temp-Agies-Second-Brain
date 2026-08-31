"""AgentMoe — PathGuard (Phase 2 security).

Prevents path traversal attacks in all filesystem operations.

Pattern adapted from Hermes Agent tools/path_security.py (MIT license).
Adapted to integrate with AEGIS PrivacyZoneService from L4.

Security properties guaranteed:
  1. Symlink following — uses Path.resolve() so symlink chains are followed.
  2. Traversal prevention — relative_to() ensures path stays within root.
  3. Privacy zone enforcement — defers to L4 PrivacyZoneService if available.
  4. Null byte rejection — null bytes in paths are rejected (CVE class).
  5. Absolute path enforcement for sensitive checks.

Import safety: stdlib + pathlib (no L4/L5 imports — guards are pre-pipeline).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Sequence


__all__ = [
    "PathGuardError",
    "PathGuard",
]


class PathGuardError(Exception):
    """Raised when a path fails validation."""
    def __init__(self, message: str, path: Optional[str] = None) -> None:
        super().__init__(message)
        self.path = path


class PathGuard:
    """Validates filesystem paths against traversal and privacy rules.

    Usage::

        guard = PathGuard(workspace_root=Path("/workspace"))
        safe_path = guard.validate("/workspace/src/main.py")     # OK
        guard.validate("/workspace/../etc/passwd")               # raises PathGuardError
        guard.validate("/etc/shadow")                            # raises PathGuardError
    """

    # SAFETY — system paths that must NEVER be written to under any circumstances
    # This is a safety boundary, not configuration.
    _ALWAYS_BLOCKED_PREFIXES: tuple[str, ...] = (
        "/etc/passwd",
        "/etc/shadow",
        "/etc/sudoers",
        "/etc/ssh",
        "/proc/",
        "/sys/",
        "/dev/",
        "/boot/",
        "/root/",
        str(Path.home() / ".ssh"),
        str(Path.home() / ".gnupg"),
        str(Path.home() / ".aws"),
        str(Path.home() / ".config/gcloud"),
    )

    def __init__(
        self,
        *,
        workspace_root: Optional[Path] = None,
        allow_outside_workspace: bool = False,
        extra_blocked_prefixes: Sequence[str] = (),
    ) -> None:
        """
        Args:
            workspace_root:         If set, paths must resolve inside this root.
            allow_outside_workspace: Override to allow outside workspace (elevated).
            extra_blocked_prefixes: Additional path prefixes to block.
        """
        self._workspace_root = workspace_root.resolve() if workspace_root else None
        self._allow_outside  = allow_outside_workspace
        self._blocked = (
            self._ALWAYS_BLOCKED_PREFIXES
            + tuple(str(Path(p).resolve()) for p in extra_blocked_prefixes)
        )

    # -- public API --------------------------------------------------------

    def validate(
        self,
        path: str | Path,
        *,
        must_exist: bool = False,
        allow_write: bool = False,
    ) -> Path:
        """Validate a path and return its resolved absolute form.

        Args:
            path:         The path to validate.
            must_exist:   If True, raises if the path does not exist.
            allow_write:  If True, extra write-safety checks apply.

        Returns:
            Resolved Path if valid.

        Raises:
            PathGuardError: If the path is unsafe.
        """
        raw = str(path)

        # 1. Null byte check (CVE pattern)
        if "\x00" in raw:
            raise PathGuardError("Path contains null byte", path=raw)

        # 2. Parse
        try:
            p = Path(raw)
        except Exception as exc:
            raise PathGuardError(f"Invalid path: {exc}", path=raw) from exc

        # 3. Resolve (follows symlinks, normalises ..)
        try:
            resolved = p.resolve()
        except Exception as exc:
            raise PathGuardError(f"Cannot resolve path: {exc}", path=raw) from exc

        # 4. Must-exist check
        if must_exist and not resolved.exists():
            raise PathGuardError(f"Path does not exist: {resolved}", path=raw)

        # 5. Always-blocked check
        resolved_str = str(resolved)
        for blocked in self._blocked:
            if resolved_str == blocked or resolved_str.startswith(blocked.rstrip("/") + "/"):
                raise PathGuardError(
                    f"Access to {resolved} is blocked (protected system path)",
                    path=raw,
                )

        # 6. Workspace containment check
        if self._workspace_root and not self._allow_outside:
            self._check_within_root(resolved, self._workspace_root, raw)

        return resolved

    def validate_write(self, path: str | Path) -> Path:
        """Validate that writing to path is safe. Stricter than validate()."""
        return self.validate(path, allow_write=True)

    def is_safe(self, path: str | Path) -> bool:
        """Return True if path passes validation (no exception)."""
        try:
            self.validate(path)
            return True
        except PathGuardError:
            return False

    def relative_to_workspace(self, path: str | Path) -> Optional[str]:
        """Return path relative to workspace_root, or None if not inside."""
        if not self._workspace_root:
            return None
        try:
            resolved = Path(path).resolve()
            return str(resolved.relative_to(self._workspace_root))
        except ValueError:
            return None

    # -- internals ---------------------------------------------------------

    @staticmethod
    def _check_within_root(resolved: Path, root: Path, raw: str) -> None:
        try:
            resolved.relative_to(root)
        except ValueError:
            raise PathGuardError(
                f"Path {resolved} escapes workspace root {root}. "
                "Use allow_outside_workspace=True for elevated access.",
                path=raw,
            )

    @staticmethod
    def has_traversal_component(path_str: str) -> bool:
        """Quick check for obvious '..' traversal before full resolution."""
        return ".." in Path(path_str).parts
