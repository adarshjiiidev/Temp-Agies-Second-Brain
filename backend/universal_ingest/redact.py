#!/usr/bin/env python3
"""Secret redaction for universal ingest. NEVER log raw matches."""
import re

_PATTERNS = [
    r'(?i)(api[_-]?key\s*[:=]\s*)(["\']?)[A-Za-z0-9_\-./+]{8,}\2',
    r'(?i)(token\s*[:=]\s*)(["\']?)[A-Za-z0-9_\-./+]{8,}\2',
    r'(?i)(password\s*[:=]\s*)(["\']?)[^\s"\']{4,}\2',
    r'(?i)(secret\s*[:=]\s*)(["\']?)[A-Za-z0-9_\-./+]{6,}\2',
    r'Bearer\s+[A-Za-z0-9_\-./+~=]{10,}',
    r'sk-or-v1[a-zA-Z0-9\-_]{8,}',
    r'sk-ant-[A-Za-z0-9\-_]{8,}',
    r'sk-[A-Za-z0-9]{16,}',
    r'xox[baprs]-[A-Za-z0-9\-]+',
    r'ghp_[A-Za-z0-9]{20,}',
    r'AKIA[0-9A-Z]{16}',
]

_COMPILED = [re.compile(p) for p in _PATTERNS]


def _mask_keyval(m):
    # group(1) is the key prefix; keep prefix, drop value
    try:
        prefix = m.group(1)
    except Exception:
        return "***"
    return prefix + "***"


def redact(text):
    """Replace API-key/token/password-shaped values with ***."""
    if not text:
        return ""
    if not isinstance(text, str):
        text = str(text)
    out = text
    for rx in _COMPILED:
        try:
            if rx.pattern.startswith("(?i)(api") or rx.pattern.startswith("(?i)(token") \
                    or rx.pattern.startswith("(?i)(password") or rx.pattern.startswith("(?i)(secret"):
                out = rx.sub(_mask_keyval, out)
            else:
                out = rx.sub("***", out)
        except Exception:
            continue
    return out
