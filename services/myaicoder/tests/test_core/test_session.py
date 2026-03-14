"""Tests for session persistence (conversation-persistence feature).

T1~T20: SessionStore, serialization, atomic write, prune, self-healing.
"""

import json
import re

import pytest

from myaicoder.core.conversation import ConversationManager
from myaicoder.core.session import (
    SessionStore,
    _atomic_write,
    _deserialize_message,
    _generate_session_id,
    _generate_title,
    _serialize_message,
)
from myaicoder.llm.base import Message, ToolCall


# ── Fixtures ──


@pytest.fixture
def sessions_dir(tmp_path):
    """Temporary sessions directory."""
    d = tmp_path / "sessions"
    d.mkdir()
    return d


@pytest.fixture
def store(sessions_dir):
    """SessionStore with temp directory."""
    return SessionStore(sessions_dir=sessions_dir)


@pytest.fixture
def conversation():
    """ConversationManager with some messages."""
    cm = ConversationManager()
    cm.add_message(Message(role="user", content="Hello, analyze this code"))
    cm.add_message(Message(role="assistant", content="Sure, let me look at it."))
    return cm


@pytest.fixture
def conversation_with_tools():
    """ConversationManager with tool call messages."""
    cm = ConversationManager()
    cm.add_message(Message(role="user", content="Read the gateway code"))
    cm.add_message(
        Message(
            role="assistant",
            content=None,
            tool_calls=[
                ToolCall(id="tc_1", name="Read", arguments={"path": "app/main.py"})
            ],
        )
    )
    cm.add_message(
        Message(role="tool", content="import fastapi...", tool_call_id="tc_1")
    )
    cm.add_message(
        Message(role="assistant", content="The gateway uses FastAPI...")
    )
    return cm


# ── T1: Session ID format ──


def test_generate_session_id_format():
    sid = _generate_session_id()
    # Format: YYYYMMDD_HHMMSSfff_XXXX
    assert re.match(r"\d{8}_\d{9}_[0-9a-f]{4}", sid), f"Invalid format: {sid}"


# ── T2: Session ID uniqueness ──


def test_generate_session_id_uniqueness():
    ids = {_generate_session_id() for _ in range(100)}
    assert len(ids) == 100, "Session IDs should be unique"


# ── T3: Serialize simple message ──


def test_serialize_message_simple():
    msg = Message(role="user", content="Hello")
    d = _serialize_message(msg)
    assert d == {"role": "user", "content": "Hello"}


# ── T4: Serialize message with tool_calls ──


def test_serialize_message_tool_calls():
    msg = Message(
        role="assistant",
        content=None,
        tool_calls=[ToolCall(id="tc_1", name="Read", arguments={"path": "x"})],
    )
    d = _serialize_message(msg)
    assert d["role"] == "assistant"
    assert len(d["tool_calls"]) == 1
    assert d["tool_calls"][0]["name"] == "Read"
    assert "content" not in d  # None content omitted


# ── T5: Serialize tool result ──


def test_serialize_message_tool_result():
    msg = Message(role="tool", content="file contents", tool_call_id="tc_1")
    d = _serialize_message(msg)
    assert d == {"role": "tool", "content": "file contents", "tool_call_id": "tc_1"}


# ── T6: Deserialize simple message ──


def test_deserialize_message_simple():
    d = {"role": "user", "content": "Hello"}
    msg = _deserialize_message(d)
    assert msg.role == "user"
    assert msg.content == "Hello"
    assert msg.tool_calls is None


# ── T7: Deserialize with malformed tool_call ──


def test_deserialize_message_malformed_tool_call():
    d = {
        "role": "assistant",
        "tool_calls": [
            {"id": "tc_1", "name": "Read", "arguments": {"path": "x"}},
            {"bad": "data"},  # malformed — should be skipped
        ],
    }
    msg = _deserialize_message(d)
    assert msg.tool_calls is not None
    assert len(msg.tool_calls) == 1
    assert msg.tool_calls[0].name == "Read"


# ── T8: Roundtrip serialization ──


