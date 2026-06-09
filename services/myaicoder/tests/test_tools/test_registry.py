"""Tests for ToolRegistry."""

from myaicoder.tools.registry import create_default_registry


class TestToolRegistry:
    def test_create_default(self):
        registry = create_default_registry()
        assert len(registry) == 11

    def test_get_tool(self):
        registry = create_default_registry()
        assert registry.get("Read") is not None
        assert registry.get("Write") is not None
        assert registry.get("Edit") is not None
        assert registry.get("Glob") is not None
        assert registry.get("Grep") is not None
        assert registry.get("Bash") is not None

    def test_get_unknown(self):
        registry = create_default_registry()
        assert registry.get("Unknown") is None

    def test_to_openai_tools(self):
        registry = create_default_registry()
        tools = registry.to_openai_tools()
        assert len(tools) == 11
        for t in tools:
            assert t["type"] == "function"
            assert "name" in t["function"]
            assert "parameters" in t["function"]

    def test_to_mcp_tool(self):
        """Tool.to_mcp_tool() returns correct MCP schema."""
        registry = create_default_registry()
        tool = registry.get("Read")
        mcp_schema = tool.to_mcp_tool()
        assert mcp_schema["name"] == "Read"
        assert "description" in mcp_schema
        assert "inputSchema" in mcp_schema
        assert mcp_schema["inputSchema"]["type"] == "object"
