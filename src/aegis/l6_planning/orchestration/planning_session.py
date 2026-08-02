"""L6 Planning Engine — Planning Session.

In-memory store for active PlanningResult objects, keyed by plan_id.
Thread-safe using a simple lock.

Import safety: stdlib + l6_planning internal only.
"""

from __future__ import annotations

import threading

from aegis.l6_planning.exceptions import PlanAlreadyCancelledError, PlanNotFoundError, PlanSessionExpiredError
from aegis.l6_planning.planning_result import PlanningResult
from aegis.l6_planning.types import PlanState

__all__ = ["PlanningSession"]


class PlanningSession:
    """In-memory store for active PlanningResult objects.

    Usage::

        session = PlanningSession()
        session.store(result)
        result = session.get(result.plan_id)
        session.cancel(result.plan_id)
    """

    def __init__(self, max_plans: int = 500) -> None:
        self._plans: dict[str, PlanningResult] = {}
        self._lock = threading.Lock()
        self._max_plans = max_plans

    def store(self, result: PlanningResult) -> None:
        """Store or update a PlanningResult."""
        with self._lock:
            if len(self._plans) >= self._max_plans and result.plan_id not in self._plans:
                # Evict oldest completed/cancelled plan
                self._evict_one()
            self._plans[result.plan_id] = result

    def get(self, plan_id: str) -> PlanningResult:
        """Retrieve a plan by ID.

        Raises:
            PlanNotFoundError: If plan_id is not in the session.
        """
        with self._lock:
            plan = self._plans.get(plan_id)
        if plan is None:
            raise PlanNotFoundError(plan_id)
        return plan

    def get_or_none(self, plan_id: str) -> PlanningResult | None:
        with self._lock:
            return self._plans.get(plan_id)

    def cancel(self, plan_id: str) -> PlanningResult:
        """Mark a plan as CANCELLED.

        Raises:
            PlanNotFoundError: If plan_id is unknown.
            PlanAlreadyCancelledError: If plan is already cancelled.
        """
        plan = self.get(plan_id)
        if plan.state is PlanState.CANCELLED:
            raise PlanAlreadyCancelledError(plan_id)
        updated = plan.transition(PlanState.CANCELLED)
        self.store(updated)
        return updated

    def update_state(self, plan_id: str, new_state: PlanState) -> PlanningResult:
        """Transition a plan to a new state."""
        plan = self.get(plan_id)
        updated = plan.transition(new_state)
        self.store(updated)
        return updated

    def list_plans(self, state_filter: PlanState | None = None) -> list[PlanningResult]:
        """Return all plans, optionally filtered by state."""
        with self._lock:
            plans = list(self._plans.values())
        if state_filter is not None:
            plans = [p for p in plans if p.state is state_filter]
        return plans

    def drop(self, plan_id: str) -> None:
        """Remove a plan from the session."""
        with self._lock:
            self._plans.pop(plan_id, None)

    def clear(self) -> None:
        """Remove all plans."""
        with self._lock:
            self._plans.clear()

    @property
    def plan_count(self) -> int:
        with self._lock:
            return len(self._plans)

    def _evict_one(self) -> None:
        """Evict the oldest terminal plan to free space. Called under lock."""
        terminal_states = {PlanState.COMPLETED, PlanState.CANCELLED, PlanState.FAILED}
        terminal = [p for p in self._plans.values() if p.state in terminal_states]
        if terminal:
            oldest = min(terminal, key=lambda p: p.created_at)
            del self._plans[oldest.plan_id]
