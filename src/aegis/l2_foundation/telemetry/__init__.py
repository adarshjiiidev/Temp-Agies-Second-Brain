"""L2 Telemetry: structured JSON logger, metrics registry, correlation context, tracer skeleton.
Prompt 02 exports logger + correlation context; metrics Counter/Gauge/Histogram;
OTel-compatible tracer is a no-op skeleton with correct Protocol surface (Prompt 23 adds vendor)."""
from aegis.l2_foundation.telemetry.logger import LogLevel, StructuredLogger, get_logger
from aegis.l2_foundation.telemetry.context import CorrelationContext
from aegis.l2_foundation.telemetry.metrics import (
    Counter,
    Gauge,
    Histogram,
    MetricsRegistry,
    get_metrics_registry,
)
from aegis.l2_foundation.telemetry.tracer import Span, Tracer, get_tracer

__all__ = [
    # Logging
    "StructuredLogger",
    "LogLevel",
    "get_logger",
    # Correlation
    "CorrelationContext",
    # Metrics
    "MetricsRegistry",
    "Counter",
    "Gauge",
    "Histogram",
    "get_metrics_registry",
    # Tracer skeleton
    "Tracer",
    "Span",
    "get_tracer",
]
