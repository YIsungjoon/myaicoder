from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator

import anyio
import httpx
import structlog

from .logging import log_usage, mask_api_key
from .metrics import ERROR_COUNT, REQUEST_LATENCY, TOKENS_TOTAL, TTFT
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


def _try_parse_usage(
    chunk: bytes, prev_prompt: int, prev_completion: int
) -> tuple[int, int]:
    """Best-effort parse usage from SSE chunk. Last chunk before [DONE] has usage."""
    try:
        text = chunk.decode("utf-8", errors="ignore")
        for line in text.split("\n"):
            if not line.startswith("data: ") or line.strip() == "data: [DONE]":
                continue
            data = json.loads(line[6:])
            usage = data.get("usage")
            if usage:
                return (
                    usage.get("prompt_tokens", prev_prompt),
                    usage.get("completion_tokens", prev_completion),
                )
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass
    return (prev_prompt, prev_completion)


def _record_usage_from_response(resp: httpx.Response, model_name: str | None) -> None:
    """Extract token usage from non-streaming response body."""
    try:
        data = json.loads(resp.content)
        usage = data.get("usage", {})
        prompt = usage.get("prompt_tokens", 0)
        completion = usage.get("completion_tokens", 0)
        if prompt > 0:
            TOKENS_TOTAL.labels(model=model_name or "unknown", type="prompt").inc(prompt)
        if completion > 0:
            TOKENS_TOTAL.labels(model=model_name or "unknown", type="completion").inc(completion)
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass


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
        final_status = resp.status_code if "resp" in dir() else 502
        REQUEST_LATENCY.labels(method=method, path=path, is_stream="false").observe(latency)
        if final_status >= 500:
            ERROR_COUNT.labels(type="upstream_error").inc()
        if "resp" in dir():
            _record_usage_from_response(resp, model_name)
        log_usage(
            user_id=user.user_id,
            user_name=user.name,
            client_ip=client_ip,
            method=method,
            path=path,
            model=model_name,
            is_stream=False,
            latency_sec=latency,
            status_code=final_status,
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
    prompt_tokens = 0
    completion_tokens = 0

    try:
        async with http_client.stream(
            method="POST", url=url, content=body, headers=clean
        ) as upstream_resp:
            status_code = upstream_resp.status_code
            async for chunk in upstream_resp.aiter_bytes():
                if ttft is None:
                    ttft = time.monotonic() - start
                prompt_tokens, completion_tokens = _try_parse_usage(
                    chunk, prompt_tokens, completion_tokens
                )
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
        REQUEST_LATENCY.labels(method="POST", path=path, is_stream="true").observe(latency)
        if ttft is not None:
            TTFT.labels(model=model_name or "unknown").observe(ttft)
        if prompt_tokens > 0:
            TOKENS_TOTAL.labels(model=model_name or "unknown", type="prompt").inc(prompt_tokens)
        if completion_tokens > 0:
            TOKENS_TOTAL.labels(model=model_name or "unknown", type="completion").inc(
                completion_tokens
            )
        if status_code >= 500:
            ERROR_COUNT.labels(type="upstream_error").inc()
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
