"""Integration tests: MiddlewareEngine with full default stack."""

import pytest

from myaicoder.core.engine import MiddlewareEngine
from myaicoder.llm.base import LLMProvider, LLMResponse, Message, ToolCall, Usage
from myaicoder.tools.base import Tool, ToolResult
from myaicoder.tools.registry import ToolRegistry


class MockLLM(LLMProvider):
    def __init__(self, responses: list[LLMResponse] | None = None):
        self._responses = list(responses or [])
        self._call_count = 0

    async def chat(self, messages, tools=None, temperature=0.0):
        if self._call_count < len(self._responses):
            resp = self._responses[self._call_count]
            self._call_count += 1
            return resp
        return LLMResponse(content="default")

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
        return "Echo"

    @property
    def parameters_schema(self) -> dict:
        return {"type": "object", "properties": {"text": {"type": "string"}}}

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, output=kwargs.get("text", ""))


class TestDefaultStackIntegration:
    """Verify MiddlewareEngine's default stack contains all 6 middlewares."""

    def test_default_stack_has_all_middlewares(self):
        registry = ToolRegistry()
        registry.register(EchoTool())
        engine = MiddlewareEngine(
            llm=MockLLM(),
            tool_registry=registry,
            approval_callback=lambda n, a: True,
            require_approval=["echo"],
        )
        names = engine.stack.middleware_names
        assert "hitl" in names
        assert "memory" in names
        assert "planning" in names
        assert "subagent" in names
        assert "filesystem" in names
        assert "summarization" in names
        assert len(names) == 6

    def test_default_stack_priority_order(self):
        registry = ToolRegistry()
        registry.register(EchoTool())
        engine = MiddlewareEngine(
            llm=MockLLM(),
            tool_registry=registry,
            approval_callback=lambda n, a: True,
            require_approval=["x"],
        )
        names = engine.stack.middleware_names
        # hitl(10) < memory(20) < planning(30) < subagent(40) < filesystem(50) < summarization(200)
        assert names.index("hitl") < names.index("memory")
        assert names.index("memory") < names.index("planning")
        assert names.index("planning") < names.index("subagent")
        assert names.index("subagent") < names.index("filesystem")
        assert names.index("filesystem") < names.index("summarization")

    def test_default_stack_without_approval(self):
        engine = MiddlewareEngine(llm=MockLLM(), tool_registry=ToolRegistry())
        names = engine.stack.middleware_names
        assert "hitl" not in names  # No approval callback → no HITL
        assert "memory" in names
        assert "planning" in names

    @pytest.mark.asyncio
    async def test_full_stack_text_response(self):
        engine = MiddlewareEngine(
            llm=MockLLM([LLMResponse(content="hello from full stack")]),
            tool_registry=ToolRegistry(),
        )
        result = await engine.chat("hi")
        assert "hello from full stack" in result

    @pytest.mark.asyncio
    async def test_full_stack_tool_execution(self):
        registry = ToolRegistry()
        registry.register(EchoTool())
        engine = MiddlewareEngine(
            llm=MockLLM([
                LLMResponse(
                    tool_calls=[ToolCall(id="t1", name="echo", arguments={"text": "world"})],
                ),
                LLMResponse(content="echoed"),
            ]),
            tool_registry=registry,
        )
        result = await engine.chat("echo world")
        assert "echoed" in result

    @pytest.mark.asyncio
    async def test_full_stack_write_todos(self):
        """Planning middleware's write_todos should work in full stack."""
        engine = MiddlewareEngine(
            llm=MockLLM([
                LLMResponse(
                    tool_calls=[ToolCall(
                        id="t1", name="write_todos",
                        arguments={"todos": [{"content": "step 1"}, {"content": "step 2"}]},
                    )],
                ),
                LLMResponse(content="plan created"),
            ]),
            tool_registry=ToolRegistry(),
        )
        result = await engine.chat("plan my work")
        assert "plan created" in result

    @pytest.mark.asyncio
    async def test_full_stack_task_delegation(self):
        """SubAgent middleware's task tool should work in full stack.

        The sub-agent uses a separate engine with the same LLM provider,
        so the parent's MockLLM must have enough responses for both
        the sub-agent's internal chat AND the parent's follow-up.
        """
        # Response 1: parent calls task tool
        # Response 2: consumed by sub-agent's internal engine
        # Response 3: parent's final response after getting sub-agent result
        engine = MiddlewareEngine(
            llm=MockLLM([
                LLMResponse(
                    tool_calls=[ToolCall(
                        id="t1", name="task",
                        arguments={"description": "write a function"},
                    )],
                ),
                LLMResponse(content="sub-agent did the work"),  # sub-agent
                LLMResponse(content="delegated"),  # parent final
            ]),
            tool_registry=ToolRegistry(),
        )
        result = await engine.chat("delegate this")
        assert "delegated" in result
