# Plan: observability

## Feature 정보

| 항목 | 내용 |
|------|------|
| Feature | observability |
| Track | C-1 (엔터프라이즈 운영 및 최적화) |
| 우선순위 | 중간 |
| 의존 | gateway (structlog 기반), rate-limiting (헤더 메트릭) |
| 로드맵 | docs/roadmap-2026-03.md |

## 1. 목적

Gateway 트래픽, LLM 응답 시간, 토큰 사용량, 에러율을 정량적으로 모니터링하여 운영 가시성을 확보한다.

### 배경

- Gateway: structlog 기반 구조적 로깅 있음 (latency_sec, ttft_sec, status_code 기록)
- myaicoder: Rich UI 출력만 있음, 구조적 로깅 없음, 도메인 레이어 로깅 0건
- **메트릭 수집 없음**: Prometheus/OpenTelemetry 미통합
- **토큰 사용량**: UI 표시만, 영속화/내보내기 없음
- **상관 관계**: 요청 ID / 트레이스 ID 없이 Gateway↔LLM 연결 추적 불가

## 2. 현재 상태 분석

### 2.1 이미 있는 것

| 항목 | 상태 | 위치 |
|------|------|------|
| Gateway structlog | JSON/console 전환 가능 | app/logging.py, app/main.py |
| 사용량 로깅 | log_usage() (latency, ttft, model, user) | app/logging.py |
| 헬스체크 | GET /health | app/routes/health.py |
| Rate-limit 헤더 | X-RateLimit-* (transient) | app/middleware.py |
| config/gateway.yaml | logging.level, logging.format | config/ |
| Rich UI 출력 | 토큰 사용량, 연결 상태 표시 | myaicoder ui/chat.py |

### 2.2 없는 것

| 항목 | 필요 이유 | 복잡도 |
|------|----------|--------|
| myaicoder structlog 통일 | Gateway와 로깅 형식 일치 | 중 |
| Prometheus 메트릭 엔드포인트 | 정량적 모니터링 | 중 |
| 핵심 메트릭 계측 | TTFT, 토큰/초, 에러율, 요청 수 | 중 |
| 요청 상관 ID | Gateway↔LLM 추적 | 낮 |
| Grafana 대시보드 | 시각화 | 중 |
| docker-compose 확장 | Prometheus + Grafana 컨테이너 | 낮 |
| 토큰 사용량 메트릭 | 사용량 추적 및 알림 | 중 |

## 3. 요구사항

### 3.1 필수 요구사항 (P0)

| ID | 요구사항 | 검증 기준 |
|----|----------|----------|
| R1 | Gateway Prometheus 메트릭 엔드포인트 | GET /metrics 응답, prometheus 형식 |
| R2 | 핵심 메트릭 4종 계측 | request_count, request_latency, ttft, error_count |
| R3 | 토큰 사용량 메트릭 | tokens_total (prompt + completion) Counter |
| R4 | 요청 상관 ID (X-Request-ID) | 모든 로그에 request_id 포함 |
| R5 | docker-compose에 Prometheus + Grafana | 컨테이너 정상 기동, 메트릭 스크레이핑 |
| R6 | Grafana 기본 대시보드 (JSON provisioning) | 4종 메트릭 패널 표시 |
| R7 | 기존 테스트 통과 (241개) | 0 regression |

### 3.2 권장 요구사항 (P1)

| ID | 요구사항 | 검증 기준 |
|----|----------|----------|
| R8 | myaicoder structlog 통일 | core/ 레이어에 구조적 로깅 추가 |
| R9 | GPU 메모리 메트릭 | nvidia-smi 기반 수집 |

### 3.3 이연 항목 (P2)

| ID | 요구사항 | 이유 |
|----|----------|------|
| R10 | OpenTelemetry 분산 트레이싱 | 단일 인스턴스에서 과도, 다중 서비스 시 필요 |
| R11 | 알림 (Alertmanager) | 먼저 메트릭 안정화 후 |
| R12 | 로그 집계 (Loki) | 현재 stdout 로깅으로 충분 |

## 4. 구현 범위

### 4.1 Gateway 메트릭 계측

```python
# 핵심 메트릭 4종 + 토큰
from prometheus_client import Counter, Histogram, Gauge

REQUEST_COUNT = Counter("gateway_requests_total", "Total requests", ["method", "path", "status"])
REQUEST_LATENCY = Histogram("gateway_request_latency_seconds", "Request latency", ["method", "path"])
TTFT = Histogram("gateway_ttft_seconds", "Time to first token", ["model"],
                 buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 30.0])
ERROR_COUNT = Counter("gateway_errors_total", "Total errors", ["type"])
TOKENS_TOTAL = Counter("gateway_tokens_total", "Token usage", ["model", "type"])  # type: prompt/completion
ACTIVE_REQUESTS = Gauge("gateway_active_requests", "Active requests")
```

#### ⚠️ SSE 스트리밍 계측 주의사항

myAiCoder의 핵심은 SSE 스트리밍이므로 메트릭 측정 시점에 주의가 필요:

**문제**: 미들웨어 레벨에서 latency를 측정하면 "HTTP 200 반환 시점" = "첫 청크 전송 시점"만 기록됨.
실제 응답 완료 시간과 토큰 사용량(마지막 청크 [DONE] 직전에 포함)은 미들웨어에서 알 수 없음.

