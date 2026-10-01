import logging
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod

log = logging.getLogger("aegis.integrations.agents")

class UniversalIdeAdapter(ABC):
    """
    Universal adapter interface for AI IDEs and Coding Agents 
    (OpenCode, Codex, Claude, Cursor, Copilot, Hermes, etc.).
    """
    
    @abstractmethod
    async def discover(self) -> bool:
        """Detect if this IDE/agent is installed and available."""
        pass
        
    @abstractmethod
    async def health(self) -> str:
        """Check health status."""
        return "NOT_SUPPORTED"

    @abstractmethod
    async def capabilities(self) -> List[str]:
        """List capabilities."""
        return []
        
    @abstractmethod
    async def start(self) -> bool:
        pass
        
    @abstractmethod
    async def stop(self) -> bool:
        pass
        
    @abstractmethod
    async def status(self) -> str:
        pass
        
    @abstractmethod
    async def send_task(self, task_id: str, context: dict) -> bool:
        pass
        
    @abstractmethod
    async def get_session(self, session_id: str) -> dict:
        pass
        
    @abstractmethod
    async def get_events(self, session_id: str) -> List[dict]:
        pass
        
    @abstractmethod
    async def get_result(self, session_id: str) -> dict:
        pass
        
    @abstractmethod
    async def ingest(self, session_id: str) -> bool:
        """Extract and normalize chat logs into AEGIS Obsidian/Memory."""
        pass
