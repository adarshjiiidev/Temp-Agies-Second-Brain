"""§19 Typed structured output contracts: Pydantic v2 validation, retry-recovery
loop helper, fenced/raw JSON extraction, never accept malformed silently,
provider neutral.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Type, TypeVar

from pydantic import BaseModel, ValidationError as PydanticValidationError

from aegis.l1_core.errors import (
    ErrorCode,
    AIStructuredOutputError,
    AIStructuredRetriesExhaustedError,
)
from aegis.l3_intelligence.ai_kernel.contracts import StructuredOutputRequirements


T = TypeVar("T", bound=BaseModel)


@dataclass
class ParsedStructuredResult:
    schema_name: str | None
    data: BaseModel | None
    raw_dict: dict | None
    raw_text: str
    is_valid: bool
    parse_errors: list[str]
    validation_errors: list[dict[str, Any]]
    partial_data: dict | None = None


def extract_json_block(text: str) -> tuple[str, bool]:
    if not text:
        return "", False

    fence_pattern = re.compile(r"```json\s*\n?\s*(.*?)\s*\n?```", re.DOTALL)
    fence_match = fence_pattern.search(text)
    if fence_match:
        return fence_match.group(1).strip(), True

    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return text[first_brace : last_brace + 1].strip(), False

    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped, False

    return stripped, False


class StructuredOutputProcessor:
    def __init__(
        self,
        *,
        max_retries: int = 3,
        include_raw_text: bool = False,
        allow_partial: bool = False,
    ) -> None:
        self.max_retries = max_retries
        self.include_raw_text = include_raw_text
        self.allow_partial = allow_partial

    def validate_schema_dict(
        self,
        data: dict,
        schema: Type[BaseModel] | dict | None,
    ) -> tuple[Any, list[dict[str, Any]]]:
        if schema is None:
            return data, []

        if isinstance(schema, type) and issubclass(schema, BaseModel):
            try:
                instance = schema.model_validate(data, strict=True)
                return instance, []
            except PydanticValidationError as exc:
                errors: list[dict[str, Any]] = []
                for err in exc.errors():
                    errors.append(
                        {
                            "loc": list(err.get("loc", ())),
                            "msg": err.get("msg", ""),
                            "type": err.get("type", ""),
                        }
                    )
                return None, errors

        if isinstance(schema, dict):
            if isinstance(data, dict):
                return data, []
            return None, [{"loc": ["__root__"], "msg": "Expected object (dict)", "type": "type_error"}]

        return data, []

    def parse(
        self,
        raw_response_text: str,
        req: StructuredOutputRequirements,
    ) -> ParsedStructuredResult:
        parse_errors: list[str] = []
        validation_errors: list[dict[str, Any]] = []
        raw_dict: dict | None = None
        data: BaseModel | None = None
        partial_data: dict | None = None

        extracted_str, _ = extract_json_block(raw_response_text)

        try:
            if extracted_str:
                raw_dict = json.loads(extracted_str)
            else:
                parse_errors.append("Empty JSON content extracted")
        except json.JSONDecodeError as exc:
            parse_errors.append(f"JSONDecodeError: {exc.msg} at line {exc.lineno} column {exc.colno}")
            raw_dict = None

        if raw_dict is not None and req.output_schema is not None:
            validated, v_errors = self.validate_schema_dict(raw_dict, req.output_schema)
            if v_errors:
                validation_errors = v_errors
                data = None
            else:
                data = validated

        if raw_dict is not None and req.json_schema is not None and req.output_schema is None:
            _, v_errors = self.validate_schema_dict(raw_dict, req.json_schema)
            if v_errors:
                validation_errors = v_errors

        allow_partial = req.allow_partial or self.allow_partial
        if allow_partial and raw_dict is not None and (parse_errors or validation_errors):
            partial_data = {}
            if isinstance(raw_dict, dict):
                schema_keys: set[str] = set()
                if req.output_schema is not None and isinstance(req.output_schema, type):
                    if hasattr(req.output_schema, "model_fields"):
                        schema_keys = set(req.output_schema.model_fields.keys())
                    elif hasattr(req.output_schema, "__fields__"):
                        schema_keys = set(req.output_schema.__fields__.keys())
                if req.json_schema is not None:
                    props = req.json_schema.get("properties", {})
                    schema_keys.update(props.keys())

                for key, value in raw_dict.items():
                    try:
                        if schema_keys:
                            if key in schema_keys:
                                json.dumps(value)
                                partial_data[key] = value
                        else:
                            json.dumps(value)
                            partial_data[key] = value
                    except (TypeError, ValueError):
                        continue

        schema_name: str | None = None
        if req.output_schema is not None and isinstance(req.output_schema, type):
            schema_name = req.output_schema.__name__
        elif req.json_schema is not None:
            schema_name = req.json_schema.get("title") or req.json_schema.get("name") or "json_schema"

        has_schema = req.has_schema
        schema_validated = has_schema and data is not None
        is_valid = not parse_errors and not validation_errors and ((not has_schema) or schema_validated)

        return ParsedStructuredResult(
            schema_name=schema_name,
            data=data,
            raw_dict=raw_dict,
            raw_text=raw_response_text,
            is_valid=is_valid,
            parse_errors=parse_errors,
            validation_errors=validation_errors,
            partial_data=partial_data,
        )

    def format_retry_prompt(
        self,
        prev_result: ParsedStructuredResult,
        *,
        original_schema_json: dict | None = None,
    ) -> str:
        parts: list[str] = []
        parts.append("Your previous response failed validation.")

        errors: list[str] = []
        if prev_result.parse_errors:
            errors.extend(f"Parse error: {e}" for e in prev_result.parse_errors)
        if prev_result.validation_errors:
            for err in prev_result.validation_errors:
                loc = ".".join(str(l) for l in err.get("loc", [])) or "<root>"
                msg = err.get("msg", "")
                errors.append(f"Validation error at {loc}: {msg}")

        if errors:
            parts.append("Errors:")
            for i, err in enumerate(errors, 1):
                parts.append(f"  {i}. {err}")
        else:
            parts.append("Errors: [unspecified validation failure]")

        if original_schema_json is not None:
            try:
                schema_str = json.dumps(original_schema_json, indent=2)
                parts.append("Please retry strictly matching schema:")
                parts.append(schema_str)
            except (TypeError, ValueError):
                parts.append("Please retry strictly matching the required schema.")
        else:
            parts.append("Please retry strictly matching the required schema.")

        return "\n".join(parts)

    def should_retry(self, result: ParsedStructuredResult, attempt_so_far: int) -> bool:
        return attempt_so_far < self.max_retries and not result.is_valid

    def raise_retries_exhausted(self) -> None:
        raise AIStructuredRetriesExhaustedError(
            ErrorCode.AI_STRUCTURED_RETRIES_EXHAUSTED,
            f"Structured output retries exhausted after {self.max_retries} attempts.",
        )


def retry_n(
    processor: StructuredOutputProcessor,
    retries_list: list[ParsedStructuredResult] | None = None,
) -> None:
    if retries_list is not None:
        if len(retries_list) >= processor.max_retries:
            processor.raise_retries_exhausted()
        if retries_list and all(not r.is_valid for r in retries_list):
            if len(retries_list) >= processor.max_retries:
                processor.raise_retries_exhausted()
