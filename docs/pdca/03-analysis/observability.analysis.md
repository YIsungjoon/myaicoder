# observability Analysis Report

> **Analysis Type**: Gap Analysis (Design vs Implementation)
>
> **Project**: myAiCoder
> **Version**: 0.1.0
> **Analyst**: gap-detector
> **Date**: 2026-03-14
> **Design Doc**: [observability.design.md](../02-design/features/observability.design.md)

---

## 1. Analysis Overview

### 1.1 Analysis Purpose

observability 기능(Prometheus 메트릭 계측 + Grafana 대시보드)의 설계 문서 대비 구현 일치율을 검증한다.
설계 항목 D1~D9 전체를 대상으로 하며, 기존 테스트 통과 여부도 확인한다.

### 1.2 Analysis Scope

- **Design Document**: `docs/pdca/02-design/features/observability.design.md`
- **Implementation Path**: `services/gateway/app/`, `config/`, `docker-compose.yml`
- **Analysis Date**: 2026-03-14

---

## 2. Gap Analysis (Design vs Implementation)

### 2.1 설계 항목별 비교 (D1-D9)

| # | 설계 항목 | 파일 | Status | 비고 |
|---|----------|------|:------:|------|
| D1 | metrics.py -- 6 메트릭 정의 | `services/gateway/app/metrics.py` | ✅ | 6개 메트릭, labels, buckets 완전 일치 |
| D2 | proxy.py -- 스트리밍 계측 | `services/gateway/app/proxy.py` | ✅ | finally 블록 계측, _try_parse_usage, _record_usage_from_response |
| D3 | routes/metrics.py -- GET /metrics | `services/gateway/app/routes/metrics.py` | ✅ | 엔드포인트, 인증 없음, PlainTextResponse |
| D4 | main.py -- metrics_middleware | `services/gateway/app/main.py` | ✅ | clear_contextvars, request_id, ACTIVE_REQUESTS, REQUEST_COUNT |
| D5 | logging.py -- request_id 추가 | `services/gateway/app/logging.py` | ✅ | request_id 파라미터 추가, 로그 출력 포함 |
| D6 | pyproject.toml -- prometheus-client | `services/gateway/pyproject.toml` | ✅ | `prometheus-client>=0.21.0` |
| D7 | config/prometheus.yml | `config/prometheus.yml` | ✅ | scrape 설정 완전 일치 |
| D8 | config/grafana/ -- provisioning + dashboard | `config/grafana/` | ✅ | 3개 provisioning 파일 + gateway.json (6패널) |
| D9 | docker-compose.yml -- prometheus + grafana | `docker-compose.yml` | ✅ | 두 서비스 + grafana_data volume |

### 2.2 메트릭 정의 상세 비교 (D1)

| 메트릭 | 설계 이름 | 구현 이름 | Labels | Buckets | Status |
|--------|----------|----------|--------|---------|:------:|
| REQUEST_COUNT | gateway_requests_total | gateway_requests_total | method, path, status | - | ✅ |
| ACTIVE_REQUESTS | gateway_active_requests | gateway_active_requests | - | - | ✅ |
| REQUEST_LATENCY | gateway_request_latency_seconds | gateway_request_latency_seconds | method, path, is_stream | 0.1~120.0 (10개) | ✅ |
| TTFT | gateway_ttft_seconds | gateway_ttft_seconds | model | 0.05~30.0 (10개, 20.0/30.0 포함) | ✅ |
| TOKENS_TOTAL | gateway_tokens_total | gateway_tokens_total | model, type | - | ✅ |
| ERROR_COUNT | gateway_errors_total | gateway_errors_total | type | - | ✅ |

### 2.3 Grafana 대시보드 패널 비교 (D8)

| # | 설계 패널 | 구현 패널 | PromQL | Type | Status |
|---|----------|----------|--------|------|:------:|
| 1 | Request Rate | Request Rate | rate(gateway_requests_total[5m]) | timeseries | ✅ |
| 2 | Latency p50/p95 | Latency p50/p95/p99 | histogram_quantile(...) | timeseries | ✅+ |
| 3 | TTFT p50/p95 | TTFT p50/p95 | histogram_quantile(...) | timeseries | ✅ |
| 4 | Error Rate | Error Rate | errors / requests | stat | ✅ |
| 5 | Token Usage | Token Usage Rate | rate(gateway_tokens_total[5m]) | timeseries | ✅ |
| 6 | Active Requests | Active Requests | gateway_active_requests | gauge | ✅ |

### 2.4 Match Rate Summary

```
+---------------------------------------------+
|  Overall Match Rate: 100%                    |
+---------------------------------------------+
|  Match:               9 / 9 items (100%)    |
|  Missing design:      0 items               |
|  Not implemented:     0 items               |
+---------------------------------------------+
```

---

## 3. 구현 개선 사항 (설계 대비 Enhancement)

설계에 없지만 구현에서 개선된 항목들. 이들은 Gap이 아니라 품질 향상.

