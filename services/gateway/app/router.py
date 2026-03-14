from __future__ import annotations

import structlog

from .config import ModelsConfig
from .models import ModelRoute

logger = structlog.get_logger("gateway.router")


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

    def reload(self, model_name: str, upstream: str) -> None:
        """Reload routing for dev environment model switch.

        All model names route to the same upstream (single vLLM port in dev).
        This ensures requests with any model name reach the currently loaded model.
        """
        self._default_upstream = upstream
        for name in self._routes:
            self._routes[name] = upstream
        logger.info("routes_reloaded", current_model=model_name, upstream=upstream)

    def list_models(self) -> list[dict]:
        """Return OpenAI-compatible model list."""
        return [
            {"id": m.name, "object": "model", "owned_by": "local"}
            for m in self._models
        ]
