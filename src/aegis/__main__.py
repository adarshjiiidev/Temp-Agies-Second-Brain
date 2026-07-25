"""Entry point: `python -m aegis`.
In Prompt 02 this only exposes a runtime info + example selector.
Full CLI ships in later prompts via aegis.cli."""
from __future__ import annotations

from aegis import __version__


def main() -> int:
    print(f"AEGIS Core Runtime v{__version__}")
    print("Prompt 02: `python examples/runtime_lifecycle.py` to run the demonstration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
