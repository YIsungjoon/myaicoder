"""MiddlewareStack: orchestrates the middleware pipeline."""

from __future__ import annotations

from myaicoder.core.middleware.base import AgentMiddleware, ContextPayload
from myaicoder.tools.base import ToolResult


class MiddlewareStack:
    """Orchestrates middleware pipeline execution.

    - before(): runs in priority order (low → high)
    - handle_tool(): chain of responsibility (first handler wins)
    - after(): runs in REVERSE priority order (high → low)
    - merge_system_prompt(): combines base prompt + all instructions
    """

    def __init__(self, middlewares: list[AgentMiddleware] | None = None):
        self._middlewares: list[AgentMiddleware] = []
        if middlewares:
            for mw in middlewares:
                self.add(mw)

    def add(self, middleware: AgentMiddleware) -> None:
        """Add middleware and re-sort by priority."""
        self._middlewares.append(middleware)
        self._middlewares.sort(key=lambda m: m.priority)

    async def process_before(self, payload: ContextPayload) -> ContextPayload:
        """Run all middleware before() hooks in priority order."""
        for mw in self._middlewares:
            payload = await mw.before(payload)
        return payload

    async def handle_tool(
        self, tool_name: str, arguments: dict
    ) -> ToolResult | None:
        """Chain of responsibility: first middleware to handle wins."""
        for mw in self._middlewares:
            result = await mw.handle_tool(tool_name, arguments)
            if result is not None:
                return result
        return None

    async def process_after(self, payload: ContextPayload) -> ContextPayload:
        """Run all middleware after() hooks in REVERSE priority order."""
        for mw in reversed(self._middlewares):
            payload = await mw.after(payload)
        return payload

    def merge_system_prompt(
        self, base_prompt: str, payload: ContextPayload
    ) -> str:
        """Merge base prompt with all middleware system instructions."""
        if not payload.system_instructions:
            return base_prompt
        parts = [base_prompt, *payload.system_instructions]
        return "\n\n".join(parts)

    @property
    def middleware_names(self) -> list[str]:
        """List of middleware names in priority order."""
        return [mw.name for mw in self._middlewares]

    def __len__(self) -> int:
        return len(self._middlewares)
