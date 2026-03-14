# Design: observability

## 참조 문서
- Plan: `docs/pdca/01-plan/features/observability.plan.md`
- Gateway 코드: `services/gateway/app/`

---

## 1. 설계 개요

Gateway에 Prometheus 메트릭 계측 + Grafana 대시보드를 추가.
**핵심 원칙**: SSE 스트리밍 특성을 고려하여 미들웨어/프록시 계측 위치를 분리.

### 변경 파일 목록

| # | 파일 | 작업 | 설계 항목 |
|---|------|------|----------|
| D1 | `services/gateway/app/metrics.py` | 신규 | 메트릭 정의 모듈 |
| D2 | `services/gateway/app/proxy.py` | 수정 | 스트리밍 계측 (latency, TTFT, tokens) |
| D3 | `services/gateway/app/routes/metrics.py` | 신규 | GET /metrics 엔드포인트 |
| D4 | `services/gateway/app/main.py` | 수정 | 미들웨어 추가, 라우터 등록 |
| D5 | `services/gateway/app/logging.py` | 수정 | 요청 상관 ID (request_id) |
| D6 | `services/gateway/pyproject.toml` | 수정 | prometheus-client 의존성 |
| D7 | `config/prometheus.yml` | 신규 | Prometheus 스크레이핑 설정 |
| D8 | `config/grafana/` | 신규 | Grafana provisioning + 대시보드 JSON |
| D9 | `docker-compose.yml` | 수정 | Prometheus + Grafana 서비스 추가 |

---

## 2. D1: metrics.py — 메트릭 정의 모듈

### 파일: `services/gateway/app/metrics.py`

```python
"""Prometheus metrics definitions for Gateway observability."""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ── Request metrics (미들웨어에서 계측) ──
REQUEST_COUNT = Counter(
    "gateway_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
ACTIVE_REQUESTS = Gauge(
    "gateway_active_requests",
    "Currently active requests",
)

# ── Streaming metrics (proxy.py에서 계측) ──
REQUEST_LATENCY = Histogram(
    "gateway_request_latency_seconds",
    "Total request duration (stream completion included)",
    ["method", "path", "is_stream"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0],
)
TTFT = Histogram(
    "gateway_ttft_seconds",
    "Time to first token (streaming only)",
    ["model"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 30.0],
)
TOKENS_TOTAL = Counter(
    "gateway_tokens_total",
    "Token usage",
    ["model", "type"],  # type: prompt / completion
)

# ── Error metrics ──
ERROR_COUNT = Counter(
    "gateway_errors_total",
    "Total errors by type",
    ["type"],  # upstream_unreachable, upstream_disconnected, client_disconnected, rate_limited
)
```

### 설계 결정

| 결정 | 이유 |
|------|------|
| Histogram buckets 커스텀 | LLM 응답은 수십 초 가능, 기본 buckets 부적합 |
| TTFT 버킷에 20.0, 30.0 추가 | 로컬 LLM 콜드 스타트 시 TTFT 10초+ 가능 (이상치 모니터링) |
| `is_stream` label | 스트리밍/비스트리밍 latency 분포가 매우 다름 |
| `type` label on tokens | prompt vs completion 분리 → 비용 분석 |
| label 최소화 | cardinality 폭증 방지 (user_id는 label에 넣지 않음) |

---

## 3. D2: proxy.py 수정 — SSE 스트리밍 계측

### 핵심: 계측 위치 = proxy finally 블록

기존 `proxy.py`의 `stream_upstream()` finally 블록에 이미 `latency`, `ttft` 측정이 있음.
여기에 Prometheus 메트릭 업데이트를 추가.

### stream_upstream 변경사항

