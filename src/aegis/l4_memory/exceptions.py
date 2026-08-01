"""L4 Memory exceptions — typed error hierarchy.

All L4 exceptions extend L1 AEGISError so the core runtime can handle them
uniformly. They do NOT extend L3 AI errors.

Import safety: L1 errors + L4 types only.
"""

from __future__ import annotations

from aegis.l1_core.errors.base import AegisError
from aegis.l1_core.errors import ErrorCode


__all__ = [
    "MemoryError",
    "MemoryNotFoundError",
    "MemoryAlreadyExistsError",
    "MemoryStatusError",
    "MemoryPrivacyViolationError",
    "MemoryVersionConflictError",
    "MemoryPolicyViolationError",
    "MemoryStorageError",
    "MemorySearchError",
    "KnowledgeGraphError",
    "ContextBudgetExceededError",
    "MemoryImportError",
]


class MemoryError(AegisError):
    """Base class for all L4 Memory errors."""
    pass


class MemoryNotFoundError(MemoryError):
    """Requested memory record does not exist."""
    pass


class MemoryAlreadyExistsError(MemoryError):
    """Attempted to create a record with an ID that already exists."""
    pass


class MemoryStatusError(MemoryError):
    """Illegal lifecycle transition (e.g. restoring an active record)."""
    pass


class MemoryPrivacyViolationError(MemoryError):
    """Attempted retrieval or storage that would violate privacy tier constraints."""
    pass


class MemoryVersionConflictError(MemoryError):
    """Optimistic concurrency conflict — expected version does not match current."""
    pass


class MemoryPolicyViolationError(MemoryError):
    """Operation violates a configured MemoryPolicy rule."""
    pass


class MemoryStorageError(MemoryError):
    """Underlying storage adapter returned an unexpected error."""
    pass


class MemorySearchError(MemoryError):
    """Search query failed (malformed query, unsupported mode, etc.)."""
    pass


class KnowledgeGraphError(MemoryError):
    """Knowledge graph operation failed."""
    pass


class ContextBudgetExceededError(MemoryError):
    """Context Builder token budget was exhausted before all sections could be filled."""
    pass


class MemoryImportError(MemoryError):
    """Knowledge import adapter encountered an error."""
    pass
