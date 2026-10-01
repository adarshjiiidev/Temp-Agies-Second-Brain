"""L4 Memory — Markdown export and Obsidian adapter.

Implements the Prompt 04 Obsidian/Markdown layer per 06_MEMORY_KNOWLEDGE.md §6.

Prompt 04 scope (per 09_ROADMAP.md §PROMPT 04 + §PROMPT 11):
  - Full bidirectional Obsidian sync is a PROMPT 11 feature.
  - Prompt 04 delivers:
      * MarkdownExporter: render a MemoryRecord to Markdown with YAML frontmatter
      * ObsidianAdapter: import a vault note as a candidate MemoryRecord (T3 DRAFT)
      * Wikilink extraction from Markdown content
      * YAML frontmatter parse/write helpers

Obsidian sync, filesystem watcher, live vault integration — NOT implemented here.
Those ship in Prompt 11.

Import safety: l4_memory.* + stdlib ONLY.
"""

from __future__ import annotations

import re
import textwrap
import time
import uuid
from pathlib import Path
from typing import Any

from aegis.l4_memory.models import MemoryRecord, ProvenanceChain, ProvenanceLink
from aegis.l4_memory.types import (
    Importance,
    MemoryKind,
    MemoryStatus,
    MemoryTier,
    ProvenanceKind,
)

__all__ = ["MarkdownExporter", "ObsidianAdapter"]

# ---------------------------------------------------------------------------
# YAML frontmatter helpers
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_WIKILINK_RE = re.compile(r"\[\[([^\[\]|]+?)(?:\|([^\[\]]+?))?\]\]")


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Extract YAML frontmatter from markdown text.

    Returns (frontmatter_dict, body_without_frontmatter).
    Minimal parser — handles simple key: value pairs only.
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text

    fm_text = match.group(1)
    body = text[match.end():]
    fm: dict[str, Any] = {}

    for line in fm_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            # Handle list values: "- item" style on next lines is NOT supported
            # in this minimal parser. Inline lists: [a, b] → parse as list.
            if value.startswith("[") and value.endswith("]"):
                items = [v.strip().strip('"').strip("'") for v in value[1:-1].split(",")]
                fm[key] = [i for i in items if i]
            elif value in ("true", "True"):
                fm[key] = True
            elif value in ("false", "False"):
                fm[key] = False
            else:
                try:
                    fm[key] = int(value)
                except ValueError:
                    try:
                        fm[key] = float(value)
                    except ValueError:
                        fm[key] = value.strip('"').strip("'")

    return fm, body


