"""Per-user and global concurrency limiter for LLM requests.

Non-blocking: returns immediately if limit exceeded (no queuing).
"""

from __future__ import annotations

import asyncio
from collections import defaultdict

import structlog

logger = structlog.get_logger("gateway.concurrency")


class ConcurrencyLimiter:
    """Limits concurrent in-flight LLM requests.

    - max_per_user: max concurrent requests per API key (default: 1)
    - max_global: max concurrent requests across all users (default: 4)

    Uses try_acquire (non-blocking). Returns False immediately if limit exceeded.
    """

    def __init__(self, max_per_user: int = 1, max_global: int = 4):
        self.max_per_user = max_per_user
        self.max_global = max_global
        self._user_counts: dict[str, int] = defaultdict(int)
        self._global_count = 0
        self._lock = asyncio.Lock()

    async def try_acquire(self, user_id: str) -> bool:
        """Try to acquire a slot. Returns False if limit exceeded (non-blocking)."""
        async with self._lock:
            if self._global_count >= self.max_global:
                logger.warning(
                    "concurrency_global_exceeded",
                    user_id=user_id,
                    current=self._global_count,
                    max=self.max_global,
                )
                return False
            if self._user_counts[user_id] >= self.max_per_user:
                logger.warning(
                    "concurrency_user_exceeded",
                    user_id=user_id,
                    current=self._user_counts[user_id],
                    max=self.max_per_user,
                )
                return False
            self._user_counts[user_id] += 1
            self._global_count += 1
            return True

    async def release(self, user_id: str) -> None:
        """Release a slot after request completes."""
        async with self._lock:
            self._user_counts[user_id] = max(0, self._user_counts[user_id] - 1)
            self._global_count = max(0, self._global_count - 1)
            if self._user_counts[user_id] == 0:
                del self._user_counts[user_id]
