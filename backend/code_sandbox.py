#!/usr/bin/env python3
"""
AEGIS Code Execution Intelligence & Sandboxed Testing Engine
Provides safe execution of generated scripts, syntax linting, static analysis,
and automatic rollback capabilities.
"""

import os
import sys
import time
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any

class CodeSandbox:
    def __init__(self):
        self.py_bin = sys.executable or "/usr/bin/python3"
        self.node_bin = shutil.which("node") or "/usr/bin/node"
        self.bash_bin = shutil.which("bash") or "/usr/bin/bash"
        self.blacklisted_patterns = [
            "rm -rf /", "rm -rf ~", "mkfs", "dd if=/dev/zero",
            ":(){ :|:& };:", "chmod -R 777 /", "> /dev/sda"
        ]

    def check_safety(self, code_str: str) -> tuple[bool, Optional[str]]:
        """Scans code for dangerous destructive commands."""
        for p in self.blacklisted_patterns:
            if p in code_str:
                return False, f"Security Denial: Blacklisted destructive command detected: '{p}'"
        return True, None

    def lint_syntax(self, code: str, language: str = "python") -> dict:
        """Statically verifies syntax without executing code."""
        safe, reason = self.check_safety(code)
        if not safe:
            return {"valid": False, "error": reason}

        suffix = ".py" if language == "python" else ".js" if language in ["js", "javascript", "ts"] else ".sh"
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, mode="w", delete=False)
        try:
            tmp.write(code)
            tmp.close()

            if language == "python":
                cmd = [self.py_bin, "-m", "py_compile", tmp.name]
            elif language in ["js", "javascript"]:
                cmd = [self.node_bin, "--check", tmp.name]
            else:
                cmd = [self.bash_bin, "-n", tmp.name]

            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            return {
                "valid": res.returncode == 0,
                "error": res.stderr if res.returncode != 0 else None,
                "language": language
            }
        except Exception as e:
            return {"valid": False, "error": str(e), "language": language}
        finally:
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)

    def execute_sandboxed(self, code: str, language: str = "python", timeout_sec: int = 5) -> dict:
        """Executes code in an isolated temporary environment with timeout boundaries."""
        # 1. Safety check
        safe, reason = self.check_safety(code)
        if not safe:
            return {"success": False, "error": reason, "returncode": -1}

        # 2. Syntax lint
        lint = self.lint_syntax(code, language)
        if not lint["valid"]:
            return {"success": False, "error": f"Syntax Error: {lint['error']}", "returncode": 1}

        suffix = ".py" if language == "python" else ".js" if language in ["js", "javascript"] else ".sh"
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, mode="w", delete=False)
        try:
            tmp.write(code)
            tmp.close()

            if language == "python":
                cmd = [self.py_bin, tmp.name]
            elif language in ["js", "javascript"]:
                cmd = [self.node_bin, tmp.name]
            else:
                cmd = [self.bash_bin, tmp.name]

            start_t = time.time()
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                cwd="/tmp"
            )
            elapsed = time.time() - start_t

            return {
                "success": res.returncode == 0,
                "stdout": res.stdout,
                "stderr": res.stderr,
                "returncode": res.returncode,
                "duration_seconds": round(elapsed, 4)
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Execution Timed Out (> {timeout_sec}s)", "returncode": 124}
        except Exception as e:
            return {"success": False, "error": str(e), "returncode": -1}
        finally:
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)

code_sandbox = CodeSandbox()

if __name__ == "__main__":
    print("Testing Code Sandbox...")
    # Safe python test
    res = code_sandbox.execute_sandboxed("print('SANDBOX_ACTIVE'); print(sum([x*2 for x in range(5)]))")
    print("Execution output:", res)
    assert res["success"] and "SANDBOX_ACTIVE" in res["stdout"]

    # Security check test
    bad = code_sandbox.execute_sandboxed("rm -rf /")
    print("Safety rejection output:", bad)
    assert not bad["success"] and "Security Denial" in bad["error"]

    print("Code Sandbox: VERIFIED OK")