```python
# 기존 코드 (유지)
async def stream_upstream(...) -> AsyncIterator[bytes]:
    start = time.monotonic()
    ttft: float | None = None
    model_name = _extract_model(body)
    # ...
    status_code = 200
+   prompt_tokens = 0
+   completion_tokens = 0

    try:
        async with http_client.stream(...) as upstream_resp:
            status_code = upstream_resp.status_code
            async for chunk in upstream_resp.aiter_bytes():
                if ttft is None:
                    ttft = time.monotonic() - start
+               # usage 파싱: 마지막 청크에서 토큰 수 추출
+               prompt_tokens, completion_tokens = _try_parse_usage(
+                   chunk, prompt_tokens, completion_tokens
+               )
                yield chunk
    except ...:
        # (기존 에러 핸들링 유지)
    finally:
        latency = time.monotonic() - start
+       # ── Prometheus 계측 (스트림 완료 시점) ──
+       from .metrics import REQUEST_LATENCY, TTFT, TOKENS_TOTAL, ERROR_COUNT
+       REQUEST_LATENCY.labels(method="POST", path=path, is_stream="true").observe(latency)
+       if ttft is not None:
+           TTFT.labels(model=model_name or "unknown").observe(ttft)
+       if prompt_tokens > 0:
+           TOKENS_TOTAL.labels(model=model_name or "unknown", type="prompt").inc(prompt_tokens)
+       if completion_tokens > 0:
+           TOKENS_TOTAL.labels(model=model_name or "unknown", type="completion").inc(completion_tokens)
+       if status_code >= 500:
+           ERROR_COUNT.labels(type="upstream_error").inc()

        # 기존 log_usage 호출 유지
        log_usage(...)
```

### forward_request 변경사항 (비스트리밍)

```python
async def forward_request(...) -> httpx.Response:
    start = time.monotonic()
    # ...
    finally:
        latency = time.monotonic() - start
+       from .metrics import REQUEST_LATENCY, TOKENS_TOTAL, ERROR_COUNT
+       REQUEST_LATENCY.labels(method=method, path=path, is_stream="false").observe(latency)
+       # 비스트리밍: 응답 body에서 usage 파싱
+       if "resp" in dir():
+           _record_usage_from_response(resp, model_name)
+       if (resp.status_code if "resp" in dir() else 502) >= 500:
+           ERROR_COUNT.labels(type="upstream_error").inc()
        log_usage(...)
```

### 신규 헬퍼 함수

```python
def _try_parse_usage(
    chunk: bytes, prev_prompt: int, prev_completion: int
) -> tuple[int, int]:
    """SSE 청크에서 usage 필드를 best-effort 파싱.

    OpenAI-compatible API는 마지막 청크(또는 [DONE] 직전)에
    usage: {prompt_tokens, completion_tokens} 를 포함.
    """
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
    """비스트리밍 응답 body에서 usage 추출하여 메트릭 기록."""
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
```

### 검증 기준
- 스트리밍 요청 후 /metrics에 `gateway_ttft_seconds`, `gateway_tokens_total` 증가
- 비스트리밍 요청 후 /metrics에 `gateway_request_latency_seconds` 기록
- 기존 log_usage 로그 출력 변함없음

---

## 4. D3: /metrics 엔드포인트

### 파일: `services/gateway/app/routes/metrics.py`

```python
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

router = APIRouter()


@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics() -> PlainTextResponse:
    """Expose Prometheus metrics. No auth required for scraping."""
    return PlainTextResponse(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
```

### 검증 기준
- `curl localhost:8080/metrics` → Prometheus text format 응답
- 인증 불필요 (Prometheus scraper 접근)

---

## 5. D4: main.py 수정

### 변경사항

```python
# 기존 import에 추가
from .routes.metrics import router as metrics_router

def create_app(...) -> FastAPI:
    # ...

+   # Metrics middleware (request count + active requests)
+   @app.middleware("http")
+   async def metrics_middleware(request: Request, call_next):
+       import uuid
+       import structlog
+       from .metrics import REQUEST_COUNT, ACTIVE_REQUESTS
+
+       # ⚠️ 디테일 A: 이전 요청의 contextvars 잔류 방지 (필수)
+       # FastAPI ContextVars 특성상 clear 없이 bind하면 이전 요청 ID가 섞임
+       structlog.contextvars.clear_contextvars()
+       request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
+       request.state.request_id = request_id
+       structlog.contextvars.bind_contextvars(request_id=request_id)
+
+       ACTIVE_REQUESTS.inc()
+       try:
+           response = await call_next(request)
+           return response
+       finally:
+           ACTIVE_REQUESTS.dec()
+           path = request.url.path
+           method = request.method
+           status = str(response.status_code) if "response" in dir() else "500"
+           REQUEST_COUNT.labels(method=method, path=path, status=status).inc()

    app.add_middleware(RateLimitHeaderMiddleware)

    app.include_router(health_router)
    app.include_router(internal_router)
+   app.include_router(metrics_router)
    app.include_router(v1_router)

    return app
```

