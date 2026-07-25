"""Prompt 02 tests: Config layered loading, validation, immutability, env overrides, secrets refs."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

import aegis
from aegis import ConfigLoader, ValidationError, secret_ref


def test_default_config_has_required_fields():
    snap = ConfigLoader().build()
    assert snap.schema_version >= 1
    assert snap.aegis["instance_id"] is not None
    assert snap.paths["data_dir"] is not None
    assert snap.log_level().name in ("INFO", "DEBUG", "WARNING", "ERROR")
    # Logging format default from _DEFAULT_CONFIG
    assert snap.logging["format"] == "development"


def test_file_config_overrides_defaults(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AEGIS_DATA_DIR", str(tmp_path))
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        """
aegis:
  instance_id: "fixture-instance-1"
logging:
  level: ERROR
  format: json
""",
        encoding="utf-8",
    )
    snap = ConfigLoader(file_path=cfg).build()
    assert snap.aegis["instance_id"] == "fixture-instance-1"
    assert snap.logging["format"] == "json"
    assert snap.log_level().name == "ERROR"


def test_env_overrides_file(tmp_path: Path, monkeypatch):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("logging:\n  level: WARNING\n", encoding="utf-8")
    monkeypatch.setenv("AEGIS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AEGIS_LOGGING__LEVEL", "DEBUG")
    snap = ConfigLoader(file_path=cfg).build()
    assert snap.log_level().name == "DEBUG"


def test_invalid_logging_format_rejected(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AEGIS_DATA_DIR", str(tmp_path))
    loader = ConfigLoader()
    loader.set_runtime_override("logging.format", "garbage")
    with pytest.raises(ValidationError):
        loader.build()


def test_snapshot_is_immutable_via_accessors(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AEGIS_DATA_DIR", str(tmp_path))
    snap = ConfigLoader().build()
    flags = snap.feature_flags
    # Mutate the returned dict; ensure the snapshot copy is unaffected
    flags_again = snap.feature_flags
    assert flags is not flags_again  # deep copies
    logging = snap.logging
    logging["level"] = "CRITICAL"
    assert snap.logging["level"] != "CRITICAL"


def test_runtime_override_applied(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AEGIS_DATA_DIR", str(tmp_path))
    loader = ConfigLoader()
    loader.set_runtime_override("aegis.instance_id", "override-id")
    snap = loader.build()
    assert snap.aegis["instance_id"] == "override-id"


def test_secret_ref_not_inlined_in_loggable_dict(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AEGIS_DATA_DIR", str(tmp_path))
    loader = ConfigLoader()
    # Place a secret ref directly inside a runtime override; the safe serialization must redact it
    loader.set_runtime_override("extra_secrets.provider.api_key", secret_ref("providers", "x"))
    snap = loader.build()
    safe = snap.as_dict_safe()
    raw = snap.as_dict_raw()
    assert "SECRET_REF" in str(safe)
    assert "<SECRET_REF>" in str(safe)


def test_secret_store_roundtrip_via_config(tmp_path: Path):
    # Create .env.aegis manually, then snapshot can resolve secret://file/x references
    data_dir = tmp_path
    (data_dir / ".env.aegis").write_text("file.my_api_key=abc123\n", encoding="utf-8")
    loader = ConfigLoader()
    loader.set_runtime_override("paths.data_dir", str(data_dir))
    snap = loader.build()
    assert snap.resolve_secret("file", "my_api_key") == "abc123"
    ref = "secret://file/my_api_key"
    assert snap.resolve(ref) == "abc123"
