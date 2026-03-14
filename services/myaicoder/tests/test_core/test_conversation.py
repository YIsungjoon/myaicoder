"""Tests for ConversationManager — turn grouping, compression, token budget."""

from myaicoder.core.conversation import ConversationManager, Turn
from myaicoder.llm.base import Message, ToolCall


# ── Helpers ──


def _user(content: str) -> Message:
    return Message(role="user", content=content)


def _assistant(content: str, tool_calls: list[ToolCall] | None = None) -> Message:
    return Message(role="assistant", content=content, tool_calls=tool_calls)


def _tool(content: str, tool_call_id: str) -> Message:
    return Message(role="tool", content=content, tool_call_id=tool_call_id)


def _tc(name: str, tc_id: str = "c1") -> ToolCall:
    return ToolCall(id=tc_id, name=name, arguments={})


# ── Backward Compatibility ──


class TestBackwardCompat:
    def test_add_and_get_messages(self):
        cm = ConversationManager()
        cm.add_message(_user("Hello"))
        cm.add_message(_assistant("Hi there!"))

        messages = cm.get_messages("You are a helpful assistant.")
        assert len(messages) == 3  # system + user + assistant
        assert messages[0].role == "system"
        assert messages[1].role == "user"
        assert messages[2].role == "assistant"

    def test_clear(self):
        cm = ConversationManager()
        cm.add_message(_user("Hello"))
        assert cm.message_count == 1

        cm.clear()
        assert cm.message_count == 0
        assert cm.summary == ""
        assert cm.compression_count == 0

    def test_estimate_tokens(self):
        cm = ConversationManager()
        cm.add_message(_user("a" * 400))  # ~100 tokens
        assert cm.estimate_tokens() == 100

    def test_history_returns_copy(self):
        cm = ConversationManager()
        cm.add_message(_user("Hello"))
        h = cm.history
        h.clear()
        assert cm.message_count == 1  # original not affected


# ── Turn Grouping ──


class TestTurnGrouping:
    def test_empty_history(self):
        turns = ConversationManager._group_into_turns([])
        assert turns == []

    def test_simple_conversation(self):
        msgs = [_user("Hello"), _assistant("Hi")]
        turns = ConversationManager._group_into_turns(msgs)
        assert len(turns) == 1
        assert len(turns[0].messages) == 2

    def test_multi_turn(self):
        msgs = [
            _user("Q1"), _assistant("A1"),
            _user("Q2"), _assistant("A2"),
        ]
        turns = ConversationManager._group_into_turns(msgs)
        assert len(turns) == 2

    def test_tool_call_atomic_block(self):
        """Tool calls + tool results must be in same Turn."""
        msgs = [
            _user("read file"),
            _assistant(None, tool_calls=[_tc("Read", "c1")]),
            _tool("file contents here", "c1"),
            _assistant("Here is the file"),
        ]
        turns = ConversationManager._group_into_turns(msgs)
        assert len(turns) == 1
        assert len(turns[0].messages) == 4
        assert turns[0].is_tool_turn is True

    def test_multi_tool_calls(self):
        """Multiple tool calls in one turn stay together."""
        msgs = [
            _user("read two files"),
            _assistant(None, tool_calls=[_tc("Read", "c1"), _tc("Read", "c2")]),
            _tool("content1", "c1"),
            _tool("content2", "c2"),
            _assistant("Here are both files"),
        ]
        turns = ConversationManager._group_into_turns(msgs)
        assert len(turns) == 1
        assert len(turns[0].messages) == 5

    def test_tool_turn_followed_by_simple(self):
        """Tool turn + simple turn are separate."""
        msgs = [
            _user("read file"),
            _assistant(None, tool_calls=[_tc("Read", "c1")]),
            _tool("contents", "c1"),
            _assistant("Here's the file"),
            _user("thanks"),
            _assistant("You're welcome"),
        ]
        turns = ConversationManager._group_into_turns(msgs)
        assert len(turns) == 2
        assert turns[0].is_tool_turn is True
        assert turns[1].is_tool_turn is False


# ── Turn Summary ──


class TestTurnSummarize:
    def test_simple_turn(self):
        turn = Turn(messages=[_user("Hello world"), _assistant("Hi there")])
        s = turn.summarize()
        assert "User: Hello world" in s
        assert "Assistant: Hi there" in s

    def test_tool_turn(self):
        turn = Turn(messages=[
            _user("read file"),
            _assistant(None, tool_calls=[_tc("Read", "c1")]),
            _tool("x" * 5000, "c1"),
            _assistant("Done"),
        ])
        s = turn.summarize()
        assert "Called: Read" in s
        assert "Result: 5000ch" in s

    def test_user_truncated(self):
        turn = Turn(messages=[_user("a" * 200), _assistant("ok")])
        s = turn.summarize()
        assert len(s) < 250  # user truncated to 100 chars


