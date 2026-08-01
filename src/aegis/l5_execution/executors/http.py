"""L5 Execution Engine — HTTP Executor.

Handles net.get / net.post / net.put / net.delete / net.patch actions.
All requests are gated by a domain allowlist policy.

Parameters:
  - url (str): full URL
  - headers (dict, optional)
  - body (str | dict, optional): for POST/PUT/PATCH
  - timeout_seconds (float, optional)
  - json_body (bool, optional): if True, body is JSON-serialised

Import safety: urllib.request + stdlib + l5_execution.* ONLY.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from aegis.l5_execution.contracts import ExecutorManifest, SandboxContext
from aegis.l5_execution.exceptions import ExecutorError, ResourceScopeError
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

__all__ = ["HttpExecutor"]

# Default allowlist: domains the executor will reach without extra approval
_DEFAULT_ALLOWLIST: frozenset[str] = frozenset({
    "api.openrouter.ai",
    "api.groq.com",
    "ollama.ai",
    "raw.githubusercontent.com",
    "pypi.org",
    "pypi.python.org",
    "files.pythonhosted.org",
})

_VERB_METHOD: dict[ActionKind, str] = {
    ActionKind.NET_GET: "GET",
    ActionKind.NET_POST: "POST",
    ActionKind.NET_PUT: "PUT",
    ActionKind.NET_DELETE: "DELETE",
    ActionKind.NET_PATCH: "PATCH",
}


class HttpExecutor:
    """HTTP executor with domain allowlist gating.

    Usage::

        executor = HttpExecutor(allowlist={"api.openrouter.ai"})
        result = await executor.execute(action, sandbox)
    """

    manifest = ExecutorManifest(
        name="http",
        version="0.1.0",
        description="HTTP requests (GET/POST/PUT/DELETE/PATCH) gated by domain allowlist.",
        handles=[
            ActionKind.NET_GET,
            ActionKind.NET_POST,
            ActionKind.NET_PUT,
            ActionKind.NET_DELETE,
            ActionKind.NET_PATCH,
        ],
        min_sandbox_tier=SandboxTier.T0_NONE,
        supports_rollback=False,
        default_timeout_seconds=30.0,
    )

    def __init__(
        self,
        allowlist: set[str] | None = None,
        *,
        default_timeout: float = 30.0,
    ) -> None:
        self._allowlist = allowlist if allowlist is not None else set(_DEFAULT_ALLOWLIST)
        self._timeout = default_timeout

    def add_to_allowlist(self, domain: str) -> None:
        self._allowlist.add(domain.lower())

    async def execute(self, action: Action, sandbox: SandboxContext) -> ActionResult:
        started = time.time()
        p = action.parameters
        url = p.get("url", "")

        if not url:
            return ActionResult(
                action_id=action.action_id,
                status=ExecutionStatus.FAILED,
                error="No url provided in parameters['url']",
                error_code="E_EXE_EXECUTOR_FAILED",
                executor_name="http",
            )

        # Domain allowlist check
        try:
            parsed = urllib.parse.urlparse(url)
            domain = parsed.netloc.lower()
            if ":" in domain:
                domain = domain.split(":")[0]
        except Exception:
            domain = ""

        if domain not in self._allowlist:
            raise ResourceScopeError(
                f"Domain {domain!r} is not in the HTTP executor allowlist. "
                f"Add it via permission grant or HttpExecutor.add_to_allowlist().",
                stage="execute",
            )

        if sandbox.dry_run:
            return ActionResult(
                action_id=action.action_id,
                status=ExecutionStatus.SUCCESS,
                output={"dry_run": True, "url": url, "method": _VERB_METHOD.get(action.kind, "GET")},
                sandbox_tier=sandbox.tier,
                permission_decision=PermissionDecision.ALLOW,
                executor_name="http",
            )

        try:
            output = self._make_request(action, p, url)
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
                executor_name="http",
            )
        except urllib.error.HTTPError as exc:
            return ActionResult(
                action_id=action.action_id,
                status=ExecutionStatus.FAILED,
                error=f"HTTP {exc.code}: {exc.reason}",
                error_code="E_EXE_EXECUTOR_FAILED",
                executor_name="http",
            )
        except Exception as exc:
            return ActionResult(
                action_id=action.action_id,
                status=ExecutionStatus.FAILED,
                error=str(exc),
                error_code="E_EXE_EXECUTOR_FAILED",
                executor_name="http",
            )

    def _make_request(self, action: Action, p: dict, url: str) -> dict:
        method = _VERB_METHOD.get(action.kind, "GET")
        headers: dict[str, str] = p.get("headers", {})
        timeout = p.get("timeout_seconds", self._timeout)
        body = p.get("body")
        as_json = p.get("json_body", isinstance(body, dict))

        data: bytes | None = None
        if body is not None:
            if as_json:
                data = json.dumps(body).encode("utf-8")
                headers.setdefault("Content-Type", "application/json")
            elif isinstance(body, str):
                data = body.encode("utf-8")
            elif isinstance(body, bytes):
                data = body

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            resp_headers = dict(resp.headers)
            resp_body = resp.read()
            content_type = resp_headers.get("Content-Type", "")
            try:
                decoded = resp_body.decode("utf-8", errors="replace")
                if "application/json" in content_type:
                    decoded_json = json.loads(decoded)
                else:
                    decoded_json = None
            except Exception:
                decoded = ""
                decoded_json = None

        return {
            "status": status,
            "url": url,
            "method": method,
            "headers": resp_headers,
            "body": decoded,
            "json": decoded_json,
        }

    async def rollback(self, action: Action, result: ActionResult) -> dict[str, Any]:
        return {"supported": False}

    async def health(self) -> ExecutorHealth:
        return ExecutorHealth(
            name="http",
            healthy=True,
            message=f"HTTP executor operational (allowlist: {len(self._allowlist)} domains)",
        )
