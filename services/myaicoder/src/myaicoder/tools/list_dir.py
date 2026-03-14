"""ListDir tool — display directory structure as a tree."""

from pathlib import Path

from myaicoder.tools.base import Tool, ToolResult

SKIP_DIRS = {
    "node_modules", "__pycache__", "venv", ".venv",
    ".next", "dist", ".mypy_cache", ".ruff_cache",
    ".tox", ".eggs", "build", ".build",
}

MAX_ITEMS = 500


class ListDirTool(Tool):
    @property
    def name(self) -> str:
        return "ListDir"

    @property
    def description(self) -> str:
        return (
            "List directory contents as a tree structure. "
            "Automatically skips hidden directories and common build artifacts. "
            "Use max_depth to control tree depth."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to list.",
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Maximum depth (default: 3).",
                },
                "show_hidden": {
                    "type": "boolean",
                    "description": "Show hidden files/dirs (default: false).",
                },
            },
            "required": ["path"],
        }

    async def execute(self, **kwargs) -> ToolResult:
        path_str = kwargs.get("path", ".")
        max_depth = kwargs.get("max_depth", 3)
        show_hidden = kwargs.get("show_hidden", False)

        root = Path(path_str).resolve()
        if not root.is_dir():
            return ToolResult(
                success=False, output="", error=f"Not a directory: {path_str}"
            )

        lines = _build_tree(root, max_depth, show_hidden)
        return ToolResult(success=True, output="\n".join(lines))


def _build_tree(root: Path, max_depth: int, show_hidden: bool) -> list[str]:
    """Build directory tree with FB-A filtering."""
    lines: list[str] = [f"{root.name}/"]
    count = 1

    def _walk(dir_path: Path, prefix: str, depth: int) -> None:
        nonlocal count
        if depth > max_depth or count >= MAX_ITEMS:
            return

        try:
            entries = sorted(
                dir_path.iterdir(),
                key=lambda e: (not e.is_dir(), e.name.lower()),
            )
        except PermissionError:
            return

        # FB-A: Filter entries — skip hidden and ignored dirs BEFORE recursion
        visible = []
        for entry in entries:
            if not show_hidden and entry.name.startswith("."):
                continue
            if entry.is_dir() and entry.name in SKIP_DIRS:
                continue
            visible.append(entry)

        for i, entry in enumerate(visible):
            if count >= MAX_ITEMS:
                lines.append(f"{prefix}\u2514\u2500\u2500 ... ({MAX_ITEMS} items limit)")
                return

            is_last = i == len(visible) - 1
            connector = "\u2514\u2500\u2500 " if is_last else "\u251c\u2500\u2500 "
            suffix = "/" if entry.is_dir() else ""
            lines.append(f"{prefix}{connector}{entry.name}{suffix}")
            count += 1

            if entry.is_dir():
                extension = "    " if is_last else "\u2502   "
                _walk(entry, prefix + extension, depth + 1)

    _walk(root, "", 1)
    return lines
