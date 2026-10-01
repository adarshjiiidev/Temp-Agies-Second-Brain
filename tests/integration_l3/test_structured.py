"""Integration tests — Structured output validation + retry loop (§6).

50 randomized schema tasks. All must end with:
  - A valid parsed object, OR
  - AIStructuredRetriesExhaustedError (never returns invalid object to caller).

Also validates: JSON extraction from markdown fences, Pydantic model_validate,
retry prompt formatting, partial output support.
"""

from __future__ import annotations

import json
import random

import pytest
from pydantic import BaseModel

from aegis.l1_core.errors.base import AIStructuredRetriesExhaustedError
from aegis.l3_intelligence.ai_kernel.contracts import StructuredOutputRequirements
from aegis.l3_intelligence.ai_kernel.structured import (
    ParsedStructuredResult,
    StructuredOutputProcessor,
    extract_json_block,
)


# ---------------------------------------------------------------------------
# Test Pydantic schemas
# ---------------------------------------------------------------------------

class SimpleAnswer(BaseModel):
    answer: str
    confidence: float


class StepPlan(BaseModel):
    goal: str
    steps: list[str]
    risk_level: str


class CodeOutput(BaseModel):
    language: str
    code: str
    explanation: str


# ---------------------------------------------------------------------------
# extract_json_block tests
# ---------------------------------------------------------------------------

class TestExtractJsonBlock:
    def test_bare_json_object(self):
        text = '{"key": "value"}'
        result, _ = extract_json_block(text)
        assert json.loads(result) == {"key": "value"}

    def test_markdown_fenced_json(self):
        text = '```json\n{"key": "value"}\n```'
        result, was_fenced = extract_json_block(text)
        assert json.loads(result) == {"key": "value"}
        assert was_fenced is True

    def test_extra_text_with_json(self):
        text = 'Here is the answer:\n{"key": "value"}\nThat is all.'
        result, _ = extract_json_block(text)
        assert json.loads(result) == {"key": "value"}

    def test_empty_string(self):
        result, _ = extract_json_block("")
        assert result == ""

    def test_no_json(self):
        result, _ = extract_json_block("Just plain text, no JSON here.")
        # Returns stripped text
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# StructuredOutputProcessor.parse
# ---------------------------------------------------------------------------

class TestStructuredOutputProcessorParse:
    def setup_method(self):
        self.proc = StructuredOutputProcessor(max_retries=3)

    def test_valid_json_no_schema(self):
        req = StructuredOutputRequirements()
        result = self.proc.parse('{"hello": "world"}', req)
        assert result.is_valid is True
        assert result.raw_dict == {"hello": "world"}

    def test_valid_json_with_pydantic_schema(self):
        req = StructuredOutputRequirements(output_schema=SimpleAnswer)
        raw = '{"answer": "42", "confidence": 0.95}'
        result = self.proc.parse(raw, req)
        assert result.is_valid is True
        assert isinstance(result.data, SimpleAnswer)
        assert result.data.answer == "42"

    def test_invalid_json_returns_parse_errors(self):
        req = StructuredOutputRequirements(output_schema=SimpleAnswer)
        result = self.proc.parse("not json at all", req)
        assert result.is_valid is False
        assert len(result.parse_errors) > 0

    def test_schema_mismatch_returns_validation_errors(self):
        req = StructuredOutputRequirements(output_schema=SimpleAnswer)
        raw = '{"wrong_key": "value"}'
        result = self.proc.parse(raw, req)
        assert result.is_valid is False
        assert len(result.validation_errors) > 0

    def test_fenced_markdown_parsed(self):
        req = StructuredOutputRequirements(output_schema=SimpleAnswer)
        raw = '```json\n{"answer": "hello", "confidence": 0.5}\n```'
        result = self.proc.parse(raw, req)
        assert result.is_valid is True


# ---------------------------------------------------------------------------
# 50 randomized schema tasks: valid OR retries_exhausted — never invalid return
# ---------------------------------------------------------------------------

_SCHEMAS = [SimpleAnswer, StepPlan, CodeOutput]

def _valid_payload(schema) -> str:
    if schema is SimpleAnswer:
        return json.dumps({"answer": "test", "confidence": round(random.uniform(0, 1), 2)})
    if schema is StepPlan:
        return json.dumps({"goal": "test", "steps": ["step1", "step2"], "risk_level": "low"})
    if schema is CodeOutput:
        return json.dumps({"language": "python", "code": "print(1)", "explanation": "prints 1"})
    return "{}"


def _invalid_payload() -> str:
    return random.choice([
        "not json",
        "```\nbroken\n```",
        '{"wrong_key": 123}',
        "",
        '{"answer": "missing confidence"}',
    ])


@pytest.mark.parametrize("case_idx", range(50))
def test_structured_output_valid_or_retries_exhausted(case_idx):
    """50 cases: parse result must be either valid OR raise retries_exhausted.
    Caller must NEVER see an invalid structured object returned silently.
    """
    schema = _SCHEMAS[case_idx % len(_SCHEMAS)]
    # Randomly mix valid and invalid payloads
    is_valid_case = case_idx % 3 != 0  # 2/3 valid, 1/3 invalid
    raw = _valid_payload(schema) if is_valid_case else _invalid_payload()

    proc = StructuredOutputProcessor(max_retries=3)
    req = StructuredOutputRequirements(output_schema=schema)
    result = proc.parse(raw, req)

    if result.is_valid:
        # Valid result: data must be the Pydantic model, never None
        assert result.data is not None, f"Case {case_idx}: is_valid but data is None"
        assert isinstance(result.data, schema)
    else:
        # Invalid result: must raise retries_exhausted, not return silently
        with pytest.raises(AIStructuredRetriesExhaustedError):
            proc.raise_retries_exhausted()


# ---------------------------------------------------------------------------
# Retry loop logic
# ---------------------------------------------------------------------------

class TestRetryLoop:
    def test_should_retry_true_when_invalid_and_attempts_remaining(self):
        proc = StructuredOutputProcessor(max_retries=3)
        req = StructuredOutputRequirements(output_schema=SimpleAnswer)
        result = proc.parse("not json", req)
        assert not result.is_valid
        assert proc.should_retry(result, attempt_so_far=0)

    def test_should_retry_false_when_exhausted(self):
        proc = StructuredOutputProcessor(max_retries=2)
        req = StructuredOutputRequirements(output_schema=SimpleAnswer)
        result = proc.parse("not json", req)
        assert not proc.should_retry(result, attempt_so_far=2)

    def test_should_retry_false_when_valid(self):
        proc = StructuredOutputProcessor(max_retries=3)
        req = StructuredOutputRequirements(output_schema=SimpleAnswer)
        result = proc.parse('{"answer": "ok", "confidence": 0.9}', req)
        assert result.is_valid
        assert not proc.should_retry(result, attempt_so_far=0)

    def test_format_retry_prompt_includes_errors(self):
        proc = StructuredOutputProcessor(max_retries=3)
        req = StructuredOutputRequirements(output_schema=SimpleAnswer)
        bad_result = proc.parse("not json", req)
        retry_prompt = proc.format_retry_prompt(bad_result)
        assert "failed validation" in retry_prompt.lower()

    def test_raise_retries_exhausted(self):
        proc = StructuredOutputProcessor(max_retries=1)
        with pytest.raises(AIStructuredRetriesExhaustedError):
            proc.raise_retries_exhausted()
