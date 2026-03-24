"""Tests for Sub-Agent system (SubAgent, Registry, Runner, Middleware)."""

import pytest

from myaicoder.core.middleware.base import ContextPayload
from myaicoder.core.middleware.subagent import SubAgentMiddleware
from myaicoder.core.subagent.base import SubAgent
from myaicoder.core.subagent.registry import SubAgentRegistry
from myaicoder.core.subagent.runner import SubAgentRunner
from myaicoder.llm.base import LLMProvider, LLMResponse, Message, Usage


class MockLLM(LLMProvider):
    def __init__(self, response: str = "done"):
        self._response = response

    async def chat(self, messages, tools=None, temperature=0.0):
        return LLMResponse(content=self._response)

    async def chat_stream(self, messages, tools=None, temperature=0.0):
        yield self._response

    async def health_check(self):
        return True


# --- SubAgent ---

class TestSubAgent:
    def test_basic_creation(self):
        agent = SubAgent(name="test", description="A test agent")
        assert agent.name == "test"
        assert agent.max_iterations == 15
        assert agent.tools_override is None

    def test_with_keywords(self):
        agent = SubAgent(
            name="file-ops", description="File operations",
            keywords=["file", "read", "write"],
        )
        assert len(agent.keywords) == 3


# --- SubAgentRegistry ---

class TestSubAgentRegistry:
    def test_register_and_get(self):
        reg = SubAgentRegistry()
        agent = SubAgent(name="coder", description="Code writing agent")
        reg.register(agent)
        assert reg.get("coder") is agent

    def test_get_nonexistent(self):
        reg = SubAgentRegistry()
        assert reg.get("missing") is None

    def test_find_best_by_keywords(self):
        reg = SubAgentRegistry()
        reg.register(SubAgent(
            name="reviewer", description="Code review",
            keywords=["review", "check"],
        ))
        reg.register(SubAgent(
            name="writer", description="Code writing",
            keywords=["write", "create"],
        ))
        found = reg.find_best("please review this code")
        assert found.name == "reviewer"

    def test_find_best_by_description(self):
        reg = SubAgentRegistry()
        reg.register(SubAgent(name="tester", description="testing automation"))
        found = reg.find_best("run the testing suite")
        assert found.name == "tester"

    def test_find_best_fallback_to_general(self):
        reg = SubAgentRegistry()
        reg.register(SubAgent(name="specific", description="very specific"))
        found = reg.find_best("completely unrelated task about cooking")
        assert found.name == "general"

    def test_list_agents(self):
        reg = SubAgentRegistry()
        reg.register(SubAgent(name="a", description="agent a"))
        reg.register(SubAgent(name="b", description="agent b"))
        assert len(reg.list_agents()) == 2

    def test_len(self):
        reg = SubAgentRegistry()
        assert len(reg) == 0
        reg.register(SubAgent(name="x", description="x"))
        assert len(reg) == 1


# --- SubAgentRunner ---

class TestSubAgentRunner:
    @pytest.mark.asyncio
    async def test_run_returns_result(self):
        runner = SubAgentRunner(llm=MockLLM("sub-agent result"))
        result = await runner.run(task="do something")
        assert "sub-agent result" in result

    @pytest.mark.asyncio
    async def test_max_depth_exceeded(self):
        runner = SubAgentRunner(
            llm=MockLLM(), _depth=SubAgentRunner.MAX_DEPTH
        )
        result = await runner.run(task="nested task")
        assert "Maximum sub-agent depth" in result

    @pytest.mark.asyncio
    async def test_ds02_output_boundary(self):
        """DS-02: Results exceeding MAX_RESULT_TOKENS are compressed."""
        long_response = "x" * (SubAgentRunner.MAX_RESULT_TOKENS * 4 + 1000)
        runner = SubAgentRunner(llm=MockLLM(long_response))
        result = await runner.run(task="large task")
        assert len(result) <= SubAgentRunner.MAX_RESULT_TOKENS * 4 + 100  # margin for markers
        assert "compressed" in result

    @pytest.mark.asyncio
    async def test_short_result_not_compressed(self):
        runner = SubAgentRunner(llm=MockLLM("short"))
        result = await runner.run(task="quick task")
        assert result == "short"
        assert "compressed" not in result

    def test_depth_property(self):
        runner = SubAgentRunner(llm=MockLLM(), _depth=2)
        assert runner.depth == 2

    @pytest.mark.asyncio
    async def test_run_with_named_agent(self):
        reg = SubAgentRegistry()
        reg.register(SubAgent(
            name="helper", description="Helps",
            system_prompt="Be helpful.",
        ))
        runner = SubAgentRunner(llm=MockLLM("helped"), registry=reg)
        result = await runner.run(task="help me", agent_name="helper")
        assert "helped" in result


# --- SubAgentMiddleware ---

class TestSubAgentMiddleware:
    def _make_middleware(self) -> SubAgentMiddleware:
        reg = SubAgentRegistry()
        reg.register(SubAgent(name="coder", description="Code writing"))
        runner = SubAgentRunner(llm=MockLLM("task done"), registry=reg)
        return SubAgentMiddleware(runner=runner, registry=reg)

    @pytest.mark.asyncio
    async def test_before_injects_task_tool(self):
        mw = self._make_middleware()
        payload = await mw.before(ContextPayload())
        tool_names = [t["function"]["name"] for t in payload.tools]
        assert "task" in tool_names

    @pytest.mark.asyncio
    async def test_before_lists_agents(self):
        mw = self._make_middleware()
        payload = await mw.before(ContextPayload())
        assert any("coder" in s for s in payload.system_instructions)

    @pytest.mark.asyncio
    async def test_handle_task_tool(self):
        mw = self._make_middleware()
        result = await mw.handle_tool("task", {"description": "write code"})
        assert result is not None
        assert result.success
        assert "task done" in result.output

    @pytest.mark.asyncio
    async def test_handle_task_empty_description(self):
        mw = self._make_middleware()
        result = await mw.handle_tool("task", {"description": ""})
        assert result is not None
        assert not result.success

    @pytest.mark.asyncio
    async def test_handle_ignores_other_tools(self):
        mw = self._make_middleware()
        result = await mw.handle_tool("read_file", {})
        assert result is None

    def test_name_and_priority(self):
        mw = self._make_middleware()
        assert mw.name == "subagent"
        assert mw.priority == 40
