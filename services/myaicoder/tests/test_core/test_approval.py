"""Tests for tool approval mechanism."""

import pytest

from myaicoder.core.engine import AgentEngine
from myaicoder.llm.base import LLMResponse, ToolCall, Usage
from myaicoder.tools.registry import create_default_registry

from tests.conftest import MockLLMProvider


class TestToolApproval:
    @pytest.mark.asyncio
    async def test_approved_tool_executes(self, tmp_path):
        """Tool executes when user approves."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("approved content\n")

        responses = [
            LLMResponse(
                content=None,
                tool_calls=[
                    ToolCall(id="c1", name="Read", arguments={"file_path": str(test_file)})
                ],
                usage=Usage(),
            ),
            LLMResponse(content="File read successfully.", usage=Usage()),
        ]
        llm = MockLLMProvider(responses)
        registry = create_default_registry()

        # Always approve
        engine = AgentEngine(
            llm=llm,
            tool_registry=registry,
            approval_callback=lambda name, args: True,
            require_approval=["Read"],
        )
        result = await engine.chat("Read the file")
        assert "successfully" in result.lower()

    @pytest.mark.asyncio
    async def test_denied_tool_returns_error(self):
        """Tool returns denial error when user rejects."""
        responses = [
            LLMResponse(
                content=None,
                tool_calls=[
                    ToolCall(id="c1", name="Bash", arguments={"command": "rm -rf /"})
                ],
                usage=Usage(),
            ),
            LLMResponse(content="I understand, the tool was denied.", usage=Usage()),
        ]
        llm = MockLLMProvider(responses)
        registry = create_default_registry()

        # Always deny
        engine = AgentEngine(
            llm=llm,
            tool_registry=registry,
            approval_callback=lambda name, args: False,
            require_approval=["Bash"],
        )
        result = await engine.chat("Delete everything")
        assert "denied" in result.lower() or "understand" in result.lower()

    @pytest.mark.asyncio
    async def test_auto_approve_tools_skip_callback(self, tmp_path):
        """Tools not in require_approval list skip the callback."""
        test_file = tmp_path / "auto.txt"
        test_file.write_text("auto approved\n")

        responses = [
            LLMResponse(
                content=None,
                tool_calls=[
                    ToolCall(id="c1", name="Read", arguments={"file_path": str(test_file)})
                ],
                usage=Usage(),
            ),
            LLMResponse(content="Read auto-approved.", usage=Usage()),
        ]
        llm = MockLLMProvider(responses)
        registry = create_default_registry()

        # Callback would deny, but Read is not in require_approval
        engine = AgentEngine(
            llm=llm,
            tool_registry=registry,
            approval_callback=lambda name, args: False,
            require_approval=["Bash", "Write", "Edit"],  # Read not listed
        )
        result = await engine.chat("Read the file")
        assert "auto-approved" in result.lower()

    @pytest.mark.asyncio
    async def test_no_callback_skips_approval(self):
        """Without callback, all tools execute without approval."""
        responses = [
            LLMResponse(
                content=None,
                tool_calls=[
                    ToolCall(
                        id="c1", name="Bash", arguments={"command": "echo 'hi'"}
                    )
                ],
                usage=Usage(),
            ),
            LLMResponse(content="Command ran.", usage=Usage()),
        ]
        llm = MockLLMProvider(responses)
        registry = create_default_registry()

        # No callback → no approval check
        engine = AgentEngine(
            llm=llm,
            tool_registry=registry,
            require_approval=["Bash"],
        )
        result = await engine.chat("Run echo")
        assert "ran" in result.lower()
