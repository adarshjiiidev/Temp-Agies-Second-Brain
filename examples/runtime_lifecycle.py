"""Prompt 02 example — demonstrates the full Core Runtime lifecycle.

Flow:
  Create Runtime
    ↓
  Register Configuration (via ConfigLoader + ImmutableConfigSnapshot)
    ↓
  Register Logger (configure_root_logger)
    ↓
  Register Event Bus
    ↓
  Register Services (health aggregator, DI container, two example services)
    ↓
  Start Runtime (dependency-ordered initialize + start)
    ↓
  Publish Event on the bus (hello.world)
    ↓
  Run a background task (heartbeat counter, 10ms)
    ↓
  Check Runtime Health (aggregated)
    ↓
  Graceful Shutdown (stop services in reverse dependency order, timeout 3s)

Intentionally does NOT contain any future subsystem code (no LLM calls, no memory, no agents, no browser, …).
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Any

import aegis
from aegis import (
    BackgroundTaskManager,
    ConfigLoader,
    CoreEventBus,
    CoreRuntime,
    CorrelationContext,
    DIContainer,
    EventEnvelope,
    HealthAggregator,
    HealthState,
    Lifetime,
    LogLevel,
    RetryPolicy,
    RuntimeState,
    ServiceInfo,
    StructuredLogger,
    Topic,
    configure_root_logger,
    get_logger,
)

EXAMPLE_TOPIC = Topic(name="aegis.example.hello", version=1, durable=False)


class _HeartbeatService:
    """Minimal example service implementing the L1 Service protocol by duck-typing."""

    def __init__(self) -> None:
        self.log: StructuredLogger = get_logger("example.heartbeat")
        self.beats: list[int] = []
        self._started = False

    async def initialize(self, context: dict[str, Any] | None = None) -> None:
        self.log.info("Heartbeat.initialize")

    async def start(self) -> None:
        self._started = True
        self.log.info("Heartbeat.start", started=self._started)

    async def stop(self, timeout: float | None = None) -> None:
        self._started = False
        self.log.info("Heartbeat.stop")

    async def close(self) -> None:
        self.log.info("Heartbeat.close")

    def health(self) -> dict[str, Any]:
        return {
            "state": HealthState.HEALTHY.value if self._started else HealthState.UNKNOWN.value,
            "beats_count": len(self.beats),
        }


class _GreeterService:
    """Depends on HeartbeatService — demonstrates dependency ordering."""

    def __init__(self) -> None:
        self.log = get_logger("example.greeter")
        self.started = False

    async def initialize(self, context: dict[str, Any] | None = None) -> None:
        self.log.info("Greeter.initialize")

    async def start(self) -> None:
        self.started = True
        self.log.info("Greeter.start")

    async def stop(self, timeout: float | None = None) -> None:
        self.started = False
        self.log.info("Greeter.stop")

    async def close(self) -> None:
        self.log.info("Greeter.close")

    def health(self) -> dict[str, Any]:
        return {"state": HealthState.HEALTHY.value if self.started else HealthState.UNKNOWN.value}


async def main() -> int:
    # --- Setup: use temp data_dir so example leaves no trace ---
    with tempfile.TemporaryDirectory(prefix="aegis-p02-example-") as tmp:
        tmpdir = Path(tmp)
        os.environ["AEGIS_DATA_DIR"] = str(tmpdir)

        # 1. Configuration
        cfg = ConfigLoader().build(runtime_overrides={"logging": {"level": "INFO", "format": "development"}})
        configure_root_logger(level=cfg.log_level(), format=cfg.logging["format"])
        log = get_logger("example.main")
        log.notice("=== AEGIS Prompt 02 Core Runtime Example ===", instance=cfg.aegis["instance_id"])

        # 2. Dependency Injection
        di = DIContainer()
        di.register_singleton("config", cfg)
        di.register("heartbeat", Lifetime.SINGLETON, lambda: _HeartbeatService())
        di.register("greeter", Lifetime.SINGLETON, lambda: _GreeterService(), deps=["heartbeat"])

        # 3. Health Aggregator
        agg = HealthAggregator()

        # 4. Event Bus
        bus = CoreEventBus(durable=False, dead_letter_enabled=True)
        bus.start()
        received_events: list[EventEnvelope] = []
        bus.subscribe(EXAMPLE_TOPIC, lambda ev: received_events.append(ev))

        # 5. Core Runtime
        rt = CoreRuntime(
            startup_timeout=float(cfg.aegis.get("startup_timeout_seconds", 30)),
            shutdown_timeout=float(cfg.aegis.get("shutdown_timeout_seconds", 10)),
            instance_id=cfg.aegis["instance_id"],
        )
        hb = di.resolve("heartbeat")
        gr = di.resolve("greeter")
        sid_hb = rt.register_service(
            hb,
            depends_on=[],
            info=ServiceInfo(service_id="example.heartbeat", name="Heartbeat", version="0.1.0"),
        )
        sid_gr = rt.register_service(
            gr,
            depends_on=[sid_hb],
            info=ServiceInfo(service_id="example.greeter", name="Greeter", version="0.1.0"),
        )
        rt.register_health_aggregator(agg)

        async def health_check_heartbeat():
            from aegis import ComponentHealth, HealthState
            h = hb.health()
            state = HealthState(h.get("state", "unknown"))
            return ComponentHealth(component="heartbeat", state=state, latency_ms=0.1, details=h)

        async def health_check_greeter():
            from aegis import ComponentHealth, HealthState
            h = gr.health()
            state = HealthState(h.get("state", "unknown"))
            return ComponentHealth(component="greeter", state=state, latency_ms=0.1, details=h)

        agg.register_check("heartbeat", health_check_heartbeat, timeout_seconds=1.0)
        agg.register_check("greeter", health_check_greeter, timeout_seconds=1.0)

        # 6. Start Runtime with correlation context
        with CorrelationContext.new(metadata={"example": "p02"}).enter() as ctx:
            log.info("Starting CoreRuntime", correlation_id=str(ctx.correlation_id)[:8])
            await rt.start()
            assert rt.state == RuntimeState.RUNNING
            log.info("Runtime RUNNING", services=list(rt._services.keys()))  # type: ignore[attr-defined]

            # 7. Publish event
            env = bus.publish(
                "hello.world",
                {"greeting": "from AEGIS Prompt 02"},
                topic=EXAMPLE_TOPIC,
                source="example.main",
                metadata={"example_version": "p02"},
            )
            log.info("Published event", event_id=str(env.event_id)[:8], type=env.event_type)
            assert len(received_events) == 1

            # 8. Background task: heartbeat that increments beat counter every 10ms
            btm = BackgroundTaskManager(
                event_bus=bus,
                default_retry=RetryPolicy(max_attempts=2, base_backoff_seconds=0.001, jitter=0.0),
            )
            btm.start()
            loop = asyncio.get_running_loop()

            async def beat_task():
                # 5 beats, 10ms apart
                for _ in range(5):
                    hb.beats.append(1)
                    await asyncio.sleep(0.01)
                return len(hb.beats)

            beat_tid = btm.submit(loop, beat_task, name="heartbeat")
            await asyncio.sleep(0.2)  # allow task to finish

            info = btm.get(beat_tid)
            log.info(
                "Background task finished",
                name=info.name,
                state=info.state.value,
                result=info.result,
                attempts=info.attempts,
            )

            # 9. Check runtime health
            report = await agg.check_all()
            log.info(
                "Health report",
                overall=report.overall.value,
                total_components=len(report.components),
                duration_ms=report.duration_ms,
            )
            assert report.overall == HealthState.HEALTHY

            # 10. Graceful shutdown
            log.info("Graceful shutdown begin", timeout_seconds=cfg.aegis.get("shutdown_timeout_seconds"))
            await btm.graceful_shutdown(timeout=2.0)
            await rt.stop()
            await bus.astop()
            assert rt.state == RuntimeState.STOPPED
            log.notice("=== AEGIS Prompt 02 Core Runtime Example: SUCCESS ===")
            return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
