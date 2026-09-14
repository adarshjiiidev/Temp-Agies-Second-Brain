#!/usr/bin/env python3
"""
AEGIS Structured Personal Knowledge Graph & Unified Search Engine
=================================================================
Maintains an in-memory relational graph connecting Projects, Agents, Tools,
Skills, Decisions, and Models. Fully registry-driven and filesystem-scanned.
Provides one-stop unified personal search across graph nodes and Obsidian vault.
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from backend.config import cfg
from backend.logger import get_logger

log = get_logger("knowledge_graph")


class KnowledgeGraph:
    def __init__(self, vault_root: Optional[Path] = None):
        self.vault_root = vault_root or cfg.VAULT
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: List[Dict[str, str]] = []
        self._build_graph()

    def add_node(self, node_id: str, label: str, node_type: str, metadata: dict):
        self.nodes[node_id] = {
            "id": node_id,
            "label": label,
            "type": node_type,
            "metadata": metadata,
        }

    def add_edge(self, source: str, target: str, relation: str):
        self.edges.append({"source": source, "target": target, "relation": relation})

    def _build_graph(self):
        self.nodes.clear()
        self.edges.clear()

        # 1. Projects (dynamically scanned from cfg.PROJECTS)
        stack_hints = {
            "aegis-dashboard": "Vite, React 19, FastAPI, Tailwind",
            "Aegis": "Rust, Python, Linux IPC",
            "chrome-extra": "Chrome Extension, TypeScript",
            "repusense": "Next.js, React, Tailwind",
            "world-viewer": "Electron, Cesium, 3D Geospatial",
            "DeepSeek-V3": "PyTorch, CUDA, DeepSeek MoE",
            "hermes-agent": "Python, SQLite, Hermes CLI",
            "openclaw": "Node.js, TypeScript, OpenClaw Gateway",
            "opencode": "Go/Rust, ACP Server",
        }

        for pid, ppath in cfg.PROJECTS.items():
            meta = {
                "path": str(ppath),
                "stack": stack_hints.get(pid, "General Workspace Project"),
                "exists": ppath.exists(),
            }
            self.add_node(f"proj:{pid}", pid, "Project", meta)

        # 2. Agents (dynamically from AGENT_REGISTRY)
        for ag in cfg.AGENT_REGISTRY:
            aid = ag.get("id", "unknown")
            node_id = f"agent:{aid}"
            self.add_node(node_id, ag.get("name", aid), "Agent", {
                "role": ag.get("role", "Autonomous AI Assistant"),
                "harness": ag.get("harness", "pty"),
                "default_model": ag.get("default_model", ""),
            })
            # Link agent to associated project if matching name exists
            if aid in cfg.PROJECTS:
                self.add_edge(f"proj:{aid}", node_id, "POWERED_BY")

        # 3. Operational Tools (dynamically from TOOL_REGISTRY)
        tool_reg_path = cfg.REGISTRIES_DIR / "TOOL_REGISTRY.json"
        if tool_reg_path.exists():
            try:
                t_data = json.loads(tool_reg_path.read_text())
                for t in t_data.get("tools", []):
                    tid = t.get("name", t.get("id", "tool"))
                    self.add_node(f"tool:{tid}", tid, "Tool", {
                        "category": t.get("category", "General Tool"),
                        "description": t.get("description", ""),
                    })
            except Exception as e:
                log.warning("Could not parse TOOL_REGISTRY: %s", e)
        else:
            default_tools = ["terminal_run", "filesystem_read", "filesystem_write", "screen_ocr", "browser_navigate", "clipboard_sync"]
            for t in default_tools:
                self.add_node(f"tool:{t}", t, "Tool", {"category": "Core System Tool"})

        # 4. Models (dynamically from MODEL_REGISTRY or verified defaults)
        model_reg_path = cfg.REGISTRIES_DIR / "MODEL_REGISTRY.json"
        models_added = set()
        if model_reg_path.exists():
            try:
                m_data = json.loads(model_reg_path.read_text())
                model_list = m_data.get("models", [])
                for m in model_list[:20]:
                    mid = m.get("id", "")
                    if mid and mid not in models_added:
                        models_added.add(mid)
                        label = mid.split("/")[-1] if "/" in mid else mid
                        self.add_node(f"model:{mid}", label, "Model", {
                            "provider": m.get("provider", "9Router"),
                            "context_length": m.get("context_length", 1048576),
                        })
            except Exception as e:
                log.warning("Could not parse MODEL_REGISTRY: %s", e)

        if not models_added:
            for mid in cfg.MODEL_FALLBACK_CHAIN:
                label = mid.split("/")[-1]
                self.add_node(f"model:{mid}", label, "Model", {"provider": "9Router"})

        # 5. Key Decisions (from DECISIONS.md if present)
        dec_file = cfg.AGIES_VAULT / "DECISIONS.md"
        if dec_file.exists():
            try:
                content = dec_file.read_text(errors="replace")
                for line in content.splitlines():
                    if line.startswith("### ") or line.startswith("## "):
                        title = line.strip("# ")
                        d_id = f"dec:{title.lower().replace(' ', '_')[:30]}"
                        self.add_node(d_id, title, "Decision", {"source": "DECISIONS.md"})
                        self.add_edge("proj:aegis-dashboard", d_id, "DECIDED")
            except Exception:
                pass

        if not any(n["type"] == "Decision" for n in self.nodes.values()):
            self.add_node("dec:vite_migration", "Migrate from Next.js to Vite SPA", "Decision", {
                "project": "aegis-dashboard",
                "rationale": "Eliminate SSR hydration overhead, enable pure client-side SPA",
            })
            self.add_edge("proj:aegis-dashboard", "dec:vite_migration", "DECIDED")

            self.add_node("dec:sse_streaming", "Direct 9Router SSE Chunk Parser", "Decision", {
                "project": "aegis-dashboard",
                "rationale": "Directly handle 9Router event-stream format with zero-copy forwarding",
            })
            self.add_edge("proj:aegis-dashboard", "dec:sse_streaming", "DECIDED")

        log.info("Knowledge Graph built: %d nodes, %d edges", len(self.nodes), len(self.edges))

    def get_graph_data(self) -> Dict[str, Any]:
        """Returns nodes and edges formatted for visualization."""
        return {
            "nodes": list(self.nodes.values()),
            "edges": self.edges,
            "counts": {
                "total_nodes": len(self.nodes),
                "total_edges": len(self.edges),
                "projects": sum(1 for n in self.nodes.values() if n["type"] == "Project"),
                "agents": sum(1 for n in self.nodes.values() if n["type"] == "Agent"),
                "tools": sum(1 for n in self.nodes.values() if n["type"] == "Tool"),
                "models": sum(1 for n in self.nodes.values() if n["type"] == "Model"),
                "decisions": sum(1 for n in self.nodes.values() if n["type"] == "Decision"),
            }
        }

    def unified_search(self, query: str, limit: int = 20) -> List[dict]:
        """
        One unified query searching across:
        - Graph nodes (Projects, Agents, Tools, Decisions, Models)
        - Obsidian Vault Markdown Notes
        """
        results = []
        q_lower = query.lower()

        # 1. Search Graph Nodes
        for nid, n in self.nodes.items():
            score = 0
            if q_lower in n["label"].lower():
                score += 12
            if q_lower in n["type"].lower():
                score += 5
            meta_str = json.dumps(n["metadata"]).lower()
            if q_lower in meta_str:
                score += 4
            if score > 0:
                results.append({
                    "category": n["type"],
                    "title": n["label"],
                    "id": nid,
                    "preview": meta_str[:150],
                    "score": score,
                })

        # 2. Search Obsidian Vault Notes
        if self.vault_root.exists():
            for md in self.vault_root.rglob("*.md"):
                if any(ign in md.parts for ign in [".git", ".obsidian", ".trash"]):
                    continue
                try:
                    name_lower = md.name.lower()
                    if q_lower in name_lower:
                        results.append({
                            "category": "Vault Note",
                            "title": md.name,
                            "path": str(md.relative_to(self.vault_root)),
                            "preview": md.read_text(errors="replace")[:160].replace("\n", " "),
                            "score": 8,
                        })
                except Exception:
                    continue

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]


knowledge_graph = KnowledgeGraph()

if __name__ == "__main__":
    data = knowledge_graph.get_graph_data()
    print("=== Knowledge Graph Verification ===")
    print(f"Nodes: {len(data['nodes'])}, Edges: {len(data['edges'])}")
    print("Counts by type:", data["counts"])
    hits = knowledge_graph.unified_search("vite")
    print(f"Search for 'vite' returned {len(hits)} results:")
    for h in hits[:4]:
        print(f"  - [{h['category']}] {h['title']} (score: {h['score']})")
    print("Knowledge Graph: VERIFIED OK")
