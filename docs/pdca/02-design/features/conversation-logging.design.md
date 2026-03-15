# Design: Conversation Logging — 서버 측 대화 저장

- **Feature**: conversation-logging
- **Level**: Enterprise
- **Created**: 2026-03-16
- **Plan Reference**: `docs/pdca/01-plan/features/conversation-logging.plan.md`

---

## 1. 설계 개요

Gateway를 통과하는 모든 chat completion 요청과 응답을 PostgreSQL에 비동기로 저장한다. 스트리밍 응답은 SSE 청크에서 `delta.content`를 파싱하여 깔끔한 텍스트로 누적 저장한다.

### 1.1 산출물 매핑

| # | 산출물 | Plan 참조 | 설계 섹션 |
|---|--------|----------|----------|
| D1 | `app/config.py` 수정 | S4 | §2 |
| D2 | `app/db.py` 신규 | S1, S2, S3 | §3 |
| D3 | `app/main.py` 수정 | S3 | §4 |
| D4 | `app/proxy.py` 수정 | S2 | §5 |
| D5 | `app/routes/internal.py` 수정 | S5 | §6 |
| D6 | `config/gateway.prod.yaml` 수정 | S4 | §7 |
| D7 | `pyproject.toml` 수정 | — | §8 |

---

## 2. D1: app/config.py — DatabaseConfig 추가

### 2.1 변경 내용

```python
class DatabaseConfig(BaseModel):
    url: str = ""
    enabled: bool = False

class GatewayConfig(BaseModel):
    server: ServerConfig = ServerConfig()
    auth: AuthConfig = AuthConfig()
    models: ModelsConfig = ModelsConfig()
    rate_limit: RateLimitConfig = RateLimitConfig()
    logging: LoggingConfig = LoggingConfig()
    database: DatabaseConfig = DatabaseConfig()  # NEW
```

### 2.2 설계 항목

| # | 항목 | 상세 |
|---|------|------|
| D1-1 | DatabaseConfig | `url` (PostgreSQL 접속 문자열) + `enabled` (활성화 플래그) |
| D1-2 | 기본값 | `enabled=False` — DB 설정 없으면 로깅 비활성화 (기존 동작 유지) |
| D1-3 | URL 형식 | `postgresql+asyncpg://user:pass@host:port/dbname` |

### 2.3 엣지 케이스

| # | 상황 | 대응 |
|---|------|------|
| EC-D1-A | database 섹션 없는 기존 config | `DatabaseConfig()` 기본값 → enabled=False → 로깅 안 함 |

---

## 3. D2: app/db.py — 신규 (DB 연결 + 테이블 + 저장)

### 3.1 설계 의도
- SQLAlchemy Core (ORM 없음) + asyncpg로 경량 비동기 DB 접근
- fire-and-forget 패턴으로 프록시 응답 블로킹 없이 저장
- SSE 청크 파싱 유틸리티 포함

### 3.2 파일 내용

```python
"""Conversation logging — async PostgreSQL storage."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import (
    Boolean, Column, DateTime, Integer, String, Text,
    MetaData, Table, create_engine,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

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
    Column("created_at", DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True),
)


_engine: AsyncEngine | None = None


async def init_db(database_url: str) -> None:
    """Create async engine and ensure tables exist."""
    global _engine
    _engine = create_async_engine(database_url, pool_size=5, max_overflow=5)

    # Create tables via run_sync (no sync driver needed)
    async with _engine.begin() as conn:
        await conn.run_sync(metadata.create_all)

    logger.info("database_initialized", url=database_url.split("@")[-1])


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


def save_conversation_bg(**kwargs) -> None:
    """Schedule save_conversation as fire-and-forget background task."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(save_conversation(**kwargs))
    except RuntimeError:
        pass


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
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                }
                for row in rows
            ]
    except Exception as e:
        logger.error("conversation_list_failed", error=str(e))
        return []
```

### 3.3 설계 항목

