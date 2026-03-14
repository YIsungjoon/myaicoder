# Design: rate-limiting

**Feature**: rate-limiting
**날짜**: 2026-03-14
**Phase**: Design
**Level**: Enterprise
**Plan Reference**: `docs/pdca/01-plan/features/rate-limiting.plan.md`

---

## 1. 설계 개요

Gateway에 Sliding Window Counter 기반 사용자별·역할별 요청 제한을 추가한다.
모든 설정은 프로젝트 루트 `config/` 디렉토리에서 중앙 관리한다.

### 핵심 설계 제약 (사용자 피드백 반영)

| 제약 | 해결 |
|------|------|
| **A. 메모리 누수 방지** | 만료된 윈도우 카운터 자동 eviction |
| **B. 동시성 안전** | read-increment 사이에 `await` 없는 동기 블록 |
| **C. 응답 헤더 주입** | Middleware(헤더 주입) + Dependency(차단) 분리 |

### 변경 범위

| 위치 | 변경 내용 |
|------|----------|
| `services/gateway/app/` | `rate_limiter.py` 신규, `config.py` 확장, `main.py` 미들웨어 추가, `deps.py` 의존성 추가 |
| `config/` | `gateway.yaml` 이동 + rate_limit 섹션 추가 |
| `services/gateway/app/config.py` | config 로드 경로에 `config/` 추가 |

## 2. 디렉토리 구조

### 2.1 신규 파일

```
services/gateway/
├── app/
│   └── rate_limiter.py              # SlidingWindowLimiter + RateLimitMiddleware

services/gateway/tests/
├── test_rate_limiter.py             # 알고리즘 + 미들웨어 테스트

config/                              # 중앙 설정 제어판 (신규 디렉토리)
├── gateway.yaml                     # gateway 전체 설정 (rate_limit 포함)
├── models.yaml                      # 모델 프로필 (기존 이동)
```

### 2.2 수정 파일

| 파일 | 수정 내용 |
|------|----------|
| `services/gateway/app/config.py` | `RateLimitConfig` 추가, config 로드 경로 확장 |
| `services/gateway/app/main.py` | `RateLimitMiddleware` 등록, lifespan에 limiter 초기화 |
| `services/gateway/app/deps.py` | `check_rate_limit` 의존성 추가 |
| `services/gateway/gateway.yaml.example` | rate_limit 섹션 예시 추가 |

## 3. 모듈 상세 설계

### 3.1 Config 확장 (`config.py`)

```python
class RoleLimitConfig(BaseModel):
    requests_per_minute: int = 30
    requests_per_hour: int = 500


class UserOverrideConfig(BaseModel):
    user_id: str
    requests_per_minute: int
    requests_per_hour: int


class RateLimitConfig(BaseModel):
    enabled: bool = True
    roles: dict[str, RoleLimitConfig] = {
        "admin": RoleLimitConfig(requests_per_minute=120, requests_per_hour=3600),
        "user": RoleLimitConfig(requests_per_minute=30, requests_per_hour=500),
    }
    overrides: list[UserOverrideConfig] = []


class GatewayConfig(BaseModel):
    server: ServerConfig = ServerConfig()
    auth: AuthConfig = AuthConfig()
    models: ModelsConfig = ModelsConfig()
    logging: LoggingConfig = LoggingConfig()
    rate_limit: RateLimitConfig = RateLimitConfig()  # 추가

    @classmethod
    def load(cls, path: str | Path | None = None) -> GatewayConfig:
        """Load config. Search: explicit → config/ → ./ → env var → defaults."""
        if path is None:
            env_path = os.environ.get("GATEWAY_CONFIG")
            search = [
                Path("config/gateway.yaml"),       # 중앙 config (신규)
                Path("gateway.yaml"),               # 서비스 디렉토리 (하위 호환)
            ]
            if env_path:
                search.insert(0, Path(env_path))

            for p in search:
                if p.exists():
                    path = p
                    break

        if path is not None:
            config_path = Path(path)
            if config_path.exists():
                with open(config_path, encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                return cls.model_validate(data)

        return cls()
```

### 3.2 SlidingWindowLimiter (`rate_limiter.py`)

Sliding Window Counter 알고리즘을 구현한다.

#### 알고리즘 원리

