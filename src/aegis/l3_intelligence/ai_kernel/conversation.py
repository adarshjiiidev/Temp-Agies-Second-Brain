"""§18 Provider-neutral conversation abstraction.

Short-lived in-memory conversation state only. Long-term persistence / memory
is the responsibility of the L4 subsystem (handled separately). This module
depends only on L1 ChatMessage interface plus Python stdlib.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Iterator

from aegis.l1_core.interfaces.llm import ChatMessage


@dataclass
class ConversationMessage:
    role: str
    content: Any = None
    name: str | None = None
    tool_calls: list[Any] | None = None
    tool_call_id: str | None = None
    ts: float = field(default_factory=time.time)

    def to_chat_message(self) -> ChatMessage:
        return ChatMessage(
            role=self.role,
            content=self.content,
            name=self.name,
            tool_calls=self.tool_calls,
            tool_call_id=self.tool_call_id,
        )


class Conversation:
    def __init__(
        self,
        conversation_id: str | None = None,
        *,
        system_instruction: str | None = None,
        model_id_last_used: str | None = None,
        estimated_tokens_total: int = 0,
        context_window_limit: int | None = None,
    ) -> None:
        if conversation_id is None:
            conversation_id = f"conv_{uuid.uuid4().hex[:12]}"
        self._conversation_id: str = conversation_id
        self._messages: list[ConversationMessage] = []
        self.system_instruction: str | None = system_instruction
        self.model_id_last_used: str | None = model_id_last_used
        self.estimated_tokens_total: int = estimated_tokens_total
        self.context_window_limit: int | None = context_window_limit

    @property
    def id(self) -> str:
        return self._conversation_id

    @property
    def messages(self) -> list[ConversationMessage]:
        return list(self._messages)

    def add_message(self, role: str, content: Any, **kw: Any) -> ConversationMessage:
        msg = ConversationMessage(role=role, content=content, **kw)
        self._messages.append(msg)
        return msg

    def add_system(self, content: str, **kw: Any) -> ConversationMessage:
        return self.add_message("system", content, **kw)

    def add_user(self, content: Any, **kw: Any) -> ConversationMessage:
        return self.add_message("user", content, **kw)

    def add_assistant(self, content: Any, *, tool_calls: Any = None, **kw: Any) -> ConversationMessage:
        return self.add_message("assistant", content, tool_calls=tool_calls, **kw)

    def add_tool(self, tool_call_id: str, content: Any, **kw: Any) -> ConversationMessage:
        return self.add_message("tool", content, tool_call_id=tool_call_id, **kw)

    def to_chat_messages(self, *, system_instruction_prefix: str | None = None) -> list[ChatMessage]:
        result: list[ChatMessage] = []
        prefix = system_instruction_prefix if system_instruction_prefix is not None else self.system_instruction
        if prefix is not None:
            result.append(ChatMessage(role="system", content=prefix))
        for msg in self._messages:
            result.append(msg.to_chat_message())
        return result

    def estimate_tokens(
        self,
        *,
        per_message_overhead: int = 4,
        approx_chars_per_token: float = 3.5,
    ) -> int:
        total_chars = 0
        for msg in self._messages:
            if msg.content is not None:
                total_chars += len(str(msg.content))
            if msg.name is not None:
                total_chars += len(msg.name)
        if approx_chars_per_token <= 0:
            estimated = total_chars + per_message_overhead * len(self._messages)
        else:
            estimated = int(total_chars / approx_chars_per_token) + per_message_overhead * len(self._messages)
        self.estimated_tokens_total = estimated
        return estimated

    def fits_context(self, estimated_output_tokens: int = 1024) -> bool:
        if self.context_window_limit is None:
            return True
        return self.estimate_tokens() + estimated_output_tokens <= self.context_window_limit

    def trim(self, max_messages: int | None = None, max_chars: int | None = None) -> int:
        removed = 0
        while True:
            non_system_indices = [i for i, m in enumerate(self._messages) if m.role != "system"]
            if not non_system_indices:
                break
            if max_messages is not None:
                total_count = len(self._messages)
                if total_count <= max_messages:
                    if max_chars is None:
                        break
                else:
                    victim_idx = non_system_indices[0]
                    del self._messages[victim_idx]
                    removed += 1
                    continue
            if max_chars is not None:
                total_chars = 0
                for msg in self._messages:
                    if msg.content is not None:
                        total_chars += len(str(msg.content))
                    if msg.name is not None:
                        total_chars += len(msg.name)
                if total_chars <= max_chars:
                    break
                victim_idx = non_system_indices[0]
                del self._messages[victim_idx]
                removed += 1
                continue
            break
        return removed

    def clear(self) -> None:
        self._messages.clear()

    def __len__(self) -> int:
        return len(self._messages)

    def __iter__(self) -> Iterator[ConversationMessage]:
        return iter(self._messages)
