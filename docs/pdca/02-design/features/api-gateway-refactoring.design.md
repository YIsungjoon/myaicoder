# Design: Gateway 서비스 구조 개선 및 고도화 (Refactoring)

> **상태**: D (Design)
> **작성일**: 2026-03-24
> **목표**: Gateway 루트의 잔류 파일을 완전히 정리하고, DB 트랜잭션의 원자성과 동시성 제어의 안정성을 강화한다.

---

## 1. 아키텍처 상세 설계 (Architecture Details)

### 1.1 패키지 구조 (Package Structure)

```
gateway/app/
├── main.py                    ← FastAPI 앱 초기화 및 미들웨어 등록 전담
├── config/                    ← 중앙 설정 관리 (Singleton 패턴)
│   ├── __init__.py            ← GatewayConfig 인스턴스 노출
│   ├── settings.py            ← 환경 변수 로드 및 유효성 검사 (Pydantic)
│   └── models.py              ← 공통 API 스키마 및 데이터 모델
├── auth/                      ← 인증 (API Key)
│   ├── __init__.py
│   └── store.py               ← API Key 저장소 및 검증 로직 (AuthStore)
├── middleware/                ← 요청 처리 파이프라인
│   ├── __init__.py
│   ├── concurrency.py         ← Semaphore 기반 동시 접속 제어
│   ├── rate_limiter.py        ← Sliding Window 기반 속도 제한
│   ├── errors.py              ← 전역 예외 처리 및 로깅 (New)
│   └── deps.py                ← FastAPI 의존성 (Depends) 중앙 집중
├── proxy/                     ← LLM 요청 중계
│   ├── __init__.py
│   ├── forward.py             ← OpenAI API 호환 요청 전달 및 스트리밍
│   └── router.py              ← 모델 가중치/상태 기반 라우팅
├── infra/                     ← 인프라 및 핵심 유틸리티
│   ├── __init__.py
│   ├── db.py                  ← DB 엔진, 원자적 세션 관리 (Atomicity)
│   ├── logging.py             ← 구조화된 로깅 (structlog)
│   └── metrics.py             ← Prometheus 메트릭 수집 및 노출
└── routes/                    ← 도메인별 API 엔드포인트
    ├── __init__.py
    ├── v1.py                  ← 코딩 어시스턴트 핵심 API
    ├── internal.py            ← 내부 상태 및 설정 관리
    └── health.py              ← 헬스체크 및 메트릭 엔드포인트
```

---

## 2. DB 트랜잭션 원자성 설계 (Atomicity Design)

### 2.1 `asynccontextmanager` 기반 세션 관리
`infra/db.py`에 다음과 같은 세션 관리자를 도입하여 다중 접속 환경에서도 안전한 트랜잭션을 보장합니다.

```python
from contextlib import asynccontextmanager
from databases import Database

database = Database(DATABASE_URL)

@asynccontextmanager
async def get_db_session():
    """
    DB 세션을 생성하고 예외 발생 시 자동으로 롤백을 수행하는 컨텍스트 매니저.
    원자성(Atomicity)을 보장하기 위해 모든 DB 작업은 이 내부에서 수행되어야 함.
    """
    async with database.transaction() as transaction:
        try:
            yield database
        except Exception as e:
            # transaction()은 내부적으로 예외 발생 시 롤백함
            logger.error("Database transaction failed", error=str(e))
            raise
```

---

## 3. 중복 코드 및 결합도 해소 설계

### 3.1 통합 에러 핸들링 미들웨어 (`middleware/errors.py`)
기존에 각 라우트(`routes/v1.py`)에서 `try-except`로 중복 처리하던 로직을 전역 미들웨어로 통합합니다.

- **장점**: 코드량 감소, 일관된 에러 응답 형식(JSON) 보장, 누락 없는 로깅.

### 3.2 의존성 관리 (`middleware/deps.py`)
`deps.py`는 패키지 내부의 기능을 조합하여 FastAPI `Depends`로 제공하는 역할만 수행합니다. 
- `check_concurrency`, `check_rate_limit`, `get_auth_store` 등을 여기서 한곳에 모아 관리함으로써 `main.py`의 결합도를 낮춥니다.

---

## 4. 리팩토링 수행 가이드 (Implementation Strategy)

### Step 1: 루트 파일 완전 제거 (Clean Sweep)
- `gateway/app/` 루트에 있는 `concurrency.py`, `config.py`, `db.py` 등 Backward compatibility용 파일들을 삭제합니다.
- 이에 의존하던 모든 코드(`routes/`, `main.py`)의 import 경로를 새로운 패키지 경로로 전면 수정합니다.

### Step 2: DB 원자성 강화
- `infra/db.py`에 `asynccontextmanager`를 적용하고, 기존의 전역 `database` 변수 직접 사용을 제한하도록 리팩토링합니다.

### Step 3: 중복 에러 처리 제거
- `routes/v1.py`의 각 엔드포인트 내 `try-except` 구문을 제거하고 전역 에러 핸들러로 위임합니다.

---

## 5. 검증 계획 (Validation Plan)

1. **단위 테스트**: `uv run pytest tests/` 실행 (기존 43개 테스트 통과 확인).
2. **트랜잭션 테스트**: 강제로 예외를 발생시켜 DB 롤백이 완벽히 이루어지는지 확인하는 테스트 케이스 추가.
3. **동시 접속 테스트**: 다수의 사용자가 동시에 요청을 보낼 때 세션 충돌이나 데드락이 발생하지 않는지 검증.
