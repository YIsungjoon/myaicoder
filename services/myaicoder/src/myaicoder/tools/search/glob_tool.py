"""Glob tool — find files by pattern."""


from myaicoder.tools.base import Tool, ToolResult


class GlobTool(Tool):
    @property
    def name(self) -> str:
        return "Glob"

    @property
    def description(self) -> str:
        return (
            "Find files matching a glob pattern. "
            'Supports patterns like "**/*.py", "src/**/*.ts". '
            "Returns matching file paths sorted by modification time."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": 'Glob pattern (e.g., "**/*.py").',
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in. Defaults to current directory.",
                },
            },
            "required": ["pattern"],
        }

    async def execute(self, **kwargs) -> ToolResult:
        pattern = kwargs.get("pattern", "")
        search_path = kwargs.get("path", ".")

        if not pattern:
            return ToolResult(success=False, output="", error="pattern is required")

        try:
            base = self.validate_path(search_path)
        except ValueError as e:
            return ToolResult(success=False, output="", error=str(e))
        if not base.is_dir():
            return ToolResult(
                success=False, output="", error=f"Not a directory: {search_path}"
            )

        try:
            matches = sorted(base.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

        # Filter out hidden dirs and common ignore patterns
        skip_dirs = {
            ".git", "node_modules", "__pycache__", ".venv", "venv",
            ".next", "dist", ".mypy_cache", ".ruff_cache",
        }

        filtered = []
        for m in matches:
            parts = m.relative_to(base).parts
            if any(p in skip_dirs for p in parts):
                continue
            if m.is_file():
                filtered.append(str(m))

        if not filtered:
            return ToolResult(success=True, output="No matching files found.")

        # Limit output
        total = len(filtered)
        shown = filtered[:200]
        output = "\n".join(shown)
        if total > 200:
            output += f"\n... and {total - 200} more files"

        return ToolResult(success=True, output=output)