| # | 항목 | 상세 |
|---|------|------|
| D2-1 | 테이블 정의 | SQLAlchemy Core `Table` — ORM 없이 경량 |
| D2-2 | `response_content` | 스트리밍 파싱된 깔끔한 텍스트 (분석용) |
| D2-3 | `response_raw` | 비스트리밍: 전체 JSON, 스트리밍: None (너무 큼) |
| D2-4 | `messages` (JSONB) | 요청 body의 messages 배열 저장 |
| D2-5 | `init_db()` | async engine 생성 + `conn.run_sync(metadata.create_all)` (sync 드라이버 불필요) |
| D2-6 | `close_db()` | engine dispose (lifespan shutdown) |
| D2-7 | `save_conversation()` | 비동기 INSERT, try/except으로 에러 격리 |
| D2-8 | `save_conversation_bg()` | `asyncio.create_task`로 fire-and-forget |
| D2-9 | `extract_stream_content()` | SSE 청크에서 `delta.content`만 추출 |
| D2-10 | `extract_stream_usage()` | SSE 청크에서 `usage` 추출 (마지막 청크) |
| D2-11 | `list_conversations()` | 필터링 조회 (user_id, model, pagination) |
| D2-12 | 인덱스 | `user_id`, `model`, `created_at` 3개 |
| D2-13 | pool_size | 5 (소규모 내부 사용, 과도한 커넥션 방지) |

### 3.4 엣지 케이스

| # | 상황 | 대응 |
|---|------|------|
| EC-D2-A | DB 연결 실패 | `save_conversation`에서 try/except → 로그만, 프록시 정상 동작 |
| EC-D2-B | SSE 청크에 content 없는 경우 (thinking mode) | `delta.get("content", "")` → 빈 문자열 반환, reasoning_content는 무시 |
| EC-D2-C | usage가 없는 모델 | fallback: `len(accumulated_content) // 4`로 토큰 추정 |
| EC-D2-D | _engine이 None (DB 비활성화) | `save_conversation`, `list_conversations` 즉시 return |
| EC-D2-E | 대용량 응답 (>1MB) | `response_content` 최대 1MB로 truncate |

---

## 4. D3: app/main.py — DB lifespan 연결

### 4.1 변경 내용

lifespan에 DB init/close 추가:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app.state.config = config
    app.state.auth_store = AuthStore(config)
    app.state.model_router = ModelRouter(config.models)
    app.state.rate_limiter = SlidingWindowLimiter()
    app.state.http_client = httpx.AsyncClient(...)

    # NEW: DB 초기화
    if config.database.enabled and config.database.url:
        from .db import init_db
        await init_db(config.database.url)

    yield

    # Shutdown
    await app.state.http_client.aclose()

    # NEW: DB 종료
    if config.database.enabled:
        from .db import close_db
        await close_db()
```

### 4.2 설계 항목

| # | 항목 | 상세 |
|---|------|------|
| D3-1 | 조건부 초기화 | `database.enabled and database.url` 확인 후 init |
| D3-2 | lazy import | `from .db import init_db` — DB 미사용 시 import 안 함 |
| D3-3 | shutdown 순서 | HTTP client close → DB close |

---

## 5. D4: app/proxy.py — 대화 저장 호출

### 5.1 forward_request 변경 (비스트리밍)

`finally` 블록에 저장 호출 추가:

```python
async def forward_request(...) -> httpx.Response:
    ...
    try:
        resp = await http_client.request(...)
    except httpx.ConnectError:
        ...
    finally:
        latency = time.monotonic() - start
        ...
        # NEW: 대화 저장
        if path == "chat/completions" and "resp" in dir() and resp.status_code == 200:
            _save_chat_completion(
                body=body, response=resp.content,
                user=user, model_name=model_name,
                latency=latency, status_code=resp.status_code,
                is_stream=False, client_ip=client_ip,
            )
    return resp
