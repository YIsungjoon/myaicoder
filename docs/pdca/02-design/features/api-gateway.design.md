# Design: api-gateway

**Feature**: api-gateway
**날짜**: 2026-03-14
**Phase**: Design (rev.2 — 실용적 타협 반영)
**Level**: Enterprise
**Plan 참조**: `docs/pdca/01-plan/features/api-gateway.plan.md`

---

## 1. 기술 스택

| 영역 | 기술 | 비고 |
|------|------|------|
| 런타임 | Python `>=3.11` | 프로젝트 전체 기준 일치 |
| 프레임워크 | FastAPI | async 기반, OpenAPI 자동 생성 |
| HTTP 클라이언트 | httpx (async) | 스트리밍 프록시, connection pool |
| 로깅 | structlog (JSON) | 구조화된 로그 출력 |
| 설정 | pydantic-settings + YAML | 타입 안전, 환경변수 오버라이드 |
| 테스트 | pytest + httpx.AsyncClient | FastAPI 공식 권장 패턴 |
| 린트 | ruff | 프로젝트 기준 통일 |
| 패키지 관리 | uv | 프로젝트 기준 통일 |

## 2. 설계 원칙

### 2.1 실용적 계층 압축

API Gateway는 복잡한 비즈니스 로직(Domain)보다 **데이터의 빠르고 투명한 통과(Pass-through)**가 핵심이다.
정통 Clean Architecture 4-layer를 엄격하게 적용하면 단순히 데이터를 넘겨주기만 하는 불필요한 인터페이스가 양산된다.

**결정**: domain/application 계층을 `core/`로 병합. ABC 인터페이스 대신 직접 구현.

```
Gateway는 프록시다. 프록시의 미덕은 투명성과 속도다.
계층이 아니라 관심사(auth, proxy, logging)로 분리한다.
```

### 2.2 성능 우선 원칙

- 인증 데이터는 startup 시 메모리 캐싱 (매 요청 파일 I/O 금지)
- httpx 공유 connection pool (매 요청 client 생성 금지)
- 스트리밍은 chunk를 그대로 전달 (불필요한 파싱 최소화)

### 2.3 자원 안전 원칙

- 모든 스트리밍 경로에 `try-finally` 자원 해제
- 클라이언트 중단(Broken Pipe) 시 upstream 연결 즉시 정리
- upstream 사망 시 적절한 에러 응답 + 로깅

## 3. 시스템 아키텍처

```text
External Client (Antigravity IDE / VS Code Extension / curl)
  |
  | HTTP (Bearer API Key)
  v
┌─────────────────────────────────────────────┐
│  API Gateway (services/gateway)              │
│                                              │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐ │
│  │ Auth     │→ │ Proxy     │→ │ Logging  │ │
│  │ (deps.py)│  │ (proxy.py)│  │(logging) │ │
│  └──────────┘  └───────────┘  └──────────┘ │
│                      │                       │
│              ┌───────┴────────┐              │
│              │ Model Router   │              │
│              │  (in-memory)   │              │
│              └───────┬────────┘              │
└──────────────────────┼──────────────────────┘
                       │
          ┌────────────┼────────────┐
          v            v            v
     vLLM:8000    vLLM:8001    vLLM:800N
     (Qwen-27B)  (Qwen-9B)   (Future)
```

## 4. 모듈 구조 (압축된 Pragmatic Architecture)

```text
services/gateway/
├── pyproject.toml
├── app/
│   ├── __init__.py
│   ├── main.py               # FastAPI app factory + lifespan
│   ├── config.py              # GatewayConfig (pydantic-settings + YAML)
│   ├── models.py              # User, ModelRoute, UsageLog (dataclass)
│   ├── deps.py                # 의존성 주입 (get_user, get_http_client)
│   ├── auth.py                # 인증 로직 (startup 시 메모리 캐싱)
│   ├── proxy.py               # 프록시 핵심 로직 (일반 + 스트리밍)
│   ├── router.py              # 모델 라우팅 (name → upstream URL)
│   ├── logging.py             # structlog 기반 사용량 로깅
│   └── routes/
│       ├── __init__.py
│       ├── health.py          # GET /health
│       └── v1.py              # /v1/** 프록시 라우트
├── tests/
│   ├── __init__.py
│   ├── conftest.py            # fixtures: test client, mock config
│   ├── test_auth.py
│   ├── test_proxy.py
│   ├── test_router.py
│   ├── test_health.py
│   └── test_streaming.py
└── gateway.yaml.example       # 설정 파일 예시
```

**이전 대비 변경**: 17개 파일 → 12개 파일. domain/ application/ infrastructure/ 3개 디렉토리 제거.
관심사(auth, proxy, logging, router)별 단일 모듈로 분리하되 불필요한 ABC/인터페이스 없음.

