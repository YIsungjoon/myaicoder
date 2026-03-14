from __future__ import annotations

from .config import ModelsConfig
from .models import ModelRoute


class ModelRouter:
    """Routes model names to upstream vLLM URLs. Built once at startup."""

    def __init__(self, config: ModelsConfig):
        self._routes: dict[str, str] = {}
        self._models: list[ModelRoute] = []
        self._default_upstream: str = ""

        for r in config.routes:
            route = ModelRoute(name=r.name, upstream=r.upstream, description=r.description)
            self._routes[r.name] = r.upstream
            self._models.append(route)

        # Determine default upstream
        if config.default and config.default in self._routes:
            self._default_upstream = self._routes[config.default]
        elif config.routes:
            self._default_upstream = config.routes[0].upstream

    def resolve(self, model_name: str | None) -> str:
        """Resolve model name to upstream URL. Falls back to default."""
        if not model_name:
            return self._default_upstream
        return self._routes.get(model_name, self._default_upstream)

    def list_models(self) -> list[dict]:
        """Return OpenAI-compatible model list."""
        return [
            {"id": m.name, "object": "model", "owned_by": "local"}
            for m in self._models
        ]
