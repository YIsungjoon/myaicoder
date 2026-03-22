"""BuildRunner tool — execute build/test commands with structured error parsing."""

import asyncio
import re
from pathlib import Path

from myaicoder.tools.base import Tool, ToolResult

# Error parsing patterns (order: most specific first)
ERROR_PATTERNS = [
    # pytest: FAILED tests/foo.py::test_name - ErrorType: msg
    re.compile(r"FAILED\s+(.+?)::(\S+)\s*[-—]\s*(.+)"),
    # Python traceback: File "path", line N
    re.compile(r'File "(.+?)", line (\d+)'),
    # TypeScript: path(line,col): error TSxxxx: msg
    re.compile(r"(.+?)\((\d+),\d+\):\s*error\s+(.+)"),
    # Generic: path:line:col: error/warning: msg
    re.compile(r"(.+?):(\d+):\d+:\s*(?:error|warning):\s*(.+)"),
]

MAX_RAW_OUTPUT = 30000


class BuildRunnerTool(Tool):
    @property
    def name(self) -> str:
        return "BuildRunner"

    @property
    def description(self) -> str:
        return (
            "Execute a build or test command and parse errors into structured format. "
            "Supports pytest, Python tracebacks, TypeScript, and generic error formats. "
            "Always includes raw output as fallback."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Build/test command to execute.",
                },
                "working_dir": {
                    "type": "string",
                    "description": "Working directory for the command.",
                },
                "parse_errors": {
                    "type": "boolean",
                    "description": "Parse errors from output (default: true).",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default: 300).",
                },
            },
            "required": ["command"],
        }

    async def execute(self, **kwargs) -> ToolResult:
        command = kwargs.get("command", "")
        working_dir = kwargs.get("working_dir", None)
        parse_errors = kwargs.get("parse_errors", True)
        timeout = kwargs.get("timeout", 300)
        proc = None

        if not command:
            return ToolResult(success=False, output="", error="command is required")

        cwd = None
        if working_dir:
            cwd = Path(working_dir)
            if not cwd.is_dir():
                return ToolResult(
                    success=False, output="",
                    error=f"Not a directory: {working_dir}",
                )

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            if proc is not None:
                proc.kill()
                try:
                    await proc.communicate()
                except Exception:
                    pass
            return ToolResult(
                success=False, output="",
                error=f"Command timed out after {timeout}s",
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

        stdout_str = stdout.decode("utf-8", errors="replace") if stdout else ""
        stderr_str = stderr.decode("utf-8", errors="replace") if stderr else ""
        combined = stdout_str + ("\n" + stderr_str if stderr_str else "")

        # Build structured output
        parts = [f"exit_code: {proc.returncode}"]

        # Extract summary line (last non-empty line often has summary)
        summary = _extract_summary(combined)
        if summary:
            parts.append(f"summary: {summary}")

        # Parse errors
        if parse_errors and proc.returncode != 0:
            errors = _parse_errors(combined)
            if errors:
                parts.append("\nerrors:")
                for i, err in enumerate(errors, 1):
                    line_info = f":{err['line']}" if err.get("line") else ""
                    parts.append(f"  [{i}] {err['file']}{line_info} — {err['message']}")

        # Raw output (truncated)
        raw = combined[:MAX_RAW_OUTPUT]
        if len(combined) > MAX_RAW_OUTPUT:
            raw += "\n... (truncated)"
        parts.append(f"\nraw_output:\n{raw}")

        return ToolResult(
            success=proc.returncode == 0,
            output="\n".join(parts),
            error=f"Exit code: {proc.returncode}" if proc.returncode != 0 else None,
        )


def _parse_errors(output: str) -> list[dict]:
    """Parse structured errors from build output."""
    errors: list[dict] = []
    seen = set()

    for pattern in ERROR_PATTERNS:
        for match in pattern.finditer(output):
            groups = match.groups()
            if len(groups) >= 3:
                key = (groups[0], groups[1])
                if key not in seen:
                    seen.add(key)
                    errors.append({
                        "file": groups[0],
                        "line": groups[1],
                        "message": groups[2].strip(),
                    })
            elif len(groups) == 2:
                key = (groups[0], groups[1])
                if key not in seen:
                    seen.add(key)
                    errors.append({
                        "file": groups[0],
                        "line": groups[1],
                        "message": "",
                    })

    return errors[:20]  # Limit to 20 errors


def _extract_summary(output: str) -> str:
    """Extract summary line from build output."""
    lines = output.strip().splitlines()
    # Look for common summary patterns from the end
    for line in reversed(lines[-10:] if len(lines) > 10 else lines):
        line = line.strip()
        if not line:
            continue
        # pytest: "X passed", "X failed, Y passed"
        if re.search(r"\d+\s+(passed|failed|error)", line):
            return line
        # make/gcc: "Error" or "error"
        if "error" in line.lower() and len(line) < 200:
            return line
    return ""
