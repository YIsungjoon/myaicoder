"""Configuration management."""

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LLMConfig:
    provider: str = "vllm"
    base_url: str = "http://localhost:8080/v1"
    model: str = "qwen3.5-9b"
    temperature: float = 0.0
    max_tokens: int = 8192


@dataclass
class UIConfig:
    theme: str = "dark"
    markdown_render: bool = True
    show_token_usage: bool = True


@dataclass
class ToolsConfig:
    enabled: bool = True
    require_approval: list[str] = field(
        default_factory=lambda: ["Bash", "Write", "Edit"]
    )
    auto_approve: list[str] = field(
        default_factory=lambda: ["Read", "Glob", "Grep"]
    )
    max_result_tokens: int = 4000


@dataclass
class ServerConfig:
    """MCP Server configuration."""

    transport: str = "stdio"
    port: int = 3000
    allow_bash: bool = False
    working_dir: str | None = None
    max_concurrent: int = 1
    enable_agentic: bool = False


@dataclass
class ContextConfig:
    max_tokens: int = 32768
    compression_threshold: float = 0.8


@dataclass
class SessionConfig:
    auto_save: bool = True
    auto_load: bool = True
    max_sessions: int = 20
    sessions_dir: str | None = None


@dataclass
class AppConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    tools: ToolsConfig = field(default_factory=ToolsConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    session: SessionConfig = field(default_factory=SessionConfig)

    @classmethod
    def load(cls, path: str | None = None) -> "AppConfig":
        """Load config from JSON file.

        Search order:
        1. Explicit path
        2. ./myaicoder.json (project scope)
        3. ~/.config/myaicoder/config.json (user scope)
        """
        search_paths = []
        if path:
            search_paths.append(Path(path))
        search_paths.extend([
            Path.cwd() / "myaicoder.json",
            Path.home() / ".config" / "myaicoder" / "config.json",
        ])

        for p in search_paths:
            if p.exists():
                return cls._from_file(p)

        return cls()

    @classmethod
    def _from_file(cls, path: Path) -> "AppConfig":
        with open(path) as f:
            data = json.load(f)

        config = cls()
        if "llm" in data:
            for k, v in data["llm"].items():
                if hasattr(config.llm, k):
                    setattr(config.llm, k, v)
        if "tools" in data:
            for k, v in data["tools"].items():
                if hasattr(config.tools, k):
                    setattr(config.tools, k, v)
        if "ui" in data:
            for k, v in data["ui"].items():
                if hasattr(config.ui, k):
                    setattr(config.ui, k, v)
        if "context" in data:
            for k, v in data["context"].items():
                if hasattr(config.context, k):
                    setattr(config.context, k, v)
        if "server" in data:
            for k, v in data["server"].items():
                if hasattr(config.server, k):
                    setattr(config.server, k, v)
        if "session" in data:
            for k, v in data["session"].items():
                if hasattr(config.session, k):
                    setattr(config.session, k, v)

        return config
