"""Capabilities discovery — LocalModelDiscoveryProvider.

Probes local LLM servers (Ollama, LM Studio) via HTTP and registers
discovered models as CapabilityRecords of category LOCAL_MODEL.

Works fully offline (only contacts localhost).

Import safety: stdlib + aegis.capabilities.model only.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request

from aegis.capabilities.discovery_providers.base import CapabilityDiscoveryProvider
from aegis.capabilities.model.capability import (
    CapabilityCategory,
    CapabilityRecord,
    ProvenanceSource,
    TrustState,
)
from aegis.capabilities.model.composition import BuiltinRef
from aegis.capabilities.model.health import CapabilityHealth, HealthStatus

logger = logging.getLogger(__name__)

__all__ = ["LocalModelDiscoveryProvider"]

_HTTP_TIMEOUT = 2.0


def _http_get_json(url: str) -> dict | list | None:
    """GET a URL and return parsed JSON, or None on any error."""
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
            return json.loads(resp.read())
    except Exception:  # noqa: BLE001
        return None


class LocalModelDiscoveryProvider(CapabilityDiscoveryProvider):
    """Discovers local LLM model servers via HTTP.

    Probes:
    1. Ollama at http://localhost:11434/api/tags
    2. LM Studio compatible endpoint at http://localhost:1234/v1/models

    Each discovered model becomes a CapabilityRecord of category LOCAL_MODEL.
    Models start as VERIFIED (server is reachable and returned model metadata).
    They are automatically privacy tier P0 (local processing, no external calls).
    """

    OLLAMA_BASE = "http://localhost:11434"
    LM_STUDIO_BASE = "http://localhost:1234"

    def __init__(
        self,
        ollama_base: str | None = None,
        lm_studio_base: str | None = None,
    ) -> None:
        self._ollama_base = ollama_base or self.OLLAMA_BASE
        self._lm_studio_base = lm_studio_base or self.LM_STUDIO_BASE

    @property
    def name(self) -> str:
        return "local_model_discovery_provider"

    def discover(self, deadline: float) -> list[CapabilityRecord]:
        records: list[CapabilityRecord] = []
        records.extend(self._probe_ollama(deadline))
        if time.monotonic() < deadline:
            records.extend(self._probe_lm_studio(deadline))
        return records

    # ------------------------------------------------------------------ #
    # Ollama
    # ------------------------------------------------------------------ #

    def _probe_ollama(self, deadline: float) -> list[CapabilityRecord]:
        if time.monotonic() > deadline:
            return []

        data = _http_get_json(f"{self._ollama_base}/api/tags")
        if not isinstance(data, dict):
            return []

        models = data.get("models", [])
        if not isinstance(models, list):
            return []

        records = []
        for model in models:
            if time.monotonic() > deadline:
                break
            name = model.get("name", "")
            if not name:
                continue
            cap_id = f"ollama:{name}"
            size_bytes = model.get("size", 0)
            modified_at = model.get("modified_at", "")
            records.append(CapabilityRecord(
                capability_id=cap_id,
                name=f"Ollama/{name}",
                description=f"Local LLM model {name!r} served via Ollama",
                category=CapabilityCategory.LOCAL_MODEL,
                version=model.get("digest", "unknown")[:12],
                provider_id="ollama",
                provenance=ProvenanceSource.SYSTEM_DISCOVERY,
                trust_state=TrustState.VERIFIED,
                online_required=False,
                privacy_tier="P0",
                required_permissions=["network.local"],
                implementation=BuiltinRef(
                    executor_name="http_executor",
                    action_kind="http.post",
                    module_path="aegis.l5_execution.executors.http",
                ),
                health=CapabilityHealth(status=HealthStatus.AVAILABLE),
                enabled=True,
                input_schema={
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string"},
                        "model": {"type": "string", "const": name},
                    },
                    "required": ["prompt"],
                },
                output_schema={
                    "type": "object",
                    "properties": {"response": {"type": "string"}},
                },
            ))

        if records:
            logger.debug(
                "LocalModelDiscoveryProvider: found %d Ollama model(s)", len(records)
            )
        return records

    # ------------------------------------------------------------------ #
    # LM Studio
    # ------------------------------------------------------------------ #

    def _probe_lm_studio(self, deadline: float) -> list[CapabilityRecord]:
        if time.monotonic() > deadline:
            return []

        data = _http_get_json(f"{self._lm_studio_base}/v1/models")
        if not isinstance(data, dict):
            return []

        models_data = data.get("data", [])
        if not isinstance(models_data, list):
            return []

        records = []
        for model in models_data:
            if time.monotonic() > deadline:
                break
            model_id = model.get("id", "")
            if not model_id:
                continue
            cap_id = f"lm_studio:{model_id}"
            records.append(CapabilityRecord(
                capability_id=cap_id,
                name=f"LMStudio/{model_id}",
                description=f"Local LLM model {model_id!r} served via LM Studio",
                category=CapabilityCategory.LOCAL_MODEL,
                version=str(model.get("created", "unknown")),
                provider_id="lm_studio",
                provenance=ProvenanceSource.SYSTEM_DISCOVERY,
                trust_state=TrustState.VERIFIED,
                online_required=False,
                privacy_tier="P0",
                required_permissions=["network.local"],
                implementation=BuiltinRef(
                    executor_name="http_executor",
                    action_kind="http.post",
                    module_path="aegis.l5_execution.executors.http",
                ),
                health=CapabilityHealth(status=HealthStatus.AVAILABLE),
                enabled=True,
            ))
        if records:
            logger.debug(
                "LocalModelDiscoveryProvider: found %d LM Studio model(s)", len(records)
            )
        return records
