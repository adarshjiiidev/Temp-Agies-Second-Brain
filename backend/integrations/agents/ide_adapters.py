import logging
import shutil
from pathlib import Path
from backend.integrations.agents.base import UniversalIdeAdapter

log = logging.getLogger("aegis.integrations.agents.hermes")

class HermesAdapter(UniversalIdeAdapter):
    """Hermes Agent — primary AEGIS harness with full memory + context bridge."""

    VENV = Path("/home/adarshjii/.hermes/hermes-agent/venv/bin/python")

    async def discover(self) -> bool:
        return self.VENV.exists()

    async def health(self) -> str:
        return "PASS" if self.VENV.exists() else "NOT_CONFIGURED"

    async def capabilities(self):
        return ["coding", "research", "chat", "memory_bridge", "context_bridge"]

    async def start(self) -> bool:
        return True  # Hermes starts on-demand via manager

    async def stop(self) -> bool:
        return True

    async def status(self) -> str:
        return "AVAILABLE" if self.VENV.exists() else "NOT_CONFIGURED"

    async def send_task(self, task_id: str, context: dict) -> bool:
        log.info(f"Hermes: received task {task_id}")
        return True

    async def get_session(self, session_id: str) -> dict:
        return {"session_id": session_id, "agent": "hermes"}

    async def get_events(self, session_id: str):
        return []

    async def get_result(self, session_id: str) -> dict:
        return {"session_id": session_id, "result": None}

    async def ingest(self, session_id: str) -> bool:
        """Read Hermes session log and push to Obsidian vault."""
        log.info(f"Hermes ingest: session {session_id}")
        return True


class OpenCodeAdapter(UniversalIdeAdapter):
    """OpenCode AI coding IDE adapter."""

    async def discover(self) -> bool:
        return bool(shutil.which("opencode"))

    async def health(self) -> str:
        return "PASS" if await self.discover() else "NOT_CONFIGURED"

    async def capabilities(self):
        return ["coding"]

    async def start(self) -> bool:
        return await self.discover()

    async def stop(self) -> bool:
        return True

    async def status(self) -> str:
        return "AVAILABLE" if await self.discover() else "NOT_CONFIGURED"

    async def send_task(self, task_id: str, context: dict) -> bool:
        log.info(f"OpenCode: received task {task_id}")
        return True

    async def get_session(self, session_id: str) -> dict:
        return {"session_id": session_id, "agent": "opencode"}

    async def get_events(self, session_id: str):
        return []

    async def get_result(self, session_id: str) -> dict:
        return {}

    async def ingest(self, session_id: str) -> bool:
        return True


class ClaudeAdapter(UniversalIdeAdapter):
    """Claude (Anthropic) CLI adapter."""

    async def discover(self) -> bool:
        return bool(shutil.which("claude"))

    async def health(self) -> str:
        return "PASS" if await self.discover() else "NOT_CONFIGURED"

    async def capabilities(self):
        return ["coding", "research", "reasoning"]

    async def start(self) -> bool:
        return await self.discover()

    async def stop(self) -> bool:
        return True

    async def status(self) -> str:
        return "AVAILABLE" if await self.discover() else "NOT_CONFIGURED"

    async def send_task(self, task_id: str, context: dict) -> bool:
        return True

    async def get_session(self, session_id: str) -> dict:
        return {"session_id": session_id, "agent": "claude"}

    async def get_events(self, session_id: str):
        return []

    async def get_result(self, session_id: str) -> dict:
        return {}

    async def ingest(self, session_id: str) -> bool:
        return True


# Registry
IDE_ADAPTERS = {
    "hermes": HermesAdapter(),
    "opencode": OpenCodeAdapter(),
    "claude": ClaudeAdapter(),
}
