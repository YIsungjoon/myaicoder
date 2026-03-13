"""MCP configuration loader — Claude Code .mcp.json compatible."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class MCPServerConfig:
    """Configuration for a single MCP server."""

    transport: str  # "stdio" | "http"
    command: str | None = None  # stdio: command to run
    args: list[str] = field(default_factory=list)  # stdio: command arguments
    env: dict[str, str] = field(default_factory=dict)  # environment variables
    url: str | None = None  # http: server URL


@dataclass
class MCPConfig:
    """Collection of MCP server configurations."""

    servers: dict[str, MCPServerConfig] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | None = None) -> "MCPConfig":
        """Load .mcp.json compatible with Claude Code.

        Search order:
        1. Explicit path
        2. {cwd}/.mcp.json (project scope)
        3. ~/.myaicoder/mcp.json (user scope)
        """
        search_paths: list[Path] = []
        if path:
            search_paths.append(Path(path))
        search_paths.extend([
            Path.cwd() / ".mcp.json",
            Path.home() / ".myaicoder" / "mcp.json",
        ])

        for p in search_paths:
            if p.exists():
                return cls._from_file(p)

        return cls()

    @classmethod
    def _from_file(cls, path: Path) -> "MCPConfig":
        with open(path) as f:
            data = json.load(f)

        servers: dict[str, MCPServerConfig] = {}

        # Claude Code format: {"mcpServers": {...}}
        raw_servers = data.get("mcpServers", data.get("servers", {}))

        for name, cfg in raw_servers.items():
            transport = cfg.get("transport", "stdio")

            # Resolve environment variable references like ${VAR}
            env = {}
            for k, v in cfg.get("env", {}).items():
                if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
                    env_var = v[2:-1]
                    env[k] = os.environ.get(env_var, "")
                else:
                    env[k] = v

            servers[name] = MCPServerConfig(
                transport=transport,
                command=cfg.get("command"),
                args=cfg.get("args", []),
                env=env,
                url=cfg.get("url"),
            )

        return cls(servers=servers)
