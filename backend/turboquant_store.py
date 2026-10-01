#!/usr/bin/env python3
"""
AEGIS TurboQuant Knowledge Storage (Local Equivalent)
Provides configurable vector-like semantic retrieval with provenance metadata preservation.
"""

import sys
import json
import uuid
import time
from pathlib import Path
from typing import List, Dict, Any

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from backend.config import cfg
from backend.logger import get_logger

log = get_logger("turboquant")

class TurboQuantStore:
    def __init__(self):
        self.store_file = cfg.AEGIS_DIR / "turboquant_store.json"
        self._cache = []
        self._load()

    def _load(self):
        if self.store_file.exists():
            try:
                self._cache = json.loads(self.store_file.read_text(errors="replace"))
            except Exception as e:
                log.error(f"Failed to load TurboQuant store: {e}")
                self._cache = []
        else:
            self._cache = []

    def _save(self):
        try:
            self.store_file.parent.mkdir(parents=True, exist_ok=True)
            self.store_file.write_text(json.dumps(self._cache, indent=2))
        except Exception as e:
            log.error(f"Failed to save TurboQuant store: {e}")

    def ingest(self, source_id: str, content: str, metadata: Dict[str, Any]):
        """Chunks content and stores it with provenance."""
        # Simple paragraph chunking
        chunks = [c.strip() for c in content.split("\n\n") if len(c.strip()) > 50]
        for c in chunks:
            self._cache.append({
                "id": str(uuid.uuid4()),
                "source_id": source_id,
                "content": c,
                "metadata": metadata,
                "timestamp": time.time()
            })
        self._save()
        log.info(f"Ingested {len(chunks)} chunks from {source_id} into TurboQuant store.")

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Simulate semantic retrieval using keyword density ranking."""
        query_terms = set(query.lower().split())
        scored = []
        for chunk in self._cache:
            content_lower = chunk["content"].lower()
            score = sum(1 for term in query_terms if term in content_lower)
            if score > 0:
                scored.append((score, chunk))
        
        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for score, c in scored[:limit]]

turboquant_store = TurboQuantStore()

if __name__ == "__main__":
    tq = TurboQuantStore()
    tq.ingest("test_doc_1", "TurboQuant is a semantic retrieval system. It stores embeddings.", {"author": "AEGIS"})
    res = tq.search("TurboQuant semantic", limit=2)
    print("TurboQuant test search result:")
    print(json.dumps(res, indent=2))
