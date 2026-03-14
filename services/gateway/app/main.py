from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
import structlog
from fastapi import FastAPI

from .auth import AuthStore
from .config import GatewayConfig
from .rate_limiter import RateLimitHeaderMiddleware, SlidingWindowLimiter
from .router import ModelRouter
from .routes.health import router as health_router
from .routes.internal import router as internal_router
from .routes.v1 import router as v1_router


def configure_structlog() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer()
            if structlog.is_configured()
            else structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(),
    )


def create_app(config: GatewayConfig | None = None) -> FastAPI:
    """App factory. Accepts optional config for testing."""

    if config is None:
        config = GatewayConfig.load()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup: build in-memory stores + shared HTTP client
        app.state.config = config
        app.state.auth_store = AuthStore(config)
        app.state.model_router = ModelRouter(config.models)
        app.state.rate_limiter = SlidingWindowLimiter()
        app.state.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=None, write=5.0, pool=5.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        )
        yield
        # Shutdown: close HTTP client
        await app.state.http_client.aclose()

    configure_structlog()

    app = FastAPI(
        title="myAiCoder Gateway",
        description="API Gateway for vLLM - auth, logging, model routing, rate limiting",
        lifespan=lifespan,
    )

    app.add_middleware(RateLimitHeaderMiddleware)

    app.include_router(health_router)
    app.include_router(internal_router)
    app.include_router(v1_router)

    return app
