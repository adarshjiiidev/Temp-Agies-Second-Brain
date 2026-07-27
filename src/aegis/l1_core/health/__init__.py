"""L1 Health monitoring primitives.
HealthState follows exactly 4 states per Prompt 01: HEALTHY / DEGRADED / UNHEALTHY / UNKNOWN."""

from aegis.l1_core.health.checks import health_check_threshold, health_check_timeout
from aegis.l1_core.health.registry import (
    ComponentHealth,
    HealthAggregator,
    HealthCheck,
    HealthReport,
    HealthState,
)

__all__ = [
    "ComponentHealth",
    "HealthAggregator",
    "HealthCheck",
    "HealthReport",
    "HealthState",
    "health_check_threshold",
    "health_check_timeout",
]
