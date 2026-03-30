"""SubAgentRunner: executes sub-agents with output boundary enforcement (DS-02)."""

from __future__ import annotations

from myaicoder.core.context import ContextManager
from myaicoder.core.subagent.registry import SubAgentRegistry
from myaicoder.llm.base import LLMProvider
from myaicoder.tools.registry import ToolRegistry


class SubAgentRunner:
    """Executes sub-agents in isolated engine instances.

    DS-02: Output boundary enforcement — sub-agent results are force-compressed
    to MAX_RESULT_TOKENS before returning to the parent agent.
    """

    MAX_RESULT_TOKENS = 1000
    MAX_DEPTH = 3

    def __init__(
        self,
        llm: LLMProvider,
        context_manager: ContextManager | None = None,
        tool_registry: ToolRegistry | None = None,
        registry: SubAgentRegistry | None = None,
        _depth: int = 0,
    ):
        self._llm = llm
        self._context = context_manager
        self._tool_registry = tool_registry
        self._registry = registry or SubAgentRegistry()
        self._depth = _depth

    async def run(self, task: str, agent_name: str | None = None) -> str:
        """Run a sub-agent and return compressed result.

        Args:
            task: What the sub-agent should do.
            agent_name: Specific sub-agent name, or None for auto-select.

        Returns:
            Compressed result string (≤ MAX_RESULT_TOKENS * 4 chars).
        """
        if self._depth >= self.MAX_DEPTH:
            return (
                f"Error: Maximum sub-agent depth ({self.MAX_DEPTH}) exceeded. "
                "Cannot create nested sub-agents beyond this level."
            )

        # Resolve sub-agent spec
        if agent_name:
            agent = self._registry.get(agent_name)
            if agent is None:
                agent = self._registry.find_best(task)
        else:
            agent = self._registry.find_best(task)

        # Create isolated MiddlewareEngine for sub-agent
        # Import here to avoid circular import
        from myaicoder.core.engine import MiddlewareEngine

        sub_engine = MiddlewareEngine(
            llm=self._llm,
            context_manager=self._context,
            tool_registry=self._tool_registry,
            max_context_tokens=16384,  # Smaller context for sub-agents
            subagent_depth=self._depth + 1,
        )

        # Prepend sub-agent's system prompt to the task
        prompt = task
        if agent.system_prompt:
            prompt = f"{agent.system_prompt}\n\nTask: {task}"

        result = await sub_engine.chat(prompt)
        return self._compress_result(result)

    def _compress_result(self, result: str) -> str:
        """DS-02: Force compress result to MAX_RESULT_TOKENS."""
        max_chars = self.MAX_RESULT_TOKENS * 4
        if len(result) <= max_chars:
            return result

        # Preserve head (summary) + tail (final result)
        half = max_chars // 2
        head = result[:half]
        tail = result[-half:]
        return (
            f"{head}\n"
            f"... (compressed, {len(result)} chars total) ...\n"
            f"{tail}"
        )

    @property
    def depth(self) -> int:
        return self._depth
