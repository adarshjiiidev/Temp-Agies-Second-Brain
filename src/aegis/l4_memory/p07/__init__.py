"""L4 P07 — Adaptive Intelligence & Personal Environment Learning.

Sub-packages:
    model/       — Environment graph types, freshness tracking
    privacy/     — Privacy zones, redaction (applied FIRST at all ingestion boundaries)
    persistence/ — EnvironmentStore + CandidateStore (wraps MemoryManager/KnowledgeGraph)
    scanners/    — Bounded, opt-in environment discovery (app, project, CLI, relations)
    observer/    — Synthetic behavior observer (opt-in, privacy-filtered, expiring)
    inference/   — Workflow & preference candidate inference (deterministic heuristics)
    discovery/   — Consent gate + scanning coordinator

Architectural invariants:
    - Import safety: l4_memory.* + stdlib ONLY. Never import from L5/L6/L3.
    - Privacy zone filter applied FIRST at every ingestion boundary.
    - T5_PERSONAL candidates: PENDING_REVIEW only; no auto-promotion.
    - All observation is OPT-IN, pausable, and audit-logged.
    - Scanners use lazy iteration with max_seconds budget (STAB-01 precedent).
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