```
시간축: ────[이전 윈도우]────[현재 윈도우]────→
             prev_count       curr_count

가중 평균 = curr_count + prev_count × (1 - 현재 윈도우 경과 비율)

예) 윈도우 = 60초, 현재 40초 경과
    가중 평균 = curr_count + prev_count × (1 - 40/60)
             = curr_count + prev_count × 0.333
```

#### 핵심 구현

```python
import time
from dataclasses import dataclass, field


@dataclass
class WindowCounter:
    """Single window's counter data."""
    window_key: int = 0       # window start time (truncated)
    count: int = 0
    prev_count: int = 0
    prev_window_key: int = 0


class SlidingWindowLimiter:
    """In-memory sliding window counter rate limiter.

    Thread/async safety: all state mutations are synchronous (no await
    between read and increment), safe under asyncio single-thread model.

    Memory safety: expired entries are evicted periodically via _evict().
    """

    def __init__(self):
        # key: (user_id, window_seconds) → WindowCounter
        self._counters: dict[tuple[str, int], WindowCounter] = {}
        self._last_eviction: float = 0.0
        self._eviction_interval: float = 300.0  # 5분마다 정리

    def check_and_increment(
        self, user_id: str, limit: int, window_seconds: int
    ) -> tuple[bool, int, int]:
        """Check rate limit and increment counter atomically (no await!).

        Returns:
            (allowed, remaining, reset_at)
            - allowed: True if under limit
            - remaining: requests left in current window
            - reset_at: unix timestamp when window resets
        """
        now = time.time()

        # ── Eviction (주기적 메모리 정리) ──
        if now - self._last_eviction > self._eviction_interval:
            self._evict(now)
            self._last_eviction = now

        key = (user_id, window_seconds)
        current_window = int(now // window_seconds)
        window_progress = (now % window_seconds) / window_seconds

        counter = self._counters.get(key)

        if counter is None:
            counter = WindowCounter(window_key=current_window)
            self._counters[key] = counter

        # 윈도우 전환 처리
        if counter.window_key != current_window:
            if counter.window_key == current_window - 1:
                # 바로 이전 윈도우 → prev로 이동
                counter.prev_count = counter.count
                counter.prev_window_key = counter.window_key
            else:
                # 2개 이상 지난 윈도우 → prev 리셋
                counter.prev_count = 0
                counter.prev_window_key = 0
            counter.window_key = current_window
            counter.count = 0

        # ── 가중 평균 계산 (동기 블록 — await 없음!) ──
        weighted = counter.count + counter.prev_count * (1.0 - window_progress)
        remaining = max(0, limit - int(weighted) - 1)  # -1 for this request
        reset_at = (current_window + 1) * window_seconds

        if weighted >= limit:
            return (False, 0, int(reset_at))

        # 허용 → 카운터 증가
        counter.count += 1
        return (True, remaining, int(reset_at))

    def _evict(self, now: float) -> None:
        """Remove expired window counters to prevent memory leak.

        A counter is expired if its window_key is more than 2 windows old.
        """
        expired_keys: list[tuple[str, int]] = []
        for key, counter in self._counters.items():
            _, window_seconds = key
            current_window = int(now // window_seconds)
            if counter.window_key < current_window - 1:
                expired_keys.append(key)

        for key in expired_keys:
            del self._counters[key]
```

#### 동시성 안전 보장

`check_and_increment` 메서드 전체가 **동기 코드**다.
`time.time()` 호출부터 `counter.count += 1`까지 사이에 `await`가 한 번도 없으므로,
asyncio 이벤트 루프가 중간에 다른 코루틴으로 전환할 수 없다.
따라서 Lock 없이도 race condition이 발생하지 않는다.

#### 메모리 누수 방지

`_evict()` 메서드가 5분마다 만료된 카운터를 정리한다.
`check_and_increment` 호출 시 `_last_eviction`과 현재 시간을 비교하여
별도 백그라운드 태스크 없이 lazy eviction을 수행한다.

### 3.3 RateLimitMiddleware (`rate_limiter.py`에 포함)

**설계 결정**: Dependency(차단) + Middleware(헤더) 분리가 아닌,
**Middleware 단일 방식**으로 차단과 헤더 주입을 모두 처리한다.

