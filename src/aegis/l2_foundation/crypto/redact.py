"""L2 Automatic redaction service.
Prompt 02 §8 / §05 Security Boundary SB06: Secrets never appear in logs, traces, crash dumps, stdout.
Pattern-based redactor covers API keys, tokens, passwords, private keys, credit cards, Aadhaar, PAN,
custom user-provided patterns, and `secret_ref` wrappers.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Pattern

# Default patterns: label → compiled regex. Matches common secret formats seen in the wild.
DEFAULT_PATTERNS: dict[str, Pattern[str]] = {
    # API key style prefixes
    "api_key_generic": re.compile(r"(?i)\b(?:api[_-]?key|apikey)\s*[:=]\s*['\"]?([A-Za-z0-9_\-]{16,})['\"]?"),
    # Bearer token
    "bearer_token": re.compile(r"(?i)\bbearer\s+([A-Za-z0-9\-._~+/]+=*)"),
    # Private keys (RSA/EC/SSH/PEM) — capture the PEM block
    "private_key_pem": re.compile(
        r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----[\s\S]+?-----END (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----"
    ),
    # AWS Access Key
    "aws_access_key": re.compile(r"(?i)\b(AKIA[0-9A-Z]{16})\b"),
    # Generic hex/token 32+
    "long_hex_token": re.compile(r"\b[0-9a-fA-F]{32,}\b"),
    # JSON web token (JWT)
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    # Password assignment
    "password_assign": re.compile(r"(?i)\b(?:password|passwd|pwd)\s*[:=]\s*['\"]?([^\s,]{4,})['\"]?"),
    # Credit card — loose 13-19 digits with optional separators
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
    # Aadhaar (India): 4-4-4 format or 12 digits
    "aadhaar": re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"),
    # PAN (India): 5 letters + 4 digits + 1 letter
    "pan_india": re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),
}

REDACT_PLACEHOLDER = "<REDACTED:{}>"


def _redact_str(value: str, patterns: dict[str, Pattern[str]]) -> str:
    out = value
    # Pattern 1: replace entire match for private key
    for lbl, pat in patterns.items():
        def _sub(m: re.Match[str], label: str = lbl) -> str:  # noqa: D401 - closure
            return REDACT_PLACEHOLDER.format(label)
        out = pat.sub(_sub, out)
    return out


def secret_ref(scope: str, identifier: str) -> str:
    """Build a reference string matching config's secret:// URL form.
    These NEVER resolve to plaintext when logged — see ImmutableConfigSnapshot handling."""
    return f"secret://{scope}/{identifier}"


def is_secret_ref(value: Any) -> bool:  # noqa: ANN401
    return isinstance(value, str) and value.startswith("secret://")


@dataclass
class Redactor:
    """Configurable redactor. Additional patterns may be appended at init time."""

    extra_patterns: dict[str, Pattern[str] | str] = field(default_factory=dict)
    redact_refs: bool = True

    def __post_init__(self) -> None:
        self._compiled: dict[str, Pattern[str]] = dict(DEFAULT_PATTERNS)
        for lbl, pat in self.extra_patterns.items():
            self._compiled[lbl] = re.compile(pat) if isinstance(pat, str) else pat

    # -------- public --------

    def redact(self, value: Any, *, max_depth: int = 5, _depth: int = 0) -> Any:  # noqa: ANN401
        if _depth > max_depth:
            return REDACT_PLACEHOLDER.format("MAXDEPTH")
        if value is None or isinstance(value, (int, float, complex, bool)):
            return value
        if is_secret_ref(value) and self.redact_refs:
            return REDACT_PLACEHOLDER.format("SECRET_REF")
        if isinstance(value, bytes):
            # Heuristic: treat bytes as sensitive; show length only.
            return f"<REDACTED:BYTES len={len(value)}>"
        if isinstance(value, str):
            return _redact_str(value, self._compiled)
        if isinstance(value, dict):
            result: dict[str, Any] = {}
            for k, v in value.items():
                if any(s in str(k).lower() for s in ("secret", "password", "token", "api_key", "private", "credential")):
                    result[str(k)] = REDACT_PLACEHOLDER.format("KEY_" + str(k))
                else:
                    result[str(k)] = self.redact(v, max_depth=max_depth, _depth=_depth + 1)
            return result
        if isinstance(value, (list, tuple, set, frozenset)):
            return type(value)(self.redact(x, max_depth=max_depth, _depth=_depth + 1) for x in value)  # type: ignore[call-arg]
        # Fallback: convert to repr, redact as string
        return _redact_str(repr(value), self._compiled)


# Module-level singleton used by default logger/errors
_DEFAULT_REDACTOR: Redactor | None = None


def get_default_redactor() -> Redactor:
    global _DEFAULT_REDACTOR
    if _DEFAULT_REDACTOR is None:
        _DEFAULT_REDACTOR = Redactor()
    return _DEFAULT_REDACTOR


def redact_value(value: Any) -> Any:  # noqa: ANN401
    """Convenience using the default redactor singleton."""
    return get_default_redactor().redact(value)
