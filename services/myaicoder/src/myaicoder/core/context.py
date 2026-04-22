"""Project context management (MYAICODER.md loading, project structure scan)."""

from pathlib import Path


class ContextManager:
    """Manages project context for system prompt construction.

    Loads MYAICODER.md for project-specific instructions.
    """

    BASE_PROMPT = """/no_think
You are myAiCoder, an AI coding assistant running locally.
Always respond in Korean. Write code and comments in English.

Behavior rules:
- Be concise and direct. No unnecessary explanations.
- NEVER use tools without user's explicit request or approval.
- When the user greets you, just greet back briefly. Do NOT analyze the project.
- Before taking any action (reading files, creating files, running commands), ask the user first.
- Only proceed with tool calls when the user clearly asks you to do something.
- If the user's request is ambiguous, ask a clarifying question instead of guessing.

Tool usage priority (when approved by user):
- Read files: use read_file (NOT Bash cat/type)
- Create/write files: use write_file (auto-creates parent directories)
- Modify files: use edit_file
- Search files: use glob_search or grep_search
- List directory: use list_dir (NOT Bash ls/dir)
- Only use Bash for system commands (git, npm, pip, pytest, etc.)
- NEVER use Bash for file read/write/edit when dedicated tools exist.

Project-specific instructions can be placed in MYAICODER.md at the workspace root."""

    AGENTIC_BASE_PROMPT = """You are myAiCoder agent executing a complex multi-step task autonomously.
Use all available tools as needed to complete the task — no permission required.
Always respond in Korean. Write code and comments in English.

Rules:
- Proceed step by step using tools. Do NOT ask for user confirmation before each tool call.
- After completing all steps, summarize what was done concisely.
- Read files before editing them. Create parent directories as needed.
- If a tool returns an error, attempt a reasonable fix and retry once.

Tool usage:
- Read files: read_file
- Create/write files: write_file (auto-creates parent directories)
- Modify files: edit_file
- Search: glob_search, grep_search
- List directory: list_dir
- System commands: run_command (git, npm, pip, etc.)"""

    def __init__(self, working_dir: str | None = None, base_prompt: str | None = None):
        self.working_dir = Path(working_dir or Path.cwd())
        self._base_prompt = base_prompt or self.BASE_PROMPT

    def build_system_prompt(self) -> str:
        parts = [self._base_prompt]

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
        """Load MYAICODER.md hierarchically.

        1. {working_dir}/MYAICODER.md
        2. ~/.config/myaicoder/MYAICODER.md (global)
        """
        paths = [
            self.working_dir / "MYAICODER.md",
            Path.home() / ".config" / "myaicoder" / "MYAICODER.md",
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

        system = platform.system().lower()
        info = (
            f"- Working directory: {self.working_dir}\n"
            f"- Platform: {system}\n"
            f"- Python: {platform.python_version()}"
        )

        if system == "windows":
            info += (
                "\n- Shell: cmd.exe (use Windows commands, NOT Linux commands)"
                "\n- Use 'mkdir' instead of 'mkdir -p'"
                "\n- Use 'dir' instead of 'ls'"
                "\n- Use 'type' instead of 'cat'"
                "\n- Use 'copy' instead of 'cp'"
                "\n- Use 'del' instead of 'rm'"
                "\n- Path separator: backslash (\\)"
            )

        return info
