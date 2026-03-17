from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel


class UserConfig(BaseModel):
    api_key_hash: str
    user_id: str
    name: str
    org: str
    role: str = "user"


class AuthConfig(BaseModel):
    users: list[UserConfig] = []
    internal_token: str = ""


class RouteConfig(BaseModel):
    name: str
    upstream: str
    description: str = ""


class ModelsConfig(BaseModel):
    default: str = ""
    routes: list[RouteConfig] = []


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8080


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: str = "json"


class RoleLimitConfig(BaseModel):
    requests_per_minute: int = 30
    requests_per_hour: int = 500


class UserOverrideConfig(BaseModel):
    user_id: str
    requests_per_minute: int
    requests_per_hour: int


class RateLimitConfig(BaseModel):
    enabled: bool = True
    roles: dict[str, RoleLimitConfig] = {
        "admin": RoleLimitConfig(requests_per_minute=120, requests_per_hour=3600),
        "user": RoleLimitConfig(requests_per_minute=30, requests_per_hour=500),
    }
    overrides: list[UserOverrideConfig] = []


class DatabaseConfig(BaseModel):
    url: str = ""
    enabled: bool = False


class ConcurrencyConfig(BaseModel):
    max_per_user: int = 1
    max_global: int = 4


class GatewayConfig(BaseModel):
    server: ServerConfig = ServerConfig()
    auth: AuthConfig = AuthConfig()
    models: ModelsConfig = ModelsConfig()
    rate_limit: RateLimitConfig = RateLimitConfig()
    concurrency: ConcurrencyConfig = ConcurrencyConfig()
    logging: LoggingConfig = LoggingConfig()
    database: DatabaseConfig = DatabaseConfig()

    @classmethod
    def load(cls, path: str | Path | None = None) -> GatewayConfig:
        """Load config from YAML file.

        Search order:
        1. Explicit path argument
        2. GATEWAY_CONFIG env var
        3. config/gateway.yaml (central config directory)
        4. ./gateway.yaml (service directory, backward compat)
        """
        if path is not None:
            config_path = Path(path)
            if config_path.exists():
                return cls._load_yaml(config_path)
            return cls()

        env_path = os.environ.get("GATEWAY_CONFIG")
        search: list[Path] = []
        if env_path:
            search.append(Path(env_path))
        search.extend([
            Path("config/gateway.yaml"),
            Path("gateway.yaml"),
        ])

        for p in search:
            if p.exists():
                return cls._load_yaml(p)

        return cls()

    @classmethod
    def _load_yaml(cls, path: Path) -> GatewayConfig:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls.model_validate(data)
