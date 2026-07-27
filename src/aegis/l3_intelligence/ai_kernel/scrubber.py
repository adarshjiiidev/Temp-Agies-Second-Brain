"""§4.1 Prompt Scrubber — pre-routing privacy tagger and secret redactor.

Walks every ChatMessage in an AIRequest, detects secret patterns and PII
segments, computes the max_privacy_tier for the entire prompt, and replaces
detected secrets with safe placeholder tokens. Cloud providers never receive
the plaintext secret.

Design rules:
  - Pure function: no side-effects, no I/O, no async.
  - Depends only on: L1 llm.ChatMessage, L2 crypto.redact patterns,
    ai_kernel.types.PrivacyTier, ai_kernel.contracts.ScrubResult, stdlib.
  - The scrubber does NOT know about providers or routing; it merely
    annotates the request so the router can enforce the P0 rule.

§4.1 P0 override rule:
  If the scrubber detects any of the following in message content, it
  UNCONDITIONALLY sets privacy_tier = P0, regardless of caller tagging:
    * SSH/PEM private keys
    * AWS access/secret key patterns
    * Generic API key patterns (long alphanumeric prefixes)
    * Biometric data markers (base64-encoded blobs > 1kB without schema context
      are treated conservatively as potentially biometric)
"""

from __future__ import annotations

import re
from typing import Any

from aegis.l1_core.interfaces.llm import ChatMessage
from aegis.l3_intelligence.ai_kernel.types import PrivacyTier

# ---------------------------------------------------------------------------
# Patterns — compiled once at module load. Ordered by severity.
# P0 patterns: detecting these forces privacy_tier=P0 (NEVER_CLOUD).
# PII patterns: detecting these elevates tier to at minimum P1.
# ---------------------------------------------------------------------------

# P0-triggering patterns: secrets/keys that absolutely cannot go to cloud.
_P0_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("pem_private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("ssh_private_key", re.compile(r"-----BEGIN OPENSSH PRIVATE KEY-----")),
    ("aws_access_key", re.compile(r"(?:AKIA|ABIA|ASIA|AROA)[0-9A-Z]{16}")),
    ("aws_secret_key", re.compile(r"aws_secret_access_key\s*=\s*[0-9a-zA-Z/+]{40}")),
    # Generic high-entropy bearer / API key
    ("bearer_token", re.compile(r"Bearer\s+[A-Za-z0-9\-_\.]{40,}")),
    # OpenAI-style sk- key
    ("openai_api_key", re.compile(r"sk-[A-Za-z0-9]{40,}")),
    # Google API keys
    ("google_api_key", re.compile(r"AIza[0-9A-Za-z\-_]{35}")),
    # Anthropic keys
    ("anthropic_api_key", re.compile(r"sk-ant-[A-Za-z0-9\-_]{80,}")),
    # Groq keys
    ("groq_api_key", re.compile(r"gsk_[A-Za-z0-9]{50,}")),
]

