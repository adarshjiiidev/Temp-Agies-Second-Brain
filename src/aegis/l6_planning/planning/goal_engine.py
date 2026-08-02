"""L6 Planning Engine — Goal Engine.

Creates, validates, and refines Mission objects from raw user goal text.
The GoalEngine is the entry point for the planning pipeline.

Import safety: stdlib + l6_planning internal only.
"""

from __future__ import annotations

from typing import Any

from aegis.l6_planning.exceptions import PlanGoalInvalidError
from aegis.l6_planning.intent.ambiguity_detector import AmbiguityDetector
from aegis.l6_planning.intent.intent_parser import IntentParser
from aegis.l6_planning.intent.requirement_extractor import RequirementExtractor
from aegis.l6_planning.planning.mission import Mission
from aegis.l6_planning.planning.objective import Objective
from aegis.l6_planning.types import (
    Constraint,
    ConstraintKind,
    EffortEstimate,
    IntentDomain,
    PlanningStrategy,
    RiskLevel,
    ValidationIssue,
)

__all__ = ["GoalEngine"]

# Domain → initial objective template
_DOMAIN_OBJECTIVES: dict[IntentDomain, list[dict[str, Any]]] = {
    IntentDomain.CODING: [
        {"title": "Understand requirements and scope", "priority": 1},
        {"title": "Design solution architecture", "priority": 2},
        {"title": "Implement core functionality", "priority": 3},
        {"title": "Write tests", "priority": 4},
        {"title": "Review and refine", "priority": 5},
    ],
    IntentDomain.RESEARCH: [
        {"title": "Define research question and scope", "priority": 1},
        {"title": "Gather and review sources", "priority": 2},
        {"title": "Analyse and synthesise findings", "priority": 3},
        {"title": "Produce research output", "priority": 4},
    ],
    IntentDomain.BROWSER: [
        {"title": "Identify target resources", "priority": 1},
        {"title": "Retrieve and parse content", "priority": 2},
        {"title": "Process and store results", "priority": 3},
    ],
    IntentDomain.FILESYSTEM: [
        {"title": "Identify files and directories in scope", "priority": 1},
        {"title": "Apply file operations", "priority": 2},
        {"title": "Verify results", "priority": 3},
    ],
    IntentDomain.TERMINAL: [
        {"title": "Identify required commands", "priority": 1},
        {"title": "Execute and verify commands", "priority": 2},
    ],
    IntentDomain.FINANCE: [
        {"title": "Gather financial data", "priority": 1},
        {"title": "Analyse data", "priority": 2},
        {"title": "Generate output", "priority": 3},
    ],
    IntentDomain.AUTOMATION: [
        {"title": "Define automation scope and triggers", "priority": 1},
        {"title": "Implement automation steps", "priority": 2},
        {"title": "Test and validate automation", "priority": 3},
    ],
    IntentDomain.VISION: [
        {"title": "Capture or load visual input", "priority": 1},
        {"title": "Process visual data", "priority": 2},
        {"title": "Produce output", "priority": 3},
    ],
    IntentDomain.VOICE: [
        {"title": "Capture or load audio input", "priority": 1},
        {"title": "Process audio", "priority": 2},
        {"title": "Produce output", "priority": 3},
    ],
    IntentDomain.PLANNING: [
        {"title": "Define goal and constraints", "priority": 1},
        {"title": "Create structured plan", "priority": 2},
        {"title": "Review and finalise plan", "priority": 3},
    ],
    IntentDomain.MIXED: [
        {"title": "Define scope across domains", "priority": 1},
        {"title": "Execute primary domain tasks", "priority": 2},
        {"title": "Execute secondary domain tasks", "priority": 3},
        {"title": "Integrate and verify", "priority": 4},
    ],
    IntentDomain.UNKNOWN: [
        {"title": "Clarify goal and scope", "priority": 1},
        {"title": "Execute identified tasks", "priority": 2},
        {"title": "Verify completion", "priority": 3},
    ],
}


