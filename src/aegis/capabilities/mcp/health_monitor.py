"""Capabilities MCP abstraction — MCPHealthMonitor.

Performs periodic health checks on registered MCP servers and updates
their health records in the MCPServerRegistry.

Checks are lightweight: only connectivity, not tool execution.

Import safety: stdlib + aegis.capabilities.mcp.server_registry only.
"""

from __future__ import annotations

import asyncio
import logging
import time
import urllib.error
import urllib.request

from aegis.capabilities.mcp.server_registry import MCPServerRegistry
from aegis.capabilities.mcp.types import MCPTransport
from aegis.capabilities.model.health import CapabilityHealth, HealthStatus

logger = logging.getLogger(__name__)

__all__ = ["MCPHealthMonitor"]

_DEFAULT_CHECK_INTERVAL = 60.0   # seconds
_DEFAULT_TIMEOUT = 3.0
_FAILURE_THRESHOLD = 3            # failures before marking UNAVAILABLE


class MCPHealthMonitor:
    """Async background monitor that health-checks registered MCP servers.

    For HTTP/SSE servers: sends a lightweight GET to the server root or
    a known health endpoint. For STDIO servers: checks if the command exists.

    Usage::

        monitor = MCPHealthMonitor(registry, check_interval=30.0)
        # In async context:
        task = asyncio.create_task(monitor.run())
        # On shutdown:
        monitor.stop()
        await task
    """

    def __init__(
        self,
        registry: MCPServerRegistry,
        check_interval: float = _DEFAULT_CHECK_INTERVAL,
        http_timeout: float = _DEFAULT_TIMEOUT,
        failure_threshold: int = _FAILURE_THRESHOLD,
    ) -> None:
        self._registry = registry
        self._check_interval = check_interval
        self._http_timeout = http_timeout
        self._failure_threshold = failure_threshold
        self._running = False
        self._failure_counts: dict[str, int] = {}

    async def run(self) -> None:
        """Background loop — checks all servers periodically."""
        self._running = True
        logger.info("MCPHealthMonitor: started (interval=%.1fs)", self._check_interval)
        try:
            while self._running:
                await self._check_all()
                await asyncio.sleep(self._check_interval)
        except asyncio.CancelledError:
            pass
        finally:
            logger.info("MCPHealthMonitor: stopped")

    def stop(self) -> None:
        """Signal the run loop to exit on the next iteration."""
        self._running = False

    async def _check_all(self) -> None:
        """Check all registered servers once."""
        servers = self._registry.list_servers()
        for server in servers:
            if not self._running:
                break
            try:
                ok, error = await asyncio.get_event_loop().run_in_executor(
                    None, self._check_server, server.server_id,
                    server.transport, server.endpoint, server.command,
                )
            except Exception as exc:  # noqa: BLE001
                ok, error = False, str(exc)

            self._update_health(server.server_id, ok, error)

    def _check_server(
        self,
        server_id: str,
        transport: MCPTransport,
        endpoint: str,
        command: list[str],
    ) -> tuple[bool, str | None]:
        """Synchronous health check for one server."""
        if transport == MCPTransport.STDIO:
            return self._check_stdio(command)
        return self._check_http(endpoint)

    def _check_http(self, endpoint: str) -> tuple[bool, str | None]:
        """Check HTTP reachability."""
        if not endpoint:
            return False, "No endpoint configured"
        try:
            req = urllib.request.Request(endpoint, method="GET")
            with urllib.request.urlopen(req, timeout=self._http_timeout) as resp:
                _ = resp.read(64)   # Read minimal bytes
            return True, None
        except urllib.error.HTTPError as exc:
            # 4xx means the server is reachable but rejected our request
            # (expected — most MCP endpoints require proper requests)
            if exc.code < 500:
                return True, None
            return False, f"HTTP {exc.code}"
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)

    def _check_stdio(self, command: list[str]) -> tuple[bool, str | None]:
        """Check that the STDIO command binary exists."""
        import shutil
        if not command:
            return False, "No command configured"
        binary = command[0]
        path = shutil.which(binary)
        if path:
            return True, None
        return False, f"Command not found: {binary!r}"

    def _update_health(
        self,
        server_id: str,
        ok: bool,
        error: str | None,
    ) -> None:
        """Update the server's health record based on the check result."""
        if ok:
            self._failure_counts[server_id] = 0
            health = CapabilityHealth(
                status=HealthStatus.AVAILABLE,
                last_checked=time.time(),
                last_error=None,
            )
        else:
            count = self._failure_counts.get(server_id, 0) + 1
            self._failure_counts[server_id] = count
            status = (
                HealthStatus.UNAVAILABLE
                if count >= self._failure_threshold
                else HealthStatus.DEGRADED
            )
            health = CapabilityHealth(
                status=status,
                last_checked=time.time(),
                failure_count=count,
                last_error=error,
            )
        self._registry.update_health(server_id, health)
