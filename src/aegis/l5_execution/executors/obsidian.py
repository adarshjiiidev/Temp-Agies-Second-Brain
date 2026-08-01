"""L5 Execution Engine — Obsidian Executor.

Handles obsidian.* ActionKinds for Obsidian vault read/create/update/delete/search.

Vault is accessed as a local filesystem directory.
Vault path is resolved from action.parameters['vault'] or the default
configured path.

Invariant: obsidian.delete requires action.user_confirmed=True.

Import safety: stdlib + l5_execution.* ONLY.
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any

from aegis.l5_execution.contracts import ExecutorManifest, SandboxContext
from aegis.l5_execution.exceptions import ExecutorError, PermissionDeniedError
from aegis.l5_execution.executors.base import ExecutorHealth
from aegis.l5_execution.types import (
    Action,
    ActionKind,
    ActionResult,
    ExecutionStatus,
    PermissionDecision,
    SandboxTier,
    VerificationResult,
)

__all__ = ["ObsidianExecutor"]

# Default vault location on Windows (common path)
_DEFAULT_VAULT_CANDIDATES = [
    Path.home() / "Documents" / "Obsidian",
    Path.home() / "Obsidian",
    Path.home() / "vault",
]


def _find_default_vault() -> Path | None:
    for p in _DEFAULT_VAULT_CANDIDATES:
        if p.exists() and p.is_dir():
            return p
    return None


class ObsidianExecutor:
    """Concrete executor for all obsidian.* actions."""

    manifest = ExecutorManifest(
        name="obsidian",
        version="0.1.0",
        description="Read, create, update, delete, and search Obsidian vault notes.",
        handles=[
            ActionKind.OBSIDIAN_READ,
            ActionKind.OBSIDIAN_CREATE,
            ActionKind.OBSIDIAN_UPDATE,
            ActionKind.OBSIDIAN_DELETE,
            ActionKind.OBSIDIAN_SEARCH,
        ],
        min_sandbox_tier=SandboxTier.T0_NONE,
        supports_rollback=True,
        default_timeout_seconds=10.0,
    )

    def __init__(self, default_vault: Path | str | None = None) -> None:
        self._default_vault = Path(default_vault) if default_vault else _find_default_vault()

    def _resolve_vault(self, p: dict) -> Path:
        vault_path = p.get("vault")
        if vault_path:
            vault = Path(vault_path).expanduser().resolve()
        elif self._default_vault:
            vault = self._default_vault.resolve()
        else:
            raise ExecutorError(
                "No Obsidian vault found. Provide 'vault' in action parameters or "
                "set the default vault path in ObsidianExecutor()."
            )
        if not vault.exists():
            raise ExecutorError(f"Vault directory not found: {vault}")
        return vault

    def _resolve_note(self, vault: Path, note: str) -> Path:
        """Resolve a note path within the vault, adding .md if missing."""
        if not note.endswith(".md"):
            note = note + ".md"
        note_path = (vault / note).resolve()
        # Security: note must be inside vault
        try:
            note_path.relative_to(vault)
        except ValueError:
            raise PermissionDeniedError(
                f"Note path {note!r} escapes vault boundary.",
                verb="obsidian.*",
                resource=str(note_path),
                stage="execute",
            )
        return note_path

    async def execute(self, action: Action, sandbox: SandboxContext) -> ActionResult:
        started = time.time()
        p = action.parameters
        try:
            vault = self._resolve_vault(p)
            output, rollback_info = await self._dispatch(action, p, vault, sandbox)
            return ActionResult(
                action_id=action.action_id,
                status=ExecutionStatus.SUCCESS,
                output=output,
                sandbox_tier=sandbox.tier,
                permission_decision=PermissionDecision.ALLOW,
                verification_result=VerificationResult.PASSED,
                started_at=started,
                completed_at=time.time(),
                duration_ms=(time.time() - started) * 1000,
                executor_name="obsidian",
                metadata={"rollback_info": rollback_info} if rollback_info else {},
            )
        except (PermissionDeniedError, ExecutorError):
            raise
        except Exception as exc:
            return ActionResult(
                action_id=action.action_id,
                status=ExecutionStatus.FAILED,
                error=str(exc),
                error_code="E_EXE_EXECUTOR_FAILED",
                executor_name="obsidian",
            )

    async def rollback(self, action: Action, result: ActionResult) -> dict[str, Any]:
        ri = result.metadata.get("rollback_info") if result.metadata else None
        if not ri:
            return {"supported": True, "succeeded": False, "reason": "no backup"}
        op = ri.get("operation")
        backup = ri.get("backup_content")
        note_path = ri.get("note_path")

        if op in ("create",) and note_path:
            p = Path(note_path)
            if p.exists():
                p.unlink()
            return {"supported": True, "succeeded": True, "deleted_new": note_path}

        if op in ("update", "delete") and backup is not None and note_path:
            Path(note_path).write_text(backup, encoding="utf-8")
            return {"supported": True, "succeeded": True, "restored": note_path}

        return {"supported": True, "succeeded": False}

    async def health(self) -> ExecutorHealth:
        vault = self._default_vault
        if vault and vault.exists():
            notes = len(list(vault.rglob("*.md")))
            return ExecutorHealth(
                name="obsidian",
                healthy=True,
                message=f"Vault at {vault} ({notes} notes)",
            )
        return ExecutorHealth(
            name="obsidian",
            healthy=True,
            message="No default vault configured (provide vault in parameters)",
        )

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def _dispatch(
        self, action: Action, p: dict, vault: Path, sandbox: SandboxContext
    ) -> tuple[Any, dict | None]:
        kind = action.kind

        if kind == ActionKind.OBSIDIAN_READ:
            note_path = self._resolve_note(vault, p["note"])
            if not note_path.exists():
                raise ExecutorError(f"Note not found: {note_path}")
            content = note_path.read_text(encoding="utf-8")
            return {"note": str(note_path), "content": content, "size": len(content)}, None

        if kind == ActionKind.OBSIDIAN_CREATE:
            note_path = self._resolve_note(vault, p["note"])
            if note_path.exists() and not p.get("overwrite", False):
                raise ExecutorError(
                    f"Note already exists: {note_path}. Use overwrite=True to replace."
                )
            content = p.get("content", "")
            rollback_info = {"operation": "create", "note_path": str(note_path)}
            if not sandbox.dry_run:
                note_path.parent.mkdir(parents=True, exist_ok=True)
                note_path.write_text(content, encoding="utf-8")
            return {"note": str(note_path), "created": True, "dry_run": sandbox.dry_run}, rollback_info

        if kind == ActionKind.OBSIDIAN_UPDATE:
            note_path = self._resolve_note(vault, p["note"])
            old_content = note_path.read_text(encoding="utf-8") if note_path.exists() else ""
            rollback_info = {
                "operation": "update",
                "note_path": str(note_path),
                "backup_content": old_content,
            }
            new_content = p.get("content", old_content)
            # Optional: apply patch instead of full replace
            if p.get("append"):
                new_content = old_content + "\n" + p["append"]
            if not sandbox.dry_run:
                note_path.parent.mkdir(parents=True, exist_ok=True)
                note_path.write_text(new_content, encoding="utf-8")
            return {"note": str(note_path), "updated": True, "dry_run": sandbox.dry_run}, rollback_info

        if kind == ActionKind.OBSIDIAN_DELETE:
            if not action.user_confirmed:
                raise PermissionDeniedError(
                    "obsidian.delete requires user_confirmed=True.",
                    verb="obsidian.delete",
                    resource=p.get("note", ""),
                    stage="execute",
                )
            note_path = self._resolve_note(vault, p["note"])
            old_content = note_path.read_text(encoding="utf-8") if note_path.exists() else ""
            rollback_info = {
                "operation": "delete",
                "note_path": str(note_path),
                "backup_content": old_content,
            }
            if not sandbox.dry_run and note_path.exists():
                note_path.unlink()
            return {"note": str(note_path), "deleted": True, "dry_run": sandbox.dry_run}, rollback_info

        if kind == ActionKind.OBSIDIAN_SEARCH:
            query = p.get("query", "")
            max_results = p.get("max_results", 50)
            results = self._search_vault(vault, query, max_results)
            return {"query": query, "results": results, "count": len(results)}, None

        raise ExecutorError(f"Unsupported Obsidian ActionKind: {kind.value!r}")

    @staticmethod
    def _search_vault(vault: Path, query: str, max_results: int) -> list[dict]:
        """Simple full-text search across all .md files in the vault."""
        pattern = re.compile(re.escape(query), re.IGNORECASE)
        matches = []
        for note_path in vault.rglob("*.md"):
            try:
                content = note_path.read_text(encoding="utf-8", errors="replace")
                if pattern.search(content):
                    matches.append({
                        "note": str(note_path.relative_to(vault)),
                        "path": str(note_path),
                        "snippet": _extract_snippet(content, pattern),
                    })
                    if len(matches) >= max_results:
                        break
            except Exception:
                continue
        return matches


def _extract_snippet(content: str, pattern: re.Pattern, context: int = 100) -> str:
    m = pattern.search(content)
    if not m:
        return content[:200]
    start = max(0, m.start() - context)
    end = min(len(content), m.end() + context)
    return content[start:end]
