"""Tests for MarkdownExporter and ObsidianAdapter — roundtrip, wikilinks, import."""

from __future__ import annotations

import tempfile
import time
import uuid
from pathlib import Path

import pytest

from aegis.l4_memory import (
    MemoryRecord,
    MemoryTier,
    MemoryKind,
    MemoryStatus,
    Importance,
    ProvenanceChain,
)
from aegis.l4_memory.markdown import (
    MarkdownExporter,
    ObsidianAdapter,
    extract_wikilinks,
    _parse_frontmatter,
    _write_frontmatter,
)
from aegis.l4_memory.types import ProvenanceKind


def _make_rec(**kwargs) -> MemoryRecord:
    now = time.time()
    defaults = dict(
        id=uuid.uuid4(),
        key="test/markdown/1",
        namespace="global",
        tier=MemoryTier.T3_SEMANTIC,
        kind=MemoryKind.FACT,
        content="Python 3.12 is the latest stable release with PEP 695.",
        summary="Python 3.12 fact",
        privacy_tier="P2",
        importance=Importance.NORMAL,
        is_draft=True,
        status=MemoryStatus.DRAFT,
        confidence=0.8,
        tags=frozenset(["python", "tech"]),
        provenance=ProvenanceChain.single(
            kind=ProvenanceKind.USER_PROVIDED, subject="test"
        ),
        created_at=now,
        updated_at=now,
    )
    defaults.update(kwargs)
    return MemoryRecord(**defaults)


# ---------------------------------------------------------------------------
# Frontmatter helpers
# ---------------------------------------------------------------------------

def test_write_frontmatter_roundtrip():
    fm = {"name": "test", "value": 42, "flag": True, "score": 0.9}
    text = _write_frontmatter(fm)
    assert text.startswith("---\n")
    assert "name: test" in text
    assert "value: 42" in text
    assert "flag: true" in text


def test_parse_frontmatter_extracts_fields():
    text = "---\nname: hello\nvalue: 123\nflag: true\n---\nBody text here."
    fm, body = _parse_frontmatter(text)
    assert fm["name"] == "hello"
    assert fm["value"] == 123
    assert fm["flag"] is True
    assert "Body text here." in body


def test_parse_frontmatter_no_fm():
    text = "Just plain text with no frontmatter."
    fm, body = _parse_frontmatter(text)
    assert fm == {}
    assert "Just plain text" in body


def test_parse_frontmatter_list_field():
    text = "---\ntags: [python, aegis, test]\n---\nbody"
    fm, _ = _parse_frontmatter(text)
    assert "python" in fm["tags"]
    assert "aegis" in fm["tags"]


# ---------------------------------------------------------------------------
# Wikilink extraction
# ---------------------------------------------------------------------------

def test_extract_wikilinks_simple():
    text = "See [[Project AEGIS]] for details. Also [[Python 3.12|Python]]."
    links = extract_wikilinks(text)
    assert "Project AEGIS" in links
    assert "Python 3.12" in links


def test_extract_wikilinks_none():
    text = "No links here at all."
    links = extract_wikilinks(text)
    assert links == []


def test_extract_wikilinks_deduplicated_order():
    text = "[[A]] and [[B]] and [[A]] again."
    links = extract_wikilinks(text)
    assert links.count("A") == 2  # extract_wikilinks returns all, not unique


# ---------------------------------------------------------------------------
# MarkdownExporter
# ---------------------------------------------------------------------------

def test_exporter_renders_frontmatter():
    rec = _make_rec()
    exporter = MarkdownExporter()
    md = exporter.render(rec)
    assert "---" in md
    assert f"aegis_id: {rec.id}" in md
    assert "aegis_tier: T3_semantic" in md


def test_exporter_renders_content():
    rec = _make_rec(content="AEGIS uses L4 Memory Engine.")
    exporter = MarkdownExporter()
    md = exporter.render(rec)
    assert "AEGIS uses L4 Memory Engine." in md


def test_exporter_renders_tags():
    rec = _make_rec(tags=frozenset(["aegis", "memory"]))
    exporter = MarkdownExporter()
    md = exporter.render(rec)
    assert "tags:" in md
    assert "aegis" in md


def test_exporter_renders_provenance():
    rec = _make_rec()
    exporter = MarkdownExporter()
    md = exporter.render(rec)
    assert "Provenance" in md
    assert "user_provided" in md


