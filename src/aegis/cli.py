"""Prompt 02: minimal CLI skeleton only.
Full Typer-based CLI ships in later prompts; here we only expose info."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aegis import __version__


@dataclass(frozen=True)
class _Sentinel:
    """Sentinel placeholder to avoid heavy CLI dependency (Typer) in Prompt 02."""


def _app_entry(_args: list[str] | None = None) -> int:  # pragma: no cover - placeholder
    print(f"AEGIS Core Runtime v{__version__}")
    return 0


class _CliCompat:
    """Prompt 02 shim — keeps __init__ exports honest without pulling Typer early."""

    def __call__(self, *_args: Any, **_kwargs: Any) -> int:  # pragma: no cover - trivial
        return _app_entry()


app = _CliCompat()
