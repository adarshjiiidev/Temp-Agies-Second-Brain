"""L6 Planning Engine — Task Decomposer.

Converts a Mission's Objectives into a flat Task/Subtask hierarchy
and populates a DependencyGraph.

Import safety: stdlib + pydantic + l6_planning internal only.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from aegis.l6_planning.decomposition.dependency_graph import DependencyGraph
from aegis.l6_planning.planning.mission import Mission
from aegis.l6_planning.planning.objective import Objective
from aegis.l6_planning.types import EffortEstimate, IntentDomain, RiskLevel

__all__ = ["Task", "Subtask", "DecompositionResult", "TaskDecomposer"]


class Subtask(BaseModel):
    """An atomic unit of work within a Task."""

    subtask_id: str = Field(default_factory=lambda: f"st-{uuid.uuid4()!s:.8}")
    title: str
    description: str = ""
    action_kind_hint: str | None = None   # e.g. "fs.write", "git.commit"
    estimated_seconds: float = 60.0
    is_approval_point: bool = False
    risk_level: RiskLevel = RiskLevel.LOW
    reversible: bool = True

    def __repr__(self) -> str:
        return f"Subtask({self.subtask_id!r}, {self.title!r})"


class Task(BaseModel):
    """A unit of work decomposed from an Objective."""

    task_id: str = Field(default_factory=lambda: f"tsk-{uuid.uuid4()!s:.8}")
    title: str
    description: str = ""
    objective_id: str
    subtasks: list[Subtask] = Field(default_factory=list)
    action_kind_hint: str | None = None
    estimated_effort: EffortEstimate = Field(default_factory=EffortEstimate.small)
    estimated_seconds: float = 300.0
    resource_requirements: list[str] = Field(default_factory=list)
    is_approval_point: bool = False
    risk_level: RiskLevel = RiskLevel.LOW
    reversible: bool = True
    depends_on: list[str] = Field(default_factory=list)   # other Task IDs
    can_run_parallel: bool = False
    tags: list[str] = Field(default_factory=list)

    @property
    def subtask_count(self) -> int:
        return len(self.subtasks)

    @property
    def is_high_risk(self) -> bool:
        return self.risk_level >= RiskLevel.HIGH

    def __repr__(self) -> str:
        return f"Task({self.task_id!r}, {self.title!r}, risk={self.risk_level.value})"


class DecompositionResult(BaseModel):
    """Output of the TaskDecomposer."""

    tasks: list[Task] = Field(default_factory=list)
    graph: dict[str, Any] = Field(default_factory=dict)   # serialized DependencyGraph
    total_estimated_seconds: float = 0.0
    parallel_task_count: int = 0
    sequential_task_count: int = 0
    approval_point_count: int = 0
    critical_path: list[str] = Field(default_factory=list)


# Domain-specific task templates: objective index → [(title, action_hint, risk, seconds, reversible)]
_TASK_TEMPLATES: dict[IntentDomain, list[list[tuple[str, str | None, RiskLevel, float, bool]]]] = {
    IntentDomain.CODING: [
        # Objective 1: Understand requirements
        [("Read existing codebase", "fs.read", RiskLevel.LOW, 120, True),
         ("Identify dependencies", "fs.read", RiskLevel.LOW, 60, True)],
        # Objective 2: Design
        [("Draft architecture", None, RiskLevel.LOW, 300, True),
         ("Create file/directory structure", "fs.mkdir", RiskLevel.LOW, 30, True)],
        # Objective 3: Implement
        [("Write core module", "fs.write", RiskLevel.LOW, 900, True),
         ("Integrate with existing code", "fs.write", RiskLevel.MEDIUM, 300, True)],
        # Objective 4: Test
        [("Write unit tests", "fs.write", RiskLevel.LOW, 600, True),
         ("Run test suite", "shell.exec", RiskLevel.MEDIUM, 120, True)],
        # Objective 5: Review
        [("Code review pass", "fs.read", RiskLevel.LOW, 300, True),
         ("Commit changes", "git.commit", RiskLevel.LOW, 30, True)],
    ],
    IntentDomain.RESEARCH: [
        [("Define research scope document", "fs.write", RiskLevel.LOW, 120, True)],
        [("Search and collect sources", "net.get", RiskLevel.LOW, 600, True),
         ("Download and store references", "fs.write", RiskLevel.LOW, 120, True)],
        [("Read and annotate sources", "fs.read", RiskLevel.LOW, 1800, True),
         ("Synthesise key findings", "fs.write", RiskLevel.LOW, 600, True)],
        [("Write final report", "fs.write", RiskLevel.LOW, 900, True),
         ("Review and export", "fs.read", RiskLevel.LOW, 120, True)],
    ],
    IntentDomain.FILESYSTEM: [
        [("Identify target files/directories", "fs.search", RiskLevel.LOW, 60, True)],
        [("Apply file operations", "fs.write", RiskLevel.MEDIUM, 120, True)],
        [("Verify results", "fs.read", RiskLevel.LOW, 30, True)],
    ],
    IntentDomain.TERMINAL: [
        [("Identify commands to run", None, RiskLevel.LOW, 30, True)],
        [("Execute commands (approval required)", "shell.exec", RiskLevel.HIGH, 60, False)],
    ],
    IntentDomain.BROWSER: [
        [("Identify target URLs", None, RiskLevel.LOW, 30, True)],
        [("Navigate and retrieve content", "browser.navigate", RiskLevel.LOW, 120, True),
         ("Extract relevant data", "browser.read", RiskLevel.LOW, 60, True)],
        [("Process and store results", "fs.write", RiskLevel.LOW, 60, True)],
    ],
    IntentDomain.PLANNING: [
        [("Gather requirements and constraints", None, RiskLevel.LOW, 120, True)],
        [("Draft plan structure", None, RiskLevel.LOW, 300, True)],
        [("Review and finalise plan", None, RiskLevel.LOW, 120, True)],
    ],
}


def _default_templates(objective_count: int) -> list[list[tuple[str, str | None, RiskLevel, float, bool]]]:
    """Fallback templates for unknown/mixed domains."""
    return [
        [("Gather information", "fs.read", RiskLevel.LOW, 120, True),
         ("Plan approach", None, RiskLevel.LOW, 60, True)]
        for _ in range(objective_count)
    ]


class TaskDecomposer:
    """Decomposes Mission objectives into Tasks and populates a DependencyGraph.

    Usage::

        decomposer = TaskDecomposer()
        result = decomposer.decompose(mission)
        # result.tasks = [Task(...), ...]
        # result.graph = {serialized DAG}
    """

    def decompose(self, mission: Mission) -> DecompositionResult:
        """Decompose a Mission into Tasks with a dependency graph.

        Args:
            mission: Validated Mission from GoalEngine.

        Returns:
            DecompositionResult with tasks and serialized dependency graph.
        """
        objectives = mission.objectives_by_priority()
        domain = mission.parsed_intent.domain

        templates = _TASK_TEMPLATES.get(domain, _default_templates(len(objectives)))
        graph = DependencyGraph()
        all_tasks: list[Task] = []
        prev_objective_last_task_id: str | None = None

        for obj_idx, objective in enumerate(objectives):
            obj_templates = templates[obj_idx] if obj_idx < len(templates) else templates[-1]
            obj_tasks: list[Task] = []
            prev_task_id: str | None = None

            for tmpl_idx, (title, action_hint, risk, seconds, reversible) in enumerate(obj_templates):
                # Adjust risk if domain is high-risk
                if mission.requirements.max_risk_level >= RiskLevel.HIGH and risk < RiskLevel.HIGH:
                    risk = RiskLevel.MEDIUM

                task = Task(
                    title=f"{title} [{objective.title.split('—')[0].strip()}]",
                    description=f"Part of objective: {objective.title}",
                    objective_id=objective.objective_id,
                    action_kind_hint=action_hint,
                    estimated_seconds=seconds,
                    estimated_effort=self._seconds_to_effort(seconds),
                    risk_level=risk,
                    reversible=reversible,
                    is_approval_point=(risk >= RiskLevel.HIGH),
                    can_run_parallel=(tmpl_idx > 0 and prev_task_id is not None and risk < RiskLevel.HIGH),
                    depends_on=[prev_task_id] if prev_task_id and not (tmpl_idx > 0 and risk < RiskLevel.HIGH) else [],
                    subtasks=self._make_subtasks(title, action_hint, risk),
                )
                obj_tasks.append(task)
                graph.add_node(task.task_id, task.title, weight=seconds)

                # Wire sequential dep within objective
                if prev_task_id and not task.can_run_parallel:
                    graph.add_edge(prev_task_id, task.task_id)

                prev_task_id = task.task_id

            # Wire first task of this objective to last task of previous objective
            if prev_objective_last_task_id and obj_tasks:
                first_task = obj_tasks[0]
                first_task = first_task.model_copy(update={
                    "depends_on": [prev_objective_last_task_id] + first_task.depends_on
                })
                obj_tasks[0] = first_task
                graph.add_edge(prev_objective_last_task_id, first_task.task_id)

            if obj_tasks:
                prev_objective_last_task_id = obj_tasks[-1].task_id
            all_tasks.extend(obj_tasks)

        # Compute stats
        graph_data = graph.to_dict()
        try:
            cpath = graph.critical_path()
        except ValueError:
            cpath = []

        parallel_count = sum(1 for t in all_tasks if t.can_run_parallel)
        total_seconds = sum(t.estimated_seconds for t in all_tasks)
        approval_count = sum(1 for t in all_tasks if t.is_approval_point)

        return DecompositionResult(
            tasks=all_tasks,
            graph=graph_data,
            total_estimated_seconds=total_seconds,
            parallel_task_count=parallel_count,
            sequential_task_count=len(all_tasks) - parallel_count,
            approval_point_count=approval_count,
            critical_path=cpath,
        )

    def _seconds_to_effort(self, seconds: float) -> EffortEstimate:
        if seconds < 60:
            return EffortEstimate.trivial()
        if seconds < 900:
            return EffortEstimate.small()
        if seconds < 7200:
            return EffortEstimate.medium()
        return EffortEstimate.large()

    def _make_subtasks(
        self, title: str, action_hint: str | None, risk: RiskLevel
    ) -> list[Subtask]:
        """Generate 1–2 subtasks for a task."""
        subtasks = [
            Subtask(
                title=f"Prepare: {title}",
                action_kind_hint=None,
                estimated_seconds=15.0,
                risk_level=RiskLevel.LOW,
            )
        ]
        if action_hint:
            subtasks.append(Subtask(
                title=f"Execute: {title}",
                action_kind_hint=action_hint,
                estimated_seconds=30.0,
                risk_level=risk,
                is_approval_point=(risk >= RiskLevel.HIGH),
                reversible=(risk < RiskLevel.HIGH),
            ))
        return subtasks
