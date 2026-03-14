"""Models configuration — YAML loading and environment-aware settings."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class VLLMArgs:
    gpu_memory_utilization: float = 0.9
    max_model_len: int = 32768
    extra_args: list[str] = field(default_factory=list)


@dataclass
class ModelDefaults:
    temperature: float = 0.0
    max_tokens: int = 8192


@dataclass
class ModelProfile:
    name: str
    file: str
    description: str = ""
    port: int = 8001
    always_on: bool = False
    vllm_args: VLLMArgs = field(default_factory=VLLMArgs)
    defaults: ModelDefaults = field(default_factory=ModelDefaults)


@dataclass
class ModelsConfig:
    environment: str = "dev"
    models_dir: str = "~/models"
    default_model: str = ""
    port: int = 8001
    gateway_url: str = ""
    internal_token: str = ""
    instances: list[ModelProfile] = field(default_factory=list)

    @classmethod
    def load(cls, path: str | Path | None = None) -> ModelsConfig:
        """Load models config.

        Search order:
        1. Explicit path
        2. ./models.yaml (project scope)
        3. ~/.config/myaicoder/models.yaml (user scope)
        """
        search: list[Path] = []
        if path:
            search.append(Path(path))
        search.extend([
            Path.cwd() / "models.yaml",
            Path.home() / ".config" / "myaicoder" / "models.yaml",
        ])

        for p in search:
            if p.exists():
                return cls._from_yaml(p)
        return cls()

    @classmethod
    def _from_yaml(cls, path: Path) -> ModelsConfig:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        instances: list[ModelProfile] = []
        for item in data.get("instances", []):
            vllm_raw = item.get("vllm_args", {})
            defaults_raw = item.get("defaults", {})
            instances.append(ModelProfile(
                name=item["name"],
                file=item["file"],
                description=item.get("description", ""),
                port=item.get("port", data.get("port", 8001)),
                always_on=item.get("always_on", False),
                vllm_args=VLLMArgs(
                    gpu_memory_utilization=vllm_raw.get("gpu_memory_utilization", 0.9),
                    max_model_len=vllm_raw.get("max_model_len", 32768),
                    extra_args=vllm_raw.get("extra_args", []),
                ),
                defaults=ModelDefaults(
                    temperature=defaults_raw.get("temperature", 0.0),
                    max_tokens=defaults_raw.get("max_tokens", 8192),
                ),
            ))

        return cls(
            environment=data.get("environment", "dev"),
            models_dir=data.get("models_dir", "~/models"),
            default_model=data.get("default_model", ""),
            port=data.get("port", 8001),
            gateway_url=data.get("gateway_url", ""),
            internal_token=data.get("internal_token", ""),
            instances=instances,
        )

    def is_prod(self) -> bool:
        return self.environment == "prod"

    def get_profile(self, name: str) -> ModelProfile | None:
        return next((m for m in self.instances if m.name == name), None)

    def get_default_profile(self) -> ModelProfile | None:
        if self.default_model:
            return self.get_profile(self.default_model)
        return self.instances[0] if self.instances else None
