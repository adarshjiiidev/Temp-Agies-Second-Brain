"""P07 Privacy — Redactor.

Strips sensitive path components and P0/P1 fields from scan results
before they reach EnvironmentStore. Applied at the ingestion boundary
after ZoneRegistry.check_node() passes.

Import safety: stdlib ONLY.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

__all__ = ["Redactor", "RedactionConfig"]

# Patterns that indicate credentials / secrets in attribute keys
_SENSITIVE_KEY_PATTERNS: list[re.Pattern] = [
    re.compile(r"password", re.I),
    re.compile(r"secret", re.I),
    re.compile(r"token", re.I),
    re.compile(r"api[_\-]?key", re.I),
    re.compile(r"private[_\-]?key", re.I),
    re.compile(r"credential", re.I),
]

_REDACTED_MARKER = "<REDACTED>"


@dataclass
class RedactionConfig:
    """Configuration for the Redactor.

    Attributes:
        strip_home_prefix:  Replace the home directory prefix with ``~``
                            in all path strings (reduces personal exposure).
        redact_env_vars:    Redact environment variable values in attribute dicts.
        max_path_depth:     If > 0, truncate paths deeper than this to their
                            last N components (reduces specificity).
    """
    strip_home_prefix: bool = True
    redact_env_vars: bool = True
    max_path_depth: int = 0  # 0 = no truncation


class Redactor:
    """Deterministic scrubber applied to node attributes before storage.

    The Redactor never touches privacy zone decisions (that is ZoneRegistry's
    job). It only normalises and strips sensitive values from attribute dicts.

    Usage::

        redactor = Redactor()
        clean_attrs = redactor.scrub_attributes(raw_attrs)
        clean_path  = redactor.scrub_path(raw_path)
    """

    def __init__(self, config: RedactionConfig | None = None) -> None:
        self._config = config or RedactionConfig()
        self._home = os.path.expanduser("~")

    def scrub_path(self, path: str) -> str:
        """Normalise a path string per RedactionConfig."""
        if not path:
            return path
        expanded = os.path.expanduser(path)
        if self._config.strip_home_prefix and expanded.startswith(self._home):
            path = "~" + expanded[len(self._home):]
        else:
            path = expanded

        if self._config.max_path_depth > 0:
            parts = path.replace("\\", "/").split("/")
            if len(parts) > self._config.max_path_depth:
                path = "/".join(parts[-self._config.max_path_depth:])

        return path

    def scrub_attributes(self, attrs: dict) -> dict:
        """Strip or replace sensitive attribute values."""
        result: dict = {}
        for key, value in attrs.items():
            if self._is_sensitive_key(key):
                result[key] = _REDACTED_MARKER
            elif isinstance(value, str):
                result[key] = self.scrub_path(value) if "/" in value or "\\" in value else value
            elif isinstance(value, dict):
                result[key] = self.scrub_attributes(value)
            elif isinstance(value, list):
                result[key] = [
                    self.scrub_attributes(v) if isinstance(v, dict)
                    else (self.scrub_path(v) if isinstance(v, str) and ("/" in v or "\\" in v) else v)
                    for v in value
                ]
            else:
                result[key] = value
        return result

    def _is_sensitive_key(self, key: str) -> bool:
        return any(pat.search(key) for pat in _SENSITIVE_KEY_PATTERNS)
