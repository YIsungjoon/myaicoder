"""FilesystemMiddleware: wraps existing ToolRegistry as a middleware."""

from __future__ import annotations

from myaicoder.core.middleware.base import AgentMiddleware, ContextPayload
from myaicoder.tools.base import ToolResult
from myaicoder.tools.registry import ToolRegistry


class FilesystemMiddleware(AgentMiddleware):
    """Wraps existing ToolRegistry tools into the middleware pipeline."""

    @property
    def name(self) -> str:
        return "filesystem"

    @property
    def priority(self) -> int:
        return 50

    def __init__(self, registry: ToolRegistry):
        self._registry = registry

    async def before(self, payload: ContextPayload) -> ContextPayload:
        return payload.with_tools(self._registry.to_openai_tools())

    async def handle_tool(
        self, tool_name: str, arguments: dict
    ) -> ToolResult | None:
        tool = self._registry.get(tool_name)
        if tool is None:
            return None
        try:
            return await tool.execute(**arguments)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