### 미들웨어 순서

```
요청 → metrics_middleware (count + active) → RateLimitHeaderMiddleware → route handler
```

### 주의: REQUEST_COUNT는 미들웨어에서, REQUEST_LATENCY는 proxy에서

| 메트릭 | 위치 | 이유 |
|--------|------|------|
| REQUEST_COUNT | 미들웨어 | 모든 요청 (스트리밍/비스트리밍) 카운트 |
| ACTIVE_REQUESTS | 미들웨어 | 동시 접속 추적 |
| REQUEST_LATENCY | proxy.py | **SSE 완료 시점** 측정 필수 |
| TTFT, TOKENS | proxy.py | 스트림 내부에서만 접근 가능 |

### 검증 기준
- /metrics에 `gateway_requests_total`, `gateway_active_requests` 노출
- /health, /v1/models 요청 시 request_count 증가

---

## 6. D5: logging.py 수정 — 요청 상관 ID

### 변경사항

```python
# log_usage() 시그니처에 request_id 추가
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
+   request_id: str = "",
) -> None:
    logger.info(
        "request_completed",
        # ... 기존 필드 유지
+       request_id=request_id,
    )
```

### 요청 ID 생성 위치: D4 metrics_middleware

요청 ID 생성은 D4의 `metrics_middleware` 최상단에서 수행 (위 D4 참조).

**⚠️ 필수**: `clear_contextvars()` → `bind_contextvars(request_id=...)` 순서.
clear 없이 bind하면 asyncio ContextVars 특성상 이전 요청 ID가 잔류하여 로그가 오염됨.

### 검증 기준
- 모든 로그에 `request_id` 필드 포함
- X-Request-ID 헤더 전달 시 해당 ID 사용
- 미전달 시 자동 생성 (8자리 UUID)

---

## 7. D6: pyproject.toml 수정

```toml
dependencies = [
    # ... 기존 유지
    "prometheus-client>=0.21.0",
]
```

### 검증 기준
- `uv sync` 성공
- `python -c "import prometheus_client"` 에러 없음

---

## 8. D7: Prometheus 설정

### 파일: `config/prometheus.yml`

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: "gateway"
    static_configs:
      - targets: ["host.docker.internal:8080"]
    metrics_path: /metrics
    scrape_interval: 10s
```

### 검증 기준
- Prometheus UI (localhost:9090) → Targets → gateway UP

---

## 9. D8: Grafana 대시보드

### 디렉토리 구조

```
config/grafana/
├── provisioning/
│   ├── datasources/
│   │   └── prometheus.yml       ← Prometheus 데이터소스 자동 등록
│   └── dashboards/
│       └── dashboards.yml       ← 대시보드 프로비저닝 설정
└── dashboards/
    └── gateway.json             ← 메인 대시보드 (6개 패널)
```

### provisioning/datasources/prometheus.yml

```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
```

### provisioning/dashboards/dashboards.yml

```yaml
apiVersion: 1
providers:
  - name: "default"
    folder: ""
    type: file
    options:
      path: /var/lib/grafana/dashboards
