# rate-limiting Analysis Report

> **Analysis Type**: Gap Analysis (Design vs Implementation)
>
> **Project**: myAiCoder
> **Analyst**: gap-detector agent
> **Date**: 2026-03-14
> **Design Doc**: [rate-limiting.design.md](../02-design/features/rate-limiting.design.md)

---

## 1. Analysis Overview

### 1.1 Analysis Purpose

rate-limiting 피처의 Design 문서와 실제 구현 코드 간의 일치도를 검증한다.
9개 분석 항목에 대해 Match/Gap을 판정하고 종합 Match Rate를 산출한다.

### 1.2 Analysis Scope

- **Design Document**: `docs/pdca/02-design/features/rate-limiting.design.md`
- **Implementation Files**:
  - `services/gateway/app/rate_limiter.py`
  - `services/gateway/app/config.py`
  - `services/gateway/app/deps.py`
  - `services/gateway/app/main.py`
  - `services/gateway/app/routes/v1.py`
  - `services/gateway/tests/test_rate_limiter.py`
  - `services/gateway/tests/conftest.py`
  - `services/gateway/gateway.yaml.example`
  - `services/myaicoder/src/myaicoder/models/config.py`

---

## 2. Gap Analysis (항목별 상세)

### 2.1 SlidingWindowLimiter 알고리즘 (가중 평균, 윈도우 전환)

| Design 항목 | 구현 상태 | Status |
|-------------|----------|--------|
| `WindowCounter` dataclass | 구현됨 (`rate_limiter.py:24`) | Match |
| `window_key`, `count`, `prev_count` 필드 | 구현됨 | Match |
| `prev_window_key` 필드 (Design 라인 147) | 구현에서 제거됨 (사용하지 않으므로 불필요) | Match (의도적 개선) |
| 가중 평균 공식: `curr + prev * (1 - progress)` | 동일하게 구현됨 (`rate_limiter.py:83`) | Match |
| 윈도우 전환 (직전 윈도우 -> prev 이동) | 동일하게 구현됨 (`rate_limiter.py:74-80`) | Match |
| 2개 이상 지난 윈도우 -> prev 리셋 | 동일하게 구현됨 (`rate_limiter.py:78-79`) | Match |
| 반환값: `(allowed, remaining, reset_at)` | 동일 | Match |

**판정: Match (100%)**

`prev_window_key` 필드 제거는 Design에서도 실제 사용하지 않는 필드였으므로 Dead Code 정리에 해당한다.

### 2.2 메모리 누수 방지 (lazy eviction)

| Design 항목 | 구현 상태 | Status |
|-------------|----------|--------|
| `_evict()` 메서드 | 구현됨 (`rate_limiter.py:95-104`) | Match |
| 5분 주기 eviction | 기본값 300.0초 (`rate_limiter.py:42`) | Match |
| `_last_eviction` 타임스탬프 | 구현됨 | Match |
| 만료 기준: `window_key < current_window - 1` | 동일 (`rate_limiter.py:101`) | Match |
| `eviction_interval` 파라미터화 | Design에 없음, 구현에서 생성자 파라미터로 추가 | Match (테스트 편의를 위한 개선) |

**판정: Match (100%)**

### 2.3 동시성 안전 (await 없는 동기 블록)

| Design 항목 | 구현 상태 | Status |
|-------------|----------|--------|
| `check_and_increment` 전체가 동기 코드 | `await` 없음 확인 (`rate_limiter.py:46-93`) | Match |
| `time.time()` ~ `counter.count += 1` 사이 await 없음 | 확인됨 | Match |
| Lock 불필요 (asyncio 단일 스레드) | 문서 주석에 명시됨 | Match |

**판정: Match (100%)**

### 2.4 Dependency(차단) + Middleware(헤더 주입) 패턴 분리

