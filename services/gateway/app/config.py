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


class GatewayConfig(BaseModel):
    server: ServerConfig = ServerConfig()
    auth: AuthConfig = AuthConfig()
    models: ModelsConfig = ModelsConfig()
    logging: LoggingConfig = LoggingConfig()

    @classmethod
    def load(cls, path: str | Path | None = None) -> GatewayConfig:
        """Load config from YAML file. Falls back to env var GATEWAY_CONFIG, then defaults."""
        if path is None:
            path = os.environ.get("GATEWAY_CONFIG", "gateway.yaml")

        config_path = Path(path)
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return cls.model_validate(data)

        return cls()
