from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_models_endpoint_requires_auth(client: AsyncClient):
    """GET /v1/models without auth should return 403."""
    resp = await client.get("/v1/models")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_models_endpoint_with_auth(client: AsyncClient, auth_headers: dict):
    """GET /v1/models with valid auth should return model list."""
    resp = await client.get("/v1/models", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["object"] == "list"
    assert len(data["data"]) == 2
    assert data["data"][0]["id"] == "test-model"


@pytest.mark.asyncio
async def test_models_endpoint_invalid_key(client: AsyncClient):
    """GET /v1/models with wrong key should return 403."""
    resp = await client.get("/v1/models", headers={"Authorization": "Bearer wrong-key"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_chat_completions_upstream_unreachable(
    client: AsyncClient, auth_headers: dict
):
    """POST /v1/chat/completions should return 502 when upstream is down."""
    resp = await client.post(
        "/v1/chat/completions",
        headers=auth_headers,
        json={"model": "test-model", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_catch_all_requires_auth(client: AsyncClient):
    """Catch-all proxy requires auth."""
    resp = await client.get("/v1/embeddings")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_catch_all_upstream_unreachable(client: AsyncClient, auth_headers: dict):
    """Catch-all proxy returns 502 when upstream is down."""
    resp = await client.get("/v1/embeddings", headers=auth_headers)
    assert resp.status_code == 502
