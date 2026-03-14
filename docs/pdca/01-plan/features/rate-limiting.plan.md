# Plan: rate-limiting

**Feature**: rate-limiting
**날짜**: 2026-03-14
**Phase**: Plan
**Level**: Enterprise
**Parent Context**: myAiCoder API Gateway — 사용자별/역할별 요청 제한
**Origin**: api-gateway FR-08 (P2에서 승격)

---

## 1. 개요

API Gateway에 **사용자별·역할별 요청 제한(Rate Limiting)**을 추가한다.

현재 Gateway는 인증된 사용자라면 무제한 요청이 가능하다. LLM 추론은 GPU 자원을 대량 소모하므로, 무제한 요청은 다음 문제를 야기한다:

- **GPU 자원 고갈**: 한 사용자가 대량 요청 시 다른 사용자 서비스 불가
- **비용 통제 불가**: 토큰 사용량에 대한 제한 없음
- **공정성 부재**: 사용자 간 자원 분배 메커니즘 없음

### 현재 상태

- Gateway에 rate limiting 관련 코드 **전무** (0 matches)
- 인증 후 `User(user_id, name, org, role)` 객체를 `request.state`에 보관 — rate limiter에 바로 활용 가능
- 모든 데이터가 config + memory 기반 — 외부 의존성(Redis 등) 없는 설계 가능
- 사용량 로깅은 post-request(finally 블록) — 사전 차단이 아닌 기록만

## 2. 핵심 요구사항

### 2.1 기능 요구사항

| ID | 기능 | 설명 | 우선순위 |
|----|------|------|----------|
| FR-01 | 요청 수 제한 | 사용자별 분당/시간당 요청 수 제한 | P0 |
| FR-02 | 역할별 차등 제한 | admin / user 역할에 따라 다른 한도 적용 | P0 |
| FR-03 | 표준 응답 헤더 | `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` 헤더 반환 | P0 |
| FR-04 | 429 응답 | 한도 초과 시 HTTP 429 Too Many Requests + Retry-After 헤더 | P0 |
| FR-05 | Config 기반 설정 | `gateway.yaml`에서 역할별 한도 설정 | P0 |
| FR-06 | 사용자별 오버라이드 | 특정 사용자에게 커스텀 한도 설정 | P1 |
| FR-07 | 토큰 기반 제한 | 요청 수 외에 토큰 사용량 기반 제한 | P2 |

### 2.2 비기능 요구사항

| ID | 항목 | 기준 |
|----|------|------|
| NFR-01 | 성능 | Rate check 오버헤드 < 1ms (in-memory) |
| NFR-02 | 정확성 | 동시 요청에서 race condition 없음 |
| NFR-03 | 무중단 | Gateway 재시작 시 카운터 리셋 허용 (in-memory 특성) |
| NFR-04 | 테스트 가능성 | 시간 의존 로직에 대한 단위 테스트 존재 |
| NFR-05 | 확장성 | 추후 Redis 백엔드로 교체 가능한 인터페이스 |

## 3. 범위

### 3.1 In Scope

| # | 항목 | 우선순위 |
|---|------|----------|
| 1 | 프로젝트 루트 `config/` 디렉토리 생성 + config 로드 경로 통합 | P0 |
| 2 | Sliding Window 기반 in-memory rate limiter | P0 |
| 3 | FastAPI 의존성으로 요청 사전 차단 | P0 |
| 4 | 역할별 기본 한도 (admin: 높음, user: 보통) | P0 |
| 5 | 표준 Rate Limit 응답 헤더 | P0 |
| 6 | `config/gateway.yaml`에 rate_limit 섹션 추가 | P0 |
| 7 | 기존 `gateway.yaml`, `models.yaml` → `config/`로 이동 | P0 |
| 8 | 사용자별 커스텀 오버라이드 | P1 |
| 9 | pytest 테스트 | P0 |

### 3.2 Out of Scope

| 항목 | 사유 |
|------|------|
| Redis/외부 스토어 백엔드 | 현재 단일 인스턴스, 추후 확장 |
| 토큰 기반 제한 (P2) | 응답 파싱 필요, 별도 feature |
| IP 기반 제한 | 인증된 사용자 기반으로 충분 |
| 관리자 대시보드 | 별도 feature |
| 동적 한도 변경 API | 현재 config 재시작으로 충분 |

## 4. 알고리즘 선택

### Sliding Window Counter

**Token Bucket**이나 **Fixed Window** 대신 **Sliding Window Counter**를 사용한다.

| 알고리즘 | 장점 | 단점 | 적합성 |
|----------|------|------|--------|
| Fixed Window | 구현 단순 | 경계 시점 burst 허용 | ✗ |
| Token Bucket | burst 제어 | 구현 복잡, 리필 로직 | △ |
| Sliding Window Log | 정확함 | 메모리 사용 큼 (요청별 기록) | ✗ |
| **Sliding Window Counter** | 정확 + 효율 | 약간의 근사치 | **✓** |

Sliding Window Counter는 현재 윈도우와 이전 윈도우의 가중 평균으로 요청 수를 계산한다.
메모리 효율이 좋고(윈도우당 카운터 2개), 경계 burst 문제가 없다.

## 5. 중앙 Config 제어판 (핵심 설계 결정)

### 5.1 문제: 설정 파일 분산

