# Plan: Gateway 서비스 구조 개선 및 고도화 (Refactoring)

> **상태**: P (Plan)
> **작성일**: 2026-03-24
> **목표**: Gateway 루트의 13개 파일을 기능별 서브패키지로 분리하여 결합도를 낮추고, 다중 접속 및 트랜잭션 안정성을 강화한다.

---

## 1. 배경 및 필요성
- **구조적 부채**: `gateway/app/` 루트에 인증, 프록시, DB, 설정 등이 혼재되어 있어 유지보수가 어렵고 결합도가 매우 높음 (`main.py`, `deps.py` 집중 현상).
- **안정성 강화**: 다중 사용자의 동시 접속 상황에서 리소스 경합 및 DB 트랜잭션의 원자성을 보장하는 구조적 기반 필요.
- **중복 제거**: 반복되는 의존성 주입 및 에러 핸들링 로직을 추상화하여 단순화.

---

## 2. 핵심 설계 원칙
1. **관심사 분리 (SoC)**: 각 모듈은 하나의 책임만 가지며, 서브패키지 단위로 격리한다.
2. **트랜잭션 원자성**: DB 작업은 Context Manager를 사용하여 예외 발생 시 자동 롤백을 보장하고, 다중 접속 환경에서의 데이터 정합성을 유지한다.
3. **의존성 단순화**: 중앙 집중된 `deps.py`를 각 도메인 패키지 내부로 분산하거나, 인터페이스 기반으로 추상화하여 순환 참조를 방지한다.
4. **DRY (Don't Repeat Yourself)**: 공통 미들웨어 및 유틸리티를 통합하여 코드 중복을 최소화한다.

---

## 3. 목표 구조 (Target Architecture)

```
gateway/app/
├── main.py                    ← 진입점 (최소 로직)
├── config/                    ← 설정 및 전역 상스
│   ├── settings.py            ← GatewayConfig
│   └── models.py              ← 공통 데이터 모델
├── auth/                      ← 인증 및 권한
│   ├── store.py               ← AuthStore (API Key 관리)
│   └── deps.py                ← 인증 관련 의존성
├── middleware/                ← 전역 미들웨어
│   ├── concurrency.py         ← 동시성 제어 (Semaphore)
│   ├── rate_limiter.py        ← 속도 제한
│   └── errors.py              ← 통합 에러 핸들러 (중복 제거)
├── proxy/                     ← 핵심 LLM 프록시 로직
│   ├── forward.py             ← 요청 전달 및 스트리밍
│   └── router.py              ← 모델 라우팅 엔진
├── infra/                     ← 인프라 및 외부 시스템
│   ├── db.py                  ← DB 엔진 및 원자적 세션 관리
│   ├── logging.py             ← 구조화된 로깅
│   └── metrics.py             ← Prometheus 메트릭
└── routes/                    ← API 엔드포인트
    ├── v1.py
    └── internal.py
```

---

## 4. 실행 단계 (Implementation Steps)

### Phase 1: 기반 인프라 정리 (P -> D)
1. `infra/` 및 `config/` 패키지 생성 및 이동.
2. `db.py` 개선: 트랜잭션 원자성을 보장하는 Context Manager (`get_db_session`) 구현.
3. `logging.py` 및 `metrics.py` 이동 및 초기화 로직 정리.

### Phase 2: 미들웨어 및 인증 분리
1. `middleware/` 패키지 생성: `concurrency`, `rate_limiter` 이동.
2. `auth/` 패키지 생성: `auth.py`를 `store.py`로 이동하고 로직 단순화.
3. 공통 에러 핸들링 미들웨어 도입으로 각 라우트의 중복된 `try-except` 제거.

### Phase 3: 핵심 프록시 로직 리팩토링
1. `proxy/` 패키지 생성: `proxy.py`, `router.py` 이동.
2. 프록시 로직 내의 중복된 요청 설정 및 응답 처리 로직을 추상화.

### Phase 4: 최종 통합 및 검증 (Check)
1. `main.py` 및 `routes/`의 import 경로 전면 수정.
2. 기존 테스트 케이스(43 passed) 실행 및 다중 접속 부하 테스트 수행.
3. DB 트랜잭션 롤백 시나리오 검증.

---

## 5. 위험 요소 및 대응
- **순환 참조 (Circular Imports)**: 패키지 분리 시 발생 가능. 인터페이스(Protocol)나 별도의 `deps` 모듈을 통해 해결.
- **가동 중단**: 리팩토링 중 서비스 가용성 저하 방지를 위해 단계별 커밋 및 테스트 수행.
- **테스트 누락**: 리팩토링 후 기존 기능이 동일하게 동작하는지 `uv run pytest`로 상시 확인.

---

## 6. 성공 지표
- `gateway/app/` 루트 파일 수: 13개 -> 2개 (`main.py`, `__init__.py`)
- 코드 중복률 감소 (복제된 에러 처리 및 세션 관리 로직 제거)
- 모든 기존 테스트 패스 및 DB 원자성 검증 완료