## 5. 인터페이스 설계

### 5.1 API 엔드포인트

| Method | Path | 설명 | 인증 |
|--------|------|------|------|
| GET | `/health` | Gateway + upstream 상태 | 없음 |
| GET | `/v1/models` | 사용 가능한 모델 목록 | 필요 |
| POST | `/v1/chat/completions` | Chat completion 프록시 (일반/스트리밍) | 필요 |
| ANY | `/v1/{path:path}` | 기타 OpenAI 호환 API catch-all 프록시 | 필요 |

### 5.2 인증 흐름 (메모리 캐싱)

```text
[Startup]
  gateway.yaml 로딩 → users 목록 → {api_key_hash: User} dict로 메모리 캐싱

[매 요청]
  Request → Authorization Header 추출
         → "Bearer " prefix 제거
         → SHA-256(api_key) 계산
         → in-memory dict 조회 (O(1))
         → User 반환 또는 403 Forbidden
         → request.state.user에 저장
```

파일 I/O 없음. dict lookup만 수행하므로 인증 오버헤드 최소화.

### 5.3 프록시 흐름 (일반 요청)

```text
Request → Auth 통과
       → body에서 model 추출
       → ModelRouter.resolve(model) → target upstream URL
       → httpx_client.request(method, target_url, content, headers)
       → Response 반환
       → log_usage(user, request_meta, response_meta, latency)
```

### 5.4 프록시 흐름 (스트리밍 + 자원 안전)

```text
POST /v1/chat/completions (stream: true)
  → Auth 통과
  → ModelRouter.resolve(model) → target upstream URL
  → StreamingResponse(stream_generator(...))

stream_generator():
  start_time = now()
  ttft = None
  try:
      async with httpx_client.stream("POST", url, ...) as upstream:
          async for chunk in upstream.aiter_bytes():
              if ttft is None:
                  ttft = now() - start_time
              yield chunk
  except httpx.RemoteProtocolError:
      # upstream이 중간에 죽은 경우
      log.warning("upstream_disconnected", ...)
  except anyio.get_cancelled_exc_class():
      # 클라이언트가 연결을 끊은 경우 (Broken Pipe)
      log.info("client_disconnected", ...)
  finally:
      # 어떤 경우든 사용량 로깅 수행
      log_usage(user, request_meta, latency, ttft, is_stream=True)
```

핵심: `try-finally`로 upstream 연결 정리와 로깅을 보장.
`async with`가 upstream httpx 응답의 소켓을 자동 해제.
클라이언트 중단 시 `anyio.get_cancelled_exc_class()`로 캐치하여 자원 누수 방지.

### 5.5 모델 라우팅

설정 파일 (`gateway.yaml`) 기반:

```yaml
server:
  host: "0.0.0.0"
  port: 8080

auth:
  users:
    - api_key_hash: "sha256:abc123..."  # 해시 저장
      user_id: "admin_01"
      name: "관리자"
      org: "MyAiCoder Team"
      role: "admin"
    - api_key_hash: "sha256:def456..."
      user_id: "user_01"
      name: "사용자1"
      org: "External"
      role: "user"

models:
  default: "qwen3.5-27b"
  routes:
    - name: "qwen3.5-27b"
      upstream: "http://localhost:8000/v1"
      description: "Qwen 3.5 27B (Main)"
    - name: "qwen3.5-9b"
      upstream: "http://localhost:8001/v1"
      description: "Qwen 3.5 9B (Fast)"

logging:
  level: "INFO"
  format: "json"
```

### 5.6 모델 라우팅 로직

```python
class ModelRouter:
    """Startup 시 config에서 route table을 메모리에 구축"""

    def __init__(self, config: ModelsConfig):
        self._routes: dict[str, str] = {r.name: r.upstream for r in config.routes}
        self._default = config.routes[0].upstream  # default 모델의 upstream
        self._models = config.routes

    def resolve(self, model_name: str | None) -> str:
        if not model_name:
            return self._default
        return self._routes.get(model_name, self._default)

    def list_models(self) -> list[dict]:
        return [{"id": r.name, "object": "model", "owned_by": "local"} for r in self._models]
```

## 6. 데이터 모델

```python
@dataclass(frozen=True, slots=True)
class User:
    user_id: str
    name: str
    org: str
    role: str  # "admin" | "user"

@dataclass(frozen=True, slots=True)
class ModelRoute:
    name: str
    upstream: str
    description: str = ""
```

`frozen=True, slots=True`로 불변성 + 메모리 효율.
UsageLog는 별도 dataclass 없이 structlog에 dict로 직접 기록 (pass-through 철학).

## 7. 보안 설계

