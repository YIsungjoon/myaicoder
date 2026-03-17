"""Conversation logging — async PostgreSQL storage."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

logger = structlog.get_logger("gateway.db")

metadata = MetaData()

conversations = Table(
    "conversations",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("user_id", String(100), nullable=False, index=True),
    Column("user_name", String(100)),
    Column("model", String(100), index=True),
    Column("messages", JSONB, nullable=False),
    Column("response_content", Text),
    Column("response_raw", JSONB),
    Column("prompt_tokens", Integer, default=0),
    Column("completion_tokens", Integer, default=0),
    Column("total_tokens", Integer, default=0),
    Column("latency_ms", Integer),
    Column("status_code", Integer),
    Column("is_stream", Boolean, default=False),
    Column("client_ip", String(45)),
    Column(
        "created_at",
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    ),
)


_engine: AsyncEngine | None = None


async def init_db(database_url: str) -> None:
    """Create async engine and ensure tables exist."""
    global _engine
    _engine = create_async_engine(database_url, pool_size=5, max_overflow=5)

    async with _engine.begin() as conn:
        await conn.run_sync(metadata.create_all)

    from urllib.parse import urlparse

    parsed = urlparse(database_url)
    safe_url = f"{parsed.hostname}:{parsed.port}{parsed.path}" if parsed.hostname else "(local)"
    logger.info("database_initialized", url=safe_url)


async def close_db() -> None:
    """Close async engine."""
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None


async def save_conversation(
    *,
    user_id: str,
    user_name: str,
    model: str | None,
    messages: list[dict],
    response_content: str | None,
    response_raw: dict | None,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: int,
    status_code: int,
    is_stream: bool,
    client_ip: str,
) -> None:
    """Save conversation to DB. Fire-and-forget safe."""
    if _engine is None:
        return

    try:
        async with _engine.begin() as conn:
            await conn.execute(
                conversations.insert().values(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    user_name=user_name,
                    model=model or "unknown",
                    messages=messages,
                    response_content=response_content,
                    response_raw=response_raw,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                    latency_ms=latency_ms,
                    status_code=status_code,
                    is_stream=is_stream,
                    client_ip=client_ip,
                )
            )
    except Exception as e:
        logger.error("conversation_save_failed", error=str(e))


def _on_task_done(task: asyncio.Task) -> None:
    """Log errors from fire-and-forget background tasks."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        logger.error("background_task_failed", error=str(exc), task=task.get_name())


def save_conversation_bg(**kwargs) -> None:
    """Schedule save_conversation as fire-and-forget background task."""
    try:
        loop = asyncio.get_running_loop()
        task = loop.create_task(save_conversation(**kwargs), name="save_conversation")
        task.add_done_callback(_on_task_done)
    except RuntimeError:
        logger.warning("save_conversation_bg_no_loop")


def extract_stream_content(chunk: bytes) -> str:
    """Extract delta.content from SSE chunk. Returns empty string on parse failure."""
    try:
        text = chunk.decode("utf-8", errors="ignore")
        content_parts = []
        for line in text.split("\n"):
            if not line.startswith("data: ") or line.strip() == "data: [DONE]":
                continue
            data = json.loads(line[6:])
            choices = data.get("choices", [])
            if choices:
                delta = choices[0].get("delta", {})
                c = delta.get("content", "")
                if c:
                    content_parts.append(c)
        return "".join(content_parts)
    except (json.JSONDecodeError, UnicodeDecodeError, IndexError, KeyError):
        return ""


def extract_stream_usage(chunk: bytes) -> tuple[int, int] | None:
    """Extract usage from SSE chunk. Returns (prompt, completion) or None."""
    try:
        text = chunk.decode("utf-8", errors="ignore")
        for line in text.split("\n"):
            if not line.startswith("data: ") or line.strip() == "data: [DONE]":
                continue
            data = json.loads(line[6:])
            usage = data.get("usage")
            if usage:
                return (
                    usage.get("prompt_tokens", 0),
                    usage.get("completion_tokens", 0),
                )
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass
    return None


async def list_conversations(
    *,
    user_id: str | None = None,
    model: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Query conversations with filters."""
    if _engine is None:
        return []

    query = conversations.select().order_by(conversations.c.created_at.desc())
    if user_id:
        query = query.where(conversations.c.user_id == user_id)
    if model:
        query = query.where(conversations.c.model == model)
    query = query.limit(limit).offset(offset)

    try:
        async with _engine.connect() as conn:
            result = await conn.execute(query)
            rows = result.mappings().all()
            return [
                {
                    "id": str(row["id"]),
                    "user_id": row["user_id"],
                    "user_name": row["user_name"],
                    "model": row["model"],
                    "messages": row["messages"],
                    "response_content": row["response_content"],
                    "prompt_tokens": row["prompt_tokens"],
                    "completion_tokens": row["completion_tokens"],
                    "total_tokens": row["total_tokens"],
                    "latency_ms": row["latency_ms"],
                    "is_stream": row["is_stream"],
                    "created_at": row["created_at"].isoformat()
                    if row["created_at"]
                    else None,
                }
                for row in rows
            ]
    except Exception as e:
        logger.error("conversation_list_failed", error=str(e))
        return []
