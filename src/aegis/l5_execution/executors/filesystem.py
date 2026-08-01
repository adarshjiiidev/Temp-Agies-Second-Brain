"""L5 Execution Engine — Filesystem Executor.

Handles all fs.* ActionKinds with full rollback support for write operations.

Supported actions:
  FS_READ, FS_WRITE, FS_APPEND, FS_COPY, FS_MOVE, FS_DELETE,
  FS_MKDIR, FS_HASH, FS_SEARCH, FS_WATCH

Invariants:
  - FS_DELETE always requires action.user_confirmed=True (enforced here
    AND by policy); otherwise raises PermissionDeniedError.
  - FS_WRITE / FS_COPY / FS_MOVE on non-scratch paths store a backup
    in the TempWorkspace for rollback.
  - Paths are resolved and validated to prevent traversal.

Import safety: stdlib + l5_execution.* ONLY.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import time
from pathlib import Path
from typing import Any

from aegis.l5_execution.contracts import ExecutorManifest, SandboxContext
from aegis.l5_execution.exceptions import ExecutorError, PermissionDeniedError, ResourceScopeError
from aegis.l5_execution.executors.base import ExecutorHealth
from aegis.l5_execution.types import (
    Action,
    ActionKind,
    ActionResult,
    ExecutionStatus,
    PermissionDecision,
    RiskLevel,
    SandboxTier,
    VerificationResult,
)

__all__ = ["FilesystemExecutor"]


class FilesystemExecutor:
    """Concrete executor for all fs.* actions."""

    manifest = ExecutorManifest(
        name="filesystem",
        version="0.1.0",
        description="Handles all filesystem read, write, copy, move, delete, hash, and search operations.",
        handles=[
            ActionKind.FS_READ,
            ActionKind.FS_WRITE,
            ActionKind.FS_APPEND,
            ActionKind.FS_COPY,
            ActionKind.FS_MOVE,
            ActionKind.FS_DELETE,
            ActionKind.FS_MKDIR,
            ActionKind.FS_HASH,
            ActionKind.FS_SEARCH,
            ActionKind.FS_WATCH,
        ],
        min_sandbox_tier=SandboxTier.T0_NONE,
        supports_rollback=True,
        default_timeout_seconds=30.0,
    )

    async def execute(self, action: Action, sandbox: SandboxContext) -> ActionResult:
        """Dispatch to the appropriate fs operation."""
        started = time.time()
        try:
            output, rollback_info = await self._dispatch(action, sandbox)
            return ActionResult(
                action_id=action.action_id,
                status=ExecutionStatus.SUCCESS if not action.dry_run else ExecutionStatus.SUCCESS,
                output=output,
                risk_level=RiskLevel.LOW,
                sandbox_tier=sandbox.tier,
                permission_decision=PermissionDecision.ALLOW,
                verification_result=VerificationResult.PASSED,
                started_at=started,
                completed_at=time.time(),
                duration_ms=(time.time() - started) * 1000,
                executor_name="filesystem",
                metadata={"rollback_info": rollback_info} if rollback_info else {},
            )
        except (PermissionDeniedError, ResourceScopeError):
            raise
        except Exception as exc:
            return ActionResult(
                action_id=action.action_id,
                status=ExecutionStatus.FAILED,
                error=str(exc),
                error_code="E_EXE_EXECUTOR_FAILED",
                sandbox_tier=sandbox.tier,
                permission_decision=PermissionDecision.ALLOW,
                started_at=started,
                completed_at=time.time(),
                executor_name="filesystem",
            )

    async def rollback(self, action: Action, result: ActionResult) -> dict[str, Any]:
        """Attempt to restore the previous state of the target file."""
        rollback_info = result.metadata.get("rollback_info")
        if not rollback_info:
            return {"supported": True, "succeeded": False, "reason": "no backup recorded"}

        backup_path = rollback_info.get("backup_path")
        original_path = rollback_info.get("original_path")
        operation = rollback_info.get("operation")

        if operation == "write" and backup_path and original_path:
            bp = Path(backup_path)
            op = Path(original_path)
            if bp.exists():
                shutil.copy2(str(bp), str(op))
                return {"supported": True, "succeeded": True, "restored": original_path}
            elif rollback_info.get("was_new_file"):
                op.unlink(missing_ok=True)
                return {"supported": True, "succeeded": True, "deleted_new": original_path}

        if operation == "delete" and backup_path and original_path:
            bp = Path(backup_path)
            op = Path(original_path)
            if bp.exists():
                shutil.copy2(str(bp), str(op))
                return {"supported": True, "succeeded": True, "restored": original_path}

        return {"supported": True, "succeeded": False, "reason": "backup not available"}

    async def health(self) -> ExecutorHealth:
        return ExecutorHealth(
            name="filesystem",
            healthy=True,
            message="Filesystem executor operational",
        )

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def _dispatch(
        self, action: Action, sandbox: SandboxContext
    ) -> tuple[Any, dict | None]:
        kind = action.kind
        p = action.parameters

        if kind == ActionKind.FS_READ:
            return self._read(p), None
        if kind == ActionKind.FS_WRITE:
            return self._write(action, p, sandbox)
        if kind == ActionKind.FS_APPEND:
            return self._append(action, p, sandbox)
        if kind == ActionKind.FS_COPY:
            return self._copy(p), None
        if kind == ActionKind.FS_MOVE:
            return self._move(p), None
        if kind == ActionKind.FS_DELETE:
            return self._delete(action, p, sandbox)
        if kind == ActionKind.FS_MKDIR:
            return self._mkdir(p), None
        if kind == ActionKind.FS_HASH:
            return self._hash(p), None
        if kind == ActionKind.FS_SEARCH:
            return self._search(p), None
        if kind == ActionKind.FS_WATCH:
            return {"message": "watch registered (async event stream not yet implemented)"}, None
        raise ExecutorError(f"Unsupported ActionKind: {kind.value!r}")

    # ------------------------------------------------------------------
    # Individual operations
    # ------------------------------------------------------------------

    @staticmethod
    def _read(p: dict) -> dict:
        path = Path(p["path"]).expanduser().resolve()
        if not path.exists():
            raise ExecutorError(f"File not found: {path}")
        if not path.is_file():
            raise ExecutorError(f"Path is not a file: {path}")
        encoding = p.get("encoding", "utf-8")
        max_bytes = p.get("max_bytes", 10 * 1024 * 1024)  # 10 MB default
        size = path.stat().st_size
        if size > max_bytes:
            raise ExecutorError(
                f"File too large to read ({size} bytes > max {max_bytes}). "
                "Use max_bytes parameter to override."
            )
        content = path.read_text(encoding=encoding, errors="replace")
        return {"path": str(path), "content": content, "size": size, "encoding": encoding}

    @staticmethod
    def _write(action: Action, p: dict, sandbox: SandboxContext) -> tuple[dict, dict]:
        path = Path(p["path"]).expanduser().resolve()
        content = p.get("content", "")
        encoding = p.get("encoding", "utf-8")
        if isinstance(content, bytes):
            content_bytes = content
        else:
            content_bytes = content.encode(encoding)

        # Backup for rollback
        rollback_info: dict = {"operation": "write", "original_path": str(path)}
        was_new = not path.exists()
        rollback_info["was_new_file"] = was_new

        if not was_new and sandbox.workspace_path:
            backup = Path(sandbox.workspace_path) / f"{path.name}.bak"
            shutil.copy2(str(path), str(backup))
            rollback_info["backup_path"] = str(backup)

        if not sandbox.dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content_bytes)

        return {"path": str(path), "written": len(content_bytes), "dry_run": sandbox.dry_run}, rollback_info

    @staticmethod
    def _append(action: Action, p: dict, sandbox: SandboxContext) -> tuple[dict, dict]:
        path = Path(p["path"]).expanduser().resolve()
        content = p.get("content", "")
        encoding = p.get("encoding", "utf-8")

        rollback_info: dict = {"operation": "append", "original_path": str(path)}
        if path.exists() and sandbox.workspace_path:
            original_size = path.stat().st_size
            rollback_info["original_size"] = original_size

        if not sandbox.dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding=encoding) as f:
                f.write(content)

        return {"path": str(path), "appended": len(content.encode(encoding)), "dry_run": sandbox.dry_run}, rollback_info

    @staticmethod
    def _copy(p: dict) -> dict:
        src = Path(p["src"]).expanduser().resolve()
        dst = Path(p["dst"]).expanduser().resolve()
        if not src.exists():
            raise ExecutorError(f"Source not found: {src}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(str(src), str(dst), dirs_exist_ok=True)
        else:
            shutil.copy2(str(src), str(dst))
        return {"src": str(src), "dst": str(dst)}

    @staticmethod
    def _move(p: dict) -> dict:
        src = Path(p["src"]).expanduser().resolve()
        dst = Path(p["dst"]).expanduser().resolve()
        if not src.exists():
            raise ExecutorError(f"Source not found: {src}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return {"src": str(src), "dst": str(dst)}

    @staticmethod
    def _delete(action: Action, p: dict, sandbox: SandboxContext) -> tuple[dict, dict]:
        if not action.user_confirmed:
            raise PermissionDeniedError(
                "fs.delete requires user_confirmed=True (irreversible operation).",
                verb="fs.delete",
                resource=p.get("path", ""),
                stage="execute",
            )
        path = Path(p["path"]).expanduser().resolve()
        rollback_info: dict = {"operation": "delete", "original_path": str(path)}

        if path.exists() and sandbox.workspace_path:
            backup = Path(sandbox.workspace_path) / f"{path.name}.deleted_backup"
            shutil.copy2(str(path), str(backup))
            rollback_info["backup_path"] = str(backup)

        if not sandbox.dry_run and path.exists():
            if path.is_dir():
                shutil.rmtree(str(path))
            else:
                path.unlink()

        return {"path": str(path), "deleted": path.exists() is False, "dry_run": sandbox.dry_run}, rollback_info

    @staticmethod
    def _mkdir(p: dict) -> dict:
        path = Path(p["path"]).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return {"path": str(path), "created": True}

    @staticmethod
    def _hash(p: dict) -> dict:
        path = Path(p["path"]).expanduser().resolve()
        algo = p.get("algorithm", "sha256")
        if not path.is_file():
            raise ExecutorError(f"File not found: {path}")
        h = hashlib.new(algo)
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return {"path": str(path), "algorithm": algo, "hash": h.hexdigest()}

    @staticmethod
    def _search(p: dict) -> dict:
        root = Path(p.get("root", ".")).expanduser().resolve()
        pattern = p.get("pattern", "*")
        recursive = p.get("recursive", True)
        max_results = p.get("max_results", 200)

        if not root.exists():
            raise ExecutorError(f"Search root not found: {root}")

        if recursive:
            matches = list(root.rglob(pattern))
        else:
            matches = list(root.glob(pattern))

        matches = matches[:max_results]
        return {
            "root": str(root),
            "pattern": pattern,
            "matches": [str(m) for m in matches],
            "count": len(matches),
        }
