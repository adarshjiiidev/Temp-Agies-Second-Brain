"""Prompt Library — Registry.

Discovers, loads, and caches versioned YAML prompt templates from the
``library/`` subdirectory.  Acts as the single source of truth for all
prompt content in AEGIS.

Usage::

    library = PromptLibrary()  # auto-discovers library/ directory
    template = library.get("intent_analysis_v1")
    rendered = template.render({"goal_text": "Build a web app", "schema": "..."})

Import safety: stdlib + pydantic + aegis.prompts.types only.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Iterator

from aegis.prompts.types import PromptMetadata, PromptTemplate

logger = logging.getLogger(__name__)

__all__ = ["PromptLibrary", "PromptNotFoundError"]

# Default location: the ``library/`` directory next to this file
_DEFAULT_LIBRARY_DIR = Path(__file__).parent / "library"


class PromptNotFoundError(KeyError):
    """Raised when a prompt ID is not in the library."""


class PromptLibrary:
    """Registry of versioned prompt templates.

    Templates are loaded lazily on first access and cached in memory.
    Hot-reloading is supported via ``reload()``.

    The registry supports multiple versions of the same logical prompt.
    ``get(id)`` returns the latest non-deprecated version.
    ``get(id, version="1.0.0")`` returns a specific version.
    """

    def __init__(self, library_dir: Path | str | None = None) -> None:
        """
        Args:
            library_dir: Path to the YAML template directory.
                         Defaults to ``prompts/library/``.
        """
        self._dir = Path(library_dir) if library_dir else _DEFAULT_LIBRARY_DIR
        self._cache: dict[str, PromptTemplate] = {}   # key = "id::version"
        self._loaded = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, prompt_id: str, version: str | None = None) -> PromptTemplate:
        """Return the prompt template for ``prompt_id``.

        Args:
            prompt_id: The ``id`` field from the YAML front-matter.
            version:   Optional semantic version string. If omitted, the
                       latest non-deprecated version is returned.

        Raises:
            PromptNotFoundError: No template matches the id/version.
        """
        self._ensure_loaded()

        if version is not None:
            key = f"{prompt_id}::{version}"
            if key not in self._cache:
                raise PromptNotFoundError(
                    f"Prompt {prompt_id!r} version {version!r} not found. "
                    f"Available: {self._available_versions(prompt_id)}"
                )
            return self._cache[key]

        # Return latest non-deprecated
        candidates = [
            t for k, t in self._cache.items()
            if k.startswith(f"{prompt_id}::") and not t.metadata.deprecated
        ]
        if not candidates:
            raise PromptNotFoundError(
                f"Prompt {prompt_id!r} not found. "
                f"Available IDs: {sorted(self.ids())}"
            )
        # Sort by version string (semver-ish)
        candidates.sort(key=lambda t: t.metadata.version, reverse=True)
        return candidates[0]

    def ids(self) -> list[str]:
        """Return all unique prompt IDs in the library."""
        self._ensure_loaded()
        seen: set[str] = set()
        result = []
        for key in self._cache:
            pid = key.split("::")[0]
            if pid not in seen:
                seen.add(pid)
                result.append(pid)
        return sorted(result)

    def reload(self) -> int:
        """Force-reload all templates from disk. Returns count loaded."""
        self._cache.clear()
        self._loaded = False
        self._ensure_loaded()
        return len(self._cache)

    def __iter__(self) -> Iterator[PromptTemplate]:
        self._ensure_loaded()
        yield from self._cache.values()

    def __len__(self) -> int:
        self._ensure_loaded()
        return len(self._cache)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if not self._dir.exists():
            logger.warning(
                "PromptLibrary: directory %s does not exist. No templates loaded.",
                self._dir,
            )
            self._loaded = True
            return
        count = 0
        for path in sorted(self._dir.glob("*.yaml")):
            try:
                template = _load_yaml_template(path)
                key = f"{template.metadata.id}::{template.metadata.version}"
                self._cache[key] = template
                count += 1
            except Exception as exc:
                logger.error("PromptLibrary: failed to load %s: %s", path, exc)
        self._loaded = True
        logger.debug("PromptLibrary: loaded %d templates from %s", count, self._dir)

    def _available_versions(self, prompt_id: str) -> list[str]:
        return [
            k.split("::")[1]
            for k in self._cache
            if k.startswith(f"{prompt_id}::")
        ]


# ---------------------------------------------------------------------------
# YAML loader
# ---------------------------------------------------------------------------

def _load_yaml_template(path: Path) -> PromptTemplate:
    """Load a single YAML prompt template file."""
    try:
        import yaml  # optional dependency; only needed for production use
    except ImportError as exc:
        raise ImportError(
            "PyYAML is required to load prompt templates. "
            "Install it: pip install pyyaml"
        ) from exc

    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    metadata_data = {k: v for k, v in data.items() if k != "template"}
    template_text = data.get("template", "")

    metadata = PromptMetadata(**metadata_data)
    return PromptTemplate(metadata=metadata, template=template_text)
