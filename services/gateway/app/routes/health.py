from __future__ import annotations

import httpx
from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
async def health(request: Request) -> dict:
    """Gateway health check. Optionally pings default upstream."""
    gateway_ok = True
    upstream_ok = False
    upstream_url = ""

    model_router = request.app.state.model_router
    default_upstream = model_router.resolve(None)

    if default_upstream:
        upstream_url = f"{default_upstream}/models"
        try:
            http_client: httpx.AsyncClient = request.app.state.http_client
            resp = await http_client.get(upstream_url, timeout=3.0)
            upstream_ok = resp.status_code == 200
        except Exception:
            upstream_ok = False

    return {
        "status": "ok" if gateway_ok else "error",
        "gateway": gateway_ok,
        "upstream": upstream_ok,
        "upstream_url": upstream_url,
    }
