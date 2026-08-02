"""L6 Planning Engine — Checkpoint definitions.

Checkpoints are verification gates at milestone boundaries.
Import safety: stdlib + pydantic + l6_planning internal only.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from aegis.l6_planning.types import Milestone

__all__ = ["Checkpoint", "CheckpointBuilder"]


class Checkpoint(BaseModel):
    checkpoint_id: str = Field(default_factory=lambda: f"cp-{uuid.uuid4()!s:.8}")
    milestone_id: str
    title: str
    criteria: list[str] = Field(default_factory=list)
    blocking: bool = True       # if True, next milestone cannot start until this passes


class CheckpointBuilder:
    def build(self, milestones: list[Milestone]) -> list[Checkpoint]:
        checkpoints: list[Checkpoint] = []
        for ms in milestones:
            if ms.is_checkpoint:
                checkpoints.append(Checkpoint(
                    milestone_id=ms.milestone_id,
                    title=f"Checkpoint: {ms.title}",
                    criteria=ms.completion_criteria,
                    blocking=True,
                ))
        return checkpoints
