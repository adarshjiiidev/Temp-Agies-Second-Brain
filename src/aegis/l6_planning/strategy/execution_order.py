"""L6 Planning Engine — Execution Order.

Produces a flat, ordered list of ExecutionStep from the task list
and dependency graph, respecting strategy-driven priorities.

Import safety: stdlib + pydantic + l6_planning internal only.
"""

from __future__ import annotations

from aegis.l6_planning.decomposition.dependency_graph import DependencyGraph
from aegis.l6_planning.decomposition.task_decomposer import Task
from aegis.l6_planning.types import ExecutionStep, PlanningStrategy, RiskLevel

__all__ = ["ExecutionOrderBuilder"]


class ExecutionOrderBuilder:
    """Converts a task list + dependency graph into a flat ExecutionStep sequence.

    Parallel groups are assigned the same `parallel_group` index so
    executors know which steps can run concurrently.

    Usage::

        builder = ExecutionOrderBuilder()
        steps = builder.build(tasks, graph, strategy=PlanningStrategy.FASTEST)
    """

    def build(
        self,
        tasks: list[Task],
        graph: DependencyGraph,
        strategy: PlanningStrategy = PlanningStrategy.BALANCED,
    ) -> list[ExecutionStep]:
        """Build ordered ExecutionSteps.

        Args:
            tasks: All tasks from TaskDecomposer.
            graph: Populated DependencyGraph.
            strategy: Planning strategy for ordering hints.

        Returns:
            Flat list of ExecutionStep with parallel groups assigned.
        """
        if not tasks:
            return []

        task_map = {t.task_id: t for t in tasks}
        parallel_groups = graph.parallel_groups()

        steps: list[ExecutionStep] = []
        step_index = 0
        completed_task_ids: set[str] = set()

        for group_idx, group in enumerate(parallel_groups):
            is_parallel_group = len(group) > 1
            group_step_indices: list[int] = []

            for task_id in group:
                task = task_map.get(task_id)
                if task is None:
                    continue

                deps_on_steps = [
                    s.step_index for s in steps
                    if s.task_id in task.depends_on
                ]

                step = ExecutionStep(
                    step_index=step_index,
                    task_id=task_id,
                    task_title=task.title,
                    parallel_group=group_idx if is_parallel_group else None,
                    is_approval_point=task.is_approval_point,
                    risk_level=task.risk_level,
                    estimated_duration_seconds=task.estimated_seconds,
                    depends_on_steps=deps_on_steps,
                    action_kind_hint=task.action_kind_hint,
                )
                steps.append(step)
                group_step_indices.append(step_index)
                completed_task_ids.add(task_id)
                step_index += 1

        # Strategy adjustments: FASTEST reorders to maximize parallelism
        # (already handled by parallel_groups). HIGHEST_QUALITY inserts
        # verification steps after HIGH/CRITICAL risk tasks.
        if strategy is PlanningStrategy.HIGHEST_QUALITY:
            steps = self._insert_verification_steps(steps, step_index)

        return steps

    def _insert_verification_steps(
        self, steps: list[ExecutionStep], next_index: int
    ) -> list[ExecutionStep]:
        """Insert verification checkpoints after HIGH/CRITICAL risk steps."""
        enriched: list[ExecutionStep] = []
        idx = next_index

        for step in steps:
            enriched.append(step)
            if step.risk_level >= RiskLevel.HIGH:
                enriched.append(ExecutionStep(
                    step_index=idx,
                    task_id=f"verify-{step.task_id}",
                    task_title=f"[VERIFY] {step.task_title}",
                    parallel_group=None,
                    is_approval_point=True,
                    risk_level=RiskLevel.LOW,
                    estimated_duration_seconds=30.0,
                    depends_on_steps=[step.step_index],
                    action_kind_hint=None,
                ))
                idx += 1

        return enriched
