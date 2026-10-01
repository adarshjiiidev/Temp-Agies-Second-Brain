"""L5 Execution Engine — Post-Execution Assertions (Stage 7).

After an executor completes, the PostExecVerifier runs typed assertions
to confirm the expected effects occurred.

If assertions fail → auto-rollback is triggered (via RollbackEngine).

Assertion types:
  - file_exists:      verify a path exists after the action
  - file_not_exists:  verify a path was deleted
  - file_contains:    verify file content contains a string
  - output_key:       verify result.output has a key with expected value
  - returncode_zero:  verify subprocess returncode == 0
  - custom:           user-provided callable (for advanced cases)

Import safety: stdlib + l5_execution.types/exceptions ONLY.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from aegis.l5_execution.exceptions import VerificationFailedError
from aegis.l5_execution.types import Action, ActionResult, VerificationResult

__all__ = ["PostExecVerifier", "Assertion", "AssertionKind"]

from enum import Enum


class AssertionKind(str, Enum):
    FILE_EXISTS = "file_exists"
    FILE_NOT_EXISTS = "file_not_exists"
    FILE_CONTAINS = "file_contains"
    OUTPUT_KEY = "output_key"
    RETURNCODE_ZERO = "returncode_zero"
    NO_STDERR = "no_stderr"
    CUSTOM = "custom"


@dataclass
class Assertion:
    """A single post-execution assertion."""

    kind: AssertionKind
    description: str = ""

    # FILE_EXISTS / FILE_NOT_EXISTS / FILE_CONTAINS
    path: str | None = None
    # FILE_CONTAINS
    contains: str | None = None
    contains_regex: bool = False
    # OUTPUT_KEY
    output_key: str | None = None
    expected_value: Any = None
    # CUSTOM
    check_fn: Callable[[Action, ActionResult], bool] | None = None


class PostExecVerifier:
    """Stage 7 — post-execution assertion engine.

    Usage::

        verifier = PostExecVerifier()
        verifier.add_assertion(Assertion(
            kind=AssertionKind.FILE_EXISTS,
            path="~/Projects/output.txt",
            description="output file was created",
        ))
        passed, message = await verifier.verify(action, result)
        if not passed:
            # trigger rollback
    """

    def __init__(self) -> None:
        self._assertions: list[Assertion] = []

    def add_assertion(self, assertion: Assertion) -> None:
        self._assertions.append(assertion)

    def clear(self) -> None:
        self._assertions.clear()

    async def verify(
        self,
        action: Action,
        result: ActionResult,
    ) -> tuple[VerificationResult, str]:
        """Run all registered assertions against the action result.

        Returns:
            (VerificationResult, message) — PASSED or FAILED with details.
        """
        if not self._assertions:
            return VerificationResult.PASSED, "No assertions registered (skip)"

        failures: list[str] = []

        for assertion in self._assertions:
            ok, msg = self._run_assertion(assertion, action, result)
            if not ok:
                failures.append(f"[{assertion.kind.value}] {assertion.description}: {msg}")

        if failures:
            return (
                VerificationResult.FAILED,
                "Verification failed — " + "; ".join(failures),
            )
        return VerificationResult.PASSED, f"{len(self._assertions)} assertion(s) passed"

    @staticmethod
    def _run_assertion(
        assertion: Assertion,
        action: Action,
        result: ActionResult,
    ) -> tuple[bool, str]:
        kind = assertion.kind

        if kind == AssertionKind.FILE_EXISTS:
            p = Path(assertion.path or "").expanduser().resolve()
            ok = p.exists()
            return ok, f"{p} {'exists' if ok else 'does not exist'}"

        if kind == AssertionKind.FILE_NOT_EXISTS:
            p = Path(assertion.path or "").expanduser().resolve()
            ok = not p.exists()
            return ok, f"{p} {'does not exist (expected)' if ok else 'still exists'}"

        if kind == AssertionKind.FILE_CONTAINS:
            if not assertion.path or not assertion.contains:
                return False, "Missing path or contains in assertion"
            p = Path(assertion.path).expanduser().resolve()
            if not p.exists():
                return False, f"File not found: {p}"
            content = p.read_text(encoding="utf-8", errors="replace")
            if assertion.contains_regex:
                ok = bool(re.search(assertion.contains, content))
            else:
                ok = assertion.contains in content
            return ok, f"{'found' if ok else 'not found'}: {assertion.contains!r}"

        if kind == AssertionKind.OUTPUT_KEY:
            if not assertion.output_key:
                return False, "Missing output_key in assertion"
            output = result.output or {}
            if not isinstance(output, dict):
                return False, f"result.output is not a dict ({type(output).__name__})"
            actual = output.get(assertion.output_key)
            if assertion.expected_value is None:
                ok = assertion.output_key in output
                return ok, f"key {assertion.output_key!r} {'present' if ok else 'absent'}"
            ok = actual == assertion.expected_value
            return ok, f"expected {assertion.expected_value!r}, got {actual!r}"

        if kind == AssertionKind.RETURNCODE_ZERO:
            output = result.output or {}
            if isinstance(output, dict):
                rc = output.get("returncode", output.get("returncode", None))
            else:
                rc = None
            ok = rc == 0
            return ok, f"returncode={rc}"

        if kind == AssertionKind.NO_STDERR:
            output = result.output or {}
            if isinstance(output, dict):
                stderr = output.get("stderr", "")
                ok = not stderr.strip()
                return ok, f"stderr: {stderr[:100]!r}" if not ok else "no stderr"
            return True, "no stderr field"

        if kind == AssertionKind.CUSTOM:
            if not assertion.check_fn:
                return False, "No check_fn provided for CUSTOM assertion"
            try:
                ok = assertion.check_fn(action, result)
                return ok, "custom check " + ("passed" if ok else "failed")
            except Exception as exc:
                return False, f"custom check raised: {exc}"

        return False, f"Unknown assertion kind: {kind.value!r}"
