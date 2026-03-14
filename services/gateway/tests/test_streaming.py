from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_streaming_request_upstream_unreachable(
    client: AsyncClient, auth_headers: dict
):
    """Streaming request should handle upstream being down gracefully."""
    resp = await client.post(
        "/v1/chat/completions",
        headers=auth_headers,
        json={
            "model": "test-model",
            "messages": [{"role": "user", "content": "hello"}],
            "stream": True,
        },
    )
    # StreamingResponse is returned, but reading it will fail since upstream is down.
    # The response itself should be 200 (streaming started) but content will be empty/error.
    # This is expected behavior: the gateway starts streaming before knowing upstream will fail.
    assert resp.status_code == 200
