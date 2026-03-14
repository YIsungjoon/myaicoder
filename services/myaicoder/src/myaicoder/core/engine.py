"""Core agent engine - the main agentic loop."""

from collections.abc import Callable
from typing import AsyncIterator

from myaicoder.core.context import ContextManager
from myaicoder.core.conversation import ConversationManager
from myaicoder.llm.base import LLMProvider, Message
from myaicoder.tools.base import ToolResult
from myaicoder.tools.registry import ToolRegistry


class AgentEngine:
    """Main agent loop: LLM call → tool execution → repeat.

    When tools are registered, the engine runs an agentic loop:
    1. Send messages + tool schemas to LLM
    2. If LLM returns tool_calls, check approval then execute
    3. Add results to conversation and repeat
    4. Stop when LLM returns text-only response
    """

    MAX_TOOL_ITERATIONS = 25
    MAX_TOOL_RETRIES = 2

    def __init__(
        self,
        llm: LLMProvider,
        context_manager: ContextManager | None = None,
        tool_registry: ToolRegistry | None = None,
        approval_callback: Callable[[str, dict], bool] | None = None,
        require_approval: list[str] | None = None,
        max_context_tokens: int = 32768,
        compression_threshold: float = 0.8,
    ):
        self.llm = llm
        self.context = context_manager or ContextManager()
        self.conversation = ConversationManager(
            max_tokens=max_context_tokens,
            compression_threshold=compression_threshold,
        )
        self.tools = tool_registry
        self._approval_callback = approval_callback
        self._require_approval = set(require_approval or [])

    async def chat(self, user_input: str) -> str:
        """Send user input and get a complete response (with tool execution)."""
        self.conversation.add_message(Message(role="user", content=user_input))

        system_prompt = self.context.build_system_prompt()
        tools_schema = self.tools.to_openai_tools() if self.tools else None

        collected_text = []

        for _ in range(self.MAX_TOOL_ITERATIONS):
            messages = self.conversation.get_messages(system_prompt)

            response = await self.llm.chat(
                messages=messages,
                tools=tools_schema if tools_schema else None,
            )

            # Collect any text content
            if response.content:
                collected_text.append(response.content)

            # No tool calls → done
            if not response.tool_calls:
                self.conversation.add_message(
                    Message(role="assistant", content=response.content or "")
                )
                break

            # Has tool calls → execute them
            self.conversation.add_message(
                Message(
                    role="assistant",
                    content=response.content,
                    tool_calls=response.tool_calls,
                )
            )

            for tc in response.tool_calls:
                result = await self._execute_tool_with_approval(
                    tc.name, tc.arguments, tc.id
                )
                content = result.output if result.success else f"Error: {result.error}"
                content = self._truncate_tool_result(content)
                self.conversation.add_message(
                    Message(
                        role="tool",
                        content=content,
                        tool_call_id=tc.id,
                    )
                )

        return "\n".join(collected_text) if collected_text else ""

    async def chat_stream(self, user_input: str) -> AsyncIterator[str]:
        """Send user input and stream the response.

        Note: Streaming only works for the final text response.
        Tool calls are executed non-streaming.
        """
        # If no tools, stream directly
        if not self.tools:
            self.conversation.add_message(Message(role="user", content=user_input))
            system_prompt = self.context.build_system_prompt()
            messages = self.conversation.get_messages(system_prompt)

            full_response = []
            async for chunk in self.llm.chat_stream(messages=messages):
                full_response.append(chunk)
                yield chunk

            self.conversation.add_message(
                Message(role="assistant", content="".join(full_response))
            )
            return

        # With tools: use non-streaming chat for tool loop,
        # the final response text is yielded at once
        response_text = await self.chat(user_input)
        if response_text:
            yield response_text

    async def _execute_tool_with_approval(
        self, name: str, arguments: dict, tool_call_id: str
    ) -> ToolResult:
        """Execute a tool, checking approval if required."""
        # Check if this tool requires approval
        if self._needs_approval(name):
            if self._approval_callback and not self._approval_callback(name, arguments):
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Tool '{name}' execution denied by user.",
                )

        result = await self._execute_tool(name, arguments)

        # Retry logic for retryable errors
        if not result.success and self._is_retryable_error(result.error):
            for _ in range(self.MAX_TOOL_RETRIES):
                result = await self._execute_tool(name, arguments)
                if result.success:
                    break

        return result

    def _needs_approval(self, tool_name: str) -> bool:
        """Check if a tool requires user approval."""
        if not self._approval_callback:
            return False
        return tool_name in self._require_approval

    async def _execute_tool(self, name: str, arguments: dict) -> ToolResult:
        """Execute a tool by name."""
        if not self.tools:
            return ToolResult(
                success=False, output="", error="No tools registered"
            )

        tool = self.tools.get(name)
        if tool is None:
            return ToolResult(
                success=False, output="", error=f"Unknown tool: {name}"
            )

        try:
            return await tool.execute(**arguments)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def _is_retryable_error(self, error: str | None) -> bool:
        """Check if an error is retryable."""
        if not error:
            return False
        non_retryable = ["permission", "denied", "auth", "connection", "refused"]
        return not any(kw in error.lower() for kw in non_retryable)

    def _truncate_tool_result(self, result: str, max_tokens: int = 4000) -> str:
        """Truncate large tool results (e.g. BIM data) to fit context."""
        max_chars = max_tokens * 4
        if len(result) > max_chars:
            return (
                result[:max_chars]
                + f"\n... (truncated, {len(result)} chars total)"
            )
        return result

    def reset(self) -> None:
        """Clear conversation history."""
        self.conversation.clear()
