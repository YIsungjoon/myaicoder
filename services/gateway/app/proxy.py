from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator

import anyio
import httpx
import structlog

from .logging import log_usage, mask_api_key
from .models import User
from .router import ModelRouter

logger = structlog.get_logger("gateway.proxy")


def _extract_model(body: bytes) -> str | None:
    """Best-effort extraction of model name from request body."""
    try:
        data = json.loads(body)
        return data.get("model")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _clean_headers(headers: dict[str, str]) -> dict[str, str]:
    """Remove hop-by-hop headers that shouldn't be forwarded."""
    skip = {"host", "authorization", "content-length", "transfer-encoding"}
    return {k: v for k, v in headers.items() if k.lower() not in skip}


async def forward_request(
    *,
    http_client: httpx.AsyncClient,
    router: ModelRouter,
    method: str,
    path: str,
    body: bytes,
    headers: dict[str, str],
    user: User,
    client_ip: str,
    raw_api_key: str,
) -> httpx.Response:
    """Forward a non-streaming request to upstream vLLM."""
    start = time.monotonic()
    model_name = _extract_model(body)
    upstream_base = router.resolve(model_name)
    url = f"{upstream_base}/{path}"
    clean = _clean_headers(headers)

    try:
        resp = await http_client.request(method=method, url=url, content=body, headers=clean)
    except httpx.ConnectError:
        logger.error("upstream_unreachable", url=url)
        raise
    finally:
        latency = time.monotonic() - start
        log_usage(
            user_id=user.user_id,
            user_name=user.name,
            client_ip=client_ip,
            method=method,
            path=path,
            model=model_name,
            is_stream=False,
            latency_sec=latency,
            status_code=resp.status_code if "resp" in dir() else 502,
            api_key_masked=mask_api_key(raw_api_key),
        )

    return resp


async def stream_upstream(
    *,
    http_client: httpx.AsyncClient,
    router: ModelRouter,
    path: str,
    body: bytes,
    headers: dict[str, str],
    user: User,
    client_ip: str,
    raw_api_key: str,
) -> AsyncIterator[bytes]:
    """Stream SSE chunks from upstream vLLM with safe resource cleanup."""
    start = time.monotonic()
    ttft: float | None = None
    model_name = _extract_model(body)
    upstream_base = router.resolve(model_name)
    url = f"{upstream_base}/{path}"
    clean = _clean_headers(headers)
    status_code = 200

    try:
        async with http_client.stream(
            method="POST", url=url, content=body, headers=clean
        ) as upstream_resp:
            status_code = upstream_resp.status_code
            async for chunk in upstream_resp.aiter_bytes():
                if ttft is None:
                    ttft = time.monotonic() - start
                yield chunk
    except httpx.RemoteProtocolError:
        logger.warning("upstream_disconnected", url=url, model=model_name)
        status_code = 502
    except anyio.get_cancelled_exc_class():
        logger.info("client_disconnected", user_id=user.user_id, model=model_name)
        status_code = 499  # nginx-style client closed
        raise
    except httpx.ConnectError:
        logger.error("upstream_unreachable", url=url)
        status_code = 502
        error_body = {"error": {"message": "Upstream server unreachable", "type": "proxy_error"}}
        error_payload = json.dumps(error_body)
        yield f"data: {error_payload}\n\n".encode()
        yield b"data: [DONE]\n\n"
    finally:
        latency = time.monotonic() - start
        log_usage(
            user_id=user.user_id,
            user_name=user.name,
            client_ip=client_ip,
            method="POST",
            path=path,
            model=model_name,
            is_stream=True,
            latency_sec=latency,
            ttft_sec=ttft,
            status_code=status_code,
            api_key_masked=mask_api_key(raw_api_key),
        )
