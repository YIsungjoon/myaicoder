"""Tests for MiddlewareStack orchestration."""

import pytest

from myaicoder.core.middleware.base import AgentMiddleware, ContextPayload
from myaicoder.core.middleware.stack import MiddlewareStack
from myaicoder.tools.base import ToolResult


class LowPriorityMW(AgentMiddleware):
    @property
    def name(self) -> str:
        return "low"

    @property
    def priority(self) -> int:
        return 10

    async def before(self, payload: ContextPayload) -> ContextPayload:
        return payload.with_instruction("low")


class HighPriorityMW(AgentMiddleware):
    @property
    def name(self) -> str:
        return "high"

    @property
    def priority(self) -> int:
        return 200

    async def before(self, payload: ContextPayload) -> ContextPayload:
        return payload.with_instruction("high")


class ToolHandlerMW(AgentMiddleware):
    @property
    def name(self) -> str:
        return "handler"

    async def handle_tool(self, tool_name: str, arguments: dict) -> ToolResult | None:
        if tool_name == "my_tool":
            return ToolResult(success=True, output="handled")
        return None


class TestMiddlewareStack:
    def test_add_and_sort_by_priority(self):
        stack = MiddlewareStack()
        stack.add(HighPriorityMW())
        stack.add(LowPriorityMW())
        assert stack.middleware_names == ["low", "high"]

    def test_len(self):
        stack = MiddlewareStack([LowPriorityMW(), HighPriorityMW()])
        assert len(stack) == 2

    @pytest.mark.asyncio
    async def test_process_before_priority_order(self):
        stack = MiddlewareStack([HighPriorityMW(), LowPriorityMW()])
        payload = ContextPayload()
        result = await stack.process_before(payload)
        # low (priority 10) runs first, high (200) runs second
        assert result.system_instructions == ("low", "high")

    @pytest.mark.asyncio
    async def test_handle_tool_chain_of_responsibility(self):
        stack = MiddlewareStack([ToolHandlerMW()])
        result = await stack.handle_tool("my_tool", {})
        assert result is not None
        assert result.output == "handled"

    @pytest.mark.asyncio
    async def test_handle_tool_returns_none_for_unknown(self):
        stack = MiddlewareStack([ToolHandlerMW()])
        result = await stack.handle_tool("unknown_tool", {})
        assert result is None

    @pytest.mark.asyncio
    async def test_process_after_reverse_order(self):
        order: list[str] = []

        class TrackingLow(AgentMiddleware):
            @property
            def name(self) -> str:
                return "track_low"

            @property
            def priority(self) -> int:
                return 10

            async def after(self, payload: ContextPayload) -> ContextPayload:
                order.append("low")
                return payload

        class TrackingHigh(AgentMiddleware):
            @property
            def name(self) -> str:
                return "track_high"

            @property
            def priority(self) -> int:
                return 200

            async def after(self, payload: ContextPayload) -> ContextPayload:
                order.append("high")
                return payload

        stack = MiddlewareStack([TrackingLow(), TrackingHigh()])
        await stack.process_after(ContextPayload())
        # after() runs in REVERSE: high first, then low
        assert order == ["high", "low"]

    def test_merge_system_prompt_no_instructions(self):
        stack = MiddlewareStack()
        payload = ContextPayload()
        result = stack.merge_system_prompt("base", payload)
        assert result == "base"

    def test_merge_system_prompt_with_instructions(self):
        stack = MiddlewareStack()
        payload = ContextPayload().with_instruction("extra1").with_instruction("extra2")
        result = stack.merge_system_prompt("base", payload)
        assert result == "base\n\nextra1\n\nextra2"

    def test_empty_stack(self):
        stack = MiddlewareStack()
        assert len(stack) == 0
        assert stack.middleware_names == []
