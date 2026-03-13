"""Grep tool — search file contents by regex pattern."""

import re
from pathlib import Path

from myaicoder.tools.base import Tool, ToolResult


class GrepTool(Tool):
    @property
    def name(self) -> str:
        return "Grep"

    @property
    def description(self) -> str:
        return (
            "Search file contents using regex patterns. "
            "Returns matching lines with file paths and line numbers. "
            "Use glob parameter to filter files by pattern."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to search for.",
                },
                "path": {
                    "type": "string",
                    "description": "File or directory to search in. Defaults to current directory.",
                },
                "glob": {
                    "type": "string",
                    "description": 'File glob filter (e.g., "*.py").',
                },
                "case_insensitive": {
                    "type": "boolean",
                    "description": "Case insensitive search (default: false).",
                },
            },
            "required": ["pattern"],
        }

    async def execute(self, **kwargs) -> ToolResult:
        pattern = kwargs.get("pattern", "")
        search_path = kwargs.get("path", ".")
        file_glob = kwargs.get("glob", None)
        case_insensitive = kwargs.get("case_insensitive", False)

        if not pattern:
            return ToolResult(success=False, output="", error="pattern is required")

        try:
            flags = re.IGNORECASE if case_insensitive else 0
            regex = re.compile(pattern, flags)
        except re.error as e:
            return ToolResult(success=False, output="", error=f"Invalid regex: {e}")

        base = Path(search_path).resolve()

        skip_dirs = {
            ".git", "node_modules", "__pycache__", ".venv", "venv",
            ".next", "dist", ".mypy_cache", ".ruff_cache",
        }

        # Collect files to search
        if base.is_file():
            files = [base]
        elif base.is_dir():
            glob_pattern = file_glob or "**/*"
            files = [
                f for f in base.glob(glob_pattern)
                if f.is_file()
                and not any(p in skip_dirs for p in f.relative_to(base).parts)
            ]
        else:
            return ToolResult(
                success=False, output="", error=f"Path not found: {search_path}"
            )

        results = []
        max_results = 500
        binary_exts = {".png", ".jpg", ".gif", ".ico", ".woff", ".ttf", ".zip", ".gz", ".tar", ".pyc"}

        for filepath in sorted(files):
            if filepath.suffix in binary_exts:
                continue
            try:
                text = filepath.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for lineno, line in enumerate(text.splitlines(), 1):
                if regex.search(line):
                    # Truncate long lines
                    display = line.rstrip()
                    if len(display) > 500:
                        display = display[:500] + "..."
                    results.append(f"{filepath}:{lineno}: {display}")
                    if len(results) >= max_results:
                        break
            if len(results) >= max_results:
                break

        if not results:
            return ToolResult(success=True, output="No matches found.")

        output = "\n".join(results)
        if len(results) >= max_results:
            output += f"\n... (truncated at {max_results} results)"

        return ToolResult(success=True, output=output)
