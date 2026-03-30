"""Tests for Edit tool."""

import pytest

from myaicoder.tools.filesystem.edit import EditTool


@pytest.fixture
def edit_tool():
    return EditTool()


@pytest.fixture
def sample_file(tmp_path):
    f = tmp_path / "code.py"
    f.write_text('def hello():\n    print("hello")\n\ndef world():\n    print("world")\n')
    return f


class TestEditTool:
    @pytest.mark.asyncio
    async def test_replace_unique(self, edit_tool, sample_file):
        result = await edit_tool.execute(
            file_path=str(sample_file),
            old_string='print("hello")',
            new_string='print("hi")',
        )
        assert result.success
        assert 'print("hi")' in sample_file.read_text()

    @pytest.mark.asyncio
    async def test_reject_non_unique(self, edit_tool, tmp_path):
        f = tmp_path / "dup.txt"
        f.write_text("aaa\nbbb\naaa\n")
        result = await edit_tool.execute(
            file_path=str(f), old_string="aaa", new_string="ccc"
        )
        assert not result.success
        assert "2 times" in result.error

    @pytest.mark.asyncio
    async def test_replace_all(self, edit_tool, tmp_path):
        f = tmp_path / "dup.txt"
        f.write_text("aaa\nbbb\naaa\n")
        result = await edit_tool.execute(
            file_path=str(f), old_string="aaa", new_string="ccc", replace_all=True
        )
        assert result.success
        assert f.read_text() == "ccc\nbbb\nccc\n"

    @pytest.mark.asyncio
    async def test_not_found(self, edit_tool, sample_file):
        result = await edit_tool.execute(
            file_path=str(sample_file),
            old_string="nonexistent",
            new_string="something",
        )
        assert not result.success
        assert "not found" in result.error