class GoalEngine:
    """Creates and manages Mission objects from raw user goal text.

    The GoalEngine is the first stage of the planning pipeline:
    1. Parse intent
    2. Extract requirements
    3. Detect ambiguities
    4. Build initial objectives
    5. Assemble Mission

    Usage::

        engine = GoalEngine()
        mission = engine.create_mission("Build a React portfolio website")
        issues = engine.validate_mission(mission)
    """

    def __init__(self) -> None:
        self._parser = IntentParser()
        self._extractor = RequirementExtractor()
        self._ambiguity = AmbiguityDetector()

    def create_mission(
        self,
        goal_text: str,
        context: dict[str, Any] | None = None,
        strategy: PlanningStrategy = PlanningStrategy.BALANCED,
        constraints: list[Constraint] | None = None,
        deadline: float | None = None,
    ) -> Mission:
        """Create a Mission from a raw user goal.

        Args:
            goal_text: Raw user goal string.
            context: Optional planning context (domain hints, force_offline, etc.).
            strategy: Preferred planning strategy.
            constraints: Additional hard/soft constraints.
            deadline: Optional Unix timestamp deadline.

        Returns:
            Typed Mission ready for decomposition.

        Raises:
            PlanGoalInvalidError: If goal_text is empty or too short.
        """
        text = goal_text.strip()
        if not text:
            raise PlanGoalInvalidError("Goal text is empty")
        if len(text) < 3:
            raise PlanGoalInvalidError(f"Goal text too short: {text!r}")

        # Parse intent
        intent = self._parser.parse(text, context)

        # Extract requirements
        requirements = self._extractor.extract(intent)

        # Derive a concise title
        title = self._derive_title(text)

        # Build objectives from domain template
        objectives = self._build_objectives(intent, title)

        # Build constraints list
        all_constraints = list(constraints or [])
        if intent.requires_local_only:
            all_constraints.append(Constraint(
                kind=ConstraintKind.PRIVACY,
                description="Local-only mode: no data sent off-device",
                hard=True,
            ))
        if intent.requires_internet and not intent.requires_local_only:
            all_constraints.append(Constraint(
                kind=ConstraintKind.RESOURCE,
                description="Internet access required",
                hard=False,
            ))

        return Mission(
            title=title,
            user_goal_text=text,
            parsed_intent=intent,
            requirements=requirements,
            objectives=objectives,
            constraints=all_constraints,
            strategy=strategy,
            deadline=deadline,
        )

    def refine_mission(
        self,
        mission: Mission,
        feedback: str,
        context: dict[str, Any] | None = None,
    ) -> Mission:
        """Refine an existing Mission based on user feedback.

        Parses the feedback as an amended goal, re-extracts requirements,
        and merges any new objectives while bumping the version.

        Args:
            mission: Existing Mission to refine.
            feedback: User feedback / updated goal text.
            context: Optional context overrides.

        Returns:
            Updated Mission with incremented version.
        """
        if not feedback.strip():
            return mission

        # Re-parse using combined text
        combined = f"{mission.user_goal_text}. Additionally: {feedback}"
        intent = self._parser.parse(combined, context)
        requirements = self._extractor.extract(intent)

        return mission.model_copy(update={
            "parsed_intent": intent,
            "requirements": requirements,
            "notes": mission.notes + [f"Refined with feedback: {feedback!r}"],
        }).bump_version()

    def validate_mission(self, mission: Mission) -> list[ValidationIssue]:
        """Validate a Mission for completeness and consistency.

        Args:
            mission: Mission to validate.

        Returns:
            List of ValidationIssue (may be empty if valid).
        """
        issues: list[ValidationIssue] = []

        if not mission.title:
            issues.append(ValidationIssue(severity="error", code="V001", message="Mission title is empty"))

        if not mission.objectives:
            issues.append(ValidationIssue(severity="warning", code="V002", message="No objectives defined"))

        if mission.parsed_intent.confidence < 0.30:
            issues.append(ValidationIssue(
                severity="warning",
                code="V003",
                message=f"Very low intent confidence ({mission.parsed_intent.confidence:.0%}). Consider clarifying the goal.",
            ))

        if mission.parsed_intent.is_ambiguous:
            issues.append(ValidationIssue(
                severity="info",
                code="V004",
                message=f"Intent has {len(mission.parsed_intent.ambiguities)} ambiguity flag(s). Clarification may improve plan quality.",
            ))

        # Circular objective dependencies
        obj_ids = {o.objective_id for o in mission.objectives}
        for obj in mission.objectives:
            for dep in obj.dependencies:
                if dep not in obj_ids:
                    issues.append(ValidationIssue(
                        severity="error",
                        code="V005",
                        message=f"Objective {obj.objective_id!r} depends on unknown objective {dep!r}",
                        field="objectives",
                    ))

        return issues

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _derive_title(self, goal_text: str) -> str:
        """Derive a short mission title from the goal text."""
        words = goal_text.split()
        if len(words) <= 8:
            return goal_text
        return " ".join(words[:8]) + "…"

    def _build_objectives(self, intent: Any, mission_title: str) -> list[Objective]:
        """Build initial objective list from the detected domain template."""
        templates = _DOMAIN_OBJECTIVES.get(intent.domain, _DOMAIN_OBJECTIVES[IntentDomain.UNKNOWN])
        objectives = []
        for tmpl in templates:
            effort = self._map_effort(intent.domain, tmpl["priority"])
            risk = RiskLevel.MEDIUM if intent.domain in {IntentDomain.TERMINAL, IntentDomain.FINANCE} else RiskLevel.LOW
            objectives.append(Objective(
                title=f"{tmpl['title']} — {mission_title}"[:80],
                description=f"Auto-generated objective for: {tmpl['title']}",
                priority=tmpl["priority"],
                estimated_effort=effort,
                risk_level=risk,
                success_criteria=[f"'{tmpl['title']}' is demonstrably complete"],
                failure_criteria=[f"'{tmpl['title']}' cannot be verified"],
                confidence=intent.confidence * 0.9,
                rationale=f"Derived from {intent.domain.value} domain template",
            ))
        return objectives

    def _map_effort(self, domain: IntentDomain, priority: int) -> EffortEstimate:
        """Map domain + priority index to an effort level."""
        if priority == 1:
            return EffortEstimate.small()
        if domain in {IntentDomain.CODING, IntentDomain.FINANCE, IntentDomain.MIXED}:
            return EffortEstimate.large() if priority >= 3 else EffortEstimate.medium()
        return EffortEstimate.medium()