```

### 대시보드 패널 (6개)

| # | 패널 | PromQL | 유형 |
|---|------|--------|------|
| 1 | Request Rate | `rate(gateway_requests_total[5m])` | Time series |
| 2 | Latency p50/p95 | `histogram_quantile(0.95, rate(gateway_request_latency_seconds_bucket[5m]))` | Time series |
| 3 | TTFT p50/p95 | `histogram_quantile(0.95, rate(gateway_ttft_seconds_bucket[5m]))` | Time series |
| 4 | Error Rate | `rate(gateway_errors_total[5m]) / rate(gateway_requests_total[5m])` | Stat |
| 5 | Token Usage | `rate(gateway_tokens_total[5m])` | Time series (by model, type) |
| 6 | Active Requests | `gateway_active_requests` | Gauge |

### 검증 기준
- Grafana (localhost:3000) → Dashboard → "Gateway" → 6개 패널 표시
- 기본 계정: admin/admin

---

## 10. D9: docker-compose.yml 수정

### 추가할 서비스

```yaml
  prometheus:
    image: prom/prometheus:v2.51.0
    ports:
      - "${PROMETHEUS_PORT:-9090}:9090"
    volumes:
      - ./config/prometheus.yml:/etc/prometheus/prometheus.yml:ro
    extra_hosts:
      - "host.docker.internal:host-gateway"

  grafana:
    image: grafana/grafana:10.4.0
    ports:
      - "${GRAFANA_PORT:-3000}:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD:-admin}
      - GF_USERS_ALLOW_SIGN_UP=false
    volumes:
      - ./config/grafana/provisioning:/etc/grafana/provisioning:ro
      - ./config/grafana/dashboards:/var/lib/grafana/dashboards:ro
      - grafana_data:/var/lib/grafana
    depends_on:
      - prometheus
```

### volumes 추가

```yaml
volumes:
  postgres_data:
  grafana_data:
```

### 설계 결정

| 결정 | 이유 |
|------|------|
| `host.docker.internal` | Gateway는 로컬에서 실행, Docker 내부에서 접근 |
| 환경변수 포트 | 포트 충돌 방지 |
| `:ro` 마운트 | config 파일 보호 |
| `grafana_data` volume | 대시보드 커스터마이징 영속화 |

### 검증 기준
- `docker compose up prometheus grafana` → 두 서비스 정상 기동
- Prometheus targets UP, Grafana 대시보드 렌더링

---

## 11. 구현 순서

```
S1.  pyproject.toml에 prometheus-client 추가         [D6]
S2.  app/metrics.py 생성 (메트릭 정의)                [D1]
S3.  app/routes/metrics.py 생성 (/metrics 엔드포인트)  [D3]
S4.  app/main.py 수정 (미들웨어 + 라우터 등록)         [D4]
S5.  app/proxy.py 수정 (스트리밍 계측 + usage 파싱)     [D2]
S6.  app/logging.py 수정 (request_id 추가)             [D5]
S7.  Gateway 테스트 통과 확인                          [43 passed]
S8.  config/prometheus.yml 생성                        [D7]
S9.  config/grafana/ 생성 (provisioning + dashboard)   [D8]
S10. docker-compose.yml 수정                           [D9]
S11. Prometheus + Grafana 기동 테스트                   [D9 검증]
```

## 12. 검증 매트릭스

| 설계 항목 | 검증 명령 | 성공 기준 |
|----------|----------|----------|
| D1 metrics.py | `python -c "from app.metrics import REQUEST_COUNT"` | import 성공 |
| D2 proxy 계측 | 스트리밍 요청 후 `/metrics` 확인 | TTFT, tokens 기록 |
| D3 /metrics | `curl localhost:8080/metrics` | Prometheus 형식 응답 |
| D4 미들웨어 | 아무 요청 후 `/metrics` 확인 | request_count 증가 |
| D5 request_id | 로그 출력 확인 | request_id 필드 존재 |
| D6 의존성 | `uv sync && python -c "import prometheus_client"` | 에러 없음 |
| D7 Prometheus | `docker compose up prometheus` + UI | Target UP |
| D8 Grafana | `docker compose up grafana` + UI | 6개 패널 렌더링 |
| D9 docker-compose | `docker compose up -d prometheus grafana` | 두 서비스 healthy |
| 전체 | `cd services/gateway && uv run pytest tests -q` | 43 passed |
| 전체 | `cd services/myaicoder && uv run pytest tests -q` | 178 passed |
