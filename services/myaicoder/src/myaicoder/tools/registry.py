"""Tool registry for managing built-in and MCP tools."""

from myaicoder.tools.base import Tool


class ToolRegistry:
    """Registry for all available tools."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def all_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def to_openai_tools(self) -> list[dict]:
        """Return all tools as OpenAI function calling schemas."""
        return [t.to_openai_tool() for t in self._tools.values()]

    def __len__(self) -> int:
        return len(self._tools)


def create_default_registry() -> ToolRegistry:
    """Create registry with all built-in tools."""
    from myaicoder.tools.search.bash import BashTool
    from myaicoder.tools.external.build_runner import BuildRunnerTool
    from myaicoder.tools.filesystem.edit import EditTool
    from myaicoder.tools.search.glob_tool import GlobTool
    from myaicoder.tools.search.grep_tool import GrepTool
    from myaicoder.tools.filesystem.list_dir import ListDirTool
    from myaicoder.tools.filesystem.read import ReadTool
    from myaicoder.tools.external.web_fetch import WebFetchTool
    from myaicoder.tools.filesystem.write import WriteTool

    registry = ToolRegistry()
    registry.register(ReadTool())
    registry.register(WriteTool())
    registry.register(EditTool())
    registry.register(GlobTool())
    registry.register(GrepTool())
    registry.register(BashTool())
    registry.register(BuildRunnerTool())
    registry.register(WebFetchTool())
    registry.register(ListDirTool())
    return registry
