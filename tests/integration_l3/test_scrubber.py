"""Integration tests — Prompt Scrubber §4.1.

20 attack prompts with embedded secrets → scrubber classifies P0 and
blocks cloud. Validates redaction, tier elevation, and segment reporting.
"""

from __future__ import annotations

import pytest

from aegis.l1_core.interfaces.llm import ChatMessage
from aegis.l3_intelligence.ai_kernel.scrubber import scrub_messages
from aegis.l3_intelligence.ai_kernel.types import PrivacyTier


def _msg(content: str) -> ChatMessage:
    return ChatMessage(role="user", content=content)


class TestScrubberP0Detection:
    """20 attack prompts: all should be detected as P0."""

    @pytest.mark.parametrize("secret", [
        "sk-" + "a" * 45,                                        # OpenAI key
        "sk-ant-api03-" + "b" * 80,                             # Anthropic
        "gsk_" + "c" * 55,                                      # Groq
        "AIza" + "d" * 35,                                      # Google API
        "AKIAIOSFODNN7EXAMPLE" + "e" * 3,                       # AWS access key
        "aws_secret_access_key = " + "f" * 40,                  # AWS secret
        "-----BEGIN RSA PRIVATE KEY-----\nMIIE...\n-----END RSA PRIVATE KEY-----",
        "-----BEGIN OPENSSH PRIVATE KEY-----\ndata\n-----END OPENSSH PRIVATE KEY-----",
        "Bearer " + "g" * 45,                                   # Bearer token
        "Authorization: Bearer " + "h" * 50,                    # Bearer in header
        "sk-" + "i" * 50 + " this is my openai key",
        "my key: " + "AIza" + "j" * 35,
        "OPENAI_API_KEY=" + "sk-" + "k" * 48,
        "export GROQ_API_KEY=gsk_" + "l" * 52,
        # Embedded in sentences:
        "Please use this key sk-" + "m" * 45 + " to access",
        "The secret key is sk-ant-" + "n" * 80 + " and must be kept safe",
        "-----BEGIN PRIVATE KEY-----\nXXXXXX==\n-----END PRIVATE KEY-----",
        "aws_secret_access_key = " + "o" * 40,
        "api_key=AIza" + "p" * 35,
        "Bearer " + "q" * 60 + " must never leave device",
    ])
    def test_p0_secret_detected(self, secret: str):
        msgs, tier, detected, segments, warnings = scrub_messages(
            [_msg(secret)],
            caller_privacy_tier=PrivacyTier.P2,
        )
        assert tier == PrivacyTier.P0, (
            f"Expected P0 for secret pattern but got {tier.value!r}: {secret[:40]!r}"
        )
        assert detected >= 1, "At least one secret should be detected"
        assert len(warnings) >= 1

    def test_redaction_removes_secret_from_content(self):
        key = "sk-" + "x" * 45
        msgs, tier, detected, segments, warnings = scrub_messages([_msg(key)])
        assert key not in (msgs[0].content or ""), "Plaintext secret must be redacted"
        assert "REDACTED" in (msgs[0].content or "")

    def test_normal_text_unchanged(self):
        text = "What is the capital of France?"
        msgs, tier, _, _, _ = scrub_messages([_msg(text)], caller_privacy_tier=PrivacyTier.P2)
        assert msgs[0].content == text
        assert tier == PrivacyTier.P2

    def test_caller_p0_not_downgraded(self):
        """Caller-declared P0 stays P0 even with clean message."""
        msgs, tier, _, _, _ = scrub_messages(
            [_msg("clean message")],
            caller_privacy_tier=PrivacyTier.P0,
        )
        assert tier == PrivacyTier.P0


class TestScrubberPIIDetection:
    def test_aadhaar_elevates_to_p1(self):
        aadhaar = "2345 6789 0123"
        msgs, tier, detected, _, warnings = scrub_messages(
            [_msg(f"My Aadhaar is {aadhaar}")],
            caller_privacy_tier=PrivacyTier.P2,
        )
        assert tier == PrivacyTier.P1
        assert detected >= 1

    def test_pan_elevates_to_p1(self):
        pan = "ABCDE1234F"
        msgs, tier, detected, _, _ = scrub_messages(
            [_msg(f"PAN: {pan}")],
            caller_privacy_tier=PrivacyTier.P2,
        )
        assert tier == PrivacyTier.P1

    def test_caller_p1_not_downgraded_by_pii(self):
        pan = "ABCDE1234F"
        msgs, tier, _, _, _ = scrub_messages(
            [_msg(f"PAN: {pan}")],
            caller_privacy_tier=PrivacyTier.P1,
        )
        assert tier == PrivacyTier.P1

    def test_p0_wins_over_pii(self):
        """Message has both an API key (P0) and PAN (P1) → P0 should win."""
        content = "sk-" + "a" * 45 + " and PAN ABCDE1234F"
        msgs, tier, _, _, _ = scrub_messages([_msg(content)])
        assert tier == PrivacyTier.P0


class TestScrubberMultiMessage:
    def test_secret_in_one_message_elevates_all(self):
        msgs = [
            _msg("Hello, my name is Alice."),
            _msg("sk-" + "z" * 45),
            _msg("Nice to meet you."),
        ]
        _, tier, detected, _, _ = scrub_messages(msgs)
        assert tier == PrivacyTier.P0
        assert detected >= 1

    def test_empty_messages_unchanged(self):
        msgs, tier, detected, _, _ = scrub_messages([])
        assert msgs == []
        assert tier == PrivacyTier.P2
        assert detected == 0
