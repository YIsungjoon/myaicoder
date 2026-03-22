"""Read tool — read file contents."""

from pathlib import Path

from myaicoder.tools.base import Tool, ToolResult


class ReadTool(Tool):
    @property
    def name(self) -> str:
        return "Read"

    @property
    def description(self) -> str:
        return (
            "Read a file from the filesystem. "
            "Returns file contents with line numbers. "
            "Use offset and limit for large files."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the file to read.",
                },
                "offset": {
                    "type": "integer",
                    "description": "Line number to start reading from (1-based).",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of lines to read.",
                },
            },
            "required": ["file_path"],
        }

    async def execute(self, **kwargs) -> ToolResult:
        file_path = kwargs.get("file_path", "")
        offset = kwargs.get("offset", 1)
        limit = kwargs.get("limit", 2000)

        if not file_path:
            return ToolResult(success=False, output="", error="file_path is required")

        path = Path(file_path)
        if not path.exists():
            return ToolResult(
                success=False, output="", error=f"File not found: {file_path}"
            )
        if not path.is_file():
            return ToolResult(
                success=False, output="", error=f"Not a file: {file_path}"
            )

        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

        lines = text.splitlines()
        start = max(0, offset - 1)
        end = start + limit
        selected = lines[start:end]

        numbered = []
        for i, line in enumerate(selected, start=start + 1):
            # Truncate long lines
            if len(line) > 2000:
                line = line[:2000] + "..."
            numbered.append(f"{i:>6}\t{line}")

        output = "\n".join(numbered)
        return ToolResult(success=True, output=output)
