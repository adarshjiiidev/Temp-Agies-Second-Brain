"""L2 Plugin Loader skeleton — Prompt 02 only.

Per Prompt 02 strict scope: plugins not implemented yet, but the runtime bootstrap must
declare a stable interface so L3+ can register plugins without breaking existing code.
We provide:
  - PluginManifest (id, version, entry_point, capabilities, requires_service_ids, security_boundary)
  - PluginLoader (scan_dir, load, list_plugins) — currently NO-OP except for manually registered stubs
  - SandboxTier (T0..T3 per 05_SECURITY_PRIVACY.md §SB06)
Plugin sandbox code, T3 cgroups, deny-by-default signatures, dynamic import gates are EXPLICITLY
deferred to Prompt 10+.
"""
from __future__ import annotations

import enum
import importlib.util
import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from aegis.l1_core.errors import ErrorCode, InitializationError, NotFoundError, ValidationError
from aegis.l2_foundation.telemetry.logger import get_logger

log = get_logger(__name__)


class SandboxTier(enum.Enum):
    T0 = "T0"  # core runtime / no sandbox needed
    T1 = "T1"  # trusted plugin (process-local, minimal sandbox)
    T2 = "T2"  # untrusted plugin (process-local + restricted APIs)
    T3 = "T3"  # untrusted remote / subprocess / cgroups (FUTURE)


@dataclass
class PluginManifest:
    plugin_id: str
    version: str
    entry_point: str
    display_name: str = ""
    description: str = ""
    authors: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    requires_service_ids: list[str] = field(default_factory=list)
    security_boundary: SandboxTier = SandboxTier.T1
    feature_flags: dict[str, Any] = field(default_factory=dict)
    integrity_sha256: str | None = None  # deny-by-default integrity pin (Prompt 10+)

    @classmethod
    def from_dict(cls, d: dict) -> "PluginManifest":
        tier_raw = d.get("security_boundary", "T1")
        try:
            tier = SandboxTier(tier_raw)
        except ValueError as exc:
            raise ValidationError(
                ErrorCode.E20602,
                f"Invalid sandbox tier in manifest: {tier_raw!r}",
            ) from exc
        return cls(
            plugin_id=str(d["plugin_id"]),
            version=str(d.get("version", "0.0.0")),
            entry_point=str(d.get("entry_point", "")),
            display_name=str(d.get("display_name", d.get("plugin_id", ""))),
            description=str(d.get("description", "")),
            authors=list(d.get("authors", [])),
            capabilities=list(d.get("capabilities", [])),
            requires_service_ids=list(d.get("requires_service_ids", [])),
            security_boundary=tier,
            feature_flags=dict(d.get("feature_flags", {})),
            integrity_sha256=d.get("integrity_sha256"),
        )


class _PluginStub:
    """Prompt 02: plugins are not actually loaded; we keep a stub so the runtime can report them."""

    def __init__(self, manifest: PluginManifest) -> None:
        self.manifest = manifest
        self.loaded = False
        self.instance: Any = None


class PluginLoader:
    """Prompt 02 plugin loader stub.

    - register_stub(manifest): in-memory only, for test/example usage.
    - scan_directory(path): reads plugin manifests ONLY; does NOT load/execute any code.
    - load(plugin_id): NO-OP until Prompt 10+.
    """

    def __init__(self, *, plugin_paths: list[str | Path] | None = None) -> None:
        self._paths = [Path(p) for p in plugin_paths or []]
        self._plugins: dict[str, _PluginStub] = {}
        self._lock = threading.RLock()
        self._initialized = False

    async def initialize(self) -> None:
        with self._lock:
            for p in self._paths:
                try:
                    self.scan_directory(p)
                except Exception as exc:  # noqa: BLE001
                    raise InitializationError(
                        ErrorCode.E20601,
                        f"Failed to scan plugin path {p}: {exc}",
                    ) from exc
            self._initialized = True

    def scan_directory(self, path: str | Path) -> list[PluginManifest]:
        """Read every plugin.json under path/. Returns discovered manifests."""
        path = Path(path)
        discovered: list[PluginManifest] = []
        if not path.exists():
            return discovered
        for manifest_path in path.rglob("plugin.json"):
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest = PluginManifest.from_dict(data)
                discovered.append(manifest)
                with self._lock:
                    if manifest.plugin_id not in self._plugins:
                        self._plugins[manifest.plugin_id] = _PluginStub(manifest)
            except Exception as exc:  # noqa: BLE001
                log.warning("plugin manifest skipped", path=str(manifest_path), error=str(exc))
        return discovered

    def register_stub(self, manifest: PluginManifest) -> None:
        with self._lock:
            self._plugins[manifest.plugin_id] = _PluginStub(manifest)

    def list_plugins(self) -> list[PluginManifest]:
        with self._lock:
            return [s.manifest for s in self._plugins.values()]

    def get(self, plugin_id: str) -> PluginManifest:
        with self._lock:
            stub = self._plugins.get(plugin_id)
        if stub is None:
            raise NotFoundError(ErrorCode.E20604, f"No such plugin: {plugin_id!r}")
        return stub.manifest

    # ---------------------------------------------------------------
    # FUTURE hooks — Prompt 10+ only. Keep as explicit no-op for now.
    # ---------------------------------------------------------------
    async def load(self, plugin_id: str) -> bool:
        with self._lock:
            stub = self._plugins.get(plugin_id)
        if stub is None:
            raise NotFoundError(ErrorCode.E20604, f"No such plugin: {plugin_id!r}")
        log.debug("Plugin loading deferred to Prompt 10+", plugin_id=plugin_id)
        stub.loaded = True  # Mark as "acknowledged load" for status reporting; NO code loaded
        return True

    async def unload(self, plugin_id: str) -> None:
        with self._lock:
            stub = self._plugins.get(plugin_id)
        if stub is None:
            return
        stub.loaded = False
