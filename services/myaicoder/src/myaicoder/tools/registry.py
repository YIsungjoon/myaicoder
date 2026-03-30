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
    """
    Create registry with all built-in tools.
    Dynamically loads tools from functional sub-packages.
    """
    from .external import TOOLS as EXTERNAL_TOOLS
    from .filesystem import TOOLS as FILESYSTEM_TOOLS
    from .search import TOOLS as SEARCH_TOOLS

    registry = ToolRegistry()

    # Iterate over each package's TOOLS list and register them
    # This design allows for easy expansion without modifying registry logic
    all_tool_classes = FILESYSTEM_TOOLS + SEARCH_TOOLS + EXTERNAL_TOOLS

    for tool_class in all_tool_classes:
        registry.register(tool_class())

    return registry
