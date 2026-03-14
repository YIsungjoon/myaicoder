from __future__ import annotations

from app.config import ModelsConfig, RouteConfig
from app.router import ModelRouter


class TestModelRouter:
    def setup_method(self):
        config = ModelsConfig(
            default="main-model",
            routes=[
                RouteConfig(name="main-model", upstream="http://vllm:8000/v1"),
                RouteConfig(name="fast-model", upstream="http://vllm:8001/v1"),
            ],
        )
        self.router = ModelRouter(config)

    def test_resolve_explicit_model(self):
        url = self.router.resolve("main-model")
        assert url == "http://vllm:8000/v1"

    def test_resolve_second_model(self):
        url = self.router.resolve("fast-model")
        assert url == "http://vllm:8001/v1"

    def test_resolve_none_returns_default(self):
        url = self.router.resolve(None)
        assert url == "http://vllm:8000/v1"

    def test_resolve_unknown_model_returns_default(self):
        url = self.router.resolve("nonexistent-model")
        assert url == "http://vllm:8000/v1"

    def test_list_models(self):
        models = self.router.list_models()
        assert len(models) == 2
        assert models[0]["id"] == "main-model"
        assert models[0]["object"] == "model"
        assert models[1]["id"] == "fast-model"

    def test_empty_config(self):
        router = ModelRouter(ModelsConfig())
        assert router.resolve(None) == ""
        assert router.resolve("anything") == ""
        assert router.list_models() == []
