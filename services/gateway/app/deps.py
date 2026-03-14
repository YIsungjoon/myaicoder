from __future__ import annotations

from fastapi import HTTPException, Request
from starlette.status import HTTP_403_FORBIDDEN

from .auth import AuthStore
from .models import User


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
