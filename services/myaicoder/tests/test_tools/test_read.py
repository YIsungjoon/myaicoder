"""Tests for Read tool."""

import pytest

from myaicoder.tools.read import ReadTool


@pytest.fixture
def read_tool():
    return ReadTool()


@pytest.fixture
def sample_file(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("line1\nline2\nline3\nline4\nline5\n")
    return f


class TestReadTool:
    @pytest.mark.asyncio
    async def test_read_file(self, read_tool, sample_file):
        result = await read_tool.execute(file_path=str(sample_file))
        assert result.success
        assert "line1" in result.output
        assert "line5" in result.output

    @pytest.mark.asyncio
    async def test_read_with_offset_limit(self, read_tool, sample_file):
        result = await read_tool.execute(
            file_path=str(sample_file), offset=2, limit=2
        )
        assert result.success
        assert "line2" in result.output
        assert "line3" in result.output
        assert "line1" not in result.output

    @pytest.mark.asyncio
    async def test_read_nonexistent(self, read_tool):
        result = await read_tool.execute(file_path="/nonexistent/file.txt")
        assert not result.success
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_schema(self, read_tool):
        schema = read_tool.to_openai_tool()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "Read"
        assert "file_path" in schema["function"]["parameters"]["properties"]
