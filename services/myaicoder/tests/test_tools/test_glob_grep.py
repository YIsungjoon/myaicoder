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
