"""Tests for Bash tool."""

import pytest

from myaicoder.tools.search.bash import BashTool


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

    # ── New: advanced-mcp-tools (T22~T27) ──

    @pytest.mark.asyncio
    async def test_working_dir(self, bash_tool, tmp_path):
        """T22: working_dir changes cwd."""
        result = await bash_tool.execute(command="pwd", working_dir=str(tmp_path))
        assert result.success
        assert str(tmp_path) in result.output

    @pytest.mark.asyncio
    async def test_env_variables(self, bash_tool):
        """T23: env injects environment variables."""
        result = await bash_tool.execute(
            command="echo $MY_TEST_VAR",
            env={"MY_TEST_VAR": "hello_from_env"},
        )
        assert result.success
        assert "hello_from_env" in result.output

    @pytest.mark.asyncio
    async def test_block_rm_rf_root(self, bash_tool):
        """T24: rm -rf / is blocked."""
        result = await bash_tool.execute(command="rm -rf /")
        assert not result.success
        assert "Blocked" in result.error

    @pytest.mark.asyncio
    async def test_block_mkfs(self, bash_tool):
        """T25: mkfs is blocked."""
        result = await bash_tool.execute(command="mkfs.ext4 /dev/sda1")
        assert not result.success
        assert "Blocked" in result.error

    @pytest.mark.asyncio
    async def test_block_fork_bomb(self, bash_tool):
        """T26: fork bomb is blocked."""
        result = await bash_tool.execute(command=":(){ :|:& };:")
        assert not result.success
        assert "Blocked" in result.error

    @pytest.mark.asyncio
    async def test_allow_normal_rm(self, bash_tool, tmp_path):
        """T27: normal rm is allowed."""
        test_file = tmp_path / "deleteme.txt"
        test_file.write_text("temp")
        result = await bash_tool.execute(command=f"rm {test_file}")
        assert result.success
