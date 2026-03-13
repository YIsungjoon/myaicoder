"""Tests for Write tool."""

import pytest

from myaicoder.tools.write import WriteTool


@pytest.fixture
def write_tool():
    return WriteTool()


class TestWriteTool:
    @pytest.mark.asyncio
    async def test_write_new_file(self, write_tool, tmp_path):
        path = tmp_path / "new.txt"
        result = await write_tool.execute(
            file_path=str(path), content="hello\nworld\n"
        )
        assert result.success
        assert path.read_text() == "hello\nworld\n"

    @pytest.mark.asyncio
    async def test_write_creates_dirs(self, write_tool, tmp_path):
        path = tmp_path / "sub" / "dir" / "file.txt"
        result = await write_tool.execute(
            file_path=str(path), content="nested"
        )
        assert result.success
        assert path.read_text() == "nested"

    @pytest.mark.asyncio
    async def test_write_overwrite(self, write_tool, tmp_path):
        path = tmp_path / "existing.txt"
        path.write_text("old content")
        result = await write_tool.execute(
            file_path=str(path), content="new content"
        )
        assert result.success
        assert path.read_text() == "new content"
