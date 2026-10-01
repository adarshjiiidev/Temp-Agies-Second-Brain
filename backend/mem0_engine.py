#!/usr/bin/env python3
"""
AEGIS Mem0 Memory Layer
=======================
Adapted from Mem0 (https://github.com/mem0ai/mem0) for AEGIS AI OS.
Implements universal personalized memory layer for agents & users:
- Single-pass ADD-only extraction: memories accumulate with entity linking & timestamp
- Multi-signal retrieval: BM25/keyword similarity, entity overlap, and recency boost
- Scopes: user_id, agent_id, run_id, project_id
- Fully local persistence with zero external service requirements
"""

import sys
import os
import json
import time
import uuid
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from backend.config import cfg
from backend.logger import get_logger

log = get_logger("mem0_engine")


class Mem0MemoryEngine:
    def __init__(self, store_path: Optional[Path] = None):
        self.store_path = store_path or (cfg.HOME / ".temporary-aegis" / "memory" / "mem0_store.json")
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.memories: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        if self.store_path.exists():
            try:
                self.memories = json.loads(self.store_path.read_text(errors="replace"))
                log.info("Loaded %d memories from Mem0 store", len(self.memories))
            except Exception as e:
                log.warning("Could not read Mem0 store, initializing empty: %s", e)
                self.memories = []
        else:
            # Seed with foundational system memories
            self.memories = [
                {
                    "id": "mem-seed-1",
                    "text": "User prefers high-performance Linux workstation environments with dark glassmorphic UI and vim/terminal workflows.",
                    "user_id": "adarshjii",
                    "agent_id": "hermes",
                    "entities": ["Linux", "UI", "terminal", "dark mode"],
                    "category": "preference",
                    "created_at": time.time(),
                    "access_count": 1,
                },
                {
                    "id": "mem-seed-2",
                    "text": "AEGIS AI OS operates on port 2981 with FastAPI backend and Vite React dashboard.",
                    "user_id": "adarshjii",
                    "agent_id": "system",
                    "entities": ["AEGIS", "FastAPI", "React", "port 2981"],
                    "category": "architecture",
                    "created_at": time.time(),
                    "access_count": 1,
                }
            ]
            self._save()

    def _save(self):
        try:
            self.store_path.write_text(json.dumps(self.memories, indent=2))
        except Exception as e:
            log.error("Failed to persist Mem0 memories: %s", e)

    def extract_entities(self, text: str) -> List[str]:
        """Lightweight entity and keyword extractor."""
        # Find capitalized terms, quoted terms, tech tokens
        tokens = re.findall(r'\b[A-Z][a-zA-Z0-9_\-]+\b|[a-z0-9_\-]+(?:\.[a-z]+)+|\b(?:react|vite|fastapi|python|rust|node|cuda|kernel|obsidian|mem0|docker)\b', text, re.I)
        cleaned = list({t.lower() for t in tokens if len(t) > 2})
        return cleaned[:8]

    def add(
        self,
        text: str,
        user_id: str = "adarshjii",
        agent_id: str = "default",
        run_id: Optional[str] = None,
        project_id: Optional[str] = None,
        category: str = "general",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Add a new memory with entity linking and metadata provenance.
        Single-pass ADD-only: preserves historical fidelity.
        """
        text = text.strip()
        if not text:
            return {"error": "Empty memory text"}

        entities = self.extract_entities(text)
        mem_id = f"mem-{uuid.uuid4().hex[:10]}"

        memory_record = {
            "id": mem_id,
            "text": text,
            "user_id": user_id,
            "agent_id": agent_id,
            "run_id": run_id,
            "project_id": project_id,
            "category": category,
            "entities": entities,
            "metadata": metadata or {},
            "created_at": time.time(),
            "updated_at": time.time(),
            "access_count": 0,
        }

        self.memories.append(memory_record)
        self._save()
        log.info("Mem0: Stored new memory [%s] for user=%s agent=%s", mem_id, user_id, agent_id)
        return memory_record

    def search(
        self,
        query: str,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        project_id: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Multi-signal retrieval scoring:
        1. BM25-like keyword overlap
        2. Entity matching
        3. Recency boost
        """
        q_lower = query.lower()
        q_tokens = set(re.findall(r'\w+', q_lower))
        q_entities = set(self.extract_entities(query))
        now = time.time()

        scored: List[tuple[float, Dict[str, Any]]] = []

        for mem in self.memories:
            # Filter scopes if provided
            if user_id and mem.get("user_id") != user_id:
                continue
            if agent_id and mem.get("agent_id") != agent_id and mem.get("agent_id") != "system":
                continue
            if project_id and mem.get("project_id") and mem.get("project_id") != project_id:
                continue

            score = 0.0
            mem_text = mem["text"].lower()

            # Exact phrase match
            if q_lower in mem_text:
                score += 15.0

            # Token overlap (Jaccard / term frequency)
            mem_tokens = set(re.findall(r'\w+', mem_text))
            intersection = q_tokens.intersection(mem_tokens)
            if intersection:
                score += (len(intersection) / (len(q_tokens) + 1e-5)) * 10.0

            # Entity overlap
            mem_entities = set(mem.get("entities", []))
            common_entities = q_entities.intersection(mem_entities)
            if common_entities:
                score += len(common_entities) * 4.0

            # Recency boost (up to 3.0 points for memories created within last 7 days)
            age_days = (now - mem.get("created_at", now)) / 86400.0
            recency_boost = max(0.0, 3.0 - (age_days * 0.1))
            score += recency_boost

            if score > 1.0:
                scored.append((score, mem))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, mem in scored[:limit]:
            mem["access_count"] = mem.get("access_count", 0) + 1
            entry = dict(mem)
            entry["score"] = round(score, 2)
            results.append(entry)

        if results:
            self._save()

        return results

    def get_all(
        self,
        user_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Returns all memories sorted by recency."""
        filtered = self.memories
        if user_id:
            filtered = [m for m in self.memories if m.get("user_id") == user_id]
        return sorted(filtered, key=lambda m: m.get("created_at", 0), reverse=True)[:limit]

    def delete(self, memory_id: str) -> bool:
        """Delete memory by id."""
        initial_count = len(self.memories)
        self.memories = [m for m in self.memories if m.get("id") != memory_id]
        if len(self.memories) < initial_count:
            self._save()
            return True
        return False


mem0_engine = Mem0MemoryEngine()

if __name__ == "__main__":
    print("Testing AEGIS Mem0 Memory Layer...")
    res = mem0_engine.search("linux dark mode")
    print(f"Search results for 'linux dark mode': {len(res)}")
    for r in res:
        print(f"  [{r['id']}] score={r['score']} - {r['text']}")