| 항목 | 설계 |
|------|------|
| API Key 저장 | SHA-256 해시로 저장, 평문 금지 |
| 인증 검증 | 입력 키를 SHA-256 해시 후 메모리 dict 조회 |
| 로그 마스킹 | API Key는 앞 8자만 노출 (`abc12345****`) |
| upstream 통신 | 내부 네트워크, 별도 인증 불필요 (vLLM 기본) |
| CORS | 초기에는 비활성, 필요 시 설정으로 활성화 |

## 8. httpx Client 관리

```python
# app/main.py lifespan에서 관리
@asynccontextmanager
async def lifespan(app: FastAPI):
    client = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=5.0, read=None, write=5.0, pool=5.0),
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    )
    app.state.http_client = client
    yield
    await client.aclose()
```

별도 Manager 클래스 불필요. lifespan context manager에서 직접 관리.
- read timeout 무제한: 스트리밍 응답이 수분 지속 가능
- connection pool: 최대 100개 동시 연결, keepalive 20개

## 9. 테스트 전략

### 9.1 테스트 파일 구성

| 파일 | 대상 | 핵심 검증 |
|------|------|----------|
| `test_auth.py` | 인증 로직 | 유효 키 성공, 무효 키 403, 키 없음 403, 해시 검증 |
| `test_router.py` | 모델 라우팅 | 기본 모델, 명시적 모델, 미존재 모델 fallback |
| `test_health.py` | Health endpoint | 200 OK |
| `test_proxy.py` | 일반 프록시 | Auth → Proxy → Response (mock upstream) |
| `test_streaming.py` | 스트리밍 프록시 | SSE chunk 전달, TTFT 측정, 중단 처리 |

### 9.2 실행 기준

```bash
cd services/gateway
uv run pytest tests -q
```

## 10. CI 확장

기존 `ci.yml`에 job 추가:

```yaml
gateway-tests:
  name: Gateway Tests
  runs-on: ubuntu-latest
  defaults:
    run:
      working-directory: services/gateway
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: "3.12"
    - uses: astral-sh/setup-uv@v5
    - run: uv sync --frozen --extra dev
    - run: uv run ruff check .
    - run: uv run pytest tests -q
```

## 11. 구현 순서

| 순서 | 항목 | 의존 |
|------|------|------|
| 1 | `pyproject.toml` + 디렉토리 구조 | 없음 |
| 2 | `models.py` (User, ModelRoute) | 없음 |
| 3 | `config.py` (GatewayConfig + YAML 로딩) | models |
| 4 | `auth.py` (메모리 캐싱 인증) | models, config |
| 5 | `router.py` (모델 라우팅) | models, config |
| 6 | `proxy.py` (일반 + 스트리밍 + try-finally) | router |
| 7 | `logging.py` (structlog 사용량 로깅) | models |
| 8 | `deps.py` (의존성 주입) | auth |
| 9 | `routes/health.py` + `routes/v1.py` | proxy, deps, logging |
| 10 | `main.py` (app factory + lifespan) | 전체 |
| 11 | 테스트 작성 | 전체 |
| 12 | CI 워크플로 확장 | 11 완료 |
| 13 | `gateway.yaml.example` | 전체 |

## 12. sungjunCode 대비 개선 사항

| 항목 | sungjunCode | 이번 설계 |
|------|-------------|----------|
| 아키텍처 | 단일 파일 | 관심사별 모듈 분리 (과도한 계층 없음) |
| 인증 성능 | 매 요청 파일 I/O | startup 시 메모리 캐싱 (O(1) lookup) |
| 사용자 저장소 | JSON 평문 | YAML + API Key SHA-256 해시 |
| HTTP 클라이언트 | 매 요청 생성 | 공유 pool (lifespan) |
| 에러 핸들링 | bare except | 명시적 예외 + try-finally 자원 해제 |
| 스트리밍 안전성 | 자원 해제 없음 | Broken Pipe/upstream 사망 시 즉시 정리 |
| 모델 지원 | 단일 vLLM | config 기반 다중 모델 라우팅 |
| 로깅 | logging + 파일 | structlog JSON |
| 테스트 | 없음 | pytest + httpx.AsyncClient |

## 13. Check 단계에서 확인할 항목

- 스트리밍 프록시가 SSE 프로토콜을 정확히 전달하는가
- 클라이언트 중단 시 자원이 즉시 해제되는가 (메모리 누수 없음)
- API Key 해시 검증이 올바르게 동작하는가
- 인증이 메모리에서 수행되고 파일 I/O가 없는가
- 모델 라우팅이 config에 정의된 대로 분기하는가
- httpx client가 lifespan에서 정상 생성/종료되는가
- 로그에 API Key 전체가 노출되지 않는가
- 테스트가 외부 vLLM 서버 없이 독립 실행되는가