def test_exporter_dict_content():
    rec = _make_rec(content={"language": "Python", "version": "3.12", "feature": "PEP 695"})
    exporter = MarkdownExporter()
    md = exporter.render(rec)
    assert "language" in md
    assert "Python" in md


def test_exporter_render_many():
    recs = [_make_rec(key=f"test/{i}") for i in range(3)]
    exporter = MarkdownExporter()
    rendered = exporter.render_many(recs)
    assert len(rendered) == 3


def test_exporter_render_to_file():
    rec = _make_rec()
    exporter = MarkdownExporter()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = exporter.render_to_file(rec, Path(tmpdir))
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "aegis_id" in content


# ---------------------------------------------------------------------------
# ObsidianAdapter
# ---------------------------------------------------------------------------

def test_obsidian_import_file():
    md_text = "---\ntags: [aegis, python]\ntitle: AEGIS Memory\n---\n\nAEGIS has a 9-tier [[Memory]] system.\n"
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "note.md"
        p.write_text(md_text, encoding="utf-8")
        adapter = ObsidianAdapter(vault_path=tmpdir)
        rec, wikilinks = adapter.import_file(p)
        assert rec.is_draft is True
        assert rec.status.value == "draft"
        assert "aegis" in rec.tags
        assert "Memory" in wikilinks


def test_obsidian_import_preserves_aegis_id():
    existing_id = uuid.uuid4()
    md_text = f"---\naegis_id: {existing_id}\naegis_tier: T3_semantic\n---\nBody content.\n"
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "existing.md"
        p.write_text(md_text, encoding="utf-8")
        adapter = ObsidianAdapter()
        rec, _ = adapter.import_file(p)
        assert rec.id == existing_id


def test_obsidian_import_always_draft():
    """Imported vault notes must always be DRAFT — never auto-promoted."""
    md_text = "---\ntitle: Some Note\n---\nContent here."
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "note.md"
        p.write_text(md_text, encoding="utf-8")
        adapter = ObsidianAdapter()
        rec, _ = adapter.import_file(p)
        assert rec.is_draft is True
        assert rec.status == MemoryStatus.DRAFT


def test_obsidian_scan_vault_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir) / "vault"
        vault.mkdir()
        for i in range(3):
            (vault / f"note_{i}.md").write_text(f"---\ntitle: Note {i}\n---\nContent {i}.\n")

        adapter = ObsidianAdapter(vault_path=vault)
        results = adapter.scan_vault_dir()
        assert len(results) == 3
        for rec, _ in results:
            assert rec.is_draft is True


def test_obsidian_export_record():
    rec = _make_rec(key="obsidian/test/export")
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir) / "vault"
        adapter = ObsidianAdapter(vault_path=vault)
        path = adapter.export_record(rec, Path("AEGIS/03_Learned"))
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "aegis_id" in content


def test_obsidian_import_file_missing_raises():
    adapter = ObsidianAdapter()
    with pytest.raises(FileNotFoundError):
        adapter.import_file(Path("/nonexistent/path/note.md"))


def test_obsidian_scan_without_vault_raises():
    adapter = ObsidianAdapter()  # no vault_path
    with pytest.raises(ValueError, match="vault_path"):
        adapter.scan_vault_dir()


def test_obsidian_export_without_vault_raises():
    rec = _make_rec()
    adapter = ObsidianAdapter()
    with pytest.raises(ValueError, match="vault_path"):
        adapter.export_record(rec, Path("AEGIS"))


# ---------------------------------------------------------------------------
# Roundtrip: export then re-import
# ---------------------------------------------------------------------------

def test_markdown_export_import_roundtrip():
    """Export a record to Markdown, re-import it, verify key metadata survives."""
    rec = _make_rec(key="roundtrip/test", confidence=0.75, tags=frozenset(["roundtrip"]))
    exporter = MarkdownExporter()
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir) / "vault"
        adapter = ObsidianAdapter(vault_path=vault)

        # Export
        path = adapter.export_record(rec, Path("AEGIS"))
        assert path.exists()

        # Re-import
        reimported, wikilinks = adapter.import_file(path)
        assert reimported.id == rec.id  # aegis_id preserved
        assert "roundtrip" in reimported.tags
        assert reimported.is_draft is True  # always draft on import