```

### 5.2 stream_upstream 변경 (스트리밍)

청크 반복문에서 content 누적 + usage 추출:

```python
async def stream_upstream(...) -> AsyncIterator[bytes]:
    ...
    accumulated_content = []  # NEW
    stream_tokens: tuple[int, int] | None = None  # NEW

    try:
        async with http_client.stream(...) as upstream_resp:
            async for chunk in upstream_resp.aiter_bytes():
                if ttft is None:
                    ttft = time.monotonic() - start
                prompt_tokens, completion_tokens = _try_parse_usage(...)

                # NEW: content 누적 + usage 추출
                content = extract_stream_content(chunk)
                if content:
                    accumulated_content.append(content)
                usage = extract_stream_usage(chunk)
                if usage:
                    stream_tokens = usage

                yield chunk
    ...
    finally:
        latency = time.monotonic() - start
        ...
        # NEW: 스트리밍 대화 저장
        if status_code == 200:
            final_content = "".join(accumulated_content)
            p_tokens = stream_tokens[0] if stream_tokens else 0
            c_tokens = stream_tokens[1] if stream_tokens else len(final_content) // 4
            _save_chat_completion(
                body=body, response_content=final_content,
                user=user, model_name=model_name,
                latency=latency, status_code=status_code,
                is_stream=True, client_ip=client_ip,
                prompt_tokens=p_tokens, completion_tokens=c_tokens,
            )
```

### 5.3 _save_chat_completion 헬퍼

```python
def _save_chat_completion(
    *, body: bytes, user: User, model_name: str | None,
    latency: float, status_code: int, is_stream: bool,
    client_ip: str,
    response: bytes | None = None,
    response_content: str | None = None,
    prompt_tokens: int = 0, completion_tokens: int = 0,
) -> None:
    """Parse request/response and schedule DB save."""
    try:
        from .db import save_conversation_bg

        request_data = json.loads(body)
        messages = request_data.get("messages", [])

        if response and not response_content:
            resp_data = json.loads(response)
            content = resp_data.get("choices", [{}])[0].get("message", {}).get("content", "")
            response_content = content
            usage = resp_data.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            response_raw = resp_data
        else:
            response_raw = None

        # Truncate large content (max 1MB)
        if response_content and len(response_content) > 1_000_000:
            response_content = response_content[:1_000_000] + "\n[TRUNCATED]"

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
    except Exception:
        pass  # Never break proxy for logging failure
```

### 5.4 설계 항목

| # | 항목 | 상세 |
|---|------|------|
| D4-1 | 비스트리밍 저장 | `forward_request` finally → `_save_chat_completion` |
| D4-2 | 스트리밍 content 누적 | `extract_stream_content()` → `accumulated_content` 리스트 |
| D4-3 | 스트리밍 usage 추출 | `extract_stream_usage()` → 마지막 청크에서 가로채기 |
| D4-4 | 토큰 fallback | usage 없으면 `len(content) // 4`로 추정 |
| D4-5 | fire-and-forget | `save_conversation_bg()` — 프록시 응답 블로킹 없음 |
| D4-6 | 200만 저장 | `status_code == 200`일 때만 (에러 응답 제외) |
| D4-7 | chat/completions만 | `path == "chat/completions"` 조건 (models, health 제외) |
| D4-8 | 1MB truncate | 대용량 응답 방어 |
| D4-9 | 에러 격리 | `except Exception: pass` — 로깅 실패가 프록시에 영향 없음 |

### 5.5 엣지 케이스

| # | 상황 | 대응 |
|---|------|------|
| EC-D4-A | 요청 body가 유효하지 않은 JSON | `json.loads(body)` 실패 → except pass |
| EC-D4-B | 스트리밍 중 클라이언트 연결 끊김 | 이미 기존 코드에서 처리, 누적된 content까지만 저장 |
| EC-D4-C | reasoning_content만 있는 Qwen3.5 thinking mode | `delta.content`만 추출하므로 thinking 내용은 저장 안 됨 → 향후 P2에서 별도 처리 |
| EC-D4-D | DB 비활성화 상태 | `save_conversation_bg` → `_engine is None` → 즉시 return |

---

## 6. D5: app/routes/internal.py — 조회 API

### 6.1 변경 내용

```python
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

    from ..db import list_conversations
    items = await list_conversations(
        user_id=user_id, model=model, limit=limit, offset=offset,
    )
    return {"conversations": items, "count": len(items)}
```

### 6.2 설계 항목

| # | 항목 | 상세 |
|---|------|------|
| D5-1 | 엔드포인트 | `GET /internal/conversations` |
| D5-2 | 인증 | `X-Internal-Token` 헤더 (기존 internal API와 동일) |
| D5-3 | 필터 | `user_id`, `model` (쿼리 파라미터) |
| D5-4 | 페이지네이션 | `limit` (기본 50), `offset` |
| D5-5 | 정렬 | `created_at DESC` (최신 우선) |