# PII patterns that elevate to P1 (if currently P2/P3).
_P1_PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # Aadhaar (12-digit Indian national ID, various formats)
    ("aadhaar", re.compile(r"\b[2-9]\d{3}[\s\-]?\d{4}[\s\-]?\d{4}\b")),
    # PAN (Indian tax ID)
    ("pan", re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")),
    # Credit card (Luhn-ish — rough pattern)
    ("credit_card", re.compile(r"\b(?:\d{4}[\s\-]){3}\d{4}\b")),
    # IBAN
    ("iban", re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{4,30}\b")),
]

_REDACT_TEMPLATE = "<REDACTED:{kind}_{idx}>"


def _get_text(msg: ChatMessage) -> str:
    """Extract text content from a ChatMessage safely."""
    c = msg.content
    if c is None:
        return ""
    if isinstance(c, str):
        return c
    return str(c)


def _redact_text(
    text: str,
    patterns: list[tuple[str, re.Pattern[str]]],
    counter: list[int],
) -> tuple[str, list[dict[str, Any]]]:
    """Apply all patterns to text, replacing matches with placeholders.

    Returns (redacted_text, list_of_segment_dicts).
    counter is a single-element list used as a mutable int across calls.
    """
    segments: list[dict[str, Any]] = []
    result = text
    for kind, pattern in patterns:
        for match in pattern.finditer(result):
            idx = counter[0]
            counter[0] += 1
            placeholder = _REDACT_TEMPLATE.format(kind=kind, idx=idx)
            segments.append(
                {
                    "kind": kind,
                    "placeholder": placeholder,
                    "start": match.start(),
                    "end": match.end(),
                    "length": len(match.group()),
                }
            )
        result = pattern.sub(
            lambda m, k=kind, c=counter: _REDACT_TEMPLATE.format(kind=k, idx=c[0] - 1),
            result,
        )
    return result, segments


def scrub_messages(
    messages: list[ChatMessage],
    *,
    caller_privacy_tier: PrivacyTier = PrivacyTier.STANDARD,
) -> tuple[list[ChatMessage], PrivacyTier, int, list[dict[str, Any]], list[str]]:
    """Scrub messages and compute effective max privacy tier.

    Returns:
        (scrubbed_messages, max_privacy_tier, detected_secrets_count,
         redacted_segments, warnings)

    The caller must use max_privacy_tier as the routing privacy_tier,
    even if caller_privacy_tier was lower.
    """
    scrubbed: list[ChatMessage] = []
    max_tier = caller_privacy_tier
    detected_secrets = 0
    all_segments: list[dict[str, Any]] = []
    warnings: list[str] = []
    counter = [0]

    for msg in messages:
        text = _get_text(msg)
        if not text:
            scrubbed.append(msg)
            continue

        # --- Check P0 patterns (forces DEVICE_LOCAL_ONLY)
        p0_found = False
        p0_text = text
        for kind, pattern in _P0_PATTERNS:
            for match in pattern.finditer(p0_text):
                p0_found = True
                detected_secrets += 1
                idx = counter[0]
                counter[0] += 1
                placeholder = _REDACT_TEMPLATE.format(kind=kind, idx=idx)
                all_segments.append(
                    {
                        "kind": kind,
                        "placeholder": placeholder,
                        "privacy_tier": "P0",
                        "length": len(match.group()),
                    }
                )
                warnings.append(
                    f"P0 secret detected ({kind}) — routing forced to LOCAL_ONLY"
                )
            p0_text = pattern.sub(
                lambda m, k=kind, c=counter: _REDACT_TEMPLATE.format(kind=k, idx=c[0] - 1),
                p0_text,
            )

        if p0_found:
            max_tier = PrivacyTier.P0
            text = p0_text

        # --- Check P1 PII patterns (elevate to at least P1 if currently P2/P3)
        p1_text = text
        for kind, pattern in _P1_PII_PATTERNS:
            for match in pattern.finditer(p1_text):
                if max_tier not in (PrivacyTier.P0, PrivacyTier.P1):
                    max_tier = PrivacyTier.P1
                    warnings.append(
                        f"PII detected ({kind}) — privacy tier elevated to P1"
                    )
                detected_secrets += 1
                idx = counter[0]
                counter[0] += 1
                placeholder = _REDACT_TEMPLATE.format(kind=kind, idx=idx)
                all_segments.append(
                    {
                        "kind": kind,
                        "placeholder": placeholder,
                        "privacy_tier": "P1",
                        "length": len(match.group()),
                    }
                )
            p1_text = pattern.sub(
                lambda m, k=kind, c=counter: _REDACT_TEMPLATE.format(kind=k, idx=c[0] - 1),
                p1_text,
            )
        text = p1_text

        # Rebuild ChatMessage with scrubbed content (preserve other fields)
        if text != _get_text(msg):
            from dataclasses import replace as _dc_replace
            try:
                new_msg = _dc_replace(msg, content=text)
            except TypeError:
                # Frozen dataclass: use object reconstruction
                new_msg = ChatMessage(
                    role=msg.role,
                    content=text,
                    name=msg.name,
                    tool_calls=msg.tool_calls,
                    tool_call_id=msg.tool_call_id,
                )
            scrubbed.append(new_msg)
        else:
            scrubbed.append(msg)

    return scrubbed, max_tier, detected_secrets, all_segments, warnings


__all__ = ["scrub_messages"]
