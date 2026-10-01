"""L6 Planning Engine — Ambiguity Detector.

Detects ambiguous intent and generates clarification questions.
Never hallucinates requirements — only flags genuine ambiguities.

Import safety: stdlib + pydantic + l6_planning.types + l6_planning.intent only.
"""

from __future__ import annotations

from aegis.l6_planning.intent.intent_parser import Intent
from aegis.l6_planning.types import ClarificationQuestion, IntentDomain

__all__ = ["AmbiguityReport", "AmbiguityDetector"]


from pydantic import BaseModel, Field


class AmbiguityReport(BaseModel):
    """Result of ambiguity detection on an intent."""

    is_ambiguous: bool
    questions: list[ClarificationQuestion] = Field(default_factory=list)
    confidence_after_clarification: float = 0.8
    blocking: bool = False  # True = cannot plan without answers

    @property
    def question_count(self) -> int:
        return len(self.questions)


class AmbiguityDetector:
    """Analyses a parsed Intent and generates clarification questions.

    Generates targeted questions when:
    - Domain confidence is low (< 0.40)
    - Intent spans multiple domains (MIXED)
    - Goal is very short or uses vague terms
    - Conflicting constraints are detected

    Usage::

        detector = AmbiguityDetector()
        report = detector.detect(intent)
        if report.is_ambiguous:
            for q in report.questions:
                print(q.question)
    """

    CONFIDENCE_THRESHOLD = 0.40

    def detect(self, intent: Intent) -> AmbiguityReport:
        """Detect ambiguities and generate clarification questions."""
        questions: list[ClarificationQuestion] = []
        blocking = False

        # Low confidence → ask for domain clarification
        if intent.confidence < self.CONFIDENCE_THRESHOLD:
            questions.append(ClarificationQuestion(
                question="What kind of task do you want AEGIS to perform?",
                context=f"Your goal {intent.raw_text!r} does not clearly indicate the domain.",
                options=[d.value for d in IntentDomain if d not in (IntentDomain.UNKNOWN, IntentDomain.MIXED)],
                required=True,
            ))
            blocking = True

        # Mixed domain → clarify primary focus
        elif intent.domain is IntentDomain.MIXED:
            questions.append(ClarificationQuestion(
                question="Your goal spans multiple areas. Which should be the primary focus?",
                context="This helps AEGIS prioritise the right tools and approach.",
                options=["coding", "research", "filesystem", "browser", "automation", "other"],
                required=True,
            ))

        # Unknown domain
        elif intent.domain is IntentDomain.UNKNOWN:
            questions.append(ClarificationQuestion(
                question="AEGIS could not determine what kind of task this is. Please describe what you want to achieve in more detail.",
                context=f"Original goal: {intent.raw_text!r}",
                options=[],
                required=True,
            ))
            blocking = True

        # Very short goal (< 4 words)
        if len(intent.raw_text.split()) < 4:
            questions.append(ClarificationQuestion(
                question="Could you provide more detail about your goal?",
                context="More context helps AEGIS build a more accurate plan.",
                options=[],
                required=False,
            ))

        # Conflicting constraints
        if intent.requires_internet and intent.requires_local_only:
            questions.append(ClarificationQuestion(
                question="Your goal seems to require internet access, but you've also requested local-only mode. Which do you prefer?",
                context="AEGIS will respect whichever you choose.",
                options=["Use internet", "Stay local-only (some features may be unavailable)"],
                required=True,
            ))
            blocking = True

        # No target resource for certain domains
        if (
            intent.domain in (IntentDomain.CODING, IntentDomain.FILESYSTEM)
            and intent.target_resource is None
            and len(intent.raw_text.split()) < 8
        ):
            questions.append(ClarificationQuestion(
                question="What is the specific file, folder, or project you want to work on?",
                context="This helps AEGIS set the correct scope for the task.",
                options=[],
                required=False,
            ))

        # Vague terms check
        vague = [w for w in ["something", "stuff", "things", "some"] if w in intent.raw_text.lower().split()]
        if vague:
            questions.append(ClarificationQuestion(
                question=f"Your goal contains vague terms ({', '.join(repr(w) for w in vague)}). Could you be more specific?",
                context="Precise goals lead to better plans.",
                options=[],
                required=False,
            ))

        is_ambiguous = len(questions) > 0
        confidence_after = min(0.90, intent.confidence + 0.25) if is_ambiguous else intent.confidence

        return AmbiguityReport(
            is_ambiguous=is_ambiguous,
            questions=questions,
            confidence_after_clarification=confidence_after,
            blocking=blocking,
        )
