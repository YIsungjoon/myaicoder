"""MCP Client — connects to external MCP servers using the official SDK.

Supports stdio and Streamable HTTP transports.
Compatible with Claude Code's .mcp.json configuration.
"""

import logging
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client

from myaicoder.mcp.config import MCPConfig, MCPServerConfig
from myaicoder.tools.base import Tool, ToolResult

logger = logging.getLogger(__name__)


class MCPToolProxy(Tool):
    """Proxy that wraps an MCP server tool as a local Tool."""

    def __init__(
        self,
        tool_name: str,
        tool_description: str,
        input_schema: dict,
        server_name: str,
        session: ClientSession,
    ):
        self._name = tool_name
        self._description = tool_description
        self._input_schema = input_schema
        self._server_name = server_name
        self._session = session

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters_schema(self) -> dict:
        return self._input_schema

    async def execute(self, **kwargs) -> ToolResult:
        try:
            result = await self._session.call_tool(self._name, arguments=kwargs)

            # MCP returns content as list of content blocks
            output_parts = []
            for block in result.content:
                if hasattr(block, "text"):
                    output_parts.append(block.text)
                elif hasattr(block, "data"):
                    output_parts.append(f"[binary data: {len(block.data)} bytes]")

            output = "\n".join(output_parts)
            is_error = getattr(result, "isError", False)

            return ToolResult(
                success=not is_error,
                output=output,
                error=output if is_error else None,
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class MCPClient:
    """Manages connections to multiple MCP servers.

    Usage:
        client = MCPClient()
        await client.connect_all()
        tools = client.get_tool_proxies()  # Register these in ToolRegistry
        ...
        await client.close()
    """

    def __init__(self, config: MCPConfig | None = None):
        self.config = config or MCPConfig.load()
        self._sessions: dict[str, ClientSession] = {}
        self._tools_by_server: dict[str, list[object]] = {}
        self._exit_stack = AsyncExitStack()

    async def connect_all(self) -> dict[str, list[str]]:
        """Connect to all configured MCP servers.

        Returns dict of server_name -> list of tool names.
        """
        connected: dict[str, list[str]] = {}

        for name, server_config in self.config.servers.items():
            try:
                tool_names = await self._connect_server(name, server_config)
                connected[name] = tool_names
                logger.info(f"MCP server '{name}' connected: {len(tool_names)} tools")
            except Exception as e:
                logger.warning(f"Failed to connect MCP server '{name}': {e}")

        return connected

    async def _connect_server(
        self, name: str, config: MCPServerConfig
    ) -> list[str]:
        """Connect to a single MCP server and return tool names."""
        if config.transport == "stdio":
            if not config.command:
                raise ValueError(f"MCP server '{name}': stdio requires 'command'")

            params = StdioServerParameters(
                command=config.command,
                args=config.args,
                env={**dict(__import__("os").environ), **config.env} if config.env else None,
            )
            read_stream, write_stream = await self._exit_stack.enter_async_context(
                stdio_client(params)
            )

        elif config.transport == "http":
            if not config.url:
                raise ValueError(f"MCP server '{name}': http requires 'url'")

            read_stream, write_stream, _ = await self._exit_stack.enter_async_context(
                streamablehttp_client(config.url)
            )

        else:
            raise ValueError(f"Unknown transport: {config.transport}")

        session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await session.initialize()

        self._sessions[name] = session

        # Discover tools
        tools_result = await session.list_tools()
        self._tools_by_server[name] = list(tools_result.tools)
        return [t.name for t in tools_result.tools]

    def get_tool_proxies(self) -> list[MCPToolProxy]:
        """Get all MCP tools as Tool proxies for ToolRegistry."""
        proxies = []
        for name, session in self._sessions.items():
            for tool in self._tools_by_server.get(name, []):
                proxies.append(
                    MCPToolProxy(
                        tool_name=tool.name,
                        tool_description=tool.description or "",
                        input_schema=tool.inputSchema if tool.inputSchema else {},
                        server_name=name,
                        session=session,
                    )
                )
        return proxies

    async def discover_tools(self) -> list[MCPToolProxy]:
        """Discover and return all tools from connected servers."""
        proxies = []

        for name, session in self._sessions.items():
            tools_result = await session.list_tools()
            self._tools_by_server[name] = list(tools_result.tools)
            for tool in tools_result.tools:
                proxy = MCPToolProxy(
                    tool_name=tool.name,
                    tool_description=tool.description or "",
                    input_schema=tool.inputSchema if tool.inputSchema else {},
                    server_name=name,
                    session=session,
                )
                proxies.append(proxy)

        return proxies

    async def close(self) -> None:
        """Close all connections."""
        await self._exit_stack.aclose()
        self._sessions.clear()
        self._tools_by_server.clear()

    @property
    def connected_servers(self) -> list[str]:
        return list(self._sessions.keys())
