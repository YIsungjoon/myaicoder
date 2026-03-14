# Plan: gateway-internal-api

**Feature**: gateway-internal-api
**날짜**: 2026-03-14
**Phase**: Plan
**Level**: Enterprise
**Parent Context**: model-management P1 후속 — CLI↔Gateway 프로세스 간 상태 동기화
**Origin**: model-management Design 섹션 7.1

---

## 1. 개요

dev 환경에서 `myaicoder model switch`로 vLLM 모델을 전환한 뒤, **Gateway가 변경 사실을 즉시 인지**하도록 내부 관리 API를 구축한다.

### 현재 문제

```
CLI: myaicoder model switch qwen3-coder-30b
  ✓ vLLM 프로세스 교체 완료 (port 8001)

Gateway (별도 프로세스, 메모리 공유 없음):
  ✗ 여전히 구 모델(qwen3.5-9b)로 라우팅 시도
  ✗ 사용자 요청이 잘못된 모델로 전달됨
```

### 해결 후

```
CLI: myaicoder model switch qwen3-coder-30b
  ✓ vLLM 프로세스 교체 완료
  ✓ POST /internal/routes/reload → Gateway에 통지

Gateway:
  ✓ ModelRouter 라우팅 테이블 즉시 갱신
  ✓ 다음 요청부터 새 모델로 정확히 라우팅
```

### 구현 현황

| 컴포넌트 | 상태 |
|----------|------|
| CLI `_notify_gateway()` | ✅ 이미 구현 (`models/manager.py`) |
| `models.yaml`의 `gateway_url`, `internal_token` | ✅ 이미 구현 (`models/config.py`) |
| Gateway `POST /internal/routes/reload` | ❌ **미구현** (이번 피처) |
| Gateway `ModelRouter.reload()` | ❌ **미구현** (이번 피처) |
| Gateway `AuthConfig.internal_token` | ❌ **미구현** (이번 피처) |

## 2. 핵심 요구사항

| ID | 기능 | 설명 | 우선순위 |
|----|------|------|----------|
| FR-01 | 내부 라우팅 갱신 API | `POST /internal/routes/reload` 엔드포인트 | P0 |
| FR-02 | 내부 토큰 인증 | `X-Internal-Token` 헤더로 내부 요청 인증 | P0 |
| FR-03 | ModelRouter 동적 갱신 | `reload()` 메서드로 라우팅 테이블 업데이트 | P0 |
| FR-04 | Config 확장 | `gateway.yaml`에 `internal_token` 설정 | P0 |
| FR-05 | E2E 검증 | CLI switch → Gateway reload → 올바른 라우팅 확인 | P0 |

## 3. 범위

### 3.1 In Scope

| # | 항목 | 우선순위 |
|---|------|----------|
| 1 | `POST /internal/routes/reload` 엔드포인트 | P0 |
| 2 | `X-Internal-Token` 인증 | P0 |
| 3 | `ModelRouter.reload()` 메서드 | P0 |
| 4 | `GatewayConfig`에 `internal_token` 필드 추가 | P0 |
| 5 | 내부 API 라우터 (`routes/internal.py`) | P0 |
| 6 | pytest 테스트 (단위 + 통합) | P0 |
| 7 | `gateway.yaml.example` 업데이트 | P0 |

### 3.2 Out of Scope

| 항목 | 사유 |
|------|------|
| prod 환경 라우팅 갱신 | prod는 Always-on, reload 불필요 |
| 다중 Gateway 인스턴스 동기화 | 현재 단일 인스턴스 |
| 모델 자동 감지 (file watcher) | 과도한 복잡성 |

## 4. 보안 설계

- `/internal/*` 경로는 **외부 사용자 API key 인증과 별도**로 `X-Internal-Token` 헤더 필요
- 토큰이 없거나 틀리면 HTTP 403
- Rate limiting 미적용 (내부 전용, 빈도 극히 낮음)
- `/internal/*` 경로는 `/v1` 라우터 밖이므로 기존 사용자 인증 dependency 미적용

## 5. 성공 기준

- [ ] `POST /internal/routes/reload`로 Gateway 라우팅이 동적으로 갱신된다
- [ ] `X-Internal-Token`이 없거나 틀리면 403이 반환된다
- [ ] CLI `model switch` → Gateway reload → 새 모델로 라우팅 확인 (E2E)
- [ ] 기존 `/v1/*`, `/health` 엔드포인트에 영향 없음
- [ ] 테스트가 `uv run pytest tests -q`로 통과한다

## 6. 기술 결정 사항

| 항목 | 결정 | 근거 |
|------|------|------|
| 엔드포인트 경로 | `/internal/routes/reload` | 내부 전용 명확히 구분 |
| 인증 | `X-Internal-Token` 헤더 | 기존 Bearer token과 분리 |
| 라우터 분리 | `routes/internal.py` | v1 라우터와 독립 |
| Rate limiting | 미적용 | 내부 전용, 빈도 낮음 |

## 7. 의존 관계

```
gateway-internal-api (이번 feature)
  ├── depends on: services/gateway (기존 인프라)
  ├── triggered by: services/myaicoder models/manager.py (_notify_gateway)
  └── completes: model-management P1 (상태 동기화 고리 연결)
```