이유:
- Dependency에서는 최종 Response 객체에 접근하기 어려움
- Middleware는 요청 전(차단)과 응답 후(헤더 주입) 모두 처리 가능
- 인증 정보가 필요하므로, 인증 Dependency 실행 후에 rate check 수행

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware.

    Execution order:
    1. Request arrives
    2. Auth dependency runs (sets request.state.user)
    3. This middleware checks rate limit
    4. If over limit → 429 response
    5. If under limit → proceed + inject headers into response
    """

    def __init__(self, app, limiter: SlidingWindowLimiter, config: RateLimitConfig):
        super().__init__(app)
        self.limiter = limiter
        self.config = config
        # Pre-build override lookup
        self._overrides: dict[str, tuple[int, int]] = {
            o.user_id: (o.requests_per_minute, o.requests_per_hour)
            for o in config.overrides
        }

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip rate limiting for non-API paths (health, docs)
        if not request.url.path.startswith("/v1"):
            return await call_next(request)

        # Skip if rate limiting disabled
        if not self.config.enabled:
            return await call_next(request)

        # User must be set by auth dependency (via router-level Depends)
        # If not set, let the request proceed (auth will handle 403)
        user = getattr(request.state, "user", None)
        if user is None:
            return await call_next(request)

        # Resolve limits for this user
        rpm, rph = self._resolve_limits(user.user_id, user.role)

        # ── Per-minute check ──
        allowed_m, remaining_m, reset_m = self.limiter.check_and_increment(
            user.user_id, rpm, 60
        )
        if not allowed_m:
            return self._too_many_requests(rpm, 0, reset_m)

        # ── Per-hour check ──
        allowed_h, remaining_h, reset_h = self.limiter.check_and_increment(
            user.user_id, rph, 3600
        )
        if not allowed_h:
            return self._too_many_requests(rph, 0, reset_h)

        # Proceed with request
        response = await call_next(request)

        # Inject rate limit headers (per-minute as primary)
        response.headers["X-RateLimit-Limit"] = str(rpm)
        response.headers["X-RateLimit-Remaining"] = str(remaining_m)
        response.headers["X-RateLimit-Reset"] = str(reset_m)

        return response

    def _resolve_limits(self, user_id: str, role: str) -> tuple[int, int]:
        """Resolve rate limits: user override > role default."""
        # Check user-specific override first
        override = self._overrides.get(user_id)
        if override:
            return override

        # Fall back to role-based limits
        role_config = self.config.roles.get(role)
        if role_config:
            return (role_config.requests_per_minute, role_config.requests_per_hour)

        # Ultimate fallback
        return (30, 500)

    def _too_many_requests(
        self, limit: int, remaining: int, reset_at: int
    ) -> JSONResponse:
        """Return HTTP 429 with standard headers."""
        import time

        retry_after = max(1, reset_at - int(time.time()))
        # Note: 실제 구현에서는 FastAPI HTTPException(detail=...) 사용
        # 아래는 참고용 — Dependency에서 HTTPException으로 처리됨
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Please retry later."},
            headers={
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_at),
                "Retry-After": str(retry_after),
            },
        )
```

### 3.4 Middleware vs Dependency 문제 해결

**문제**: Middleware는 Dependency보다 먼저 실행되므로, `request.state.user`가 아직 없다.

**해결**: `v1_router`에 이미 `dependencies=[Depends(get_current_user)]`가 적용되어 있으므로,
Middleware에서 `request.state.user`가 없으면 skip한다 (인증 미통과 경로).

하지만 **Starlette BaseHTTPMiddleware의 실행 순서**를 고려하면:

```
Request → Middleware.dispatch() → call_next() → [Route + Dependency 실행] → Response
                                                  ↑ 여기서 user가 설정됨
```

`call_next()` 호출 전에는 user가 없다. 따라서 설계를 조정한다:

**최종 방식: Dependency에서 차단 + request.state에 헤더 정보 저장 → Middleware에서 헤더 주입**

```python
# deps.py — rate limit check (차단 담당)
async def check_rate_limit(request: Request) -> None:
    """Check rate limit after authentication. Raises 429 if exceeded."""
    limiter: SlidingWindowLimiter = request.app.state.rate_limiter
    config: RateLimitConfig = request.app.state.config.rate_limit

    if not config.enabled:
        return

    user: User = request.state.user  # set by get_current_user (runs first)

    rpm, rph = resolve_limits(config, user.user_id, user.role)

    # Per-minute check
    allowed_m, remaining_m, reset_m = limiter.check_and_increment(
        user.user_id, rpm, 60
    )
    if not allowed_m:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please retry later.",
            headers={
                "X-RateLimit-Limit": str(rpm),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_m),
                "Retry-After": str(max(1, reset_m - int(time.time()))),
            },
        )

    # Per-hour check
    allowed_h, remaining_h, reset_h = limiter.check_and_increment(
        user.user_id, rph, 3600
    )
    if not allowed_h:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded (hourly). Please retry later.",
            headers={
                "X-RateLimit-Limit": str(rph),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_h),
                "Retry-After": str(max(1, reset_h - int(time.time()))),
            },
        )

    # Store for header injection
    request.state.rate_limit_headers = {
        "X-RateLimit-Limit": str(rpm),
        "X-RateLimit-Remaining": str(remaining_m),
        "X-RateLimit-Reset": str(reset_m),
    }


# routes/v1.py — dependency chain 수정
router = APIRouter(
    prefix="/v1",
    dependencies=[
        Depends(get_current_user),      # 1. 인증
        Depends(check_rate_limit),      # 2. Rate limit (인증 후 실행)
    ],
)
```

```python
# rate_limiter.py — 헤더 주입 Middleware (응답 후처리만)
class RateLimitHeaderMiddleware(BaseHTTPMiddleware):
    """Inject X-RateLimit-* headers into successful responses."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Inject headers if rate limit info was stored by dependency
        headers = getattr(request.state, "rate_limit_headers", None)
        if headers:
            for key, value in headers.items():
                response.headers[key] = value

        return response
