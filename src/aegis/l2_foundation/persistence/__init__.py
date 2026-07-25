"""L2 Persistence default implementations.
Implements L1 KVStore + DocStore in SQLite per Prompt 01 §03 weighted choice.
VectorStore / GraphStore are typed NoOp* classes — Prompt 07/08+ only."""
from aegis.l2_foundation.persistence.sql import (
    NoOpGraphStore,
    NoOpVectorStore,
    SQLiteDocStore,
    SQLiteKVStore,
)

__all__ = [
    "SQLiteKVStore",
    "SQLiteDocStore",
    "NoOpVectorStore",
    "NoOpGraphStore",
]
