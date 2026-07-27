from aegis.l3_intelligence.ai_kernel.conversation import (
    Conversation, ConversationMessage, estimate_token_count,
)
from aegis.l1_core.interfaces.llm import ChatMessage

c = Conversation(id='conv-001', max_context_tokens=100)
assert c.id == 'conv-001'
assert len(c.messages) == 0
assert c.created_at <= c.updated_at

c.prepend_system('You are helpful.')
assert len(c.messages) == 1
assert c.messages[0].role == 'system'
assert c.system_instruction == 'You are helpful.'

c.prepend_system('You are very helpful.')
assert len(c.messages) == 1
assert c.messages[0].content == 'You are very helpful.'

c.append(ChatMessage(role='user', content='hi'))
c.append({'role': 'assistant', 'content': 'hello', 'estimated_tokens': 5})
c.append(ConversationMessage(role='user', content='How are you?', estimated_tokens=10))
assert len(c.messages) == 4

chats = c.to_chat_messages()
assert len(chats) == 4
assert all(isinstance(m, ChatMessage) for m in chats)

external_total = estimate_token_count(chats)
total = c.estimate_tokens(fn=lambda msgs: estimate_token_count(msgs, 3.5))
assert total == external_total
assert sum(m.estimated_tokens for m in c.messages) == total

total2 = c.estimate_tokens()
assert total2 == total

c.messages[1].estimated_tokens = 10
c.messages[2].estimated_tokens = 10
c.messages[3].estimated_tokens = 80
c.messages[0].estimated_tokens = 5
removed = c.prune_to_limit(max_tokens=50, keep_system=True)
assert c.messages[0].role == 'system'
assert sum(m.estimated_tokens for m in c.messages) <= 50
assert len(removed) >= 1
assert all(r.role != 'system' for r in removed)

c.clear(keep_system=True)
assert len(c.messages) == 1
assert c.messages[0].role == 'system'
assert c.messages[0].estimated_tokens == 0

c.clear(keep_system=False)
assert len(c.messages) == 0

try:
    c.append(42)
    assert False
except TypeError:
    pass

assert estimate_token_count([]) == 0

msgs = [ChatMessage(
    role='assistant',
    content=None,
    name=None,
    tool_calls=[{'name': 'search', 'arguments': '{}'}],
    tool_call_id='call_123',
)]
assert estimate_token_count(msgs) > 0

print('ALL TESTS PASSED')
