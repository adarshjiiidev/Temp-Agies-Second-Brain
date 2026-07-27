"""L2 Configuration System.

Layered priority (low to high):
  DEFAULTS < FILE (.yaml/.json) < ENVIRONMENT (AEGIS_ prefix) < RUNTIME_OVERRIDES
Output: validated immutable ImmutableConfigSnapshot carrying schema_version, instance_id,
service-specific sections, feature_flags, and secret_ref wrappers. Secrets are NEVER
stored inline in the snapshot; they live only inside the (opaque) SecretVault adapter.

Prompt 02 scope: secrets stored via file:// references (`.env.aegis` inside data_dir) —
no HashiCorp Vault, no AWS KMS. External vault providers can be added later because
ConfigSnapshot only carries `secret://scope/key` references, never plaintext.
"""

from __future__ import annotations

import copy
import json
import os
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from aegis.l1_core.errors import (
    ConfigurationError,
    ErrorCode,
    NotFoundError,
    ValidationError,
)
from aegis.l2_foundation.crypto.redact import is_secret_ref
from aegis.l2_foundation.telemetry.logger import LogLevel, parse_level

# -------- Defaults (layer 0) ------------------------------------------------

_DEFAULT_CONFIG: dict[str, Any] = {
    "schema_version": 1,
    "aegis": {
        "instance_id": None,  # auto-generated at runtime if unset
        "version": "0.1.0",
        "shutdown_timeout_seconds": 10,
        "startup_timeout_seconds": 30,
        "service_stop_timeout_seconds": 5,
        "watchdog_interval_seconds": 0.5,
    },
    "paths": {
        "data_dir": None,  # resolved by Resolver to $AEGIS_DATA_DIR or ~/.aegis
        "config_dir": None,
        "log_dir": None,
        "cache_dir": None,
    },
    "logging": {
        "level": "INFO",
        "format": "development",  # development | json
        "file": None,
    },
    "event_bus": {
        "enabled": True,
        "persistence_path": None,  # relative to data_dir when set
        "durable": False,
        "dead_letter_enabled": True,
        "max_history": 100_000,
    },
    "health": {
        "enabled": True,
        "default_timeout_seconds": 1.0,
        "aggregate_timeout_seconds": 2.0,
    },
    "tasks": {
        "max_workers": 8,
        "default_retry_max_attempts": 3,
        "default_retry_base_backoff_seconds": 0.25,
        "default_retry_max_backoff_seconds": 10.0,
    },
    "recovery": {
        "default_max_attempts": 5,
        "default_reset_after_seconds": 60,
        "default_base_backoff_seconds": 0.25,
        "default_max_backoff_seconds": 10,
    },
    "feature_flags": {},
    "plugins": {"enabled": False, "path": None},
    "runtime_overrides": {},
}

_ENV_PREFIX = "AEGIS_"


# -------- Immutable Snapshot (validated, frozen via deepcopy) --------------


_DICT_FIELDS = frozenset(
    {
        "aegis",
        "paths",
        "logging",
        "event_bus",
        "health",
        "tasks",
        "recovery",
        "plugins",
        "feature_flags",
        "extra_sections",
    }
)