현재 설정이 각 서비스에 흩어져 있다:
- `services/gateway/gateway.yaml` — Gateway 서버, 인증, 모델 라우팅
- `services/myaicoder/models.yaml` — 모델 프로필, 환경 설정
- `services/myaicoder/myaicoder.json` — CLI/LLM 설정

서비스가 늘어날수록 설정 변경 시 여러 디렉토리를 돌아다녀야 한다.

### 5.2 해결: 프로젝트 루트 `config/` 디렉토리

**모든 설정을 `config/`에 중앙 집중**하여 운영자의 제어판 역할을 한다.

```
myaicoder/
├── config/                        ← 중앙 설정 제어판
│   ├── gateway.yaml               ← Gateway (서버, 인증, 라우팅, rate limit)
│   ├── models.yaml                ← 모델 프로필 (prod/dev 환경)
│   └── myaicoder.json             ← CLI/LLM 기본 설정
├── services/gateway/              ← config/ 참조
├── services/myaicoder/            ← config/ 참조
└── ...
```

### 5.3 Config 로드 우선순위 (변경)

각 서비스의 config loader에 `config/` 경로를 추가한다:

```
1. CLI/환경변수로 명시한 경로
2. config/{파일명}          ← 신규 (프로젝트 루트 config/)
3. ./{파일명}               ← 기존 (서비스 디렉토리)
4. ~/.config/myaicoder/     ← 기존 (사용자 디렉토리)
```

### 5.4 Rate Limiting 설정 (`config/gateway.yaml`에 추가)

```yaml
# config/gateway.yaml — 중앙 제어판
server:
  host: "0.0.0.0"
  port: 8080

auth:
  users:
    - api_key_hash: "sha256:..."
      user_id: "admin_01"
      name: "관리자"
      org: "MyAiCoder Team"
      role: "admin"

models:
  default: "qwen3.5-27b"
  routes:
    - name: "qwen3.5-27b"
      upstream: "http://localhost:8001/v1"
    - name: "qwen3.5-9b"
      upstream: "http://localhost:8002/v1"

rate_limit:
  enabled: true

  roles:
    admin:
      requests_per_minute: 120
      requests_per_hour: 3600
    user:
      requests_per_minute: 30
      requests_per_hour: 500

  # 사용자별 오버라이드 (P1)
  overrides:
    - user_id: "power_user_01"
      requests_per_minute: 60
      requests_per_hour: 1000

logging:
  level: "INFO"
  format: "json"
```

## 6. 요청 흐름 (Rate Limiting 적용 후)

```
HTTP Request
  │
  ▼
[1] 인증 (get_current_user) → User 객체
  │
  ▼
[2] Rate Limit 체크 (신규)
  │  ├─ RateLimiter.check(user_id, role)
  │  ├─ 허용 → 다음 단계로 + 헤더 추가
  │  └─ 초과 → HTTP 429 + Retry-After 즉시 반환
  │
  ▼
[3] 프록시 (forward_request / stream_upstream)
  │
  ▼
[4] 응답 + Rate Limit 헤더
    X-RateLimit-Limit: 30
    X-RateLimit-Remaining: 27
    X-RateLimit-Reset: 1710374460
```

## 7. 성공 기준

- [ ] 사용자별 분당 요청 제한이 동작한다
- [ ] 역할(admin/user)에 따라 다른 한도가 적용된다
- [ ] 한도 초과 시 HTTP 429 + Retry-After가 반환된다
- [ ] 정상 응답에 `X-RateLimit-*` 헤더가 포함된다
- [ ] `gateway.yaml`에서 한도를 설정할 수 있다
- [ ] 테스트가 `uv run pytest tests -q`로 통과한다
- [ ] Rate check 오버헤드가 요청 처리에 체감 영향 없음

## 8. 의존 관계

```
rate-limiting (이번 feature)
  ├── depends on: services/gateway (기존 인프라)
  ├── depends on: User.role (인증 시스템)
  ├── extends: gateway.yaml config
  └── consumed by: 모든 API 사용자
```

## 9. 기술 결정 사항

| 항목 | 결정 | 근거 |
|------|------|------|
| 알고리즘 | Sliding Window Counter | 정확성 + 메모리 효율 |
| 저장소 | In-memory (dict) | 외부 의존성 없음, 단일 인스턴스에 적합 |
| 적용 방식 | FastAPI Dependency | 기존 인증 의존성과 일관성 |
| 키 | user_id | 인증된 사용자 단위 |
| 헤더 | IETF draft 표준 | `X-RateLimit-Limit`, `Remaining`, `Reset` |
| **설정 위치** | **프로젝트 루트 `config/`** | **중앙 제어판 — 모든 설정 한 곳에서 관리** |
| Config 로드 | `config/` → `./` → `~/.config/` 순서 | 하위 호환성 유지 |

## 10. 리스크

| 리스크 | 영향 | 대응 |
|--------|------|------|
| Gateway 재시작 시 카운터 리셋 | 재시작 직후 burst 허용 | 허용 가능 (드문 이벤트) |
| asyncio 동시성 race condition | 카운터 부정확 | asyncio는 단일 스레드, Lock 불필요 |
| 메모리 증가 (사용자 수 비례) | 메모리 부족 | 사용자 수 10명 수준, 무시 가능 |
| Streaming 요청의 긴 점유 | 슬롯 낭비 | 요청 시점 1회 체크, 스트리밍 중 차단 안 함 |
