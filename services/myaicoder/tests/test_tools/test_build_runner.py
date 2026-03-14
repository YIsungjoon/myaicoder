"""Tests for BuildRunner tool (T15~T21)."""

import pytest

from myaicoder.tools.build_runner import BuildRunnerTool, _extract_summary, _parse_errors


@pytest.fixture
def tool():
    return BuildRunnerTool()


class TestBuildRunner:
    @pytest.mark.asyncio
    async def test_successful_command(self, tool):
        """T15: Successful command returns exit_code 0."""
        result = await tool.execute(command="echo 'all good'")
        assert result.success
        assert "exit_code: 0" in result.output

    @pytest.mark.asyncio
    async def test_failed_command(self, tool):
        """T16: Failed command returns non-zero exit code."""
        result = await tool.execute(command="false")
        assert not result.success
        assert "exit_code:" in result.output

    @pytest.mark.asyncio
    async def test_working_dir(self, tool, tmp_path):
        """T20: working_dir changes cwd."""
        result = await tool.execute(command="pwd", working_dir=str(tmp_path))
        assert result.success
        assert str(tmp_path) in result.output

    @pytest.mark.asyncio
    async def test_timeout(self, tool):
        """T21: Timeout handled."""
        result = await tool.execute(command="sleep 10", timeout=1)
        assert not result.success
        assert "timed out" in result.error.lower()


class TestErrorParsing:
    def test_parse_pytest_errors(self):
        """T17: pytest FAILED line parsed."""
        output = "FAILED tests/test_foo.py::test_bar - AssertionError: expected 3"
        errors = _parse_errors(output)
        assert len(errors) >= 1
        assert errors[0]["file"] == "tests/test_foo.py"
        assert "AssertionError" in errors[0]["message"]

    def test_parse_python_traceback(self):
        """T18: Python File '...', line N parsed."""
        output = '''Traceback (most recent call last):
  File "src/main.py", line 42, in foo
    raise ValueError("bad")
ValueError: bad'''
        errors = _parse_errors(output)
        assert len(errors) >= 1
        assert errors[0]["file"] == "src/main.py"
        assert errors[0]["line"] == "42"

    def test_parse_generic_errors(self):
        """T19: path:line:col: error: msg parsed."""
        output = "src/app.py:10:5: error: undefined variable 'x'\n"
        errors = _parse_errors(output)
        assert len(errors) >= 1
        assert errors[0]["file"] == "src/app.py"
        assert errors[0]["line"] == "10"

    def test_extract_summary_pytest(self):
        """Extract pytest summary line."""
        output = "collecting...\n====\n2 failed, 18 passed in 0.5s\n"
        summary = _extract_summary(output)
        assert "failed" in summary
        assert "passed" in summary
