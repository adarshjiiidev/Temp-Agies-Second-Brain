"""Capabilities MCP abstraction — MCPSchemaNormalizer.

Converts raw MCP tool JSON Schema definitions into AEGIS normalized
input/output schema format. Infers risk hints from tool metadata.

Import safety: stdlib only.
"""

from __future__ import annotations

import logging
import re
from typing import Any

__all__ = ["MCPSchemaNormalizer"]

logger = logging.getLogger(__name__)

# Keywords in tool name/description that suggest higher risk
_HIGH_RISK_PATTERNS = re.compile(
    r"\b(delete|remove|drop|destroy|execute|run|shell|cmd|admin|sudo|"
    r"write|create|modify|update|deploy|upload|send|post|publish)\b",
    re.IGNORECASE,
)

_NETWORK_PATTERNS = re.compile(
    r"\b(http|url|web|fetch|request|api|network|socket|download)\b",
    re.IGNORECASE,
)

_PRIVACY_PATTERNS = re.compile(
    r"\b(personal|private|secret|credential|password|token|key|auth|"
    r"email|contact|user|profile|message)\b",
    re.IGNORECASE,
)


class MCPSchemaNormalizer:
    """Normalizes MCP tool schemas into AEGIS format.

    Responsibilities:
    1. Extract input/output schemas from raw MCP tool definitions.
    2. Strip unknown/vendor-specific fields.
    3. Infer risk hints (required_permissions, privacy tier) from tool metadata.
    4. Validate that required MCP fields are present.
    """

    # Required fields in a valid MCP tool definition
    REQUIRED_FIELDS = {"name", "description"}

    def normalize(
        self,
        raw_tool: dict[str, Any],
        server_id: str,
    ) -> dict[str, Any]:
        """Normalize a raw MCP tool definition.

        Args:
            raw_tool: The raw tool dict from an MCP server's tool list.
            server_id: The owning server's ID (for ID construction).

        Returns:
            Normalized dict with keys: tool_name, description, input_schema,
            output_schema, risk_hints, privacy_tier, warnings.

        Raises:
            ValueError: If required fields (name, description) are missing.
        """
        missing = self.REQUIRED_FIELDS - set(raw_tool.keys())
        if missing:
            raise ValueError(
                f"MCP tool missing required fields: {missing!r} in {raw_tool!r}"
            )

        tool_name = str(raw_tool["name"])
        description = str(raw_tool.get("description", ""))

        # Extract and normalize input schema
        input_schema = self._normalize_schema(raw_tool.get("inputSchema", {}))

        # MCP spec doesn't always define output schema — use generic
        output_schema = self._normalize_schema(raw_tool.get("outputSchema", {
            "type": "object",
            "description": "Tool output",
        }))

        # Infer risk hints
        risk_hints = self._infer_risk_hints(tool_name, description, input_schema)
        privacy_tier = self._infer_privacy_tier(tool_name, description)

        warnings: list[str] = []
        if not description:
            warnings.append("Tool has no description — AI selection quality will be reduced")
        if not input_schema:
            warnings.append("Tool has no inputSchema — inputs cannot be validated")

        return {
            "tool_name": tool_name,
            "tool_id": f"{server_id}:{tool_name}",
            "description": description,
            "input_schema": input_schema,
            "output_schema": output_schema,
            "risk_hints": risk_hints,
            "privacy_tier": privacy_tier,
            "warnings": warnings,
        }

    def _normalize_schema(self, raw: Any) -> dict[str, Any]:
        """Convert a raw schema to a normalized dict."""
        if not isinstance(raw, dict):
            return {}
        # Keep only standard JSON Schema fields + a whitelist
        allowed = {
            "type", "properties", "required", "items", "enum",
            "description", "title", "format", "minimum", "maximum",
            "minLength", "maxLength", "pattern", "additionalProperties",
            "oneOf", "anyOf", "allOf", "$ref",
        }
        return {k: v for k, v in raw.items() if k in allowed}

    def _infer_risk_hints(
        self,
        tool_name: str,
        description: str,
        input_schema: dict,
    ) -> dict[str, Any]:
        """Infer risk metadata from tool name and description."""
        combined = f"{tool_name} {description}"
        hints: dict[str, Any] = {
            "required_permissions": [],
            "has_side_effects": False,
            "estimated_risk": "low",
        }

        if _HIGH_RISK_PATTERNS.search(combined):
            hints["has_side_effects"] = True
            hints["estimated_risk"] = "medium"
            hints["required_permissions"].append("mcp.tool.exec")

        if _NETWORK_PATTERNS.search(combined):
            hints["required_permissions"].append("network.request")
            hints["estimated_risk"] = "medium"

        # Check if any input property looks like credentials
        if input_schema:
            props = input_schema.get("properties", {})
            for prop_name in props:
                if _PRIVACY_PATTERNS.search(prop_name):
                    hints["estimated_risk"] = "high"
                    hints["required_permissions"].append("mcp.tool.privacy")
                    break

        return hints

    def _infer_privacy_tier(self, tool_name: str, description: str) -> str:
        """Infer privacy tier from tool name and description."""
        combined = f"{tool_name} {description}"
        if _PRIVACY_PATTERNS.search(combined):
            return "P1"
        if _NETWORK_PATTERNS.search(combined):
            return "P2"
        return "P2"   # Default for MCP tools
