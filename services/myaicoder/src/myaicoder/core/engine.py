"""Core agent engine - the main agentic loop.

Contains two engines (DS-03 Strangler Fig pattern):
- AgentEngine: original implementation (to be removed after full migration)
- MiddlewareEngine: new middleware-based implementation
"""

from collections.abc import Callable
from typing import AsyncIterator

from myaicoder.core.context import ContextManager
from myaicoder.core.conversation import ConversationManager
from myaicoder.core.memory.loader import AgentsmdLoader
from myaicoder.core.memory.store import MemoryStore
from myaicoder.core.middleware.base import ContextPayload
from myaicoder.core.middleware.filesystem import FilesystemMiddleware
from myaicoder.core.middleware.hitl import HITLMiddleware
from myaicoder.core.middleware.memory import MemoryMiddleware
from myaicoder.core.middleware.planning import PlanningMiddleware
from myaicoder.core.middleware.stack import MiddlewareStack
from myaicoder.core.middleware.subagent import SubAgentMiddleware
from myaicoder.core.middleware.summarization import SummarizationMiddleware
from myaicoder.core.subagent.registry import SubAgentRegistry
from myaicoder.core.subagent.runner import SubAgentRunner
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


class MiddlewareEngine:
    """Middleware-based agent engine (DS-03: Strangler Fig replacement).

    Same interface as AgentEngine but routes tool execution through
    a MiddlewareStack pipeline. Coexists with AgentEngine during migration.
    """

    MAX_TOOL_ITERATIONS = 25
    MAX_TOOL_RETRIES = 2

    def __init__(
        self,
        llm: LLMProvider,
        context_manager: ContextManager | None = None,
        tool_registry: ToolRegistry | None = None,
        middleware_stack: MiddlewareStack | None = None,
        approval_callback: Callable[[str, dict], bool] | None = None,
        require_approval: list[str] | None = None,
        max_context_tokens: int = 32768,
        compression_threshold: float = 0.8,
        subagent_depth: int = 0,
    ):
        self.llm = llm
        self.context = context_manager or ContextManager()
        self.conversation = ConversationManager(
            max_tokens=max_context_tokens,
            compression_threshold=compression_threshold,
        )
        self.tools = tool_registry

        if middleware_stack:
            self.stack = middleware_stack
        else:
            self.stack = self._build_default_stack(
                tool_registry=tool_registry,
                approval_callback=approval_callback,
                require_approval=require_approval,
                subagent_depth=subagent_depth,
            )

    def _build_default_stack(
        self,
        tool_registry: ToolRegistry | None,
        approval_callback: Callable[[str, dict], bool] | None,
        require_approval: list[str] | None,
        subagent_depth: int = 0,
    ) -> MiddlewareStack:
        stack = MiddlewareStack()

        # HITL (priority 10) — deny early before execution
        if approval_callback:
            stack.add(HITLMiddleware(
                callback=approval_callback,
                require_approval=set(require_approval or []),
            ))

        # Memory (priority 20) — load context early
        stack.add(MemoryMiddleware(
            store=MemoryStore(),
            loader=AgentsmdLoader(self.context.working_dir),
        ))

        # Planning (priority 30) — write_todos tool
        stack.add(PlanningMiddleware())

        # SubAgent (priority 40) — only if not at max depth
        if subagent_depth < SubAgentRunner.MAX_DEPTH:
            registry = SubAgentRegistry()
            runner = SubAgentRunner(
                llm=self.llm,
                context_manager=self.context,
                tool_registry=tool_registry,
                registry=registry,
                _depth=subagent_depth,
            )
            stack.add(SubAgentMiddleware(runner=runner, registry=registry))

        # Filesystem (priority 50) — existing tools
        if tool_registry:
            stack.add(FilesystemMiddleware(registry=tool_registry))

        # Summarization (priority 200) — last in after()
        stack.add(SummarizationMiddleware(conversation=self.conversation))

        return stack

    async def chat(self, user_input: str) -> str:
        """Send user input and get response (with middleware pipeline)."""
        self.conversation.add_message(Message(role="user", content=user_input))

        base_prompt = self.context.build_system_prompt()
        collected_text: list[str] = []

        for _ in range(self.MAX_TOOL_ITERATIONS):
            # 1. Build frozen ContextPayload
            payload = ContextPayload(
                messages=tuple(self.conversation.history)
            )

            # 2. Run middleware before() hooks
            payload = await self.stack.process_before(payload)

            # 3. Merge system prompt with middleware instructions
            system_prompt = self.stack.merge_system_prompt(base_prompt, payload)

            # 4. Get messages (with auto-compression)
            messages = self.conversation.get_messages(system_prompt)

            # 5. Call LLM with merged tools
            tools_list = list(payload.tools) if payload.tools else None
            response = await self.llm.chat(
                messages=messages,
                tools=tools_list,
            )

            if response.content:
                collected_text.append(response.content)

            # 6. No tool calls → done
            if not response.tool_calls:
                self.conversation.add_message(
                    Message(role="assistant", content=response.content or "")
                )
                break

            # 7. Execute tool calls via middleware stack
            self.conversation.add_message(
                Message(
                    role="assistant",
                    content=response.content,
                    tool_calls=response.tool_calls,
                )
            )

            for tc in response.tool_calls:
                result = await self._execute_tool(tc.name, tc.arguments)
                content = (
                    result.output if result.success else f"Error: {result.error}"
                )
                content = self._truncate_tool_result(content)
                self.conversation.add_message(
                    Message(
                        role="tool", content=content, tool_call_id=tc.id
                    )
                )

        # 8. Run middleware after() hooks
        after_payload = ContextPayload(
            messages=tuple(self.conversation.history)
        )
        await self.stack.process_after(after_payload)

        return "\n".join(collected_text) if collected_text else ""

    async def chat_stream(self, user_input: str) -> AsyncIterator[str]:
        """Send user input and stream the response."""
        if not self.tools and len(self.stack) == 0:
            self.conversation.add_message(
                Message(role="user", content=user_input)
            )
            system_prompt = self.context.build_system_prompt()
            messages = self.conversation.get_messages(system_prompt)

            full_response: list[str] = []
            async for chunk in self.llm.chat_stream(messages=messages):
                full_response.append(chunk)
                yield chunk

            self.conversation.add_message(
                Message(role="assistant", content="".join(full_response))
            )
            return

        response_text = await self.chat(user_input)
        if response_text:
            yield response_text

    async def _execute_tool(
        self, name: str, arguments: dict
    ) -> ToolResult:
        """Execute tool through middleware chain of responsibility."""
        result = await self.stack.handle_tool(name, arguments)
        if result is not None:
            return result
        return ToolResult(
            success=False, output="", error=f"Unknown tool: {name}"
        )

    def _truncate_tool_result(
        self, result: str, max_tokens: int = 4000
    ) -> str:
        """Truncate large tool results to fit context."""
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
