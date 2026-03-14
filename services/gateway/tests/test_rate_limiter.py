"""Tests for rate limiting — algorithm, eviction, dependency, middleware, integration."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth import AuthStore
from app.config import (
    AuthConfig,
    GatewayConfig,
    ModelsConfig,
    RateLimitConfig,
    RoleLimitConfig,
    RouteConfig,
    UserConfig,
    UserOverrideConfig,
)
from app.main import create_app
from app.rate_limiter import SlidingWindowLimiter, resolve_limits
from app.router import ModelRouter

# ── SlidingWindowLimiter Unit Tests ──


class TestSlidingWindowBasic:
    def test_allows_under_limit(self):
        limiter = SlidingWindowLimiter()
        with patch("app.rate_limiter.time.time", return_value=1000.0):
            allowed, remaining, reset = limiter.check_and_increment("u1", 5, 60)
        assert allowed is True
        assert remaining == 4

    def test_blocks_at_limit(self):
        limiter = SlidingWindowLimiter()
        with patch("app.rate_limiter.time.time", return_value=1000.0):
            for _ in range(5):
                limiter.check_and_increment("u1", 5, 60)
            allowed, remaining, _ = limiter.check_and_increment("u1", 5, 60)
        assert allowed is False
        assert remaining == 0

    def test_different_users_independent(self):
        limiter = SlidingWindowLimiter()
        with patch("app.rate_limiter.time.time", return_value=1000.0):
            for _ in range(5):
                limiter.check_and_increment("u1", 5, 60)
            # u1 is at limit, u2 should be fine
            allowed, _, _ = limiter.check_and_increment("u2", 5, 60)
        assert allowed is True

    def test_reset_at_is_next_window_boundary(self):
        limiter = SlidingWindowLimiter()
        # t=1000, window=60 → current_window=16, next=17*60=1020
        with patch("app.rate_limiter.time.time", return_value=1000.0):
            _, _, reset = limiter.check_and_increment("u1", 10, 60)
        assert reset == 1020


class TestSlidingWindowTransition:
    def test_window_transition_carries_prev(self):
        """Previous window count contributes to weighted average."""
        limiter = SlidingWindowLimiter()
        # Window 1: use 4 of 5
        with patch("app.rate_limiter.time.time", return_value=1000.0):
            for _ in range(4):
                limiter.check_and_increment("u1", 5, 60)

        # Window 2 at 10% progress: weighted = 0 + 4 * 0.9 = 3.6
        with patch("app.rate_limiter.time.time", return_value=1066.0):
            allowed, remaining, _ = limiter.check_and_increment("u1", 5, 60)
        assert allowed is True  # 3.6 < 5, so allowed

    def test_old_window_resets_prev(self):
        """Windows more than 1 apart don't carry over."""
        limiter = SlidingWindowLimiter()
        with patch("app.rate_limiter.time.time", return_value=1000.0):
            for _ in range(5):
                limiter.check_and_increment("u1", 5, 60)

        # Skip 2 full windows → prev should be 0
        with patch("app.rate_limiter.time.time", return_value=1200.0):
            allowed, remaining, _ = limiter.check_and_increment("u1", 5, 60)
        assert allowed is True
        assert remaining == 4


class TestEviction:
    def test_expired_counters_removed(self):
        limiter = SlidingWindowLimiter(eviction_interval=0)  # evict every call
        with patch("app.rate_limiter.time.time", return_value=1000.0):
            limiter.check_and_increment("u1", 10, 60)
            limiter.check_and_increment("u2", 10, 60)

        assert len(limiter._counters) == 2

        # Jump 3 windows ahead → both should be evicted
        with patch("app.rate_limiter.time.time", return_value=1200.0):
            limiter.check_and_increment("u3", 10, 60)

        # u1 and u2 should be evicted, only u3 remains
        assert len(limiter._counters) == 1
        assert ("u3", 60) in limiter._counters

    def test_recent_counters_preserved(self):
        limiter = SlidingWindowLimiter(eviction_interval=0)
        with patch("app.rate_limiter.time.time", return_value=1000.0):
            limiter.check_and_increment("u1", 10, 60)

        # Only 1 window ahead → prev is still needed
        with patch("app.rate_limiter.time.time", return_value=1060.0):
            limiter.check_and_increment("u2", 10, 60)

        # u1 is in prev window, should NOT be evicted
        assert ("u1", 60) in limiter._counters


# ── resolve_limits Tests ──


