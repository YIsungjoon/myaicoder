"""MCP Server — exposes built-in tools via FastMCP."""

import asyncio
import inspect
from typing import Any

from mcp.server.fastmcp import FastMCP

from myaicoder.tools.base import Tool
from myaicoder.tools.registry import ToolRegistry

# JSON Schema type → Python type mapping
_JSON_TYPE_MAP: dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
}


# MCP tool name mapping (internal → external)
TOOL_NAME_MAP = {
    "Read": "read_file",
    "Write": "write_file",
    "Edit": "edit_file",
    "Glob": "glob_search",
    "Grep": "grep_search",
    "Bash": "run_command",
    "BuildRunner": "build_run",
    "WebFetch": "web_fetch",
    "ListDir": "list_dir",
}


class MCPServer:
    """FastMCP-based MCP server for myAiCoder tools.

    Supports two routing modes:
    - Direct Pass-through: Tool.execute() directly, no LLM (<100ms)
    - Agentic Execution: agentic_task() via AgentEngine (seconds~minutes)
    """

    def __init__(
        self,
        name: str = "myaicoder",
        tool_registry: ToolRegistry | None = None,
        allow_bash: bool = False,
        working_dir: str | None = None,
        max_concurrent: int = 1,
        max_result_tokens: int = 4000,
        enable_agentic: bool = False,
        llm_provider=None,
    ):
        self.mcp = FastMCP(name)
        self.registry = tool_registry
        self.allow_bash = allow_bash
        self.working_dir = working_dir
        self.max_concurrent = max_concurrent
        self.max_result_tokens = max_result_tokens
        self._semaphore: asyncio.Semaphore | None = None

        if tool_registry:
            self._register_tools()

        if enable_agentic and llm_provider:
            self._register_agentic_task(llm_provider)

    def _register_tools(self) -> None:
        """Register all tools from ToolRegistry to FastMCP dynamically."""
        for tool in self.registry.all_tools():
            # Bash security: skip unless --allow-bash
            if tool.name == "Bash" and not self.allow_bash:
                continue

            mcp_name = TOOL_NAME_MAP.get(tool.name, tool.name.lower())
            self._register_single_tool(tool, mcp_name)

    def _register_single_tool(self, tool: Tool, mcp_name: str) -> None:
        """Register a single tool to FastMCP with proper parameter schema."""
        handler = self._build_typed_handler(tool)

        self.mcp.add_tool(
            handler,
            name=mcp_name,
            description=tool.description,
        )

    def _build_typed_handler(self, tool: Tool):
        """Build a handler function with explicit typed parameters from tool schema.

        FastMCP infers inputSchema from function signature, so we create
        a function with proper type-annotated parameters dynamically.
        """
        schema = tool.parameters_schema
        props = schema.get("properties", {})
        required = set(schema.get("required", []))

        # Build parameter list for inspect.Parameter
        params = [
            inspect.Parameter("self_placeholder", inspect.Parameter.POSITIONAL_OR_KEYWORD),
        ]
        annotations: dict[str, Any] = {"return": str}

        for name, spec in props.items():
            py_type = _JSON_TYPE_MAP.get(spec.get("type", "string"), str)
            annotations[name] = py_type

            if name in required:
                param = inspect.Parameter(
                    name, inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=py_type,
                )
            else:
                default = spec.get("default")
                if default is None:
                    # Optional param with no explicit default
                    annotations[name] = py_type | None
                    param = inspect.Parameter(
                        name, inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        default=None, annotation=py_type | None,
                    )
                else:
                    param = inspect.Parameter(
                        name, inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        default=default, annotation=py_type,
                    )
            params.append(param)

        # Create the actual handler with closure over `tool` and `self`
        server = self

        async def handler(**kwargs) -> str:
            if server._semaphore:
                async with server._semaphore:
                    return await server._execute_and_format(tool, kwargs)
            return await server._execute_and_format(tool, kwargs)

        # Set the function signature so FastMCP generates correct schema
        sig = inspect.Signature(params[1:], return_annotation=str)  # skip self_placeholder
        handler.__signature__ = sig
        handler.__annotations__ = annotations
        handler.__name__ = tool.name.lower()

        return handler

    async def _execute_and_format(self, tool: Tool, kwargs: dict) -> str:
        """Execute tool and truncate result."""
        # Remove None values so tools use their own defaults
        kwargs = {k: v for k, v in kwargs.items() if v is not None}
        result = await tool.execute(**kwargs)

        if not result.success:
            return f"Error: {result.error}"

        return self._truncate_result(result.output)

    def _truncate_result(self, output: str) -> str:
        """Truncate large results (e.g. BIM data) to fit context."""
        max_chars = self.max_result_tokens * 4  # rough char-to-token
        if len(output) > max_chars:
            return (
                output[:max_chars]
                + f"\n... (truncated, {len(output)} chars total)"
            )
        return output

    def _register_agentic_task(self, llm_provider) -> None:
        """Register agentic_task special tool for Agentic Execution mode."""
        from myaicoder.core.engine import AgentEngine

        # Persistent engine — retains conversation history across calls
        # Uses ConversationManager with 32K context window + auto-compression
        engine = AgentEngine(
            llm=llm_provider,
            tool_registry=self.registry,
            max_context_tokens=32768,
            compression_threshold=0.8,
        )

        async def agentic_task(prompt: str) -> str:
            """Execute a complex multi-step task using local LLM agent.
            Use for high-level instructions like BIM modifications or
            multi-tool workflows. The local LLM handles sub-task planning.
            Conversation history is preserved across calls."""
            return await engine.chat(prompt)

        self.mcp.add_tool(
            agentic_task,
            name="agentic_task",
            description=(
                "Execute a complex multi-step task using local LLM agent. "
                "Use for high-level instructions like BIM modifications, "
                "multi-tool workflows, or tasks requiring reasoning."
            ),
        )

    def run(self, transport: str = "stdio") -> None:
        """Run MCP server."""
        if self.max_concurrent > 1:
            self._semaphore = asyncio.Semaphore(self.max_concurrent)

        self.mcp.run(transport=transport)
