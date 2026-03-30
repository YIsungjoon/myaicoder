from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator

import anyio
import httpx
import structlog

from ..config.models import User
from ..infra.logging import log_usage, mask_api_key
from ..infra.metrics import ERROR_COUNT, REQUEST_LATENCY, TOKENS_TOTAL, TTFT
from ..proxy.router import ModelRouter

logger = structlog.get_logger("gateway.proxy")

_MAX_CONTENT_LEN = 1_000_000  # 1MB truncate limit


def _save_chat_completion(
    *,
    body: bytes,
    user: User,
    model_name: str | None,
    latency: float,
    status_code: int,
    is_stream: bool,
    client_ip: str,
    response: bytes | None = None,
    response_content: str | None = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> None:
    """Parse request/response and schedule DB save."""
    try:
        from ..infra.db import save_conversation_bg

        request_data = json.loads(body)
        messages = request_data.get("messages", [])

        response_raw = None
        if response and not response_content:
            resp_data = json.loads(response)
            choices = resp_data.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "")
                response_content = content
            usage = resp_data.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            response_raw = resp_data

        if response_content and len(response_content) > _MAX_CONTENT_LEN:
            response_content = response_content[:_MAX_CONTENT_LEN] + "\n[TRUNCATED]"

        save_conversation_bg(
            user_id=user.user_id,
            user_name=user.name,
            model=model_name,
            messages=messages,
            response_content=response_content,
            response_raw=response_raw,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=int(latency * 1000),
            status_code=status_code,
            is_stream=is_stream,
            client_ip=client_ip,
        )
    except Exception as e:
        logger.error("save_chat_completion_failed", error=str(e))


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

    resp = None
    try:
        resp = await http_client.request(method=method, url=url, content=body, headers=clean)
    except httpx.ConnectError:
        logger.error("upstream_unreachable", url=url)
        raise
    finally:
        latency = time.monotonic() - start
        final_status = resp.status_code if resp is not None else 502
        REQUEST_LATENCY.labels(method=method, path=path, is_stream="false").observe(latency)
        if final_status >= 500:
            ERROR_COUNT.labels(type="upstream_error").inc()
        if resp is not None:
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
        # Conversation logging
        if path == "chat/completions" and resp is not None and final_status == 200:
            _save_chat_completion(
                body=body,
                response=resp.content,
                user=user,
                model_name=model_name,
                latency=latency,
                status_code=final_status,
                is_stream=False,
                client_ip=client_ip,
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
    accumulated_content: list[str] = []
    stream_tokens: tuple[int, int] | None = None

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
                # Conversation logging: extract content + usage from SSE
                from ..infra.db import extract_stream_content, extract_stream_usage

                content = extract_stream_content(chunk)
                if content:
                    accumulated_content.append(content)
                usage = extract_stream_usage(chunk)
                if usage:
                    stream_tokens = usage

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
        # Conversation logging (streaming)
        if status_code == 200 and accumulated_content:
            final_content = "".join(accumulated_content)
            p_tokens = stream_tokens[0] if stream_tokens else 0
            c_tokens = stream_tokens[1] if stream_tokens else len(final_content) // 4
            _save_chat_completion(
                body=body,
                response_content=final_content,
                user=user,
                model_name=model_name,
                latency=latency,
                status_code=status_code,
                is_stream=True,
                client_ip=client_ip,
                prompt_tokens=p_tokens,
                completion_tokens=c_tokens,
            )