```

### 역할 분담 요약

| 컴포넌트 | 역할 | 실행 시점 |
|----------|------|----------|
| `check_rate_limit` (Dependency) | 차단(429) + 헤더 정보 저장 | 인증 후, 핸들러 전 |
| `RateLimitHeaderMiddleware` | 정상 응답에 헤더 주입 | 응답 반환 시 |
| `SlidingWindowLimiter` | 순수 알고리즘 (상태 관리) | Dependency에서 호출 |

## 4. 중앙 Config 통합

### 4.1 `config/` 디렉토리 구조

```
myaicoder/
├── config/                           # 중앙 설정 제어판
│   ├── gateway.yaml                  # Gateway 전체 (서버, 인증, 모델, rate limit, 로깅)
│   └── models.yaml                   # 모델 프로필 (prod/dev)
```

### 4.2 Config 로드 우선순위 변경

`GatewayConfig.load()`에 `config/gateway.yaml` 경로를 최우선으로 추가:

```
1. CLI/환경변수 GATEWAY_CONFIG로 명시한 경로
2. config/gateway.yaml          ← 신규 (프로젝트 루트 config/)
3. ./gateway.yaml               ← 기존 (하위 호환)
```

`ModelsConfig.load()`에도 동일하게 `config/models.yaml` 추가.

## 5. main.py 수정

```python
def create_app(config: GatewayConfig | None = None) -> FastAPI:
    if config is None:
        config = GatewayConfig.load()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.config = config
        app.state.auth_store = AuthStore(config)
        app.state.model_router = ModelRouter(config.models)
        app.state.rate_limiter = SlidingWindowLimiter()  # 추가
        app.state.http_client = httpx.AsyncClient(...)
        yield
        await app.state.http_client.aclose()

    app = FastAPI(...)

    # Middleware 등록 (실행 순서: 마지막 등록 = 가장 먼저 실행)
    app.add_middleware(RateLimitHeaderMiddleware)  # 추가

    app.include_router(health_router)
    app.include_router(v1_router)

    return app
