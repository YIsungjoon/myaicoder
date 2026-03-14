from __future__ import annotations

import structlog

logger = structlog.get_logger("gateway.usage")


def mask_api_key(key: str) -> str:
    """Show only first 8 chars of API key."""
    if len(key) <= 8:
        return key + "****"
    return key[:8] + "****"


def log_usage(
    *,
    user_id: str,
    user_name: str,
    client_ip: str,
    method: str,
    path: str,
    model: str | None,
    is_stream: bool,
    latency_sec: float,
    ttft_sec: float | None = None,
    status_code: int = 200,
    api_key_masked: str = "",
    request_id: str = "",
) -> None:
    """Log a structured usage entry."""
    logger.info(
        "request_completed",
        request_id=request_id,
        user_id=user_id,
        user_name=user_name,
        api_key=api_key_masked,
        client_ip=client_ip,
        method=method,
        path=path,
        model=model or "default",
        is_stream=is_stream,
        latency_sec=round(latency_sec, 3),
        ttft_sec=round(ttft_sec, 3) if ttft_sec is not None else None,
        status_code=status_code,
    )
