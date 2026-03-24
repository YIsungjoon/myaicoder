"""Tests for MiddlewareEngine (DS-03: Strangler Fig coexistence with AgentEngine)."""

import pytest

from myaicoder.core.engine import AgentEngine, MiddlewareEngine
from myaicoder.core.middleware.base import AgentMiddleware, ContextPayload
from myaicoder.core.middleware.stack import MiddlewareStack
from myaicoder.llm.base import LLMProvider, LLMResponse, ToolCall
from myaicoder.tools.base import Tool, ToolResult
from myaicoder.tools.registry import ToolRegistry


# --- Test fixtures ---


class MockLLM(LLMProvider):
    def __init__(self, responses: list[LLMResponse] | None = None):
        self._responses = list(responses or [])
        self._call_count = 0

    async def chat(self, messages, tools=None, temperature=0.0):
        if self._call_count < len(self._responses):
            resp = self._responses[self._call_count]
            self._call_count += 1
            return resp
        return LLMResponse(content="default response")

    async def chat_stream(self, messages, tools=None, temperature=0.0):
        yield "streamed"

    async def health_check(self):
        return True


class EchoTool(Tool):
    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echo input"

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        }

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, output=kwargs.get("text", ""))


def make_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(EchoTool())
    return registry


# --- Tests ---


class TestMiddlewareEngineCoexistence:
    """DS-03: Both engines must be importable and functional."""

    def test_both_engines_importable(self):
        assert AgentEngine is not None
        assert MiddlewareEngine is not None

    @pytest.mark.asyncio
    async def test_simple_text_response(self):
        llm = MockLLM([LLMResponse(content="hello")])
        engine = MiddlewareEngine(llm=llm)
        result = await engine.chat("hi")
        assert result == "hello"

    @pytest.mark.asyncio
    async def test_tool_execution_via_middleware(self):
        registry = make_registry()
        llm = MockLLM([
            # First: LLM calls echo tool
            LLMResponse(
                content=None,
                tool_calls=[ToolCall(id="tc1", name="echo", arguments={"text": "world"})],
            ),
            # Second: LLM returns final text
            LLMResponse(content="done"),
        ])
        engine = MiddlewareEngine(llm=llm, tool_registry=registry)
        result = await engine.chat("echo world")
        assert "done" in result

    @pytest.mark.asyncio
    async def test_hitl_approval_deny(self):
        registry = make_registry()
        llm = MockLLM([
            LLMResponse(
                content=None,
                tool_calls=[ToolCall(id="tc1", name="echo", arguments={"text": "x"})],
            ),
            LLMResponse(content="denied path"),
        ])
        engine = MiddlewareEngine(
            llm=llm,
            tool_registry=registry,
            approval_callback=lambda name, args: False,  # Always deny
            require_approval=["echo"],
        )
        result = await engine.chat("test")
        assert "denied path" in result

    @pytest.mark.asyncio
    async def test_custom_middleware_injects_instruction(self):
        class CustomMW(AgentMiddleware):
            @property
            def name(self) -> str:
                return "custom"

            async def before(self, payload: ContextPayload) -> ContextPayload:
                return payload.with_instruction("custom rule")

        llm = MockLLM([LLMResponse(content="ok")])
        stack = MiddlewareStack([CustomMW()])
        engine = MiddlewareEngine(llm=llm, middleware_stack=stack)
        result = await engine.chat("test")
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self):
        llm = MockLLM([
            LLMResponse(
                content=None,
                tool_calls=[ToolCall(id="tc1", name="nonexistent", arguments={})],
            ),
            LLMResponse(content="recovered"),
        ])
        engine = MiddlewareEngine(llm=llm)
        result = await engine.chat("test")
        assert "recovered" in result

    @pytest.mark.asyncio
    async def test_reset_clears_conversation(self):
        llm = MockLLM([LLMResponse(content="first")])
        engine = MiddlewareEngine(llm=llm)
        await engine.chat("hi")
        assert engine.conversation.message_count > 0
        engine.reset()
        assert engine.conversation.message_count == 0

    @pytest.mark.asyncio
    async def test_chat_stream(self):
        llm = MockLLM([LLMResponse(content="streamed result")])
        engine = MiddlewareEngine(llm=llm, tool_registry=make_registry())
        chunks = []
        async for chunk in engine.chat_stream("test"):
            chunks.append(chunk)
        assert len(chunks) > 0


class TestMiddlewareEngineMatchesAgentEngine:
    """Verify MiddlewareEngine produces same results as AgentEngine."""

    @pytest.mark.asyncio
    async def test_same_text_response(self):
        llm1 = MockLLM([LLMResponse(content="result")])
        llm2 = MockLLM([LLMResponse(content="result")])

        old = AgentEngine(llm=llm1)
        new = MiddlewareEngine(llm=llm2)

        r1 = await old.chat("test")
        r2 = await new.chat("test")
        assert r1 == r2

    @pytest.mark.asyncio
    async def test_same_tool_response(self):
        responses = [
            LLMResponse(
                content=None,
                tool_calls=[ToolCall(id="tc1", name="echo", arguments={"text": "hi"})],
            ),
            LLMResponse(content="final"),
        ]

        old = AgentEngine(
            llm=MockLLM(list(responses)),
            tool_registry=make_registry(),
        )
        new = MiddlewareEngine(
            llm=MockLLM(list(responses)),
            tool_registry=make_registry(),
        )

        r1 = await old.chat("echo hi")
        r2 = await new.chat("echo hi")
        assert r1 == r2
