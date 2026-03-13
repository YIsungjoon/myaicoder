"""Project context management (CLAUDE.md loading, project structure scan)."""

from pathlib import Path


class ContextManager:
    """Manages project context for system prompt construction.

    Compatible with Claude Code's CLAUDE.md loading convention.
    """

    BASE_PROMPT = """/no_think
You are myAiCoder, an AI coding assistant running locally.
You help users with software engineering tasks: writing code, debugging, refactoring, and more.
You have access to tools for reading, writing, and editing files, searching code, and running commands.
Be concise and direct. Focus on solving the user's problem."""

    def __init__(self, working_dir: str | None = None):
        self.working_dir = Path(working_dir or Path.cwd())

    def build_system_prompt(self) -> str:
        parts = [self.BASE_PROMPT]

        claude_md = self._load_claude_md()
        if claude_md:
            parts.append(f"# Project Context\n{claude_md}")

        structure = self._scan_project_structure()
        if structure:
            parts.append(f"# Project Structure\n```\n{structure}\n```")

        env_info = self._environment_info()
        parts.append(f"# Environment\n{env_info}")

        return "\n\n".join(parts)

    def _load_claude_md(self) -> str | None:
        """Load CLAUDE.md hierarchically.

        1. {working_dir}/CLAUDE.md
        2. ~/.config/myaicoder/CLAUDE.md (global)
        """
        paths = [
            self.working_dir / "CLAUDE.md",
            Path.home() / ".config" / "myaicoder" / "CLAUDE.md",
        ]

        contents = []
        for p in paths:
            if p.exists():
                contents.append(p.read_text(encoding="utf-8"))

        return "\n\n".join(contents) if contents else None

    def _scan_project_structure(self, max_depth: int = 3) -> str | None:
        """Scan project directory structure, respecting .gitignore."""
        if not self.working_dir.is_dir():
            return None

        lines = []
        self._walk_dir(self.working_dir, lines, depth=0, max_depth=max_depth)
        return "\n".join(lines) if lines else None

    def _walk_dir(
        self, path: Path, lines: list[str], depth: int, max_depth: int
    ) -> None:
        if depth >= max_depth:
            return

        skip_dirs = {
            ".git", "node_modules", "__pycache__", ".venv", "venv",
            ".next", "dist", ".terraform", ".mypy_cache", ".ruff_cache",
        }

        try:
            entries = sorted(path.iterdir(), key=lambda e: (not e.is_dir(), e.name))
        except PermissionError:
            return

        for entry in entries:
            if entry.name.startswith(".") and entry.is_dir():
                continue
            if entry.name in skip_dirs:
                continue

            indent = "  " * depth
            if entry.is_dir():
                lines.append(f"{indent}{entry.name}/")
                self._walk_dir(entry, lines, depth + 1, max_depth)
            else:
                lines.append(f"{indent}{entry.name}")

    def _environment_info(self) -> str:
        import platform

        return (
            f"- Working directory: {self.working_dir}\n"
            f"- Platform: {platform.system().lower()}\n"
            f"- Python: {platform.python_version()}"
        )
