"""Tests for Bash tool."""

import pytest

from myaicoder.tools.bash import BashTool


@pytest.fixture
def bash_tool():
    return BashTool()


class TestBashTool:
    @pytest.mark.asyncio
    async def test_simple_command(self, bash_tool):
        result = await bash_tool.execute(command="echo 'hello world'")
        assert result.success
        assert "hello world" in result.output

    @pytest.mark.asyncio
    async def test_failing_command(self, bash_tool):
        result = await bash_tool.execute(command="false")
        assert not result.success

    @pytest.mark.asyncio
    async def test_timeout(self, bash_tool):
        result = await bash_tool.execute(command="sleep 10", timeout=1)
        assert not result.success
        assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_multiline_output(self, bash_tool):
        result = await bash_tool.execute(command="echo 'a' && echo 'b' && echo 'c'")
        assert result.success
        lines = result.output.strip().splitlines()
        assert len(lines) == 3
