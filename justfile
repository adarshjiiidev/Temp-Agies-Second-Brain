# Project AEGIS — Task Runner (justfile syntax)
# ================================================================

set shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]

python := "python"
uv := if os_env("UV", "uv")
pytest := python + " -m pytest"
mypy   := python + " -m mypy"
ruff   := python + " -m ruff"

default:
    @echo "Project AEGIS — available tasks:"
    @echo "  install        Install dev + optional dev dependencies"
    @echo "  test         Run full test suite"
    @echo "  lint         Run ruff linter + formatter check"
    @echo "  typecheck    Run mypy --strict"
    @echo "  check        Run test + lint + typecheck"
    @echo "  example      Run minimal core runtime example"
    @echo "  clean        Remove caches + build artifacts"
    @echo "  format       Format code with ruff"

install:
    {{ python }} -m pip install -e ".[dev,crypto]"

test:
    {{ pytest }} tests/ src/aegis/ -x -q --cov=aegis --cov-report=term-missing --no-header

lint:
    {{ ruff }} check src/aegis/ tests/ examples/
    {{ ruff }} format --check src/aegis/ tests/ examples/

typecheck:
    {{ mypy }} src/aegis/

check: lint typecheck test

example:
    {{ python }} examples/runtime_lifecycle.py

format:
    {{ ruff }} check --fix src/aegis/ tests/ examples/
    {{ ruff }} format src/aegis/ tests/ examples/

clean:
    powershell -Command "Get-ChildItem -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue; Remove-Item -Recurse -Force -ErrorAction SilentlyContinue .pytest_cache, .mypy_cache, .ruff_cache, build, dist"
