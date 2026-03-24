from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

import httpx
import structlog
from fastapi import FastAPI, Request

from .auth.store import AuthStore
from .config import config as gateway_config
from .infra.db import close_db, init_db
from .infra.metrics import ACTIVE_REQUESTS, REQUEST_COUNT
from .middleware.concurrency import ConcurrencyLimiter
from .middleware.errors import global_exception_handler
from .middleware.rate_limiter import RateLimitHeaderMiddleware, SlidingWindowLimiter
from .proxy.router import ModelRouter
from .routes.health import router as health_router
from .routes.internal import router as internal_router
from .routes.metrics import router as metrics_router
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


def create_app(config=None) -> FastAPI:
    """App factory. Accepts optional config for testing, otherwise uses singleton."""

    app_config = config if config else gateway_config

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup: build in-memory stores + shared HTTP client
        app.state.config = app_config
        app.state.auth_store = AuthStore(app_config)
        app.state.model_router = ModelRouter(app_config.models)
        app.state.rate_limiter = SlidingWindowLimiter()
        app.state.concurrency_limiter = ConcurrencyLimiter(
            max_per_user=app_config.concurrency.max_per_user,
            max_global=app_config.concurrency.max_global,
        )
        app.state.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=None, write=5.0, pool=10.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        )

        # DB init (conversation logging) - Atomicity guaranteed by infra/db.py
        if app_config.database.enabled and app_config.database.url:
            await init_db(app_config.database.url)

        yield

        # Shutdown: close HTTP client + DB
        await app.state.http_client.aclose()
        if app_config.database.enabled:
            await close_db()

    configure_structlog()

    app = FastAPI(
        title="myAiCoder Gateway",
        description="API Gateway for vLLM - auth, logging, model routing, rate limiting",
        lifespan=lifespan,
    )

    # Register Global Exception Handler for Atomicity and DRY
    app.add_exception_handler(Exception, global_exception_handler)

    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        # Clear previous request context to prevent ID leaking across async requests
        structlog.contextvars.clear_contextvars()
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        request.state.request_id = request_id
        structlog.contextvars.bind_contextvars(request_id=request_id)

        ACTIVE_REQUESTS.inc()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            ACTIVE_REQUESTS.dec()
            REQUEST_COUNT.labels(
                method=request.method,
                path=request.url.path,
                status=str(status_code),
            ).inc()

    # Apply specialized middlewares
    app.add_middleware(RateLimitHeaderMiddleware)

    # Include routes with standardized prefixes
    app.include_router(health_router)
    app.include_router(internal_router)
    app.include_router(metrics_router)
    app.include_router(v1_router)

    return app


# Main entry point for uvicorn
app = create_app()