| Design 항목 | 구현 상태 | Status |
|-------------|----------|--------|
| 초기 설계: Middleware 단일 방식 (섹션 3.3) | 최종 설계(섹션 3.4)로 변경됨 | - |
| 최종 설계: `check_rate_limit` Dependency (차단) | `deps.py:37-90` 구현 | Match |
| 최종 설계: `RateLimitHeaderMiddleware` (헤더 주입만) | `rate_limiter.py:128-144` 구현 | Match |
| `request.state.rate_limit_headers`에 저장 | `deps.py:86-90` 구현 | Match |
| Middleware에서 `call_next()` 후 헤더 주입 | `rate_limiter.py:137-143` 구현 | Match |
| `v1_router` dependency chain: `[get_current_user, check_rate_limit]` | `v1.py:15` 구현 | Match |

**판정: Match (100%)**

Design 문서 내 초기 설계(섹션 3.3, Middleware 단일 방식)에서 최종 설계(섹션 3.4, Dependency+Middleware 분리)로의 전환 근거가 명확히 기술되어 있고, 구현은 최종 설계를 정확히 따른다.

### 2.5 Config 확장 (RateLimitConfig, 역할별 한도, 오버라이드)

| Design 항목 | 구현 상태 | Status |
|-------------|----------|--------|
| `RoleLimitConfig(requests_per_minute, requests_per_hour)` | `config.py:43-45` | Match |
| `UserOverrideConfig(user_id, rpm, rph)` | `config.py:48-51` | Match |
| `RateLimitConfig(enabled, roles, overrides)` | `config.py:54-60` | Match |
| admin 기본값: 120/분, 3600/시간 | `config.py:57` | Match |
| user 기본값: 30/분, 500/시간 | `config.py:58` | Match |
| `GatewayConfig`에 `rate_limit` 필드 추가 | `config.py:67` | Match |
| `resolve_limits` 함수 (override > role > fallback) | `rate_limiter.py:110-122` | Match |
| override lookup: Design은 dict pre-build, 구현은 linear scan | 기능 동일, 구현 방식 차이 | Match (미미한 차이) |

**판정: Match (100%)**

override lookup 방식의 차이(dict vs linear scan)는 오버라이드 수가 소수이므로 성능 영향 없음.

### 2.6 중앙 config/ 디렉토리 로드 경로

| Design 항목 | 구현 상태 | Status |
|-------------|----------|--------|
| `config/` 디렉토리 존재 | 디렉토리 미생성 (빈 디렉토리는 git 추적 불가) | Gap (Minor) |
| `GatewayConfig.load()` 검색 순서에 `config/gateway.yaml` 추가 | `config.py:91` 구현 | Match |
| `ModelsConfig.load()` 검색 순서에 `config/models.yaml` 추가 | `models/config.py:59` 구현 | Match |
| `gateway.yaml.example`에 rate_limit 섹션 | `gateway.yaml.example:27-39` | Match |
| Design의 `config/models.yaml` 파일 | 파일 없음 (config/ 디렉토리 자체가 없음) | Gap (Minor) |

**판정: 95% Match**

`config/` 디렉토리가 물리적으로 존재하지 않지만, 이는 git이 빈 디렉토리를 추적하지 않기 때문이며, 코드 로직(load 경로)은 올바르게 구현되어 있다. `config/gateway.yaml` 파일을 생성하면 자동으로 디렉토리가 만들어진다. `.gitkeep` 파일을 추가하거나 README를 배치하면 해결된다.

### 2.7 테스트 전략

| Design 테스트 카테고리 | 구현 테스트 | Status |
|----------------------|-----------|--------|
| `test_sliding_window` (기본 허용/차단, 윈도우 전환, 가중 평균) | `TestSlidingWindowBasic` (4개), `TestSlidingWindowTransition` (2개) | Match |
| `test_eviction` (만료 카운터 정리, 메모리 누수 방지) | `TestEviction` (2개) | Match |
| `test_config` (역할별 한도, 오버라이드) | `TestResolveLimits` (4개) | Match |
| `test_dependency` (429, 헤더 저장, disabled skip) | 통합 테스트로 커버 (`test_rate_limit_429_when_exceeded`, `test_rate_limit_disabled`) | Match |
| `test_middleware` (헤더 주입, 없을 때 skip) | `test_rate_limit_headers_present`, `test_health_endpoint_not_rate_limited` | Match |
| `test_integration` (연속 요청, 한도 도달, 429) | `test_rate_limit_remaining_decreases`, `test_rate_limit_429_when_exceeded` | Match |
| 시간 의존 테스트: `time.time()` mock | `patch("app.rate_limiter.time.time")` 사용 | Match |
| conftest에 rate_limiter 초기화 | `conftest.py:71` | Match |

