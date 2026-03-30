"""Tests for internal management API — routing reload and token auth."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth import AuthStore
from app.config import (
    AuthConfig,
    GatewayConfig,
    ModelsConfig,
    RouteConfig,
    UserConfig,
)
from app.main import create_app
from app.middleware.rate_limiter import SlidingWindowLimiter
from app.proxy.router import ModelRouter

TEST_INTERNAL_TOKEN = "test-internal-secret-xyz"
TEST_API_KEY = "internal-test-api-key"
TEST_API_KEY_HASH = AuthStore.hash_key(TEST_API_KEY)


def _make_config() -> GatewayConfig:
    return GatewayConfig(
        auth=AuthConfig(
            users=[
                UserConfig(
                    api_key_hash=TEST_API_KEY_HASH,
                    user_id="test_user",
                    name="Tester",
                    org="Test",
                    role="admin",
                ),
            ],
            internal_token=TEST_INTERNAL_TOKEN,
        ),
        models=ModelsConfig(
            default="model-a",
            routes=[
                RouteConfig(name="model-a", upstream="http://localhost:8001/v1"),
                RouteConfig(name="model-b", upstream="http://localhost:8002/v1"),
            ],
        ),
    )


@pytest.fixture
async def client():
    config = _make_config()
    app = create_app(config=config)
    app.state.config = config
    app.state.auth_store = AuthStore(config)
    app.state.model_router = ModelRouter(config.models)
    app.state.rate_limiter = SlidingWindowLimiter()
    app.state.http_client = None

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


INTERNAL_HEADERS = {"X-Internal-Token": TEST_INTERNAL_TOKEN}


# ── Success ──


@pytest.mark.asyncio
async def test_reload_success(client: AsyncClient):
    """Valid token + body → 200 + routing updated."""
    resp = await client.post(
        "/internal/routes/reload",
        json={"current_model": "qwen3-coder-30b", "port": 9001},
        headers=INTERNAL_HEADERS,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["current_model"] == "qwen3-coder-30b"
    assert body["upstream"] == "http://localhost:9001/v1"


@pytest.mark.asyncio
async def test_reload_updates_routing(client: AsyncClient):
    """After reload, all model names should resolve to new upstream."""
    # Before: model-a → 8001, model-b → 8002
    app = client._transport.app  # type: ignore[attr-defined]
    router = app.state.model_router
    assert router.resolve("model-a") == "http://localhost:8001/v1"
    assert router.resolve("model-b") == "http://localhost:8002/v1"

    # Reload
    await client.post(
        "/internal/routes/reload",
        json={"current_model": "new-model", "port": 9999},
        headers=INTERNAL_HEADERS,
    )

    # After: all → 9999
    assert router.resolve("model-a") == "http://localhost:9999/v1"
    assert router.resolve("model-b") == "http://localhost:9999/v1"
    assert router.resolve(None) == "http://localhost:9999/v1"


# ── Auth Failures ──


@pytest.mark.asyncio
async def test_reload_invalid_token(client: AsyncClient):
    """Wrong token → 403."""
    resp = await client.post(
        "/internal/routes/reload",
        json={"current_model": "test", "port": 8001},
        headers={"X-Internal-Token": "wrong-token"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_reload_missing_token(client: AsyncClient):
    """No X-Internal-Token header → 422."""
    resp = await client.post(
        "/internal/routes/reload",
        json={"current_model": "test", "port": 8001},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_reload_empty_config_token():
    """Config internal_token is empty → always 403 (safe default)."""
    config = _make_config()
    config.auth.internal_token = ""

    app = create_app(config=config)
    app.state.config = config
    app.state.auth_store = AuthStore(config)
    app.state.model_router = ModelRouter(config.models)
    app.state.rate_limiter = SlidingWindowLimiter()
    app.state.http_client = None

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post(
            "/internal/routes/reload",
            json={"current_model": "test", "port": 8001},
            headers={"X-Internal-Token": "anything"},
        )
    assert resp.status_code == 403


# ── ModelRouter.reload() Unit Test ──


class TestModelRouterReload:
    def test_reload_overwrites_all_routes(self):
        config = ModelsConfig(
            default="a",
            routes=[
                RouteConfig(name="a", upstream="http://old:8001/v1"),
                RouteConfig(name="b", upstream="http://old:8002/v1"),
            ],
        )
        router = ModelRouter(config)

        router.reload("new-model", "http://new:9001/v1")

        assert router.resolve("a") == "http://new:9001/v1"
        assert router.resolve("b") == "http://new:9001/v1"
        assert router.resolve(None) == "http://new:9001/v1"
        assert router.resolve("unknown") == "http://new:9001/v1"
