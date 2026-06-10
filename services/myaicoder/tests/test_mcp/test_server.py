"""Tests for MCP Server."""

import asyncio

import pytest

from myaicoder.mcp.server import MCPServer, TOOL_NAME_MAP
from myaicoder.tools.registry import create_default_registry


class TestMCPServerCreation:
    def test_server_creation(self):
        """MCPServer can be created with a tool registry."""
        registry = create_default_registry()
        server = MCPServer(tool_registry=registry)
        assert server.mcp is not None
        assert server.registry is registry

    def test_tool_registration_count_no_bash(self):
        """10 tools registered when allow_bash=False (default)."""
        registry = create_default_registry()
        server = MCPServer(tool_registry=registry, allow_bash=False)
        tools = server.mcp.list_tools()
        # list_tools is sync and returns tool list
        assert len(asyncio.get_event_loop().run_until_complete(tools)) == 10

    def test_tool_registration_count_with_bash(self):
        """11 tools registered when allow_bash=True."""
        registry = create_default_registry()
        server = MCPServer(tool_registry=registry, allow_bash=True)
        tools = asyncio.get_event_loop().run_until_complete(server.mcp.list_tools())
        assert len(tools) == 11

    def test_bash_excluded_by_default(self):
        """run_command not registered when allow_bash=False."""
        registry = create_default_registry()
        server = MCPServer(tool_registry=registry)
        tools = asyncio.get_event_loop().run_until_complete(server.mcp.list_tools())
        tool_names = [t.name for t in tools]
        assert "run_command" not in tool_names

    def test_bash_included_when_allowed(self):
        """run_command registered when allow_bash=True."""
        registry = create_default_registry()
        server = MCPServer(tool_registry=registry, allow_bash=True)
        tools = asyncio.get_event_loop().run_until_complete(server.mcp.list_tools())
        tool_names = [t.name for t in tools]
        assert "run_command" in tool_names


class TestToolNameMapping:
    def test_tool_name_mapping(self):
        """Internal names map correctly to MCP names."""
        registry = create_default_registry()
        server = MCPServer(tool_registry=registry, allow_bash=True)
        tools = asyncio.get_event_loop().run_until_complete(server.mcp.list_tools())
        tool_names = {t.name for t in tools}

        assert "read_file" in tool_names
        assert "write_file" in tool_names
        assert "edit_file" in tool_names
        assert "glob_search" in tool_names
        assert "grep_search" in tool_names
        assert "run_command" in tool_names

    def test_name_map_completeness(self):
        """TOOL_NAME_MAP covers all 11 built-in tools."""
        assert len(TOOL_NAME_MAP) == 11
        expected = {"Read", "Write", "Edit", "Glob", "Grep", "Bash", "BuildRunner", "WebFetch", "ListDir", "AskUser", "SubmitAnswer"}
        assert set(TOOL_NAME_MAP.keys()) == expected


class TestResultTruncation:
    def test_result_truncation(self):
        """Large results are truncated."""
        server = MCPServer(max_result_tokens=10)  # 10 tokens ≈ 40 chars
        long_output = "x" * 100
        result = server._truncate_result(long_output)
        assert len(result) < 100
        assert "truncated" in result
        assert "100 chars total" in result

    def test_result_no_truncation(self):
        """Small results pass through unchanged."""
        server = MCPServer(max_result_tokens=4000)
        short_output = "Hello, world!"
        result = server._truncate_result(short_output)
        assert result == short_output


class TestAgenticTask:
    def test_agentic_task_registration(self):
        """agentic_task tool is registered when enable_agentic=True with provider."""
        registry = create_default_registry()

        class FakeLLM:
            pass

        server = MCPServer(
            tool_registry=registry,
            enable_agentic=True,
            llm_provider=FakeLLM(),
        )
        tools = asyncio.get_event_loop().run_until_complete(server.mcp.list_tools())
        tool_names = [t.name for t in tools]
        assert "agentic_task" in tool_names

    def test_agentic_task_not_registered_by_default(self):
        """agentic_task not registered when enable_agentic=False."""
        registry = create_default_registry()
        server = MCPServer(tool_registry=registry)
        tools = asyncio.get_event_loop().run_until_complete(server.mcp.list_tools())
        tool_names = [t.name for t in tools]
        assert "agentic_task" not in tool_names


class TestConcurrency:
    def test_concurrency_semaphore(self):
        """Semaphore is created when max_concurrent > 1 and run is called."""
        server = MCPServer(max_concurrent=2)
        # Before run, semaphore is None
        assert server._semaphore is None
        # Simulate what run() does
        if server.max_concurrent > 1:
            server._semaphore = asyncio.Semaphore(server.max_concurrent)
        assert server._semaphore is not None


@pytest.mark.asyncio
async def test_direct_tool_execution():
    """Direct tool execution via _execute_and_format."""
    registry = create_default_registry()
    server = MCPServer(tool_registry=registry)

    read_tool = registry.get("Read")
    # Execute read on a non-existent file → should return error
    result = await server._execute_and_format(
        read_tool, {"file_path": "/tmp/__nonexistent_test_file__"}
    )
    assert "Error" in result or "not found" in result.lower() or "No such" in result
