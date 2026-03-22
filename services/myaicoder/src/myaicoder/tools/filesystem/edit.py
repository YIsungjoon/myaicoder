"""Edit tool — exact string replacement in files."""

from pathlib import Path

from myaicoder.tools.base import Tool, ToolResult


class EditTool(Tool):
    @property
    def name(self) -> str:
        return "Edit"

    @property
    def description(self) -> str:
        return (
            "Perform exact string replacement in a file. "
            "The old_string must match exactly and be unique in the file. "
            "Use replace_all=true to replace all occurrences."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the file to edit.",
                },
                "old_string": {
                    "type": "string",
                    "description": "The exact text to find and replace.",
                },
                "new_string": {
                    "type": "string",
                    "description": "The replacement text.",
                },
                "replace_all": {
                    "type": "boolean",
                    "description": "Replace all occurrences (default: false).",
                },
            },
            "required": ["file_path", "old_string", "new_string"],
        }

    async def execute(self, **kwargs) -> ToolResult:
        file_path = kwargs.get("file_path", "")
        old_string = kwargs.get("old_string", "")
        new_string = kwargs.get("new_string", "")
        replace_all = kwargs.get("replace_all", False)

        if not file_path:
            return ToolResult(success=False, output="", error="file_path is required")
        if not old_string:
            return ToolResult(success=False, output="", error="old_string is required")
        if old_string == new_string:
            return ToolResult(
                success=False, output="", error="old_string and new_string are identical"
            )

        path = Path(file_path)
        if not path.exists():
            return ToolResult(
                success=False, output="", error=f"File not found: {file_path}"
            )

        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

        count = content.count(old_string)
        if count == 0:
            return ToolResult(
                success=False,
                output="",
                error="old_string not found in file",
            )

        if not replace_all and count > 1:
            return ToolResult(
                success=False,
                output="",
                error=f"old_string found {count} times. Use replace_all=true or provide more context.",
            )

        if replace_all:
            new_content = content.replace(old_string, new_string)
        else:
            new_content = content.replace(old_string, new_string, 1)

        try:
            path.write_text(new_content, encoding="utf-8")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

        replacements = count if replace_all else 1
        return ToolResult(
            success=True,
            output=f"Replaced {replacements} occurrence(s) in {file_path}",
        )
