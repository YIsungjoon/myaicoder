"""AgentsmdLoader: load AGENTS.md files for agent personality/knowledge."""

from __future__ import annotations

from pathlib import Path


class AgentsmdLoader:
    """Load AGENTS.md files hierarchically.

    Search order:
    1. {working_dir}/AGENTS.md
    2. ~/.config/myaicoder/AGENTS.md (global)

    Multiple files are concatenated with double newlines.
    """

    def __init__(self, working_dir: Path | None = None):
        self._working_dir = working_dir or Path.cwd()

    def load(self) -> str | None:
        """Load and concatenate all found AGENTS.md files."""
        paths = [
            self._working_dir / "AGENTS.md",
            Path.home() / ".config" / "myaicoder" / "AGENTS.md",
        ]
        contents = []
        for p in paths:
            if p.exists():
                try:
                    text = p.read_text(encoding="utf-8").strip()
                    if text:
                        contents.append(text)
                except OSError:
                    continue
        return "\n\n".join(contents) if contents else None
