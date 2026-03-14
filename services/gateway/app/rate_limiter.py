"""Sliding Window Counter rate limiter + response header middleware.

Safety features:
- Memory leak prevention: lazy eviction of expired window counters
- Concurrency safety: no await between read and increment (atomic under asyncio)
- Streaming support: headers injected via middleware after response creation
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .config import RateLimitConfig

# ── Sliding Window Counter Algorithm ──


@dataclass
class WindowCounter:
    """A single window's counter state."""

    window_key: int = 0
    count: int = 0
    prev_count: int = 0


class SlidingWindowLimiter:
    """In-memory sliding window counter rate limiter.

    Concurrency: all state mutations are synchronous (no await between
    read and increment), safe under asyncio's single-thread model.

    Memory: expired entries are evicted periodically via lazy _evict().
    """

    def __init__(self, eviction_interval: float = 300.0):
        self._counters: dict[tuple[str, int], WindowCounter] = {}
        self._last_eviction: float = 0.0
        self._eviction_interval = eviction_interval

    def check_and_increment(
        self, user_id: str, limit: int, window_seconds: int
    ) -> tuple[bool, int, int]:
        """Check rate limit and increment counter atomically.

        IMPORTANT: This entire method is synchronous — no await anywhere.
        This guarantees no context switch between read and increment.

        Returns:
            (allowed, remaining, reset_at)
        """
        now = time.time()

        # Lazy eviction
        if now - self._last_eviction > self._eviction_interval:
            self._evict(now)
            self._last_eviction = now

        key = (user_id, window_seconds)
        current_window = int(now // window_seconds)
        window_progress = (now % window_seconds) / window_seconds

        counter = self._counters.get(key)
        if counter is None:
            counter = WindowCounter(window_key=current_window)
            self._counters[key] = counter

        # Window transition
        if counter.window_key != current_window:
            if counter.window_key == current_window - 1:
                counter.prev_count = counter.count
            else:
                counter.prev_count = 0
            counter.window_key = current_window
            counter.count = 0

        # Weighted estimate (synchronous — no await!)
        weighted = counter.count + counter.prev_count * (1.0 - window_progress)

        reset_at = int((current_window + 1) * window_seconds)

        if weighted >= limit:
            return (False, 0, reset_at)

        # Allowed — increment
        counter.count += 1
        remaining = max(0, limit - int(weighted) - 1)
        return (True, remaining, reset_at)

    def _evict(self, now: float) -> None:
        """Remove expired window counters to prevent memory leak."""
        expired: list[tuple[str, int]] = []
        for key, counter in self._counters.items():
            _, window_seconds = key
            current_window = int(now // window_seconds)
            if counter.window_key < current_window - 1:
                expired.append(key)
        for key in expired:
            del self._counters[key]


# ── Helper ──


def resolve_limits(
    config: RateLimitConfig, user_id: str, role: str
) -> tuple[int, int]:
    """Resolve rate limits: user override > role default > fallback."""
    for override in config.overrides:
        if override.user_id == user_id:
            return (override.requests_per_minute, override.requests_per_hour)

    role_config = config.roles.get(role)
    if role_config:
        return (role_config.requests_per_minute, role_config.requests_per_hour)

    return (30, 500)


# ── Response Header Middleware ──


class RateLimitHeaderMiddleware(BaseHTTPMiddleware):
    """Inject X-RateLimit-* headers into successful responses.

    The actual rate limit check is done by the check_rate_limit dependency.
    This middleware only reads request.state.rate_limit_headers (set by dep)
    and injects them into the response.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        headers = getattr(request.state, "rate_limit_headers", None)
        if headers:
            for key, value in headers.items():
                response.headers[key] = value

        return response
