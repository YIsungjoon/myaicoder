"""Tests for ListDir tool (T1~T7)."""

import pytest

from myaicoder.tools.filesystem.list_dir import ListDirTool


@pytest.fixture
def sample_project(tmp_path):
    """Create a project with various dirs including ignored ones."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')")
    (tmp_path / "src" / "utils.py").write_text("x = 1")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").write_text("pass")
    (tmp_path / "README.md").write_text("# Readme")
    # Ignored dirs
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main")
    (tmp_path / ".git" / "objects").mkdir()
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "express").mkdir()
    (tmp_path / "node_modules" / "express" / "index.js").write_text("")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "main.cpython-312.pyc").write_bytes(b"")
    # Hidden file
    (tmp_path / ".env").write_text("SECRET=123")
    return tmp_path


@pytest.fixture
def tool():
    return ListDirTool()


class TestListDir:
    @pytest.mark.asyncio
    async def test_basic_tree(self, tool, sample_project):
        """T1: Basic tree output."""
        result = await tool.execute(path=str(sample_project))
        assert result.success
        assert "src/" in result.output
        assert "main.py" in result.output
        assert "README.md" in result.output

    @pytest.mark.asyncio
    async def test_skip_hidden_dirs(self, tool, sample_project):
        """T2: .git and .venv are skipped (FB-A)."""
        result = await tool.execute(path=str(sample_project))
        assert result.success
        assert ".git" not in result.output
        assert "HEAD" not in result.output

    @pytest.mark.asyncio
    async def test_skip_node_modules(self, tool, sample_project):
        """T3: node_modules and __pycache__ are skipped (FB-A)."""
        result = await tool.execute(path=str(sample_project))
        assert result.success
        # node_modules dir should not appear as a tree entry
        assert "node_modules/" not in result.output
        assert "__pycache__/" not in result.output
        assert "express" not in result.output

    @pytest.mark.asyncio
    async def test_show_hidden_flag(self, tool, sample_project):
        """T4: show_hidden=True shows hidden files."""
        result = await tool.execute(path=str(sample_project), show_hidden=True)
        assert result.success
        assert ".env" in result.output

    @pytest.mark.asyncio
    async def test_max_depth(self, tool, sample_project):
        """T5: max_depth limits recursion."""
        result = await tool.execute(path=str(sample_project), max_depth=1)
        assert result.success
        assert "src/" in result.output
        # Files inside src should NOT appear at depth 1
        assert "main.py" not in result.output

    @pytest.mark.asyncio
    async def test_max_items_limit(self, tool, tmp_path):
        """T6: 500 items limit enforced."""
        from myaicoder.tools.filesystem.list_dir import MAX_ITEMS

        # Create many files
        for i in range(MAX_ITEMS + 50):
            (tmp_path / f"file_{i:04d}.txt").write_text("")

        result = await tool.execute(path=str(tmp_path), max_depth=1)
        assert result.success
        assert "limit" in result.output

    @pytest.mark.asyncio
    async def test_nonexistent_path(self, tool):
        """T7: Error for nonexistent path."""
        result = await tool.execute(path="/nonexistent/path")
        assert not result.success
        assert "Not a directory" in result.error
