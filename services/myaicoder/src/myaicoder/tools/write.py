"""Write tool — create or overwrite files."""

from pathlib import Path

from myaicoder.tools.base import Tool, ToolResult


class WriteTool(Tool):
    @property
    def name(self) -> str:
        return "Write"

    @property
    def description(self) -> str:
        return (
            "Write content to a file. Creates the file if it doesn't exist. "
            "Overwrites existing content. Creates parent directories as needed."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the file to write.",
                },
                "content": {
                    "type": "string",
                    "description": "The content to write to the file.",
                },
            },
            "required": ["file_path", "content"],
        }

    async def execute(self, **kwargs) -> ToolResult:
        file_path = kwargs.get("file_path", "")
        content = kwargs.get("content", "")

        if not file_path:
            return ToolResult(success=False, output="", error="file_path is required")

        try:
            path = self.validate_path(file_path)
        except ValueError as e:
            return ToolResult(success=False, output="", error=str(e))

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

        line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
        return ToolResult(
            success=True,
            output=f"Wrote {line_count} lines to {file_path}",
        )