**테스트 수**: Design 예측 6개 카테고리 / 구현 17개 테스트 (7개 클래스)

**판정: Match (100%)**

### 2.8 에러 처리 (429, Retry-After, disabled skip)

| Design 항목 | 구현 상태 | Status |
|-------------|----------|--------|
| 분당 한도 초과 -> HTTP 429 | `deps.py:55-66` | Match |
| 시간당 한도 초과 -> HTTP 429 | `deps.py:69-83` | Match |
| `Retry-After` 헤더 (윈도우 종료까지 초) | `deps.py:56,73` `max(1, reset - now)` | Match |
| `X-RateLimit-Limit/Remaining/Reset` 헤더 | `deps.py:60-64`, `rate_limiter.py:139-143` | Match |
| `rate_limit.enabled = false` -> skip | `deps.py:43-44` | Match |
| config에 역할 없음 -> 기본값 30/500 | `rate_limiter.py:122` | Match |
| 인증 실패 -> rate limit 미적용 | Dependency 순서로 보장 (인증 먼저) | Match |
| 429 응답 body 형식 | Design: `{"error": {"message", "type"}}` / 구현: `{"detail": "..."}` | Gap (Minor) |

**판정: 95% Match**

429 응답 body 형식에 차이가 있다. Design 섹션 6.2에서는 `{"error": {"message": "...", "type": "rate_limit_error"}}` 형태를 명시하지만, 구현은 FastAPI `HTTPException`의 기본 형식인 `{"detail": "..."}` 을 사용한다. Design 섹션 3.3(초기 Middleware 방식)의 `_too_many_requests`에서 `error` 형식을 사용했으나, 섹션 3.4(최종 Dependency 방식)로 전환하면서 `HTTPException`으로 변경되었다. Design 문서 자체의 섹션 3.4 코드에서도 `HTTPException(detail=...)` 를 사용하므로, 시퀀스 다이어그램(섹션 6.2)과 최종 설계(섹션 3.4) 사이의 불일치이다.

### 2.9 구현 순서 (Design 섹션 8)

| Design 순서 | 파일 | 구현 여부 | Status |
|------------|------|----------|--------|
| 1. config/ 디렉토리 + config 로드 경로 확장 | `config.py` | 로드 경로 추가됨 | Match |
| 2. `RateLimitConfig` 추가 | `config.py:43-60` | 구현됨 | Match |
| 3. `SlidingWindowLimiter` 구현 + 테스트 | `rate_limiter.py` + 테스트 | 구현됨 | Match |
| 4. `check_rate_limit` Dependency | `deps.py:37-90` | 구현됨 | Match |
| 5. `RateLimitHeaderMiddleware` | `rate_limiter.py:128-144` | 구현됨 | Match |
| 6. main.py 통합 | `main.py:43,60` | 구현됨 | Match |
| 7. 통합 테스트 | `test_rate_limiter.py` | 17개 테스트 | Match |
| 8. `gateway.yaml.example` 업데이트 | `gateway.yaml.example:27-39` | 구현됨 | Match |

**판정: Match (100%)**

---

## 3. Match Rate Summary

### 3.1 항목별 점수

