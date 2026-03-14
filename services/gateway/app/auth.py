from __future__ import annotations

import hashlib

from .config import GatewayConfig
from .models import User


class AuthStore:
    """In-memory auth store. Built once at startup from config, no file I/O per request."""

    def __init__(self, config: GatewayConfig):
        self._users: dict[str, User] = {}
        for u in config.auth.users:
            self._users[u.api_key_hash] = User(
                user_id=u.user_id,
                name=u.name,
                org=u.org,
                role=u.role,
            )

    def authenticate(self, api_key: str) -> User | None:
        """Authenticate by hashing the raw API key and looking up in memory. O(1)."""
        key_hash = f"sha256:{hashlib.sha256(api_key.encode()).hexdigest()}"
        return self._users.get(key_hash)

    @staticmethod
    def hash_key(raw_key: str) -> str:
        """Utility to generate a hash string for storing in gateway.yaml."""
        return f"sha256:{hashlib.sha256(raw_key.encode()).hexdigest()}"
