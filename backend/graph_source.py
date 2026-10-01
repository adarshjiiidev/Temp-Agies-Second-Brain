#!/usr/bin/env python3
"""
System graph source: the Obsidian vault, not this repository.

Topology (nodes, labels, wiring) is read from agent-written notes under

    <vault>/agies/system/nodes/*.md      one note per capability
    <vault>/agies/system/AEGIS_SYSTEM_GRAPH.md   the index / format contract

A node note owns its identity and its wiring; it never owns a status:

    ---
    aegis_node: true
    node_id: model_router
    label: Model Fabric
    node_type: core            # core|memory|capability|skill|executor|ide|daemon|service
    probe: model_fabric        # measurement key in backend/status_probes.py
    source: backend/free_router.py
    show_in_graph: true        # optional; false hides service rows from the graph
    ---
    Free multi-provider routing pool.

    ## Wiring
    - [[Planner]]|routes-for
    - [[Memory (mem0)]]

Edges come from the `## Wiring` wikilinks (optional `|relation` suffix). Status
values are joined later by status_probes, so an agent editing a note can change
what the dashboard shows while being unable to make anything claim it works.

This module only parses and validates. It reports structural problems rather
than papering over them, and it never invents a node.
"""

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.config import cfg

try:  # PyYAML exists in the backend venv; degrade to flat parsing elsewhere.
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None

NODE_TYPE_KEY = "node_type"
REQUIRED_FIELDS = ("node_id", "label", NODE_TYPE_KEY)
WIRING_HEADING = re.compile(r"^#{1,6}\s*Wiring\s*$", re.I)
WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]")
LIST_ITEM = re.compile(r"^\s*[-*+]\s+(.*)$")


class TopologyError(RuntimeError):
    """The vault topology could not be read or is structurally invalid."""


def nodes_dir() -> Path:
    override = os.environ.get("AEGIS_GRAPH_NODES_DIR")
    return Path(override) if override else cfg.AGIES_VAULT / "system" / "nodes"


def index_note() -> Path:
    return nodes_dir().parent / "AEGIS_SYSTEM_GRAPH.md"


def _parse_frontmatter(text: str) -> Tuple[Dict[str, Any], str]:
    """Return (frontmatter, body). Unparseable frontmatter raises, never defaults."""
    if not text.startswith("---"):
        raise TopologyError("note has no YAML frontmatter block")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise TopologyError("frontmatter block is not closed")
    raw, body = parts[1], parts[2]
    if yaml is not None:
        data = yaml.safe_load(raw)
        if not isinstance(data, dict):
            raise TopologyError("frontmatter is not a mapping")
        return data, body
    data = {}
    for line in raw.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if ":" not in line:
            raise TopologyError(f"unparseable frontmatter line: {line!r}")
        key, _, val = line.partition(":")
        val = val.strip().strip('"').strip("'")
        if val.lower() in ("true", "false"):
            data[key.strip()] = val.lower() == "true"
        else:
            data[key.strip()] = val
    return data, body


def _extract_wiring(body: str) -> List[Tuple[str, str]]:
    """Collect (wikilink_target, relation) pairs from the Wiring section only."""
    lines = body.splitlines()
    start = next((i for i, l in enumerate(lines) if WIRING_HEADING.match(l.strip())), None)
    if start is None:
        return []
    pairs: List[Tuple[str, str]] = []
    for line in lines[start + 1:]:
        if line.strip().startswith("#"):  # next section ends Wiring
            break
        item = LIST_ITEM.match(line)
        target_line = item.group(1) if item else line
        if not target_line.strip():
            continue
        for m in WIKILINK.finditer(target_line):
            target = m.group(1).strip()
            relation = (m.group(2) or "").strip()
            # `- [[Target]]|relation` is also accepted (relation after the link)
            if not relation and item:
                tail = item.group(1).split("]]", 1)[-1].strip()
                if tail.startswith("|"):
                    relation = tail[1:].strip()
            if target:
                pairs.append((target, relation))
    return pairs