def _write_frontmatter(fields: dict[str, Any]) -> str:
    """Serialize a dict to YAML frontmatter block."""
    lines = ["---"]
    for key, val in fields.items():
        if isinstance(val, list):
            lines.append(f"{key}: [{', '.join(str(v) for v in val)}]")
        elif isinstance(val, bool):
            lines.append(f"{key}: {'true' if val else 'false'}")
        elif isinstance(val, float):
            lines.append(f"{key}: {val:.4f}")
        else:
            lines.append(f"{key}: {val}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def extract_wikilinks(text: str) -> list[str]:
    """Extract all [[wikilink]] targets from markdown text."""
    matches = _WIKILINK_RE.findall(text)
    return [m[0].strip() for m in matches]


# ---------------------------------------------------------------------------
# MarkdownExporter
# ---------------------------------------------------------------------------


class MarkdownExporter:
    """Renders MemoryRecord objects to Obsidian-compatible Markdown files.

    Each rendered file has:
      - YAML frontmatter with aegis metadata (id, tier, privacy_tier, etc.)
      - A heading with record summary or content preview
      - Full content section
      - Provenance block
      - Tags list
    """

    def render(self, record: MemoryRecord) -> str:
        """Render a MemoryRecord as a Markdown string."""
        content_str = self._render_content(record.content)
        summary = record.summary or self._summarize(content_str)

        frontmatter = {
            "aegis_id": str(record.id),
            "aegis_tier": record.tier.value,
            "aegis_kind": record.kind if isinstance(record.kind, str) else record.kind.value,
            "aegis_status": record.status.value,
            "aegis_importance": record.importance.value,
            "aegis_privacy_tier": record.privacy_tier,
            "aegis_confidence": record.confidence,
            "aegis_is_draft": record.is_draft,
            "aegis_version": record.version,
            "aegis_namespace": record.namespace,
            "aegis_key": record.key,
            "aegis_created_at": record.created_at,
            "aegis_updated_at": record.updated_at,
        }

        if record.project_id:
            frontmatter["aegis_project_id"] = record.project_id
        if record.session_id:
            frontmatter["aegis_session_id"] = record.session_id
        if record.source:
            frontmatter["aegis_source"] = record.source
        if record.tags:
            frontmatter["tags"] = sorted(record.tags)

        fm_block = _write_frontmatter(frontmatter)

        tier_label = _TIER_LABELS.get(record.tier, record.tier.value)
        heading = f"# [{tier_label}] {summary}\n"

        content_section = f"\n## Content\n\n{content_str}\n"

        prov_section = self._render_provenance(record)

        return fm_block + "\n" + heading + content_section + prov_section

    def render_to_file(self, record: MemoryRecord, output_dir: Path) -> Path:
        """Render a MemoryRecord to a file in output_dir. Returns the file path."""
        output_dir.mkdir(parents=True, exist_ok=True)
        safe_key = re.sub(r"[^\w\-./]", "_", record.key)
        filename = f"{safe_key.replace('/', '__')}.md"
        path = output_dir / filename
        path.write_text(self.render(record), encoding="utf-8")
        return path

    def render_many(self, records: list[MemoryRecord]) -> dict[str, str]:
        """Render multiple records. Returns {record_key: markdown_string}."""
        return {rec.key: self.render(rec) for rec in records}

    # ------------------------------------------------------------------

    def _render_content(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, dict):
            lines = []
            for k, v in content.items():
                lines.append(f"**{k}**: {v}")
            return "\n".join(lines)
        if isinstance(content, list):
            return "\n".join(f"- {item}" for item in content)
        return str(content)

    def _summarize(self, text: str, max_len: int = 80) -> str:
        first_line = text.split("\n")[0].strip()
        if len(first_line) <= max_len:
            return first_line
        return first_line[:max_len] + "…"

    def _render_provenance(self, record: MemoryRecord) -> str:
        chain = record.provenance
        lines = ["\n## Provenance\n"]
        for i, link in enumerate(chain.links):
            subject = f"{link.subject}" if link.subject else "unknown"
            ts = f" @ {link.note}" if link.note else ""
            lines.append(f"{i + 1}. `{link.kind.value}` by **{subject}**{ts}")
        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# ObsidianAdapter
# ---------------------------------------------------------------------------


class ObsidianAdapter:
    """Reads Obsidian vault notes and imports them as candidate MemoryRecords.

    Prompt 04 scope:
      - Import a specific file as T3 Semantic DRAFT (provenance=FILE_DERIVED).
      - Scan a vault directory and import all .md files in a given path.
      - Extract wikilinks as candidate KG relationship targets.

    NOT in P04 scope:
      - Filesystem watcher (P11)
      - Bidirectional sync (P11)
      - Writing to vault on memory change (P11)
      - Conflict resolution (P11)
    """

    def __init__(
        self,
        *,
        vault_path: Path | str | None = None,
        default_namespace: str = "global",
        default_project_id: str | None = None,
    ) -> None:
        self._vault = Path(vault_path) if vault_path else None
        self._namespace = default_namespace
        self._project_id = default_project_id
        self._exporter = MarkdownExporter()

    def import_file(
        self,
        path: Path | str,
        *,
        tier: MemoryTier = MemoryTier.T3_SEMANTIC,
        privacy_tier: str = "P2",
        tags: frozenset[str] | None = None,
        project_id: str | None = None,
    ) -> tuple[MemoryRecord, list[str]]:
        """Import a single Markdown file as a candidate (DRAFT) MemoryRecord.

        Returns (record, wikilinks) where wikilinks are the extracted [[link]] targets
        as candidate KG relationship targets (caller must confirm these as edges).

        The record is always DRAFT=True (PENDING_REVIEW). No auto-promotion.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Vault file not found: {path}")

        raw_text = path.read_text(encoding="utf-8")
        fm, body = _parse_frontmatter(raw_text)

        # If this was previously exported by AEGIS, honor the stored aegis_id
        record_id: uuid.UUID = uuid.uuid4()
        if "aegis_id" in fm:
            try:
                record_id = uuid.UUID(str(fm["aegis_id"]))
            except ValueError:
                pass

        # Try to re-use stored tier if this came from AEGIS
        if "aegis_tier" in fm:
            try:
                tier = MemoryTier(fm["aegis_tier"])
            except ValueError:
                pass

        key = fm.get("aegis_key") or f"obsidian/{path.stem}"
        summary_text = fm.get("title") or path.stem

        file_tags: frozenset[str] = frozenset(fm.get("tags", []))
        if tags:
            file_tags = file_tags | tags

        now = time.time()
        provenance = ProvenanceChain(links=[
            ProvenanceLink(
                kind=ProvenanceKind.FILE_DERIVED,
                subject=str(path),
                note=f"Imported from Obsidian vault at {path}",
            )
        ])

        record = MemoryRecord(
            id=record_id,
            key=key,
            namespace=self._namespace,
            tier=tier,
            kind=MemoryKind.OBSERVATION,
            status=MemoryStatus.DRAFT,
            importance=Importance.NORMAL,
            privacy_tier=privacy_tier,
            confidence=0.6,  # file-derived; not yet corroborated
            is_draft=True,
            version=1,
            project_id=project_id or self._project_id or fm.get("aegis_project_id"),
            tags=file_tags,
            source=str(path),
            created_at=fm.get("aegis_created_at", now),
            updated_at=now,
            content={"text": body.strip(), "source_file": str(path)},
            summary=summary_text,
            provenance=provenance,
        )

        wikilinks = extract_wikilinks(body)
        return record, wikilinks

    def scan_vault_dir(
        self,
        *,
        subdir: str | None = None,
        tier: MemoryTier = MemoryTier.T3_SEMANTIC,
        privacy_tier: str = "P2",
        max_files: int = 200,
    ) -> list[tuple[MemoryRecord, list[str]]]:
        """Scan a vault directory (or subdirectory) and import all .md files.

        Returns list of (record, wikilinks) tuples. All records are DRAFT.

        IMPORTANT: This method is READ-ONLY. It does NOT modify any vault files.
        """
        base = self._vault
        if base is None:
            raise ValueError("ObsidianAdapter: vault_path must be set to scan.")

        scan_dir = base / subdir if subdir else base
        if not scan_dir.is_dir():
            raise NotADirectoryError(f"Vault directory not found: {scan_dir}")

        results: list[tuple[MemoryRecord, list[str]]] = []
        for md_file in sorted(scan_dir.rglob("*.md"))[:max_files]:
            try:
                rec, wikilinks = self.import_file(
                    md_file, tier=tier, privacy_tier=privacy_tier
                )
                results.append((rec, wikilinks))
            except Exception:
                # Skip unreadable files
                continue

        return results

    def export_record(self, record: MemoryRecord, vault_subpath: Path | str) -> Path:
        """Export a MemoryRecord to the vault. Returns the written file path.

        Only writes to the configured vault_path. Raises if no vault configured.
        """
        if self._vault is None:
            raise ValueError("ObsidianAdapter: vault_path must be set to export.")
        output_dir = self._vault / vault_subpath
        return self._exporter.render_to_file(record, output_dir)


# ---------------------------------------------------------------------------
# Tier label map
# ---------------------------------------------------------------------------

_TIER_LABELS = {
    MemoryTier.T0_WORKING:       "Working",
    MemoryTier.T1_SESSION:       "Session",
    MemoryTier.T2_EPISODIC:      "Episodic",
    MemoryTier.T3_SEMANTIC:      "Semantic",
    MemoryTier.T4_PROCEDURAL:    "Procedural",
    MemoryTier.T5_PERSONAL:      "Personal",
    MemoryTier.T6_ENVIRONMENTAL: "Environmental",
    MemoryTier.T7_PROJECT:       "Project",
    MemoryTier.T8_SKILL:         "Skill",
}
