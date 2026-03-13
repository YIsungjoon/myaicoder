"""Tests for ConversationManager."""

from myaicoder.core.conversation import ConversationManager
from myaicoder.llm.base import Message


def test_add_and_get_messages():
    cm = ConversationManager()
    cm.add_message(Message(role="user", content="Hello"))
    cm.add_message(Message(role="assistant", content="Hi there!"))

    messages = cm.get_messages("You are a helpful assistant.")
    assert len(messages) == 3  # system + user + assistant
    assert messages[0].role == "system"
    assert messages[1].role == "user"
    assert messages[2].role == "assistant"


def test_clear():
    cm = ConversationManager()
    cm.add_message(Message(role="user", content="Hello"))
    assert cm.message_count == 1

    cm.clear()
    assert cm.message_count == 0


def test_estimate_tokens():
    cm = ConversationManager()
    cm.add_message(Message(role="user", content="a" * 400))  # ~100 tokens
    assert cm.estimate_tokens() == 100
