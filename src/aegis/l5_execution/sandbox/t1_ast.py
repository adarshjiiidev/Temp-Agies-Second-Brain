"""L5 Execution Engine — T1 Python AST Jail.

The T1 sandbox uses Python's AST to statically analyse code before
execution, blocking dangerous constructs:
  - import statements (all forms)
  - open() / file I/O built-ins
  - exec() / eval() / compile()
  - __import__, __builtins__ access
  - subprocess / os / sys module references
  - Attribute access chains that reach dangerous stdlib modules

Code that passes AST analysis is then executed in a restricted namespace
using compile() + exec() with a minimal builtins dict.

Import safety: stdlib (ast, builtins, types) only.
"""

from __future__ import annotations

import ast
import builtins
import math
import time
import types
from typing import Any

from aegis.l5_execution.exceptions import SandboxEscapeError

__all__ = ["T1ASTJail", "ASTAnalyzer"]

# ---------------------------------------------------------------------------
# Blocked node types and names
# ---------------------------------------------------------------------------

_BLOCKED_NODES = (
    ast.Import,
    ast.ImportFrom,
    ast.Global,
    ast.Nonlocal,
)

_BLOCKED_NAMES: frozenset[str] = frozenset({
    "__import__",
    "__builtins__",
    "__loader__",
    "__spec__",
    "open",
    "exec",
    "eval",
    "compile",
    "breakpoint",
    "input",
    "memoryview",
    "vars",
    "dir",
    "getattr",
    "setattr",
    "delattr",
    "hasattr",
    "globals",
    "locals",
    "object",
    "type",
    "super",
    "classmethod",
    "staticmethod",
    "property",
})

_BLOCKED_ATTR_CHAINS: frozenset[str] = frozenset({
    "os",
    "sys",
    "subprocess",
    "pathlib",
    "socket",
    "shutil",
    "importlib",
    "ctypes",
    "pickle",
    "marshal",
    "shelve",
    "dbm",
    "multiprocessing",
    "threading",
    "concurrent",
    "asyncio",
    "signal",
})

# Safe built-ins allowed in T1
_SAFE_BUILTINS: dict[str, Any] = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "bytes": bytes,
    "chr": chr,
    "dict": dict,
    "divmod": divmod,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "format": format,
    "frozenset": frozenset,
    "hash": hash,
    "hex": hex,
    "int": int,
    "isinstance": isinstance,
    "issubclass": issubclass,
    "iter": iter,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "next": next,
    "oct": oct,
    "ord": ord,
    "pow": pow,
    "print": print,
    "range": range,
    "repr": repr,
    "reversed": reversed,
    "round": round,
    "set": set,
    "slice": slice,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
    "None": None,
    "True": True,
    "False": False,
    "math": math,
}


class ASTAnalyzer(ast.NodeVisitor):
    """AST visitor that raises SandboxEscapeError on dangerous constructs."""

    def __init__(self) -> None:
        self.violations: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        names = ", ".join(a.name for a in node.names)
        self.violations.append(f"import statement not allowed: import {names}")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.violations.append(
            f"import statement not allowed: from {node.module} import ..."
        )

    def visit_Global(self, node: ast.Global) -> None:
        self.violations.append("'global' statement not allowed in T1 sandbox")

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.violations.append("'nonlocal' statement not allowed in T1 sandbox")

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in _BLOCKED_NAMES:
            self.violations.append(f"blocked built-in: {node.id!r}")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # Detect top-level dangerous attribute chains: e.g. os.system, sys.exit
        root = _get_root_name(node)
        if root and root in _BLOCKED_ATTR_CHAINS:
            self.violations.append(
                f"blocked module attribute access: {root!r} (chain root)"
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # Check for __class__.__bases__ type escalation
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in ("__subclasses__", "__bases__", "__mro__"):
                self.violations.append(
                    f"blocked dunder attribute call: {node.func.attr!r}"
                )
        self.generic_visit(node)


def _get_root_name(node: ast.expr) -> str | None:
    """Walk an Attribute chain to find the root Name node."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _get_root_name(node.value)
    return None


class T1ASTJail:
    """T1 Python AST jail — static analysis + restricted exec().

    Usage::

        jail = T1ASTJail()
        result = jail.run("x = 2 + 2\\nresult = x * 3", {"input_val": 42})
        # result["result"] == 12

    Raises:
        SandboxEscapeError: if the code contains blocked constructs.
        SyntaxError:        if the code has a syntax error.
        Exception:          if the code raises at runtime.
    """

    def __init__(
        self,
        timeout_seconds: float = 5.0,
        extra_builtins: dict[str, Any] | None = None,
    ) -> None:
        self._timeout = timeout_seconds
        self._extra_builtins = extra_builtins or {}

    def analyze(self, code: str) -> list[str]:
        """Parse and analyse code.  Return list of violation strings (empty = safe)."""
        try:
            tree = ast.parse(code, mode="exec")
        except SyntaxError as exc:
            return [f"SyntaxError: {exc}"]

        analyzer = ASTAnalyzer()
        analyzer.visit(tree)
        return analyzer.violations

    def run(
        self,
        code: str,
        namespace: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Analyse then execute ``code`` in a restricted namespace.

        Returns the local namespace dict after execution (variables defined by
        the code are available here).

        Raises SandboxEscapeError if violations are detected.
        """
        violations = self.analyze(code)
        if violations:
            raise SandboxEscapeError(
                f"T1 AST jail: {len(violations)} violation(s) — "
                + "; ".join(violations[:3]),
                sandbox_tier="T1_ast",
                escape_pattern=violations[0] if violations else None,
            )

        safe_globals: dict[str, Any] = {
            "__builtins__": _SAFE_BUILTINS | self._extra_builtins,
            "__name__": "__t1_sandbox__",
        }
        local_ns: dict[str, Any] = dict(namespace or {})

        # Deadline check (simple wall-clock; full enforcement is in T2)
        start = time.monotonic()
        try:
            compiled = compile(code, "<t1_sandbox>", "exec")
            exec(compiled, safe_globals, local_ns)  # noqa: S102
        except SandboxEscapeError:
            raise
        except Exception:
            raise
        finally:
            elapsed = time.monotonic() - start
            if elapsed > self._timeout:
                raise SandboxEscapeError(
                    f"T1 AST jail: execution exceeded timeout ({self._timeout}s)",
                    sandbox_tier="T1_ast",
                    escape_pattern="timeout",
                )

        return local_ns
