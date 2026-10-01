"""L1 Interfaces — ALL system Protocols live here (Prompt 01 §02).
Future subsystems implement these protocols; concrete classes never imported directly across modules.
Forward declarations for L3+ are minimal abstract Protocol signatures only — no concrete behavior."""

from aegis.l1_core.interfaces.base import (
    HealthProvider,
    ModuleLifecycle,
    Pluggable,
    Service,
    ServiceInfo,
)
from aegis.l1_core.interfaces.events import EventBus as IEventBus
from aegis.l1_core.interfaces.events import EventHandler, Subscriber
from aegis.l1_core.interfaces.exec import Action, ActionResult, Executor
from aegis.l1_core.interfaces.llm import EmbeddingProvider, LLMProvider
from aegis.l1_core.interfaces.memory import MemoryStore
from aegis.l1_core.interfaces.storage import DocStore, GraphStore, KVStore, VectorStore

__all__ = [
    # Base
    "ModuleLifecycle",
    "HealthProvider",
    "Pluggable",
    "Service",
    "ServiceInfo",
    # Events (implemented in L2)
    "IEventBus",
    "EventHandler",
    "Subscriber",
    # Storage (implemented in L2)
    "KVStore",
    "DocStore",
    "VectorStore",
    "GraphStore",
    # LLM (forward decl — implemented in L3, Prompt 03+)
    "LLMProvider",
    "EmbeddingProvider",
    # Execution (forward decl — implemented in L3, Prompt 05+)
    "Executor",
    "Action",
    "ActionResult",
    # Memory (forward decl — implemented in L4, Prompt 04+)
    "MemoryStore",
]
