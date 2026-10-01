"""P07 Inference — PreferenceInferencer.

Detects frequency-based preferences from observed events and produces
PreferenceCandidate records. This is purely deterministic heuristic inference
— no LLM calls (L4 cannot import L3).

A preference candidate is produced when:
  - A tool, application, or path appears more frequently than others
    in the same category (top-N by count).
  - The frequency significantly exceeds the mean (> 1.5x).

All candidates are marked:
  - status = PENDING_REVIEW (never auto-promoted)
  - source = "heuristic"
  - Targets T5_PERSONAL tier (most sensitive; requires user confirmation)

Import safety: l4_memory.p07.* + stdlib ONLY.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any


from aegis.l4_memory.p07.observer.events import EventKind, ObservedEvent

__all__ = ["PreferenceCandidate", "PreferenceInferencer"]


@dataclass
class PreferenceCandidate:
    """A candidate user preference inferred from observation frequency.

    Invariants:
        - source == "heuristic" (deterministic, not AI)
        - status starts as "pending_review" and NEVER auto-changes
        - tier_target == "T5_PERSONAL" — requires explicit user promotion
    """
    key: str                            # Stable candidate key
    label: str                          # Human-readable description
    preference_value: Any               # The inferred preferred value
    category: str                       # "tool" | "app" | "command" | "path"
    observation_count: int              # How many times observed
    confidence: float                   # 0.0–1.0
    privacy_tier: str = "P2"
    source: str = "heuristic"
    status: str = "pending_review"
    tier_target: str = "T5_PERSONAL"
    context: dict[str, Any] = field(default_factory=dict)


class PreferenceInferencer:
    """Extracts frequency-based preferences from observed events.

    Usage::

        inferencer = PreferenceInferencer(top_n=3, min_count=2, dominance_ratio=1.5)
        candidates = inferencer.infer(events)
        # candidates: list[PreferenceCandidate] (all status=pending_review)

    Algorithm:
      1. Group events by category (tool use, command runs, app opens).
      2. Count frequency of each unique subject within category.
      3. If the most frequent subject appears ≥ min_count times AND
         its count / mean count ≥ dominance_ratio → candidate.
    """

    def __init__(
        self,
        top_n: int = 3,
        min_count: int = 2,
        dominance_ratio: float = 1.5,
    ) -> None:
        self.top_n = top_n
        self.min_count = min_count
        self.dominance_ratio = dominance_ratio

    def infer(self, events: list[ObservedEvent]) -> list[PreferenceCandidate]:
        """Infer preference candidates from a list of observed events.

        Args:
            events: Chronologically ordered list of ObservedEvents.

        Returns:
            List of PreferenceCandidates (may be empty). All have status=pending_review.
        """
        if not events:
            return []

        # Categorize events
        tool_uses: Counter[str] = Counter()
        app_opens: Counter[str] = Counter()
        cmd_runs: Counter[str] = Counter()

        for ev in events:
            if ev.kind == EventKind.TOOL_USE:
                tool_uses[ev.subject] += 1
            elif ev.kind == EventKind.APP_OPEN:
                app_opens[ev.subject] += 1
            elif ev.kind == EventKind.CMD_RUN:
                cmd_runs[ev.subject] += 1

        candidates: list[PreferenceCandidate] = []
        candidates.extend(self._extract_preferences(tool_uses, "tool", "preferred_tool"))
        candidates.extend(self._extract_preferences(app_opens, "app", "preferred_app"))
        candidates.extend(self._extract_preferences(cmd_runs, "command", "preferred_command"))

        return candidates

    def _extract_preferences(
        self,
        counter: Counter[str],
        category: str,
        key_prefix: str,
    ) -> list[PreferenceCandidate]:
        """Extract dominant items from a frequency counter."""
        if not counter:
            return []

        total = sum(counter.values())
        mean_count = total / len(counter)
        candidates: list[PreferenceCandidate] = []

        for subject, count in counter.most_common(self.top_n):
            if count < self.min_count:
                continue
            if len(counter) > 1 and count < mean_count * self.dominance_ratio:
                continue

            confidence = min(0.90, max(0.30, count / max(total, 1)))
            key = f"{key_prefix}:{subject.lower().replace(' ', '_')[:60]}"
            label = f"Preferred {category}: {subject}"

            candidates.append(PreferenceCandidate(
                key=key,
                label=label,
                preference_value=subject,
                category=category,
                observation_count=count,
                confidence=confidence,
                context={"total_events_in_category": total},
            ))

        return candidates