def test_roundtrip_serialization():
    original = Message(
        role="assistant",
        content="Analyzing...",
        tool_calls=[
            ToolCall(id="tc_1", name="Read", arguments={"path": "app.py"}),
            ToolCall(id="tc_2", name="Grep", arguments={"pattern": "def"}),
        ],
    )
    d = _serialize_message(original)
    restored = _deserialize_message(d)
    assert restored.role == original.role
    assert restored.content == original.content
    assert len(restored.tool_calls) == 2
    assert restored.tool_calls[0].id == "tc_1"
    assert restored.tool_calls[1].arguments == {"pattern": "def"}


# ── T9: Save and load ──


def test_save_and_load(store, conversation):
    data = store.save(conversation)
    loaded = store.load(data.id)
    assert loaded.id == data.id
    assert loaded.title == "Hello, analyze this code"
    assert loaded.message_count == 2
    assert len(loaded.messages) == 2


# ── T10: Save includes summary and compression_count (FB-1) ──


def test_save_includes_summary_and_compression_count(store):
    cm = ConversationManager()
    cm.add_message(Message(role="user", content="Test message"))
    cm.add_message(Message(role="assistant", content="Response"))
    cm._summary = "Previous conversation about gateway analysis"
    cm._compression_count = 3

    data = store.save(cm)
    loaded = store.load(data.id)
    assert loaded.summary == "Previous conversation about gateway analysis"
    assert loaded.compression_count == 3


# ── T11: Load last ──


def test_load_last(store, conversation):
    store.save(conversation)
    # Add second session
    cm2 = ConversationManager()
    cm2.add_message(Message(role="user", content="Second session"))
    cm2.add_message(Message(role="assistant", content="OK"))
    store.save(cm2)

    last = store.load_last()
    assert last is not None
    assert last.title == "Second session"


# ── T12: Load last — no sessions ──


def test_load_last_no_sessions(store):
    result = store.load_last()
    assert result is None


# ── T13: List sessions ──


def test_list_sessions(store, conversation):
    store.save(conversation)
    cm2 = ConversationManager()
    cm2.add_message(Message(role="user", content="Second session"))
    cm2.add_message(Message(role="assistant", content="OK"))
    store.save(cm2)

    sessions = store.list_sessions()
    assert len(sessions) == 2
    # Most recent first
    assert sessions[0]["title"] == "Second session"


# ── T14: Delete session ──


def test_delete_session(store, conversation):
    data = store.save(conversation)
    assert store.delete(data.id) is True
    assert store.load_last() is None
    assert len(store.list_sessions()) == 0


# ── T15: Prune old sessions ──


def test_prune_old_sessions(sessions_dir):
    store = SessionStore(sessions_dir=sessions_dir)
    store.MAX_SESSIONS = 3  # Low limit for testing

    # Save 5 sessions
    for i in range(5):
        cm = ConversationManager()
        cm.add_message(Message(role="user", content=f"Session {i}"))
        cm.add_message(Message(role="assistant", content="OK"))
        store.save(cm)

    sessions = store.list_sessions()
    assert len(sessions) == 3
    # Newest sessions should survive
    assert sessions[0]["title"] == "Session 4"


# ── T16: Atomic write ──


def test_atomic_write(tmp_path):
    path = tmp_path / "test.json"
    _atomic_write(path, '{"key": "value"}')
    assert path.exists()
    assert json.loads(path.read_text()) == {"key": "value"}
    # No .tmp file left
    assert not path.with_suffix(".tmp").exists()


# ── T17: Generate title ──


def test_generate_title():
    assert _generate_title("Analyze the gateway code") == "Analyze the gateway code"
    assert len(_generate_title("x" * 100)) == 50  # Truncated


# ── T18: Generate title — empty ──


def test_generate_title_empty():
    assert _generate_title("") == "Untitled session"
    assert _generate_title("   ") == "Untitled session"


# ── T19: Index self-healing ──


def test_index_self_healing(store, conversation, sessions_dir):
    data = store.save(conversation)

    # Manually delete session file (simulate corruption)
    session_file = sessions_dir / f"session_{data.id}.json"
    session_file.unlink()

    # Index should self-heal
    sessions = store.list_sessions()
    assert len(sessions) == 0

    # last_session_id should also be fixed
    index = json.loads((sessions_dir / "_index.json").read_text())
    assert index["last_session_id"] is None


# ── T20: Save empty conversation ──


def test_save_empty_conversation(store):
    cm = ConversationManager()
    with pytest.raises(ValueError, match="Cannot save empty conversation"):
        store.save(cm)
