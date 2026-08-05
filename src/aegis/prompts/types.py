"""Prompt Library — shared types.

Defines the data model for versioned prompt templates stored as YAML files.

Import safety: stdlib + pydantic only.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

__all__ = [
    "PromptTemplate",
    "PromptMetadata",
]


class PromptMetadata(BaseModel):
    """Version and evaluation metadata for a prompt template."""

    model_config = {"frozen": True}

    id: str
    version: str
    description: str
    output_schema: str          # Fully-qualified Python class name of the output schema
    min_context_tokens: int = 4096
    task_type: str = "chat"     # L3 TaskType hint for model routing
    eval_metrics: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    author: str = "aegis"
    deprecated: bool = False


class PromptTemplate(BaseModel):
    """A single versioned prompt template with rendering capability."""

    model_config = {"frozen": True}

    metadata: PromptMetadata
    template: str           # Jinja2-compatible template text

    def render(self, variables: dict[str, Any]) -> str:
        """Render the template by substituting ``{var}`` placeholders.

        Uses simple Python str.format_map for maximum portability (no
        Jinja2 dependency required at this layer). Variable keys that are
        not present in the template are silently ignored.

        Args:
            variables: Mapping of placeholder name → value string.

        Returns:
            Fully rendered prompt text ready to send to an LLM.
        """
        try:
            return self.template.format_map(_SafeFormatMap(variables))
        except (KeyError, ValueError):
            # If format fails, return template with best-effort substitution
            result = self.template
            for key, val in variables.items():
                result = result.replace(f"{{{key}}}", str(val))
            return result


class _SafeFormatMap(dict):
    """dict subclass that returns the key itself for missing keys."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"
