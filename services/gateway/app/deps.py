from __future__ import annotations

import time

from fastapi import HTTPException, Request
from starlette.status import HTTP_403_FORBIDDEN

from .auth import AuthStore
from .config import RateLimitConfig
from .models import User
from .rate_limiter import SlidingWindowLimiter, resolve_limits


def get_auth_store(request: Request) -> AuthStore:
    return request.app.state.auth_store


def get_raw_api_key(request: Request) -> str:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Missing API key")
    return auth_header[7:]


async def get_current_user(request: Request) -> User:
    """Extract and verify API key from Authorization header."""
    raw_key = get_raw_api_key(request)
    auth_store: AuthStore = request.app.state.auth_store
    user = auth_store.authenticate(raw_key)
    if user is None:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Invalid API key")
    request.state.user = user
    request.state.raw_api_key = raw_key
    return user


async def check_rate_limit(request: Request) -> None:
    """Check rate limit after authentication. Raises 429 if exceeded.

    Stores header info in request.state for middleware to inject into response.
    """
    rate_config: RateLimitConfig = request.app.state.config.rate_limit
    if not rate_config.enabled:
        return

    limiter: SlidingWindowLimiter = request.app.state.rate_limiter
    user: User = request.state.user

    rpm, rph = resolve_limits(rate_config, user.user_id, user.role)

    # Per-minute check
    allowed_m, remaining_m, reset_m = limiter.check_and_increment(
        user.user_id, rpm, 60
    )
    if not allowed_m:
        retry_after = max(1, reset_m - int(time.time()))
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please retry later.",
            headers={
                "X-RateLimit-Limit": str(rpm),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_m),
                "Retry-After": str(retry_after),
            },
        )

    # Per-hour check
    allowed_h, remaining_h, reset_h = limiter.check_and_increment(
        user.user_id, rph, 3600
    )
    if not allowed_h:
        retry_after = max(1, reset_h - int(time.time()))
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded (hourly). Please retry later.",
            headers={
                "X-RateLimit-Limit": str(rph),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_h),
                "Retry-After": str(retry_after),
            },
        )

    # Store for header middleware
    request.state.rate_limit_headers = {
        "X-RateLimit-Limit": str(rpm),
        "X-RateLimit-Remaining": str(remaining_m),
        "X-RateLimit-Reset": str(reset_m),
    }
