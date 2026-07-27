"""L2 Scheduler primitives.
Prompt 02 scope: local async BackgroundTaskManager, RetryPolicy with jitter/backoff.
No Celery/Temporal/Taskiq/external queue per strict scope boundary."""

from aegis.l2_foundation.scheduler.background import (
    BackgroundTaskManager,
    RetryPolicy,
    TaskInfo,
    TaskState,
    run_with_retry,
)

__all__ = [
    "BackgroundTaskManager",
    "RetryPolicy",
    "TaskInfo",
    "TaskState",
    "run_with_retry",
]
