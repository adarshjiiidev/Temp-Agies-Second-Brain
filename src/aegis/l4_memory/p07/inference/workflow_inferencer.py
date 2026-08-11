"""P07 Inference — WorkflowInferencer.

Detects repeated event sequences in the observation log and produces
WorkflowCandidate records. This is purely deterministic heuristic inference
— no LLM calls (L4 cannot import L3).

A workflow candidate is produced when:
  - A sequence of ≥2 distinct event kinds appears at least twice in the
    recent observation window.
  - The sequence appears in the same relative order.

All candidates are marked:
  - status = PENDING_REVIEW (never auto-promoted)
  - source = "heuristic"
  - confidence derived from observation frequency

Import safety: l4_memory.p07.* + stdlib ONLY.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from collections import Counter
from typing import Any


from aegis.l4_memory.p07.observer.events import EventKind, ObservedEvent

__all__ = ["WorkflowCandidate", "WorkflowInferencer"]


@dataclass
class WorkflowCandidate:
    """A candidate workflow inferred from observed event sequences.

    Invariants:
        - source == "heuristic" (deterministic, not AI)
        - status starts as "pending_review" and NEVER auto-changes
        - observation_count ≥ 2 (must appear at least twice to be a candidate)
    """
    label: str
    steps: list[str]                    # Human-readable step descriptions
    event_sequence: list[str]           # EventKind values (strings) in order
    observation_count: int              # How many times this sequence was seen
    confidence: float                   # 0.0–1.0; derived from frequency
    session_id: str                     # Session context
    privacy_tier: str = "P2"
    source: str = "heuristic"
    status: str = "pending_review"
    context: dict[str, Any] = field(default_factory=dict)


class WorkflowInferencer:
    """Detects repeated event sequences and produces WorkflowCandidates.

    Usage::

        inferencer = WorkflowInferencer(min_sequence_length=2, min_occurrences=2)
        candidates = inferencer.infer(events)
        # candidates: list[WorkflowCandidate] (all status=pending_review)

    Algorithm:
      1. Extract consecutive event-kind sequences of length ≥ min_sequence_length.
      2. Count how many times each n-gram sequence appears.
      3. Any sequence appearing ≥ min_occurrences times → WorkflowCandidate.
      4. Confidence = clamp(occurrences / 10, 0.3, 0.95).
    """

    def __init__(
        self,
        min_sequence_length: int = 2,
        max_sequence_length: int = 6,
        min_occurrences: int = 2,
    ) -> None:
        self.min_sequence_length = min_sequence_length
        self.max_sequence_length = max_sequence_length
        self.min_occurrences = min_occurrences

    def infer(self, events: list[ObservedEvent]) -> list[WorkflowCandidate]:
        """Infer workflow candidates from a list of observed events.

        Args:
            events: Chronologically ordered list of ObservedEvents.

        Returns:
            List of WorkflowCandidates (may be empty). All have status=pending_review.
        """
        if len(events) < self.min_sequence_length:
            return []

        # Group events by session
        sessions: dict[str, list[ObservedEvent]] = {}
        for ev in events:
            sessions.setdefault(ev.session_id, []).append(ev)

        # Extract kind sequences and count n-grams
        ngram_counts: Counter[tuple[str, ...]] = Counter()
        ngram_sessions: dict[tuple[str, ...], set[str]] = {}

        for session_id, session_events in sessions.items():
            kinds = [ev.kind.value for ev in session_events]
            for seq_len in range(self.min_sequence_length, min(self.max_sequence_length + 1, len(kinds) + 1)):
                for i in range(len(kinds) - seq_len + 1):
                    ngram = tuple(kinds[i:i + seq_len])
                    ngram_counts[ngram] += 1
                    ngram_sessions.setdefault(ngram, set()).add(session_id)

        # Build candidates for frequent sequences
        candidates: list[WorkflowCandidate] = []
        seen_sequences: set[tuple[str, ...]] = set()

        # Process in order of longest → shortest to avoid duplicate sub-sequences
        for ngram, count in ngram_counts.most_common():
            if count < self.min_occurrences:
                continue
            # Skip if this is a sub-sequence of an already-selected candidate
            is_subsequence = any(
                len(ngram) < len(seen) and _is_subsequence(ngram, seen)
                for seen in seen_sequences
            )
            if is_subsequence:
                continue

            seen_sequences.add(ngram)
            session_id = next(iter(ngram_sessions.get(ngram, {"unknown"})))
            confidence = min(0.95, max(0.3, count / 10.0))

            steps = [_event_kind_label(k) for k in ngram]
            label = " → ".join(steps)

            candidates.append(WorkflowCandidate(
                label=f"Workflow: {label}",
                steps=steps,
                event_sequence=list(ngram),
                observation_count=count,
                confidence=confidence,
                session_id=session_id,
                context={"ngram_sessions": list(ngram_sessions.get(ngram, set()))},
            ))

        return candidates


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EVENT_KIND_LABELS: dict[str, str] = {
    EventKind.APP_OPEN.value:      "Open application",
    EventKind.APP_CLOSE.value:     "Close application",
    EventKind.FILE_TOUCH.value:    "Read/write file",
    EventKind.CMD_RUN.value:       "Run command",
    EventKind.PROJECT_OPEN.value:  "Open project",
    EventKind.TOOL_USE.value:      "Use tool",
    EventKind.SEARCH_QUERY.value:  "Run search",
}


def _event_kind_label(kind_value: str) -> str:
    return _EVENT_KIND_LABELS.get(kind_value, kind_value)


def _is_subsequence(shorter: tuple, longer: tuple) -> bool:
    """Return True if shorter appears as a contiguous sub-sequence in longer."""
    slen = len(shorter)
    for i in range(len(longer) - slen + 1):
        if longer[i:i + slen] == shorter:
            return True
    return False