| # | 항목 | 설계 | 구현 | 영향 |
|---|------|------|------|------|
| E1 | Latency 패널 p99 추가 | p50/p95 2개 | p50/p95/p99 3개 | Low (더 정밀한 모니터링) |
| E2 | middleware status_code 처리 | `"response" in dir()` 패턴 | `status_code = 500` 기본값 변수 | Low (안전한 코드 패턴) |
| E3 | metrics import 위치 | finally 블록 내 lazy import | 파일 상단 top-level import | Low (성능 미세 개선) |
| E4 | dashboards.yml 확장 필드 | 최소 필드 | orgId, disableDeletion, editable 추가 | Low (Grafana 운영 편의) |

---

## 4. 경미한 차이 (문서 업데이트 권장)

| # | 항목 | 설계 | 구현 | 심각도 |
|---|------|------|------|:------:|
| G1 | proxy.py log_usage에 request_id 미전달 | D5에서 request_id 파라미터 추가 | log_usage 호출 시 request_id 전달하지 않음 (기본값 "" 사용) | Low |

**G1 상세**: `logging.py`에 `request_id` 파라미터가 추가되었으나(설계 일치), `proxy.py`의 `forward_request`(L102)와 `stream_upstream`(L179)에서 `log_usage()` 호출 시 `request_id=`를 전달하지 않는다. `metrics_middleware`에서 `request.state.request_id`에 저장하지만 proxy 함수에서는 접근하지 않는다. 다만 `structlog.contextvars`에 bind되어 있으므로 structlog 출력에는 request_id가 포함된다. 기능적 영향 없음.

---

## 5. Clean Architecture Compliance

| Layer | 파일 | 의존 방향 | Status |
|-------|------|----------|:------:|
| API (routes/) | routes/metrics.py | prometheus_client | ✅ |
| API (routes/) | routes/v1.py → proxy.py | Application 방향 | ✅ |
| Application | proxy.py → metrics.py, logging.py | Infrastructure 방향 | ✅ |
| Config | main.py → all routers | Composition Root | ✅ |
| Infrastructure | metrics.py | prometheus_client (외부) | ✅ |

Gateway는 Pragmatic flat modules 아키텍처 (strict 4-layer 아님). 해당 수준에서 의존 방향 위반 없음.

---

## 6. Convention Compliance

### 6.1 Naming Convention

| 카테고리 | 규칙 | 검사 대상 | 준수율 | 위반 |
|----------|------|----------|:------:|------|
| 모듈 | snake_case.py | metrics.py, proxy.py, logging.py | 100% | - |
| 함수 | snake_case | _try_parse_usage, _record_usage_from_response 등 | 100% | - |
| 상수 | UPPER_SNAKE_CASE | REQUEST_COUNT, ACTIVE_REQUESTS 등 6개 | 100% | - |
| 파일 구조 | routes/ 하위 라우터 | routes/metrics.py | 100% | - |

### 6.2 Import Order

모든 파일에서 준수:
1. `__future__` annotations
2. 표준 라이브러리 (json, time, uuid)
3. 외부 패키지 (fastapi, httpx, prometheus_client, structlog)
4. 내부 모듈 (.metrics, .logging, .routes)

### 6.3 Convention Score

```
+---------------------------------------------+
|  Convention Compliance: 100%                 |
+---------------------------------------------+
|  Naming:          100%                       |
|  Import Order:    100%                       |
|  File Structure:  100%                       |
+---------------------------------------------+
```

---

## 7. Test Verification

| 테스트 스위트 | 기대값 | 결과 | Status |
|--------------|--------|------|:------:|
| Gateway tests | 43 passed | 확인 필요 | -- |
| myaicoder tests | 178 passed, 4 skipped | 확인 필요 | -- |
| Ruff | all checks passed | 확인 필요 | -- |

> 참고: 테스트 실행은 본 분석 범위 외. 사용자가 별도 검증 요청.

---

## 8. Overall Score

```
+---------------------------------------------+
|  Overall Score: 100 / 100                    |
+---------------------------------------------+
|  Design Match:          100%  (9/9 items)    |
|  Architecture Compliance: 100%               |
|  Convention Compliance:   100%               |
+---------------------------------------------+
```

| Category | Score | Status |
|----------|:-----:|:------:|
| Design Match | 100% | PASS |
| Architecture Compliance | 100% | PASS |
| Convention Compliance | 100% | PASS |
| **Overall** | **100%** | **PASS** |

---

## 9. Recommended Actions

### 9.1 선택 사항 (필수 아님)

| 우선순위 | 항목 | 파일 | 설명 |
|----------|------|------|------|
| Low | G1: proxy.py log_usage에 request_id 명시 전달 | proxy.py:102, 179 | structlog contextvars로 이미 동작하므로 기능적 영향 없음. 명시성 개선 목적 |

### 9.2 설계 문서 업데이트 권장

| 항목 | 설명 |
|------|------|
| E1 | Latency 패널에 p99 추가된 점 반영 |
| E2 | middleware status_code 안전 패턴 반영 |
| E3 | top-level import 패턴 반영 |

---

## 10. Conclusion

설계 문서 D1~D9 전체 항목이 구현에 정확히 반영되어 있다.
Match Rate **100%**로, 추가 iteration 없이 Report 단계로 진행 가능하다.

4건의 Enhancement(E1-E4)는 구현이 설계보다 나은 방향으로 개선된 것이며,
1건의 경미한 차이(G1)는 기능적 영향이 없다(structlog contextvars 통해 request_id가 이미 로그에 포함됨).

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2026-03-14 | Initial analysis | gap-detector |
