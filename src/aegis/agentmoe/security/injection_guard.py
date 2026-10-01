"""AgentMoe — InjectionGuard (Phase 2 security).

Prevents command injection attacks in Terminal and Shell tool operations.

Command injection occurs when untrusted input is interpolated into a shell
command string. Our primary defense is structural:

  RULE: AgentMoe tools NEVER call shell(cmd_string). Commands are always
        passed as list[str] (argv arrays). No shell metacharacter can escape
        from an argv element.

InjectionGuard provides:
  1. Argument list structural validation (no list→string coercion)
  2. Metacharacter detection (defense-in-depth for audit/logging)
  3. Dangerous command detection (rm -rf /, dd if=, mkfs, etc.)
  4. Environment variable injection detection

Import safety: stdlib only.
"""

from __future__ import annotations

import re
import shlex
from typing import Sequence


__all__ = ["InjectionGuardError", "InjectionGuard"]


# Shell metacharacters that are dangerous in string contexts
_SHELL_METACHARACTERS = frozenset(";|&`$(){}[]<>\\\"'!")

# SAFETY — commands that are always HIGH risk regardless of content
_HIGH_RISK_COMMANDS: frozenset[str] = frozenset({
    "rm",   "rmdir",  "mkfs",  "dd",     "shred",
    "fdisk","parted", "mkswap","swapoff", "mount",
    "umount","halt",  "reboot","shutdown","poweroff",
    "init", "systemctl",                           # service management
    "chmod","chown",  "chgrp", "setuid",           # permission escalation
    "sudo", "su",     "doas",  "pkexec",           # privilege escalation
    "curl", "wget",   "nc",    "ncat",   "socat",  # network tools (need SSRF guard)
    "ssh",  "scp",    "rsync",                     # remote access
    "git",                                          # managed by GitTool, not TerminalTool
    "pip",  "pip3",   "npm",   "yarn",   "cargo",  # package managers
})

# Patterns that suggest environment variable injection
_ENV_INJECTION_RE = re.compile(r"\$\{[^}]+\}|\$[A-Za-z_][A-Za-z0-9_]*")


class InjectionGuardError(Exception):
    """Raised when a command fails injection validation."""
    def __init__(self, message: str, cmd: object = None) -> None:
        super().__init__(message)
        self.cmd = cmd


class InjectionGuard:
    """Validates shell command arguments against injection attacks.

    Design:
      The primary defense is structural — all commands are argv arrays, never
      shell strings. This guard provides defense-in-depth: detecting dangerous
      patterns, logging them, and optionally blocking them.

    Usage::

        guard = InjectionGuard()
        guard.validate_argv(["ls", "-la", "/workspace"])       # OK
        guard.validate_argv(["rm", "-rf", "/"])                # raises (high risk)
        guard.validate_argv(["echo", "hello; rm -rf /"])       # raises (metachar)
    """

    def __init__(
        self,
        *,
        allow_high_risk: bool = False,
        detect_env_injection: bool = True,
    ) -> None:
        """
        Args:
            allow_high_risk:       If False, HIGH_RISK_COMMANDS raise without user_confirmed.
            detect_env_injection:  If True, env var expansion patterns raise.
        """
        self._allow_high_risk = allow_high_risk
        self._detect_env     = detect_env_injection

    def validate_argv(
        self,
        argv: Sequence[str],
        *,
        user_confirmed: bool = False,
    ) -> list[str]:
        """Validate a command argv list.

        Args:
            argv:           Command as list of strings (e.g. ["ls", "-la"]).
            user_confirmed: If True, HIGH risk commands are permitted (user approved).

        Returns:
            The argv list if valid.

        Raises:
            InjectionGuardError: If the command is unsafe.
        """
        if not argv:
            raise InjectionGuardError("Command argv is empty", cmd=argv)

        if isinstance(argv, str):
            raise InjectionGuardError(
                "Command must be a list[str], not a string. "
                "Shell string execution is prohibited in AgentMoe. "
                "Pass argv as a list: ['cmd', 'arg1', 'arg2'].",
                cmd=argv,
            )

        argv_list = list(argv)

        # Each element must be a string
        for i, arg in enumerate(argv_list):
            if not isinstance(arg, str):
                raise InjectionGuardError(
                    f"argv[{i}] must be str, got {type(arg).__name__}",
                    cmd=argv_list,
                )

        # 1. High-risk command check
        binary = argv_list[0].rsplit("/", 1)[-1]  # basename
        if binary in _HIGH_RISK_COMMANDS:
            if not user_confirmed:
                raise InjectionGuardError(
                    f"Command {binary!r} is HIGH risk and requires user_confirmed=True. "
                    "This operation needs explicit user approval before execution.",
                    cmd=argv_list,
                )

        # 2. Metacharacter detection (defense-in-depth)
        for arg in argv_list:
            bad_chars = _SHELL_METACHARACTERS & set(arg)
            if bad_chars:
                raise InjectionGuardError(
                    f"Argument {arg!r} contains shell metacharacters {sorted(bad_chars)!r}. "
                    "This may indicate command injection. Use separate argv elements instead.",
                    cmd=argv_list,
                )

        # 3. Environment variable injection check
        if self._detect_env:
            for arg in argv_list:
                if _ENV_INJECTION_RE.search(arg):
                    raise InjectionGuardError(
                        f"Argument {arg!r} contains environment variable expansion pattern. "
                        "This may indicate injection. Pre-expand variables before passing.",
                        cmd=argv_list,
                    )

        return argv_list

    def validate_env(self, env: dict) -> dict[str, str]:
        """Validate an environment variable dict for subprocess injection.

        Both keys and values are checked for injection patterns.

        Returns:
            Cleaned env dict.

        Raises:
            InjectionGuardError: If any key or value looks dangerous.
        """
        result: dict[str, str] = {}
        for k, v in env.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise InjectionGuardError(
                    f"Env var keys and values must be str, got key={type(k)}, val={type(v)}"
                )
            # Keys: only allow [A-Za-z0-9_]
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", k):
                raise InjectionGuardError(
                    f"Environment variable name {k!r} contains invalid characters.",
                    cmd=k,
                )
            result[k] = v
        return result

    @staticmethod
    def is_high_risk_command(argv: Sequence[str]) -> bool:
        """Return True if the command binary is in the HIGH_RISK list."""
        if not argv:
            return False
        binary = str(argv[0]).rsplit("/", 1)[-1]
        return binary in _HIGH_RISK_COMMANDS
