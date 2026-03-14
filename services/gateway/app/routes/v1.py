from __future__ import annotations

import json

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from ..deps import get_current_user
from ..models import User
from ..proxy import forward_request, stream_upstream

router = APIRouter(prefix="/v1", dependencies=[Depends(get_current_user)])


@router.get("/models")
async def list_models(request: Request) -> dict:
    """Return available models from config."""
    model_router = request.app.state.model_router
    return {"object": "list", "data": model_router.list_models()}


@router.post("/chat/completions")
async def chat_completions(request: Request) -> Response:
    """Proxy chat completions. Supports both regular and streaming responses."""
    body = await request.body()
    user: User = request.state.user
    raw_key: str = request.state.raw_api_key
    client_ip = request.client.host if request.client else "unknown"
    headers = dict(request.headers)

    # Check if streaming
    try:
        data = json.loads(body)
        is_stream = data.get("stream", False)
    except (json.JSONDecodeError, UnicodeDecodeError):
        is_stream = False

    if is_stream:
        generator = stream_upstream(
            http_client=request.app.state.http_client,
            router=request.app.state.model_router,
            path="chat/completions",
            body=body,
            headers=headers,
            user=user,
            client_ip=client_ip,
            raw_api_key=raw_key,
        )
        return StreamingResponse(generator, media_type="text/event-stream")

    try:
        resp = await forward_request(
            http_client=request.app.state.http_client,
            router=request.app.state.model_router,
            method="POST",
            path="chat/completions",
            body=body,
            headers=headers,
            user=user,
            client_ip=client_ip,
            raw_api_key=raw_key,
        )
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="Upstream server unreachable")

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=dict(resp.headers),
        media_type=resp.headers.get("content-type"),
    )


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def catch_all(path: str, request: Request) -> Response:
    """Catch-all proxy for other OpenAI-compatible API endpoints."""
    body = await request.body()
    user: User = request.state.user
    raw_key: str = request.state.raw_api_key
    client_ip = request.client.host if request.client else "unknown"
    headers = dict(request.headers)

    try:
        resp = await forward_request(
            http_client=request.app.state.http_client,
            router=request.app.state.model_router,
            method=request.method,
            path=path,
            body=body,
            headers=headers,
            user=user,
            client_ip=client_ip,
            raw_api_key=raw_key,
        )
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="Upstream server unreachable")

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=dict(resp.headers),
        media_type=resp.headers.get("content-type"),
    )