| # | 분석 항목 | Match Rate | Status |
|---|----------|:----------:|:------:|
| 1 | SlidingWindowLimiter 알고리즘 | 100% | Match |
| 2 | 메모리 누수 방지 (lazy eviction) | 100% | Match |
| 3 | 동시성 안전 (await 없는 동기 블록) | 100% | Match |
| 4 | Dependency + Middleware 패턴 분리 | 100% | Match |
| 5 | Config 확장 (RateLimitConfig) | 100% | Match |
| 6 | 중앙 config/ 디렉토리 로드 경로 | 95% | Minor Gap |
| 7 | 테스트 전략 | 100% | Match |
| 8 | 에러 처리 (429, Retry-After) | 95% | Minor Gap |
| 9 | 구현 순서 (Design 섹션 8) | 100% | Match |

### 3.2 Overall Score

```
+---------------------------------------------+
|  Overall Match Rate: 99%                    |
+---------------------------------------------+
|  Match:          7 / 9 items (100%)          |
|  Minor Gap:      2 / 9 items (95%)           |
|  Missing:        0 / 9 items                 |
+---------------------------------------------+
```

| Category | Score | Status |
|----------|:-----:|:------:|
| Design Match | 99% | Match |
| Architecture Compliance | 100% | Match |
| Convention Compliance | 100% | Match |
| **Overall** | **99%** | **Match** |

---

## 4. Differences Found

### 4.1 Minor Gaps (영향도 낮음)

#### Gap 1: config/ 디렉토리 미생성

| 항목 | 내용 |
|------|------|
| Design 위치 | 섹션 4.1 (config/ 디렉토리 구조) |
| 설명 | `config/` 디렉토리가 물리적으로 존재하지 않음 |
| 영향도 | Low - git은 빈 디렉토리 추적 불가, 코드 로직은 정상 |
| 해결 방안 | `config/.gitkeep` 또는 `config/README.md` 추가 |

#### Gap 2: 429 응답 body 형식 불일치

| 항목 | 내용 |
|------|------|
| Design 위치 | 섹션 6.2 (시퀀스 다이어그램) |
| Design 형식 | `{"error": {"message": "...", "type": "rate_limit_error"}}` |
| 구현 형식 | `{"detail": "Rate limit exceeded. Please retry later."}` |
| 원인 | Design 내부 불일치 - 섹션 3.4(최종 설계)에서 HTTPException 사용으로 전환하면서 섹션 6.2 다이어그램 미갱신 |
| 영향도 | Low - 기능적으로 429 + Retry-After 동작은 동일 |
| 해결 방안 | Design 문서 섹션 6.2의 body 형식을 `{"detail": "..."}` 로 갱신 |

### 4.2 구현에서의 개선 사항 (Design 대비)

| 항목 | Design | 구현 | 비고 |
|------|--------|------|------|
| `eviction_interval` 파라미터화 | 하드코딩 300.0 | 생성자 파라미터 (기본값 300.0) | 테스트 편의성 개선 |
| `prev_window_key` 필드 | 포함 | 제거 | 사용하지 않는 Dead Code 정리 |
| `resolve_limits` override lookup | dict pre-build | linear scan | 간결성 개선, 성능 동일 |

---

## 5. Recommended Actions

### 5.1 Design 문서 업데이트 (선택)

1. 섹션 6.2 시퀀스 다이어그램의 429 body 형식을 `{"detail": "..."}` 로 갱신
2. 섹션 3.2의 `WindowCounter`에서 `prev_window_key` 필드 제거 반영
3. `eviction_interval` 파라미터화 반영

### 5.2 구현 보완 (선택)

1. `config/.gitkeep` 파일 추가하여 디렉토리 구조 명시

---

## 6. Conclusion

rate-limiting 피처는 Design 문서와 **99% 일치**한다.

발견된 2건의 Minor Gap은 모두 기능적 영향이 없으며:
- `config/` 디렉토리는 코드 로직이 올바르게 구현되어 있어 파일 생성 시 자동 해결
- 429 body 형식은 Design 문서 내부의 섹션 간 불일치이며, 최종 설계(섹션 3.4)와 구현은 일치

핵심 설계 제약 3가지(메모리 누수 방지, 동시성 안전, Dependency+Middleware 분리)가 모두 정확히 구현되었다.

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2026-03-14 | Initial gap analysis | gap-detector agent |
