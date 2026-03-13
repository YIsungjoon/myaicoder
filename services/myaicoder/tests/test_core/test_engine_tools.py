"""Tests for AgentEngine with tool execution (agentic loop)."""

import pytest

from myaicoder.core.engine import AgentEngine
from myaicoder.llm.base import LLMResponse, ToolCall, Usage
from myaicoder.tools.registry import create_default_registry

from tests.conftest import MockLLMProvider


@pytest.fixture
def tool_registry():
    return create_default_registry()


class TestAgenticLoop:
    @pytest.mark.asyncio
    async def test_no_tool_call(self, tool_registry):
        """LLM returns text only → no tool execution."""
        llm = MockLLMProvider(["Just a text response."])
        engine = AgentEngine(llm=llm, tool_registry=tool_registry)
        result = await engine.chat("Hello")
        assert result == "Just a text response."

    @pytest.mark.asyncio
    async def test_tool_call_then_response(self, tool_registry, tmp_path):
        """LLM calls Read tool, then responds with text."""
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("file content here\n")

        # Response 1: tool call to Read
        # Response 2: final text
        responses = [
            LLMResponse(
                content=None,
                tool_calls=[
                    ToolCall(id="call_1", name="Read", arguments={"file_path": str(test_file)})
                ],
                usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            ),
            LLMResponse(
                content="The file contains: file content here",
                usage=Usage(prompt_tokens=20, completion_tokens=10, total_tokens=30),
            ),
        ]
        llm = MockLLMProvider(responses)
        engine = AgentEngine(llm=llm, tool_registry=tool_registry)
        result = await engine.chat("Read the test file")
        assert "file content here" in result

    @pytest.mark.asyncio
    async def test_unknown_tool(self, tool_registry):
        """LLM calls unknown tool → error result fed back."""
        responses = [
            LLMResponse(
                content=None,
                tool_calls=[
                    ToolCall(id="call_1", name="UnknownTool", arguments={})
                ],
                usage=Usage(),
            ),
            LLMResponse(
                content="Sorry, that tool is not available.",
                usage=Usage(),
            ),
        ]
        llm = MockLLMProvider(responses)
        engine = AgentEngine(llm=llm, tool_registry=tool_registry)
        result = await engine.chat("Do something")
        assert "not available" in result.lower()

    @pytest.mark.asyncio
    async def test_bash_tool_in_loop(self, tool_registry):
        """LLM calls Bash tool."""
        responses = [
            LLMResponse(
                content=None,
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="Bash",
                        arguments={"command": "echo 'test output'"},
                    )
                ],
                usage=Usage(),
            ),
            LLMResponse(
                content="The command output was: test output",
                usage=Usage(),
            ),
        ]
        llm = MockLLMProvider(responses)
        engine = AgentEngine(llm=llm, tool_registry=tool_registry)
        result = await engine.chat("Run echo command")
        assert "test output" in result

    @pytest.mark.asyncio
    async def test_engine_without_tools(self):
        """Engine without tools behaves like Phase 1."""
        llm = MockLLMProvider(["Simple response"])
        engine = AgentEngine(llm=llm)
        result = await engine.chat("Hello")
        assert result == "Simple response"


class TestRetryAndTruncation:
    def test_is_retryable_error(self, tool_registry):
        llm = MockLLMProvider()
        engine = AgentEngine(llm=llm, tool_registry=tool_registry)

        # Retryable errors
        assert engine._is_retryable_error("File not found") is True
        assert engine._is_retryable_error("Invalid parameter value") is True

        # Non-retryable errors
        assert engine._is_retryable_error("Permission denied") is False
        assert engine._is_retryable_error("Connection refused") is False
        assert engine._is_retryable_error("Auth token expired") is False

        # Edge cases
        assert engine._is_retryable_error(None) is False
        assert engine._is_retryable_error("") is False

    def test_truncate_tool_result(self, tool_registry):
        llm = MockLLMProvider()
        engine = AgentEngine(llm=llm, tool_registry=tool_registry)

        # Short result: unchanged
        short = "Hello"
        assert engine._truncate_tool_result(short) == short

        # Long result: truncated
        long = "x" * 20000
        result = engine._truncate_tool_result(long, max_tokens=10)
        assert len(result) < 20000
        assert "truncated" in result
        assert "20000 chars total" in result
