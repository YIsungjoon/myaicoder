"""Configuration management."""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

_ALLOWED_LLM_SCHEMES = frozenset({"http", "https"})

# Maps env var name → (config attribute path, validator/transformer)
# Extend this table to add new env overrides — never add bare if-blocks.
_ENV_OVERRIDES: list[tuple[str, str, str]] = [
    ("MYAICODER_API_KEY",    "llm.api_key",  "str"),
    ("MYAICODER_LLM_URL",    "llm.base_url", "url"),
    ("MYAICODER_LLM_MODEL",  "llm.model",    "str"),
]


class InvalidLLMEndpointError(ValueError):
    pass


def _validate_url(raw: str) -> str:
    parsed = urlparse(raw)
    if parsed.scheme not in _ALLOWED_LLM_SCHEMES or not parsed.netloc:
        raise InvalidLLMEndpointError(
            f"MYAICODER_LLM_URL must start with http:// or https:// — got: {raw!r}"
        )
    if parsed.username or parsed.password:
        raise InvalidLLMEndpointError(
            "Credentials embedded in MYAICODER_LLM_URL are not allowed"
        )
    return raw.rstrip("/")


_TRANSFORMERS = {
    "str": str,
    "url": _validate_url,
}


@dataclass
class LLMConfig:
    provider: str = "vllm"
    base_url: str = "http://localhost:8080/v1"
    model: str = ""          # empty = omit from request; server uses its loaded model
    temperature: float = 0.0
    max_tokens: int = 4096   # safe default; raise via config if server has larger -c
    api_key: str = ""


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
        """Load config from JSON file, then apply environment variable overrides.

        Search order:
        1. Explicit path
        2. ./myaicoder.json (project scope)
        3. ~/.config/myaicoder/config.json (user scope)

        Environment variables (from .env or shell) always take final precedence.
        """
        load_dotenv()

        search_paths = []
        if path:
            search_paths.append(Path(path))
        search_paths.extend([
            Path.cwd() / "myaicoder.json",
            Path.home() / ".config" / "myaicoder" / "config.json",
        ])

        for p in search_paths:
            if p.exists():
                config = cls._from_file(p)
                break
        else:
            config = cls()

        cls._apply_env_overrides(config)
        return config

    @classmethod
    def _apply_env_overrides(cls, config: "AppConfig") -> None:
        default_llm = LLMConfig()
        for env_var, attr_path, kind in _ENV_OVERRIDES:
            raw = os.environ.get(env_var, "").strip()
            if not raw:
                continue

            transform = _TRANSFORMERS[kind]
            value = transform(raw)

            section, attr = attr_path.split(".", 1)
            setattr(getattr(config, section), attr, value)
            logger.debug("env override applied: %s → %s", env_var, attr_path)

        # Warn if URL changed but model is still the default
        if config.llm.base_url != default_llm.base_url and config.llm.model == default_llm.model:
            logger.warning(
                "MYAICODER_LLM_URL is set to a non-default server but "
                "MYAICODER_LLM_MODEL is still the default (%s) — "
                "set MYAICODER_LLM_MODEL if the remote server uses a different model.",
                config.llm.model,
            )

    @classmethod
    def _from_file(cls, path: Path) -> "AppConfig":
        with open(path) as f:
            data = json.load(f)

        config = cls()
        for section_name in ("llm", "tools", "ui", "context", "server", "session"):
            section_data = data.get(section_name, {})
            section_obj = getattr(config, section_name)
            for k, v in section_data.items():
                if hasattr(section_obj, k):
                    setattr(section_obj, k, v)

        return config
