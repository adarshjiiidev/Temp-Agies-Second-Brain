from __future__ import annotations

import os
import sys
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

# Make src/ path always on sys.path for editable installs
REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


@pytest.fixture()
def temp_data_dir() -> Generator[Path, None, None]:
    """Create a temporary data directory for an AEGIS runtime tests; clean up after.
    Tests must NOT use real user home directory or real ~/.aegis"""
    with tempfile.TemporaryDirectory(prefix="aegis_test_") as td:
        yield Path(td)


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch, temp_data_dir: Path) -> None:
    """Isolate tests from real environment variables and real AEGIS home directory."""
    # Remove any production AEGIS_ env vars that could interfere
    for k in list(os.environ.keys()):
        if k.startswith("AEGIS_"):
            monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("AEGIS_DATA_DIR", str(temp_data_dir))
