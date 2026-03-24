"""Tests for ContextPayload and AgentMiddleware ABC."""

import pytest

from myaicoder.core.middleware.base import AgentMiddleware, ContextPayload
from myaicoder.llm.base import Message
from myaicoder.tools.base import ToolResult


class DummyMiddleware(AgentMiddleware):
    @property
    def name(self) -> str:
        return "dummy"

    async def before(self, payload: ContextPayload) -> ContextPayload:
        return payload.with_instruction("dummy instruction")


class TestContextPayload:
    def test_frozen_immutability(self):
        payload = ContextPayload()
        with pytest.raises(AttributeError):
            payload.system_instructions = ("hack",)  # type: ignore[misc]

    def test_with_instruction_returns_new_payload(self):
        p1 = ContextPayload()
        p2 = p1.with_instruction("hello")
        assert p1.system_instructions == ()
        assert p2.system_instructions == ("hello",)
        assert p1 is not p2

    def test_with_instruction_chaining(self):
        p = (
            ContextPayload()
            .with_instruction("a")
            .with_instruction("b")
            .with_instruction("c")
        )
        assert p.system_instructions == ("a", "b", "c")

    def test_with_tools_returns_new_payload(self):
        p1 = ContextPayload()
        tool = {"type": "function", "function": {"name": "test"}}
        p2 = p1.with_tools([tool])
        assert p1.tools == ()
        assert len(p2.tools) == 1
        assert p2.tools[0]["function"]["name"] == "test"

    def test_with_tools_accumulates(self):
        t1 = {"type": "function", "function": {"name": "a"}}
        t2 = {"type": "function", "function": {"name": "b"}}
        p = ContextPayload().with_tools([t1]).with_tools([t2])
        assert len(p.tools) == 2

    def test_with_metadata_returns_new_payload(self):
        p1 = ContextPayload()
        p2 = p1.with_metadata("key", "value")
        assert p1.metadata == {}
        assert p2.metadata == {"key": "value"}

    def test_messages_preserved(self):
        msgs = (Message(role="user", content="hi"),)
        p = ContextPayload(messages=msgs)
        p2 = p.with_instruction("test")
        assert p2.messages == msgs

    def test_default_values(self):
        p = ContextPayload()
        assert p.messages == ()
        assert p.system_instructions == ()
        assert p.tools == ()
        assert p.metadata == {}


class TestAgentMiddleware:
    @pytest.mark.asyncio
    async def test_dummy_middleware_before(self):
        mw = DummyMiddleware()
        payload = ContextPayload()
        result = await mw.before(payload)
        assert "dummy instruction" in result.system_instructions

    def test_name_property(self):
        mw = DummyMiddleware()
        assert mw.name == "dummy"

    def test_default_priority(self):
        mw = DummyMiddleware()
        assert mw.priority == 100

    @pytest.mark.asyncio
    async def test_default_handle_tool_returns_none(self):
        mw = DummyMiddleware()
        result = await mw.handle_tool("any_tool", {})
        assert result is None

    @pytest.mark.asyncio
    async def test_default_after_passes_through(self):
        mw = DummyMiddleware()
        payload = ContextPayload().with_instruction("keep")
        result = await mw.after(payload)
        assert result is payload
