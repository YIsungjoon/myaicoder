"""Bash tool — execute shell commands."""

import asyncio

from myaicoder.tools.base import Tool, ToolResult


class BashTool(Tool):
    @property
    def name(self) -> str:
        return "Bash"

    @property
    def description(self) -> str:
        return (
            "Execute a bash command and return its output. "
            "Use for system commands, git operations, running tests, etc. "
            "Commands run in the current working directory."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute.",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default: 120).",
                },
            },
            "required": ["command"],
        }

    async def execute(self, **kwargs) -> ToolResult:
        command = kwargs.get("command", "")
        timeout = kwargs.get("timeout", 120)
        proc = None

        if not command:
            return ToolResult(success=False, output="", error="command is required")

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
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
                success=False,
                output="",
                error=f"Command timed out after {timeout}s",
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

        stdout_str = stdout.decode("utf-8", errors="replace") if stdout else ""
        stderr_str = stderr.decode("utf-8", errors="replace") if stderr else ""

        # Truncate very long output
        max_len = 50000
        if len(stdout_str) > max_len:
            stdout_str = stdout_str[:max_len] + "\n... (truncated)"
        if len(stderr_str) > max_len:
            stderr_str = stderr_str[:max_len] + "\n... (truncated)"

        output = stdout_str
        if stderr_str:
            output += f"\nSTDERR:\n{stderr_str}" if output else stderr_str

        return ToolResult(
            success=proc.returncode == 0,
            output=output,
            error=f"Exit code: {proc.returncode}" if proc.returncode != 0 else None,
        )