class TestResolveLimits:
    def test_role_based(self):
        config = RateLimitConfig(
            roles={"admin": RoleLimitConfig(requests_per_minute=100, requests_per_hour=2000)}
        )
        rpm, rph = resolve_limits(config, "u1", "admin")
        assert rpm == 100
        assert rph == 2000

    def test_user_override(self):
        config = RateLimitConfig(
            overrides=[
                UserOverrideConfig(
                    user_id="special", requests_per_minute=200, requests_per_hour=5000
                )
            ]
        )
        rpm, rph = resolve_limits(config, "special", "user")
        assert rpm == 200
        assert rph == 5000

    def test_override_takes_precedence(self):
        config = RateLimitConfig(
            roles={"user": RoleLimitConfig(requests_per_minute=30, requests_per_hour=500)},
            overrides=[
                UserOverrideConfig(
                    user_id="vip", requests_per_minute=60, requests_per_hour=1000
                )
            ],
        )
        rpm, _ = resolve_limits(config, "vip", "user")
        assert rpm == 60  # override, not role

    def test_unknown_role_fallback(self):
        config = RateLimitConfig(roles={})
        rpm, rph = resolve_limits(config, "u1", "unknown_role")
        assert rpm == 30
        assert rph == 500


# ── Integration Tests (FastAPI TestClient) ──


TEST_API_KEY = "rate-limit-test-key"
TEST_API_KEY_HASH = AuthStore.hash_key(TEST_API_KEY)


def _make_rate_limited_config(rpm: int = 3) -> GatewayConfig:
    """Create a config with very low rate limit for testing."""
    return GatewayConfig(
        auth=AuthConfig(
            users=[
                UserConfig(
                    api_key_hash=TEST_API_KEY_HASH,
                    user_id="rl_user",
                    name="Rate Limit Tester",
                    org="Test",
                    role="user",
                ),
            ]
        ),
        models=ModelsConfig(
            default="test-model",
            routes=[RouteConfig(name="test-model", upstream="http://mock:8000/v1")],
        ),
        rate_limit=RateLimitConfig(
            enabled=True,
            roles={"user": RoleLimitConfig(requests_per_minute=rpm, requests_per_hour=1000)},
        ),
    )


@pytest.fixture
async def rl_client():
    """Client with rate limiting enabled (3 requests/minute)."""
    config = _make_rate_limited_config(rpm=3)
    app = create_app(config=config)
    app.state.config = config
    app.state.auth_store = AuthStore(config)
    app.state.model_router = ModelRouter(config.models)
    app.state.rate_limiter = SlidingWindowLimiter()
    app.state.http_client = None  # Not needed for /v1/models

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


RL_HEADERS = {"Authorization": f"Bearer {TEST_API_KEY}"}


@pytest.mark.asyncio
async def test_rate_limit_headers_present(rl_client: AsyncClient):
    """Successful request should include X-RateLimit-* headers."""
    resp = await rl_client.get("/v1/models", headers=RL_HEADERS)
    assert resp.status_code == 200
    assert "X-RateLimit-Limit" in resp.headers
    assert "X-RateLimit-Remaining" in resp.headers
    assert "X-RateLimit-Reset" in resp.headers
    assert resp.headers["X-RateLimit-Limit"] == "3"


@pytest.mark.asyncio
async def test_rate_limit_remaining_decreases(rl_client: AsyncClient):
    """Remaining count should decrease with each request."""
    r1 = await rl_client.get("/v1/models", headers=RL_HEADERS)
    r2 = await rl_client.get("/v1/models", headers=RL_HEADERS)
    rem1 = int(r1.headers["X-RateLimit-Remaining"])
    rem2 = int(r2.headers["X-RateLimit-Remaining"])
    assert rem1 > rem2


@pytest.mark.asyncio
async def test_rate_limit_429_when_exceeded(rl_client: AsyncClient):
    """Exceeding rate limit returns 429 with Retry-After."""
    for _ in range(3):
        await rl_client.get("/v1/models", headers=RL_HEADERS)

    resp = await rl_client.get("/v1/models", headers=RL_HEADERS)
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    body = resp.json()
    assert body["detail"] == "Rate limit exceeded. Please retry later."


@pytest.mark.asyncio
async def test_rate_limit_disabled():
    """When rate_limit.enabled=false, no limiting occurs."""
    config = _make_rate_limited_config(rpm=1)
    config.rate_limit.enabled = False

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
        for _ in range(5):
            resp = await ac.get("/v1/models", headers=RL_HEADERS)
            assert resp.status_code == 200  # No 429


@pytest.mark.asyncio
async def test_health_endpoint_not_rate_limited(rl_client: AsyncClient):
    """/health should not be rate limited."""
    for _ in range(10):
        resp = await rl_client.get("/health")
        assert resp.status_code == 200
    assert "X-RateLimit-Limit" not in resp.headers
