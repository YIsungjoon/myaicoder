"""Tests for MCP Client."""

import os
from types import SimpleNamespace

import pytest

from myaicoder.mcp.client import MCPClient, MCPToolProxy
from myaicoder.mcp.config import MCPConfig


class TestMCPClient:
    def test_init_empty_config(self):
        """Client with empty config has no servers."""
        client = MCPClient(config=MCPConfig())
        assert client.connected_servers == []

    def test_tool_proxy_schema(self):
        """MCPToolProxy generates correct OpenAI tool schema."""

        class FakeSession:
            pass

        proxy = MCPToolProxy(
            tool_name="test_tool",
            tool_description="A test tool",
            input_schema={
                "type": "object",
                "properties": {"arg1": {"type": "string"}},
                "required": ["arg1"],
            },
            server_name="test_server",
            session=FakeSession(),
        )

        schema = proxy.to_openai_tool()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "test_tool"
        assert schema["function"]["description"] == "A test tool"
        assert "arg1" in schema["function"]["parameters"]["properties"]

    def test_get_tool_proxies_returns_cached_tools(self):
        """Cached MCP tool metadata is exposed as Tool proxies."""

        class FakeSession:
            pass

        client = MCPClient(config=MCPConfig())
        client._sessions["test_server"] = FakeSession()
        client._tools_by_server["test_server"] = [
            SimpleNamespace(
                name="read_file",
                description="Read file",
                inputSchema={"type": "object", "properties": {}},
            ),
            SimpleNamespace(
                name="write_file",
                description="Write file",
                inputSchema={"type": "object", "properties": {}},
            ),
        ]

        proxies = client.get_tool_proxies()

        assert len(proxies) == 2
        assert [proxy.name for proxy in proxies] == ["read_file", "write_file"]
        assert all(isinstance(proxy, MCPToolProxy) for proxy in proxies)


@pytest.mark.skipif(
    not os.environ.get("MCP_INTEGRATION"),
    reason="Set MCP_INTEGRATION=1 to run MCP integration tests",
)
class TestMCPIntegration:
    """Integration tests — requires myaicoder MCP server.

    Run: MCP_INTEGRATION=1 uv run pytest tests/test_mcp -q
    """

    @pytest.mark.asyncio
    async def test_connect_stdio_server(self):
        """Connect to a stdio MCP server."""
        pass