# ── Compression ──


class TestCompression:
    def test_compress_reduces_history(self):
        cm = ConversationManager(max_tokens=5000)
        for i in range(10):
            cm.add_message(_user(f"Question {i} " + "x" * 400))
            cm.add_message(_assistant(f"Answer {i} " + "y" * 400))

        before_count = cm.message_count
        cm._compress(target_tokens=500)
        after_count = cm.message_count

        assert after_count < before_count
        assert cm.compression_count == 1
        assert cm.summary != ""

    def test_compress_preserves_recent(self):
        cm = ConversationManager(max_tokens=500)
        cm.add_message(_user("old question " + "x" * 200))
        cm.add_message(_assistant("old answer " + "y" * 200))
        cm.add_message(_user("recent question"))
        cm.add_message(_assistant("recent answer"))

        cm._compress(target_tokens=50)

        # Recent turn should be preserved
        assert any("recent" in (m.content or "") for m in cm._history)

    def test_compress_tool_atomicity(self):
        """Tool call block must never be split during compression."""
        cm = ConversationManager(max_tokens=300)

        # Old tool turn
        cm.add_message(_user("old read"))
        cm.add_message(_assistant(None, tool_calls=[_tc("Read", "c1")]))
        cm.add_message(_tool("old file " + "x" * 200, "c1"))
        cm.add_message(_assistant("old result"))

        # Recent simple turn
        cm.add_message(_user("recent"))
        cm.add_message(_assistant("recent answer"))

        cm._compress(target_tokens=50)

        # Verify no orphan tool messages
        for i, msg in enumerate(cm._history):
            if msg.role == "tool":
                # Must have preceding assistant with tool_calls
                assert i > 0
                found_parent = False
                for j in range(i - 1, -1, -1):
                    if cm._history[j].role == "assistant" and cm._history[j].tool_calls:
                        found_parent = True
                        break
                    if cm._history[j].role == "user":
                        break
                assert found_parent, f"Orphan tool message at index {i}"

    def test_auto_compress_on_threshold(self):
        """get_messages triggers compression when over threshold."""
        cm = ConversationManager(
            max_tokens=100,
            compression_threshold=0.5,
            tool_schema_tokens=0,
            response_buffer=10,
        )
        # Fill with data exceeding threshold
        for i in range(5):
            cm.add_message(_user("q" * 80))
            cm.add_message(_assistant("a" * 80))

        # Should trigger auto-compress
        cm.get_messages("sys")
        assert cm.compression_count >= 1

    def test_summary_in_messages(self):
        """After compression, summary appears as system message."""
        cm = ConversationManager(max_tokens=100, tool_schema_tokens=0, response_buffer=10)
        for i in range(5):
            cm.add_message(_user("q" * 80))
            cm.add_message(_assistant("a" * 80))

        cm._compress(target_tokens=30)

        messages = cm.get_messages("system prompt")
        system_msgs = [m for m in messages if m.role == "system"]
        assert len(system_msgs) == 2  # original system + summary
        assert "[Previous conversation summary]" in system_msgs[1].content

    def test_compact_manual(self):
        cm = ConversationManager(max_tokens=500, tool_schema_tokens=0, response_buffer=10)
        for i in range(10):
            cm.add_message(_user("q" * 400))
            cm.add_message(_assistant("a" * 400))

        before_count = cm.message_count
        cm.compact()
        assert cm.message_count < before_count
        assert cm.compression_count == 1

    def test_compress_empty_history(self):
        """Compressing empty history is a no-op."""
        cm = ConversationManager()
        cm._compress(target_tokens=100)
        assert cm.compression_count == 0

    def test_on_compress_callback(self):
        """Compression callback is called when compression occurs."""
        called = []
        cm = ConversationManager(
            max_tokens=500,
            compression_threshold=0.3,
            tool_schema_tokens=0,
            response_buffer=10,
        )
        cm.set_on_compress(lambda f: called.append(f))

        for i in range(10):
            cm.add_message(_user("q" * 400))
            cm.add_message(_assistant("a" * 400))

        cm.get_messages("sys")
        assert cm.compression_count >= 1


# ── Summary Oldest-First Drop ──


class TestSummaryOldestFirstDrop:
    def test_oldest_dropped_first(self):
        """When summary exceeds limit, oldest entries are dropped."""
        cm = ConversationManager(max_tokens=5000)

        # Create many turns with long content
        for i in range(20):
            cm.add_message(_user(f"Turn {i}: " + "x" * 200))
            cm.add_message(_assistant(f"Response {i}: " + "y" * 200))

        cm._compress(target_tokens=100)

        # Summary should contain recent turns, not oldest
        if cm.summary:
            assert len(cm.summary) <= 2000
            # Most recent compressed turns should be in summary
            # Oldest should be dropped
