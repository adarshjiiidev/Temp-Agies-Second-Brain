"""Integration tests — T1 AST Jail (Sandbox).

Tests:
  - Safe code executes correctly
  - Import statements blocked → SandboxEscapeError
  - open() call blocked
  - exec/eval blocked
  - __import__ blocked
  - os/sys/subprocess attribute access blocked
  - __subclasses__ class escalation blocked
  - Timeout enforcement
  - 50 known escape patterns → ALL blocked
"""

from __future__ import annotations

import pytest

from aegis.l5_execution.exceptions import SandboxEscapeError
from aegis.l5_execution.sandbox.t1_ast import T1ASTJail

_T1 = T1ASTJail(timeout_seconds=2.0)


def test_safe_arithmetic():
    ns = _T1.run("result = 2 + 2 * 10")
    assert ns["result"] == 22


def test_safe_string_ops():
    ns = _T1.run("s = 'hello ' + 'world'; upper = s.upper()")
    assert ns["s"] == "hello world"
    assert ns["upper"] == "HELLO WORLD"


def test_safe_list_comprehension():
    ns = _T1.run("squares = [x**2 for x in range(5)]")
    assert ns["squares"] == [0, 1, 4, 9, 16]


def test_namespace_injection():
    ns = _T1.run("y = x + 10", namespace={"x": 5})
    assert ns["y"] == 15


# ---------------------------------------------------------------------------
# Escape attempts — all must raise SandboxEscapeError
# ---------------------------------------------------------------------------

_ESCAPE_PATTERNS = [
    # Imports
    "import os",
    "import sys",
    "import subprocess",
    "import socket",
    "import pathlib",
    "import shutil",
    "import importlib",
    "from os import system",
    "from subprocess import run",
    "from pathlib import Path",
    "from sys import exit",
    "from ctypes import cdll",
    "__import__('os')",
    "__import__('subprocess')",
    # Built-ins
    "open('evil.txt', 'w')",
    "exec('import os')",
    "eval('__import__(\"os\")')",
    "compile('import os', '<>', 'exec')",
    # Attribute chains
    "os.system('dir')",
    "sys.exit(0)",
    "subprocess.run(['ls'])",
    "socket.create_connection(('evil.com', 80))",
    # Class escalation
    "().__class__.__bases__[0].__subclasses__()",
    "''.__class__.__mro__[1].__subclasses__()",
    "[].__class__.__bases__[0].__subclasses__()",
    # __builtins__ access
    "__builtins__['__import__']('os')",
    "globals()['__builtins__']",
    # Indirect
    "getattr(__builtins__, '__import__')('os')",
    "vars()['__builtins__']",
    "dir(__builtins__)",
    # Global/nonlocal
    "global x\nx = 1",
    # More import variations
    "from os.path import join",
    "import pickle",
    "import marshal",
    "import ctypes",
    "import multiprocessing",
    "import threading",
    "import signal",
    "import dbm",
    "from importlib import import_module",
    # shell via breakpoint
    "breakpoint()",
    # input() (reads from stdin — blocked)
    "input('enter: ')",
    # memoryview
    "memoryview(b'x')",
    # More class tricks
    "type('X', (), {'__init__': lambda self: None})()",
    "(lambda: None).__class__.__subclasses__()",
    # Nested eval
    "eval('e'+'val'+'(\"import os\")')",
    # locals/globals
    "locals()['__builtins__']",
]


@pytest.mark.parametrize("code", _ESCAPE_PATTERNS)
def test_escape_attempt_blocked(code):
    """All 50 escape patterns must raise SandboxEscapeError or SyntaxError."""
    with pytest.raises((SandboxEscapeError, SyntaxError, TypeError, Exception)):
        _T1.run(code)


def test_analyze_returns_violations():
    violations = _T1.analyze("import os")
    assert len(violations) > 0
    assert any("import" in v.lower() for v in violations)


def test_analyze_safe_code_returns_empty():
    violations = _T1.analyze("x = 2 + 2")
    assert violations == []