---

## 7. D6: config/gateway.prod.yaml — database 설정

### 7.1 추가 내용

```yaml
database:
  enabled: true
  url: "postgresql+asyncpg://myaicoder:${DB_PASSWORD}@postgres:5432/myaicoder"
```

### 7.2 설계 항목

| # | 항목 | 상세 |
|---|------|------|
| D6-1 | enabled | `true` (prod 환경에서 활성화) |
| D6-2 | url | Docker 내부 DNS `postgres:5432`, asyncpg 드라이버 |
| D6-3 | DB_PASSWORD | .env.prod에서 주입 (기존 Postgres와 동일) |

### 7.3 엣지 케이스

| # | 상황 | 대응 |
|---|------|------|
| EC-D6-A | `${DB_PASSWORD}` 미치환 (YAML 직접 파싱) | DGX 배포 시 실제 비밀번호로 직접 입력 필요 (api-key-auth와 동일 이슈) |

---

## 8. D7: pyproject.toml — 의존성 추가

### 8.1 변경 내용

```toml
dependencies = [
    ...
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.29.0",
]
```

### 8.2 설계 항목

| # | 항목 | 상세 |
|---|------|------|
| D7-1 | sqlalchemy[asyncio] | Core + async engine (ORM 미사용) |
| D7-2 | asyncpg | PostgreSQL async 드라이버 |
| D7-3 | psycopg2 불필요 | DDL용 sync는 asyncpg가 아닌 libpq 기반이므로, `psycopg2-binary` 추가 또는 sync DDL 방식 변경 필요 |

### 8.3 엣지 케이스

| # | 상황 | 대응 |
|---|------|------|
| EC-D7-A | ~~sync DDL 문제~~ | `conn.run_sync(metadata.create_all)` 사용 — psycopg2 불필요 (해결됨) |

---

## 9. 구현 순서

| 순서 | 산출물 | 의존성 | 예상 규모 |
|------|--------|--------|----------|
| 1 | D7: pyproject.toml | 없음 | +2줄 |
| 2 | D1: config.py | 없음 | +5줄 |
| 3 | D2: db.py | D7 | 신규 ~150줄 |
| 4 | D3: main.py | D1, D2 | +10줄 |
| 5 | D4: proxy.py | D2 | +40줄 |
| 6 | D5: internal.py | D2 | +20줄 |
| 7 | D6: gateway.prod.yaml | D1 | +3줄 |

**총**: 6개 수정 파일 + 1개 신규 파일, ~230줄

---

## 10. 검증 체크리스트

| # | 검증 항목 | 성공 기준 |
|---|----------|----------|
| V1 | DatabaseConfig 로드 | `config.database.enabled`, `config.database.url` 접근 가능 |
| V2 | DB 미설정 시 동작 | `database` 섹션 없으면 로깅 비활성화, 기존 동작 유지 |
| V3 | 테이블 자동 생성 | Gateway 시작 시 `conversations` 테이블 생성 |
| V4 | 비스트리밍 저장 | curl 요청 → DB에 messages + response_content 확인 |
| V5 | 스트리밍 저장 | 스트리밍 요청 → DB에 파싱된 content 텍스트 저장 |
| V6 | 스트리밍 SSE 파싱 | raw SSE 대신 `delta.content`만 깔끔하게 누적 |
| V7 | 토큰 저장 (비스트리밍) | `usage`에서 정확히 추출 |
| V8 | 토큰 저장 (스트리밍) | 마지막 청크 usage 추출, 없으면 fallback |
| V9 | fire-and-forget | DB 저장 실패해도 프록시 정상 응답 |
| V10 | 조회 API | `GET /internal/conversations?user_id=xxx` 동작 |
| V11 | 인증 | internal token 없으면 403 |
| V12 | 응답 지연 무영향 | 저장 전후 latency 차이 <5ms |
| V13 | 1MB truncate | 대용량 응답 잘림 확인 |
| V14 | 기존 테스트 통과 | 241/241 PASS, 0 regression |