@dataclass(frozen=True)
class ImmutableConfigSnapshot:
    """Frozen, validated configuration. All lookups are deep-copied out to enforce immutability.
    Secrets (`secret://...`) are left in place; resolving them requires `self.resolve_secret`.
    """

    schema_version: int
    aegis: dict[str, Any]
    paths: dict[str, Any]
    logging: dict[str, Any]
    event_bus: dict[str, Any]
    health: dict[str, Any]
    tasks: dict[str, Any]
    recovery: dict[str, Any]
    plugins: dict[str, Any]
    feature_flags: dict[str, Any]
    extra_sections: dict[str, Any]
    # -------- private fields --------
    _resolved_defaults: dict[str, Any] = field(repr=False, compare=False)
    _secrets_store: dict[tuple[str, str], str] = field(
        default_factory=dict, repr=False, compare=False
    )

    def __getattribute__(self, name: str) -> Any:
        if name in _DICT_FIELDS:
            raw = object.__getattribute__(self, name)
            return copy.deepcopy(raw)
        return object.__getattribute__(self, name)

    # -------- public accessors --------

    def get(self, section: str, key: str | None = None, default: Any = None) -> Any:
        data = self.as_dict_raw()
        section_obj = data.get(section)
        if not key:
            return section_obj if section_obj is not None else default
        if isinstance(section_obj, dict):
            return copy.deepcopy(section_obj.get(key, default))
        return default

    def has_feature(self, flag: str) -> bool:
        return bool(self.feature_flags.get(flag))

    def feature(self, flag: str, default: Any = False) -> Any:
        return self.feature_flags.get(flag, default)

    def log_level(self) -> LogLevel:
        return parse_level(self.logging.get("level", "INFO"))

    def data_dir(self) -> Path:
        d = self.paths.get("data_dir")
        if not d:
            raise ConfigurationError(ErrorCode.E20102, "paths.data_dir is not configured")
        return Path(d)

    def resolve_secret(self, scope: str, identifier: str) -> str:
        """Resolve a `secret://scope/id` reference. Throws NotFoundError if missing."""
        key = (scope, identifier)
        if key not in self._secrets_store:
            raise NotFoundError(
                ErrorCode.E20501,
                f"Secret not found for scope={scope!r} id={identifier!r}",
            )
        return self._secrets_store[key]

    def resolve(self, ref_or_value: Any) -> Any:
        """If value is `secret://scope/id` returns the plaintext; else returns value unchanged."""
        if isinstance(ref_or_value, str) and is_secret_ref(ref_or_value):
            _, _, path = ref_or_value.partition("secret://")
            scope, _, identifier = path.partition("/")
            return self.resolve_secret(scope, identifier)
        return ref_or_value

    def as_dict_raw(self) -> dict[str, Any]:
        """Return a deep copy of the underlying configuration (secret_refs unresolved)."""
        merged: dict[str, Any] = dict(self._resolved_defaults)
        merged["schema_version"] = self.schema_version
        merged["aegis"] = dict(self.aegis)
        merged["paths"] = dict(self.paths)
        merged["logging"] = dict(self.logging)
        merged["event_bus"] = dict(self.event_bus)
        merged["health"] = dict(self.health)
        merged["tasks"] = dict(self.tasks)
        merged["recovery"] = dict(self.recovery)
        merged["plugins"] = dict(self.plugins)
        merged["feature_flags"] = dict(self.feature_flags)
        for k, v in self.extra_sections.items():
            merged[k] = copy.deepcopy(v)
        return merged

    # -------- Redacted serialization (safe for logs) --------

    def as_dict_safe(self) -> dict[str, Any]:
        def _walk(obj: Any) -> Any:
            if isinstance(obj, str) and is_secret_ref(obj):
                return "<SECRET_REF>"
            if isinstance(obj, dict):
                return {k: _walk(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_walk(v) for v in obj]
            if isinstance(obj, tuple):
                return tuple(_walk(v) for v in obj)
            return obj

        return _walk(self.as_dict_raw())


# -------- Secrets storage (Prompt 02 file-based) --------------------------


class _EnvAegisSecretsStore:
    """Prompt 02 secrets: file `$DATA_DIR/.env.aegis` with KEY=VALUE lines.
    Grouped under scope `file` by default. Keys inside the file named `scope.key=value`
    allow multiple scopes.
    """

    def __init__(self, path: Path | None) -> None:
        self._path = path
        self._lock = threading.RLock()
        self._loaded = False
        self._values: dict[tuple[str, str], str] = {}

    def load(self) -> dict[tuple[str, str], str]:
        with self._lock:
            if self._loaded:
                return dict(self._values)
            if self._path and self._path.exists():
                for raw in self._path.read_text(encoding="utf-8").splitlines():
                    line = raw.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    scope, _, rest = key.partition(".")
                    if rest:
                        self._values[(scope, rest)] = value
                    else:
                        self._values[("file", key)] = value
            self._loaded = True
            return dict(self._values)


# -------- Loader ---------------------------------------------------------


class ConfigLoader:
    """Layers: DEFAULTS → FILE → ENV → OVERRIDES. Validates. Produces ImmutableConfigSnapshot."""

    def __init__(
        self,
        *,
        defaults: dict[str, Any] | None = None,
        file_path: str | Path | None = None,
        env_prefix: str = _ENV_PREFIX,
    ) -> None:
        self._user_defaults = copy.deepcopy(defaults or {})
        self._file_path = Path(file_path) if file_path else None
        self._env_prefix = env_prefix
        self._runtime_overrides: dict[str, Any] = {}
        self._lock = threading.RLock()

    # -------- override management --------

    def set_runtime_override(self, dotted_path: str, value: Any) -> None:
        """Set runtime override. Accepts dotted paths like `logging.level`."""
        with self._lock:
            parts = dotted_path.split(".")
            cur = self._runtime_overrides
            for part in parts[:-1]:
                cur = cur.setdefault(part, {})
                if not isinstance(cur, dict):
                    raise ConfigurationError(
                        ErrorCode.E20103,
                        f"Cannot set {dotted_path!r}: parent is not a section",
                    )
            cur[parts[-1]] = value

    def clear_runtime_overrides(self) -> None:
        with self._lock:
            self._runtime_overrides = {}

    # -------- merge logic --------

    def _merge(self, base: dict, layer: dict) -> dict:
        out = dict(base)
        for k, v in (layer or {}).items():
            if k in out and isinstance(out[k], dict) and isinstance(v, dict):
                out[k] = self._merge(out[k], v)
            else:
                out[k] = copy.deepcopy(v)
        return out

    def _resolve_paths(self, merged: dict[str, Any]) -> None:
        paths = merged["paths"]
        # data_dir resolution: override → env → ~/.aegis
        data_dir = paths.get("data_dir") or os.environ.get(f"{self._env_prefix}DATA_DIR")
        if not data_dir:
            data_dir = str(Path.home() / ".aegis")
        paths["data_dir"] = str(Path(data_dir).expanduser().resolve())
        data_path = Path(paths["data_dir"])
        if not paths.get("config_dir"):
            paths["config_dir"] = str(data_path / "config")
        if not paths.get("log_dir"):
            paths["log_dir"] = str(data_path / "logs")
        if not paths.get("cache_dir"):
            paths["cache_dir"] = str(data_path / "cache")
        for key in ("config_dir", "log_dir", "cache_dir"):
            paths[key] = str(Path(paths[key]).expanduser().resolve())
        # instance id
        if not merged["aegis"].get("instance_id"):
            merged["aegis"]["instance_id"] = f"aegis-{uuid.uuid4().hex[:12]}"
        # event_bus persistence path default
        eb = merged.get("event_bus", {})
        if eb.get("durable") and not eb.get("persistence_path"):
            eb["persistence_path"] = str(data_path / "event_bus.db")
        # logging.file default
        logcfg = merged.get("logging", {})
        if logcfg.get("file") and not Path(logcfg["file"]).is_absolute():
            logcfg["file"] = str(Path(paths["log_dir"]) / logcfg["file"])

    def _load_file_layer(self) -> dict[str, Any]:
        """Load YAML/JSON from configured path, plus config_dir/config.yaml if it exists."""
        result: dict[str, Any] = {}
        candidates: list[Path] = []
        if self._file_path:
            candidates.append(self._file_path)
        if not candidates:
            # Fallback: standard locations if they exist
            for candidate in (
                Path.cwd() / "config.yaml",
                Path.cwd() / "config.yml",
                Path.cwd() / "config.json",
                Path.cwd() / "examples" / "config.example.yaml",
            ):
                if candidate.exists():
                    candidates.append(candidate)
                    break
        for path in candidates:
            if not path.exists():
                continue
            suffix = path.suffix.lower()
            text = path.read_text(encoding="utf-8")
            if suffix in (".yaml", ".yml"):
                data = yaml.safe_load(text) or {}
            elif suffix == ".json":
                data = json.loads(text)
            else:
                raise ConfigurationError(
                    ErrorCode.E20101,
                    f"Unsupported config file suffix {suffix!r}: {path}",
                )
            if not isinstance(data, dict):
                raise ValidationError(
                    ErrorCode.E20104,
                    f"Config file {path} does not contain a top-level mapping",
                )
            result = self._merge(result, data)
        return result

    def _load_env_layer(self) -> dict[str, Any]:
        """AEGIS_LOGGING__LEVEL=INFO → logging.level='INFO'. Double underscore splits sections."""
        out: dict[str, Any] = {}
        for key, value in os.environ.items():
            if not key.startswith(self._env_prefix):
                continue
            rest = key[len(self._env_prefix) :]
            parts = rest.lower().split("__")
            if not parts or any(not p for p in parts):
                continue
            # Decode obvious primitives
            decoded: Any = value
            if value.lower() in ("true", "false"):
                decoded = value.lower() == "true"
            else:
                try:
                    if "." in value:
                        decoded = float(value)
                    else:
                        decoded = int(value)
                except ValueError:
                    decoded = value
            cur = out
            for part in parts[:-1]:
                cur = cur.setdefault(part, {})
            cur[parts[-1]] = decoded
        return out

    # -------- validation gates ------------------------------------------------

    @staticmethod
    def _validate(merged: dict[str, Any]) -> None:
        # schema_version is a number and ≥1
        sv = merged.get("schema_version")
        if not isinstance(sv, int) or sv < 1:
            raise ValidationError(ErrorCode.E20104, f"Invalid schema_version: {sv!r}")
        # paths.data_dir present (already set by _resolve_paths)
        if not merged.get("paths", {}).get("data_dir"):
            raise ValidationError(ErrorCode.E20104, "paths.data_dir required")
        # log level
        ll = merged.get("logging", {}).get("level")
        try:
            parse_level(ll)
        except Exception as exc:
            raise ValidationError(ErrorCode.E20104, f"logging.level invalid: {ll!r}") from exc
        fmt = merged.get("logging", {}).get("format")
        if fmt not in ("development", "json"):
            raise ValidationError(ErrorCode.E20104, f"logging.format invalid: {fmt!r}")
        # timeout sanity
        for key, section in (
            ("aegis.shutdown_timeout_seconds", merged["aegis"]),
            ("aegis.startup_timeout_seconds", merged["aegis"]),
        ):
            val = section.get(key.split(".")[-1])
            if val is not None and (not isinstance(val, (int, float)) or val <= 0):
                raise ValidationError(ErrorCode.E20104, f"{key} must be a positive number")

    # -------- top-level: build snapshot ---------------------------------------

    def build(
        self,
        *,
        runtime_overrides: dict[str, Any] | None = None,
    ) -> ImmutableConfigSnapshot:
        with self._lock:
            merged = copy.deepcopy(_DEFAULT_CONFIG)
            if self._user_defaults:
                merged = self._merge(merged, self._user_defaults)
            merged = self._merge(merged, self._load_file_layer())
            merged = self._merge(merged, self._load_env_layer())
            if runtime_overrides:
                merged = self._merge(merged, runtime_overrides)
            if self._runtime_overrides:
                merged = self._merge(merged, self._runtime_overrides)
            self._resolve_paths(merged)
            self._validate(merged)

            # Resolve secrets store: data_dir/.env.aegis
            data_path = Path(merged["paths"]["data_dir"])
            data_path.mkdir(parents=True, exist_ok=True)
            for sub in ("config", "logs", "cache"):
                (data_path / sub).mkdir(parents=True, exist_ok=True)
            secrets_store = _EnvAegisSecretsStore(data_path / ".env.aegis")
            secrets = secrets_store.load()

        return ImmutableConfigSnapshot(
            schema_version=merged["schema_version"],
            aegis=copy.deepcopy(merged["aegis"]),
            paths=copy.deepcopy(merged["paths"]),
            logging=copy.deepcopy(merged["logging"]),
            event_bus=copy.deepcopy(merged["event_bus"]),
            health=copy.deepcopy(merged["health"]),
            tasks=copy.deepcopy(merged["tasks"]),
            recovery=copy.deepcopy(merged["recovery"]),
            plugins=copy.deepcopy(merged["plugins"]),
            feature_flags=copy.deepcopy(merged.get("feature_flags", {})),
            extra_sections={
                k: copy.deepcopy(v)
                for k, v in merged.items()
                if k
                not in {
                    "schema_version",
                    "aegis",
                    "paths",
                    "logging",
                    "event_bus",
                    "health",
                    "tasks",
                    "recovery",
                    "plugins",
                    "feature_flags",
                    "runtime_overrides",
                }
            },
            _resolved_defaults=copy.deepcopy(merged),
            _secrets_store=secrets,
        )


# Module-level convenience
def load_config(
    file_path: str | Path | None = None,
    *,
    runtime_overrides: dict[str, Any] | None = None,
) -> ImmutableConfigSnapshot:
    return ConfigLoader(file_path=file_path).build(runtime_overrides=runtime_overrides)
