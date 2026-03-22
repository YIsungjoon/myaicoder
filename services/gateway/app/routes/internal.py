"""Internal management API — called by CLI for cross-process state sync."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

logger = structlog.get_logger("gateway.internal")

router = APIRouter(prefix="/internal", tags=["internal"])


class ReloadRequest(BaseModel):
    current_model: str
    port: int


@router.post("/routes/reload")
async def reload_routes(
    request: Request,
    body: ReloadRequest,
    x_internal_token: str = Header(),
) -> dict:
    """Reload model routing after dev environment switch.

    Called by CLI (myaicoder model switch) after successful model swap.
    Requires X-Internal-Token header for authentication.
    """
    expected = request.app.state.config.auth.internal_token
    if not expected or x_internal_token != expected:
        raise HTTPException(status_code=403, detail="Invalid internal token")

    upstream = f"http://localhost:{body.port}/v1"
    request.app.state.model_router.reload(body.current_model, upstream)

    logger.info(
        "routes_reloaded",
        current_model=body.current_model,
        upstream=upstream,
    )

    return {
        "status": "ok",
        "current_model": body.current_model,
        "upstream": upstream,
    }


@router.get("/conversations")
async def list_conversations_api(
    request: Request,
    x_internal_token: str = Header(),
    user_id: str | None = None,
    model: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """List stored conversations. Requires internal token."""
    expected = request.app.state.config.auth.internal_token
    if not expected or x_internal_token != expected:
        raise HTTPException(status_code=403, detail="Invalid internal token")

    from ..infra.db import list_conversations

    items = await list_conversations(
        user_id=user_id, model=model, limit=limit, offset=offset,
    )
    return {"conversations": items, "count": len(items)}
