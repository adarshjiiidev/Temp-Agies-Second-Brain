"""L6 Planning Engine — Milestone Builder.

Groups tasks into logical milestones with completion criteria
and verification checkpoints.

Import safety: stdlib + pydantic + l6_planning internal only.
"""

from __future__ import annotations

import math

from aegis.l6_planning.decomposition.task_decomposer import DecompositionResult, Task
from aegis.l6_planning.types import Milestone

__all__ = ["MilestoneBuilder"]


class MilestoneBuilder:
    """Groups tasks from a DecompositionResult into Milestones.

    Strategy: tasks are grouped by their objective_id.
    Each objective becomes one milestone. If there are many tasks per
    objective, sub-milestones are created at natural approval points.

    Usage::

        builder = MilestoneBuilder()
        milestones = builder.build(decomp_result)
    """

    MAX_TASKS_PER_MILESTONE = 6

    def build(self, result: DecompositionResult) -> list[Milestone]:
        """Build milestones from a decomposition result.

        Args:
            result: Output of TaskDecomposer.decompose().

        Returns:
            Ordered list of Milestones.
        """
        if not result.tasks:
            return []

        # Group tasks by objective_id
        obj_groups: dict[str, list[Task]] = {}
        for task in result.tasks:
            obj_groups.setdefault(task.objective_id, []).append(task)

        milestones: list[Milestone] = []
        milestone_index = 1

        for obj_id, tasks in obj_groups.items():
            # Split into chunks if too many tasks per milestone
            chunks = self._chunk_tasks(tasks, self.MAX_TASKS_PER_MILESTONE)
            for chunk_idx, chunk in enumerate(chunks):
                title = self._derive_title(obj_id, tasks, chunk_idx, len(chunks))
                criteria = self._build_criteria(chunk)
                is_checkpoint = any(t.is_approval_point for t in chunk) or chunk_idx == len(chunks) - 1

                milestones.append(Milestone(
                    title=title,
                    description=f"Milestone {milestone_index}: {len(chunk)} task(s) across objective {obj_id[:12]}",
                    task_ids=[t.task_id for t in chunk],
                    completion_criteria=criteria,
                    is_checkpoint=is_checkpoint,
                ))
                milestone_index += 1

        return milestones

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _chunk_tasks(self, tasks: list[Task], max_size: int) -> list[list[Task]]:
        """Split tasks into chunks of at most max_size."""
        n_chunks = max(1, math.ceil(len(tasks) / max_size))
        chunk_size = math.ceil(len(tasks) / n_chunks)
        return [tasks[i:i + chunk_size] for i in range(0, len(tasks), chunk_size)]

    def _derive_title(
        self, obj_id: str, all_tasks: list[Task], chunk_idx: int, total_chunks: int
    ) -> str:
        first_title = all_tasks[0].title if all_tasks else "Tasks"
        base = first_title.split("[")[0].strip()[:40]
        if total_chunks == 1:
            return f"Milestone: {base}"
        return f"Milestone: {base} (Part {chunk_idx + 1}/{total_chunks})"

    def _build_criteria(self, tasks: list[Task]) -> list[str]:
        """Build completion criteria from the task list."""
        criteria = [f"Task '{t.title.split('[')[0].strip()}' is complete" for t in tasks]
        if any(t.is_approval_point for t in tasks):
            criteria.append("All approval points have been explicitly confirmed")
        return criteria
