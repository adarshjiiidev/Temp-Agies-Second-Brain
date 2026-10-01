import logging
from typing import List, Dict, Any, Callable
from pydantic import BaseModel

log = logging.getLogger("aegis.integrations.ecc")

class AegisSkill(BaseModel):
    id: str
    name: str
    description: str
    category: str
    requirements: List[str]
    tools: List[str]
    risk: str
    permissions: List[str]
    source: str = "ECC"
    
class EccSkillRegistry:
    """
    Normalizes and registers ECC skills into the AEGIS Skill Registry.
    """
    def __init__(self):
        self.skills: Dict[str, AegisSkill] = {}
        log.info("ECC Skill Registry initialized")
        
    def import_ecc_skill(self, ecc_skill_def: dict) -> AegisSkill:
        """Normalize an ECC skill definition into AEGIS format."""
        skill = AegisSkill(
            id=ecc_skill_def.get("id", "unknown"),
            name=ecc_skill_def.get("name", "Unnamed Skill"),
            description=ecc_skill_def.get("desc", ""),
            category=ecc_skill_def.get("category", "General"),
            requirements=ecc_skill_def.get("reqs", []),
            tools=ecc_skill_def.get("tools", []),
            risk=ecc_skill_def.get("risk", "Low"),
            permissions=ecc_skill_def.get("perms", []),
            source="ECC"
        )
        self.skills[skill.id] = skill
        return skill

class EccHookAdapter:
    """
    Maps ECC hook patterns into the AEGIS global event bus.
    """
    def __init__(self, event_bus: Callable[[str, dict], None]):
        self.event_bus = event_bus
        
    def trigger_ecc_hook(self, hook_type: str, context: dict):
        """Map ECC hook types to AEGIS bus."""
        mapping = {
            "on_start": "session.created",
            "pre_tool": "tool.before",
            "post_tool": "tool.after",
            "on_file_change": "file.edited"
        }
        aegis_event = mapping.get(hook_type, f"ecc.{hook_type}")
        self.event_bus(aegis_event, context)

# Singletons
ecc_registry = EccSkillRegistry()
