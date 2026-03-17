"""Base interface for all tools."""

import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ToolResult:
    """Result from tool execution."""

    success: bool
    output: str
    error: str | None = None


class WorkspaceGuard:
    """Validate file paths are within the allowed workspace root."""

    def __init__(self, workspace_root: str | None = None):
        self._root = Path(workspace_root or os.getcwd()).resolve()

    @property
    def root(self) -> Path:
        return self._root

    def validate(self, file_path: str) -> Path:
        """Resolve and validate path is within workspace.

        Returns the resolved Path if valid.
        Raises ValueError if path escapes workspace.
        """
        target = Path(file_path).resolve()
        try:
            target.relative_to(self._root)
        except ValueError:
            raise ValueError(
                f"Access denied: '{file_path}' is outside workspace '{self._root}'"
            )
        return target


# Blocked command patterns for BashTool and BuildRunnerTool
BLOCKED_COMMAND_PATTERNS = [
    re.compile(r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?/(?!\S)"),  # rm -rf /
    re.compile(r"\bmkfs\b"),                                      # filesystem format
    re.compile(r"\bdd\s+.*of=/dev/"),                             # disk overwrite
    re.compile(r":\(\)\s*\{.*\}\s*;"),                            # fork bomb
    re.compile(r"\bshutdown\b"),                                  # system shutdown
    re.compile(r"\breboot\b"),                                    # system reboot
    re.compile(r"\beval\s"),                                      # eval execution
    re.compile(r"\bexec\s"),                                      # exec execution
    re.compile(r"\$\("),                                          # command substitution
    re.compile(r"`[^`]+`"),                                       # backtick substitution
]


def validate_command(command: str) -> str | None:
    """Check if command matches any blocked pattern.

    Returns error message if blocked, None if safe.
    """
    for pattern in BLOCKED_COMMAND_PATTERNS:
        if pattern.search(command):
            return f"Blocked: command matches safety pattern '{pattern.pattern}'"
    return None


class Tool(ABC):
    """Tool interface. Built-in and MCP tools implement this."""

    _workspace_guard: WorkspaceGuard | None = None

    @classmethod
    def set_workspace_guard(cls, guard: WorkspaceGuard) -> None:
        """Set workspace guard for all file tools."""
        cls._workspace_guard = guard

    def validate_path(self, file_path: str) -> Path:
        """Validate path against workspace guard. Call from file tools."""
        if self._workspace_guard is None:
            return Path(file_path)
        return self._workspace_guard.validate(file_path)

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @property
    @abstractmethod
    def parameters_schema(self) -> dict:
        """OpenAI function calling compatible JSON Schema."""
        pass

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        pass

    def to_openai_tool(self) -> dict:
        """Convert to OpenAI function calling schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }

    def to_mcp_tool(self) -> dict:
        """Convert to MCP tool schema."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.parameters_schema,
        }