```

## 6. 시퀀스 다이어그램

### 6.1 정상 요청 (한도 이내)

```
Client → Gateway
  │
  ├─ [Middleware] RateLimitHeaderMiddleware.dispatch()
  │     └─ call_next() ──→
  │                        │
  │   [Dependency 1] get_current_user() → User 객체
  │   [Dependency 2] check_rate_limit()
  │       ├─ limiter.check_and_increment(user_id, 30, 60)
  │       │   └─ (True, 27, 1710374460)  ← 동기 블록, await 없음
  │       ├─ limiter.check_and_increment(user_id, 500, 3600)
  │       │   └─ (True, 485, 1710378000)
  │       └─ request.state.rate_limit_headers = {...}
  │                        │
  │   [Handler] chat_completions() → proxy → Response
  │                        │
  │     ←──────────────────┘
  │     response.headers += rate_limit_headers
  │
  └─ Response (200) + X-RateLimit-Limit: 30
                     + X-RateLimit-Remaining: 27
                     + X-RateLimit-Reset: 1710374460
```

### 6.2 한도 초과 (429)

```
Client → Gateway
  │
  ├─ [Dependency 1] get_current_user() → User 객체
  ├─ [Dependency 2] check_rate_limit()
  │       ├─ limiter.check_and_increment(user_id, 30, 60)
  │       │   └─ (False, 0, 1710374460)  ← 한도 초과
  │       └─ raise HTTPException(429)
  │
  └─ Response (429)
       + Retry-After: 23
       + X-RateLimit-Limit: 30
       + X-RateLimit-Remaining: 0
       + X-RateLimit-Reset: 1710374460
       Body: {"detail": "Rate limit exceeded. Please retry later."}
```

## 7. 테스트 전략

### 7.1 단위 테스트

| 테스트 | 대상 | 주요 케이스 |
|--------|------|-----------|
| `test_sliding_window` | SlidingWindowLimiter | 기본 허용/차단, 윈도우 전환, 가중 평균 정확성 |
| `test_eviction` | SlidingWindowLimiter._evict | 만료 카운터 정리, 메모리 누수 방지 |
| `test_config` | RateLimitConfig | YAML 파싱, 역할별 한도, 오버라이드 |
| `test_dependency` | check_rate_limit | 429 응답, 헤더 저장, disabled 시 skip |
| `test_middleware` | RateLimitHeaderMiddleware | 정상 응답 헤더 주입, 헤더 없을 때 skip |
| `test_integration` | 전체 흐름 | FastAPI TestClient로 연속 요청 → 한도 도달 → 429 |

### 7.2 시간 의존 테스트 처리

`time.time()`을 직접 mock하여 윈도우 전환을 테스트:

```python
from unittest.mock import patch

def test_window_transition():
    limiter = SlidingWindowLimiter()
    with patch("time.time", return_value=1000.0):
        limiter.check_and_increment("user1", 5, 60)  # window 16
    with patch("time.time", return_value=1060.0):
        # New window 17 — prev_count should carry over
        allowed, remaining, _ = limiter.check_and_increment("user1", 5, 60)
```

## 8. 구현 순서

| 순서 | 작업 | 파일 | 의존 |
|------|------|------|------|
| 1 | `config/` 디렉토리 생성 + config 로드 경로 확장 | `config.py`, `config/gateway.yaml` | 없음 |
| 2 | `RateLimitConfig` 추가 | `config.py` | 1 |
| 3 | `SlidingWindowLimiter` 구현 | `rate_limiter.py` + 테스트 | 없음 |
| 4 | `check_rate_limit` Dependency | `deps.py` | 2, 3 |
| 5 | `RateLimitHeaderMiddleware` | `rate_limiter.py` | 3 |
| 6 | `main.py` 통합 (lifespan + middleware + dependency chain) | `main.py`, `v1.py` | 4, 5 |
| 7 | 통합 테스트 | `test_rate_limiter.py` | 6 |
| 8 | `gateway.yaml.example` 업데이트 | example 파일 | 2 |

## 9. 에러 처리

| 상황 | 처리 |
|------|------|
| 분당 한도 초과 | HTTP 429 + Retry-After (윈도우 종료까지 초) |
| 시간당 한도 초과 | HTTP 429 + Retry-After (윈도우 종료까지 초) |
| rate_limit.enabled = false | 모든 체크 skip, 헤더 미주입 |
| config에 역할 없음 | 기본값 (30/분, 500/시간) |
| 인증 실패 요청 | rate limit 체크 안 함 (인증 dependency에서 403) |
| Gateway 재시작 | 카운터 리셋 (in-memory 특성, 허용) |
