"""Tests for Glob and Grep tools."""

import pytest

from myaicoder.tools.glob_tool import GlobTool
from myaicoder.tools.grep_tool import GrepTool


@pytest.fixture
def sample_project(tmp_path):
    """Create a sample project structure."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text('def main():\n    print("hello")\n')
    (tmp_path / "src" / "utils.py").write_text("def helper():\n    return 42\n")
    (tmp_path / "README.md").write_text("# Project\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").write_text("def test_main():\n    pass\n")
    return tmp_path


class TestGlobTool:
    @pytest.mark.asyncio
    async def test_find_py_files(self, sample_project):
        tool = GlobTool()
        result = await tool.execute(pattern="**/*.py", path=str(sample_project))
        assert result.success
        assert "main.py" in result.output
        assert "utils.py" in result.output

    @pytest.mark.asyncio
    async def test_find_md_files(self, sample_project):
        tool = GlobTool()
        result = await tool.execute(pattern="*.md", path=str(sample_project))
        assert result.success
        assert "README.md" in result.output

    @pytest.mark.asyncio
    async def test_no_matches(self, sample_project):
        tool = GlobTool()
        result = await tool.execute(pattern="*.xyz", path=str(sample_project))
        assert result.success
        assert "No matching" in result.output


class TestGrepTool:
    @pytest.mark.asyncio
    async def test_search_pattern(self, sample_project):
        tool = GrepTool()
        result = await tool.execute(pattern="def main", path=str(sample_project))
        assert result.success
        assert "main.py" in result.output

    @pytest.mark.asyncio
    async def test_search_with_glob(self, sample_project):
        tool = GrepTool()
        result = await tool.execute(
            pattern="def", path=str(sample_project), glob="**/test_*.py"
        )
        assert result.success
        assert "test_main.py" in result.output
        assert "utils.py" not in result.output

    @pytest.mark.asyncio
    async def test_no_matches(self, sample_project):
        tool = GrepTool()
        result = await tool.execute(pattern="nonexistent_xyz", path=str(sample_project))
        assert result.success
        assert "No matches" in result.output

    # ── New: advanced-mcp-tools (T28~T32) ──

    @pytest.mark.asyncio
    async def test_context_lines(self, sample_project):
        """T28: context_lines shows surrounding lines."""
        tool = GrepTool()
        result = await tool.execute(
            pattern="print", path=str(sample_project), context_lines=1,
        )
        assert result.success
        # Should show lines around 'print("hello")'
        assert "def main" in result.output  # line before
        assert "print" in result.output

    @pytest.mark.asyncio
    async def test_context_separator(self, sample_project):
        """T29: blocks separated by '--' (FB-C)."""
        # Create a file with multiple matches far apart
        big_file = sample_project / "src" / "big.py"
        lines = [f"line_{i} = {i}" for i in range(20)]
        lines[3] = "MATCH_first = True"
        lines[15] = "MATCH_second = True"
        big_file.write_text("\n".join(lines))

        tool = GrepTool()
        result = await tool.execute(
            pattern="MATCH_", path=str(big_file), context_lines=1,
        )
        assert result.success
        assert "\n--\n" in result.output

    @pytest.mark.asyncio
    async def test_output_mode_files(self, sample_project):
        """T30: output_mode='files' returns file paths only."""
        tool = GrepTool()
        result = await tool.execute(
            pattern="def", path=str(sample_project), output_mode="files",
        )
        assert result.success
        # Should have file paths but no line numbers
        assert "main.py" in result.output
        assert ":1:" not in result.output

    @pytest.mark.asyncio
    async def test_output_mode_count(self, sample_project):
        """T31: output_mode='count' returns match counts."""
        tool = GrepTool()
        result = await tool.execute(
            pattern="def", path=str(sample_project), output_mode="count",
        )
        assert result.success
        # Should have "path: N" format
        assert ": " in result.output

    @pytest.mark.asyncio
    async def test_backward_compat(self, sample_project):
        """T32: existing parameters work as before."""
        tool = GrepTool()
        result = await tool.execute(pattern="def main", path=str(sample_project))
        assert result.success
        assert "main.py:1:" in result.output
