from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.auth import AuthStore
from app.config import (
    AuthConfig,
    GatewayConfig,
    LoggingConfig,
    ModelsConfig,
    RouteConfig,
    ServerConfig,
    UserConfig,
)
from app.main import create_app
from app.router import ModelRouter

TEST_API_KEY = "test-secret-key-12345"
TEST_API_KEY_HASH = AuthStore.hash_key(TEST_API_KEY)


def make_test_config() -> GatewayConfig:
    return GatewayConfig(
        server=ServerConfig(host="127.0.0.1", port=9999),
        auth=AuthConfig(
            users=[
                UserConfig(
                    api_key_hash=TEST_API_KEY_HASH,
                    user_id="test_user",
                    name="테스트 사용자",
                    org="Test Org",
                    role="admin",
                ),
            ]
        ),
        models=ModelsConfig(
            default="test-model",
            routes=[
                RouteConfig(
                    name="test-model",
                    upstream="http://mock-vllm:8000/v1",
                    description="Test Model",
                ),
                RouteConfig(
                    name="fast-model",
                    upstream="http://mock-vllm:8001/v1",
                    description="Fast Model",
                ),
            ],
        ),
        logging=LoggingConfig(level="DEBUG", format="json"),
    )


@pytest.fixture
def test_config() -> GatewayConfig:
    return make_test_config()


@pytest.fixture
async def client(test_config: GatewayConfig) -> AsyncClient:
    app = create_app(config=test_config)

    # Manually initialize app state (lifespan doesn't run with ASGITransport)
    app.state.config = test_config
    app.state.auth_store = AuthStore(test_config)
    app.state.model_router = ModelRouter(test_config.models)
    app.state.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=2.0, read=5.0, write=2.0, pool=2.0),
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    await app.state.http_client.aclose()


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_API_KEY}"}