**계측 위치 분리**:

| 메트릭 | 측정 위치 | 이유 |
|--------|----------|------|
| REQUEST_COUNT | 미들웨어 | 요청 수는 진입 시점에서 카운트 가능 |
| ACTIVE_REQUESTS | 미들웨어 | inc/dec으로 동시 요청 추적 |
| ERROR_COUNT | 미들웨어 + proxy | 미들웨어(4xx), proxy(upstream 에러) |
| **REQUEST_LATENCY** | **proxy.py finally 블록** | 스트림 완료 시점에서 총 소요시간 측정 |
| **TTFT** | **proxy.py 첫 청크 yield 시점** | 첫 토큰까지의 시간 (기존 ttft_sec 활용) |
| **TOKENS_TOTAL** | **proxy.py finally 블록** | 마지막 청크에서 usage 파싱 후 기록 |

```python
# app/proxy.py 스트리밍 제너레이터 내부 (개념)
async def _stream_response(upstream_resp, model):
    start = time.monotonic()
    first_chunk = True
    try:
        async for chunk in upstream_resp.aiter_lines():
            if first_chunk:
                TTFT.labels(model=model).observe(time.monotonic() - start)
                first_chunk = False
            # ... usage 파싱 (마지막 청크)
            yield chunk
    finally:
        REQUEST_LATENCY.labels(...).observe(time.monotonic() - start)
        TOKENS_TOTAL.labels(model=model, type="prompt").inc(prompt_tokens)
        TOKENS_TOTAL.labels(model=model, type="completion").inc(completion_tokens)
```

### 4.2 요청 상관 ID

```
Client → Gateway (X-Request-ID 생성) → LLM Server
                  ↓
         structlog에 request_id bind
                  ↓
         모든 로그에 request_id 포함
```

### 4.3 Prometheus + Grafana 스택

```yaml
# docker-compose.yml 추가
services:
  prometheus:
    image: prom/prometheus:v2.51.0
    ports: ["9090:9090"]
    volumes: ["./config/prometheus.yml:/etc/prometheus/prometheus.yml"]

  grafana:
    image: grafana/grafana:10.4.0
    ports: ["3000:3000"]
    volumes:
      - "./config/grafana/provisioning:/etc/grafana/provisioning"
      - "./config/grafana/dashboards:/var/lib/grafana/dashboards"
```

### 4.4 Grafana 대시보드 패널

| 패널 | 메트릭 | 유형 |
|------|--------|------|
| 요청 수 | gateway_requests_total | Counter rate |
| 응답 지연 | gateway_request_latency_seconds | Histogram p50/p95/p99 |
| TTFT | gateway_ttft_seconds | Histogram p50/p95 |
| 에러율 | gateway_errors_total / gateway_requests_total | Ratio |
| 토큰 사용량 | gateway_tokens_total | Counter rate by model |
| 활성 요청 | gateway_active_requests | Gauge |

## 5. 구현 순서

| 단계 | 작업 | 산출물 |
|------|------|--------|
| S1 | prometheus-client 의존성 추가 | pyproject.toml |
| S2 | 메트릭 정의 모듈 생성 | app/metrics.py |
| S3 | /metrics 엔드포인트 추가 | app/routes/metrics.py |
| S4 | 미들웨어에 계측 추가 | app/middleware.py (request_count, active_requests, 비스트리밍 latency) |
| S5 | **프록시에 스트리밍 계측** | **app/proxy.py finally 블록 (latency, TTFT, tokens)** — SSE 완료 시점 측정 |
| S6 | 요청 상관 ID 추가 | app/middleware.py (X-Request-ID) |
| S7 | Prometheus 설정 파일 | config/prometheus.yml |
| S8 | Grafana 대시보드 JSON | config/grafana/dashboards/gateway.json |
| S9 | Grafana provisioning | config/grafana/provisioning/ |
| S10 | docker-compose 확장 | docker-compose.yml |
| S11 | 기존 테스트 통과 확인 | 241 passed 유지 |

## 6. 리스크

| 리스크 | 영향 | 대응 |
|--------|------|------|
| prometheus-client 메모리 | 메트릭 cardinality 폭증 | label 최소화 (method, path, status만) |
| /metrics 응답 지연 | Gateway 성능 영향 | 별도 스레드 서빙 (default) |
| docker-compose 포트 충돌 | 9090, 3000 사용 중일 수 있음 | 환경변수로 포트 설정 가능하게 |
| 기존 테스트 호환성 | 메트릭 미들웨어가 테스트 깨뜨릴 수 있음 | 메트릭을 선택적 의존성으로 처리 |

## 7. 성공 기준

| 기준 | 측정 방법 |
|------|----------|
| GET /metrics 정상 응답 | curl localhost:8080/metrics |
| 4종 핵심 메트릭 노출 | /metrics 출력에 gateway_requests_total 등 포함 |
| Prometheus 스크레이핑 | Prometheus UI에서 타겟 UP 확인 |
| Grafana 대시보드 렌더링 | 6개 패널 데이터 표시 |
| 요청 ID 상관 | 로그에 request_id 필드 존재 |
| 기존 테스트 241개 통과 | pytest + vitest 전체 실행 |
| Gateway 성능 영향 < 5% | 계측 전후 latency 비교 |
