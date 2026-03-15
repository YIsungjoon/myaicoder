# Plan: Conversation Logging — 서버 측 대화 저장

- **Feature**: conversation-logging
- **Level**: Enterprise
- **Created**: 2026-03-16
- **Status**: Draft

---

## 1. 배경 및 목표

### 1.1 문제
- 사용자 입력(prompt)과 LLM 응답(completion)이 서버에 저장되지 않음
- Gateway는 stateless 프록시로, 요청 메타데이터만 stdout 로그로 출력
- 서비스 개선을 위한 데이터 분석이 불가능

### 1.2 목표
- Gateway를 통과하는 모든 대화(요청 + 응답)를 PostgreSQL에 저장
- 사용자별, 모델별, 시간대별 대화 내역 조회 가능
- 비동기 저장으로 응답 지연 없이 동작

### 1.3 핵심 가치
| 가치 | 설명 |
|------|------|
| **데이터 수집** | 사용자 입력 패턴, 모델 응답 품질 분석 가능 |
| **서비스 개선** | 자주 실패하는 질문, 느린 응답 식별 |
| **이력 관리** | 사용자별 대화 히스토리 서버 보관 |
| **성능 무영향** | 비동기 저장, 프록시 응답 지연 0 |

---

## 2. 범위 (Scope)

### 2.1 In-Scope

| # | 작업 | 설명 |
|---|------|------|
| S1 | **DB 스키마** | conversations 테이블 생성 (SQLAlchemy) |
| S2 | **대화 저장 로직** | proxy.py에서 요청/응답 캡처 → 비동기 DB 저장 |
| S3 | **비동기 DB 연결** | asyncpg + SQLAlchemy async (Gateway lifespan) |
| S4 | **Gateway 설정** | gateway.yaml에 database 설정 추가 |
| S5 | **조회 API** | 관리자용 대화 히스토리 조회 엔드포인트 |
| S6 | **DB 초기화** | 자동 테이블 생성 (create_all) |

### 2.2 Out-of-Scope
- 대화 삭제/수정 API (P2)
- 대시보드 UI (P2 — Grafana 연동 또는 별도 웹)
- 데이터 분석 파이프라인 (P2)
- 개인정보 마스킹/암호화 (P2, 현재 내부망 전용)

---

## 3. 기술 분석

### 3.1 현재 아키텍처
```
Client → Gateway (proxy.py) → LLM Server
             ↓
         stdout 로그 (메타데이터만)
```

### 3.2 목표 아키텍처
```
Client → Gateway (proxy.py) → LLM Server
             ↓                      ↓
         conversations 저장 (비동기)
             ↓
         PostgreSQL (이미 Docker Compose에 존재)
```

### 3.3 저장 시점 및 스트리밍 파싱 전략

**비스트리밍**: `forward_request()` 응답 수신 후, 요청 body + 응답 JSON 함께 저장

**스트리밍** (핵심 — 두 가지 함정 주의):

1. **SSE 청크 파싱**: raw SSE 데이터(`data: {"choices":[{"delta":{"content":"..."}}]}`)를 그대로 저장하면 분석 불가능한 쓰레기 데이터. 클라이언트에게는 raw chunk를 그대로 yield하되, **저장용 변수에는 `delta.content`만 파싱하여 깔끔하게 누적**.

2. **토큰 계산**: 스트리밍 중간 청크에는 `usage` 없음. **마지막 청크(또는 직전 청크)에만 `usage` 객체**가 포함됨. 청크 반복문에서 `usage` 키 발견 시 가로채어 저장. 모델이 `usage`를 안 내려줄 경우 **fallback: `len(accumulated_text) // 4`로 토큰 수 추정**.

```
stream_upstream() 내부 흐름:
┌─ chunk 수신 ─────────────────────────────┐
│  1. yield chunk → 클라이언트 (원본 그대로) │
│  2. SSE 파싱 → delta.content 추출         │
│  3. accumulated_content += content        │
│  4. usage 발견 시 → tokens 저장           │
└──────────────────────────────────────────┘
스트림 종료 후:
  → DB 저장: messages + accumulated_content + tokens
```

### 3.4 DB 스키마

```sql
CREATE TABLE conversations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     VARCHAR(100) NOT NULL,
    user_name   VARCHAR(100),
    model       VARCHAR(100),
    messages    JSONB NOT NULL,           -- 사용자 요청 messages 배열
    response    JSONB,                     -- LLM 응답 전체
    prompt_tokens     INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens      INTEGER DEFAULT 0,
    latency_ms  INTEGER,
    status_code INTEGER,
    is_stream   BOOLEAN DEFAULT FALSE,
    client_ip   VARCHAR(45),
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_conversations_user_id ON conversations(user_id);
CREATE INDEX idx_conversations_model ON conversations(model);
CREATE INDEX idx_conversations_created_at ON conversations(created_at);
```

### 3.5 기술 선택
| 선택 | 이유 |
|------|------|
| asyncpg | FastAPI async 호환, 높은 성능 |
| SQLAlchemy 2.0 async | ORM 없이 Core만 사용 (경량) |
| JSONB | messages/response를 유연하게 저장, 쿼리 가능 |
| 비동기 fire-and-forget | `asyncio.create_task`로 저장, 프록시 응답 블로킹 안 함 |

---

## 4. 수정 대상 파일

| # | 파일 | 변경 |
|---|------|------|
| F1 | `app/config.py` | DatabaseConfig 추가 |
| F2 | `app/db.py` | **신규** — DB 연결, 테이블 정의, 저장 함수 |
| F3 | `app/main.py` | lifespan에 DB 연결/해제 추가 |
| F4 | `app/proxy.py` | forward_request, stream_upstream에 저장 호출 |
| F5 | `app/routes/internal.py` | `/internal/conversations` 조회 API |
| F6 | `config/gateway.prod.yaml` | database 설정 추가 |
| F7 | `pyproject.toml` | asyncpg, sqlalchemy 의존성 추가 |

---

## 5. 성공 기준

| # | 기준 | 측정 방법 |
|---|------|----------|
| C1 | 비스트리밍 대화 저장 | curl → DB에 레코드 확인 |
| C2 | 스트리밍 대화 저장 | 스트리밍 요청 후 DB에 완전한 응답 저장 |
| C3 | 토큰 사용량 기록 | prompt_tokens, completion_tokens 정확히 저장 |
| C4 | 응답 지연 무영향 | 저장 전후 TTFT/latency 차이 <5ms |
| C5 | 조회 API | `/internal/conversations?user_id=xxx` 동작 |
| C6 | 자동 테이블 생성 | Gateway 시작 시 conversations 테이블 자동 생성 |
| C7 | 기존 테스트 통과 | 241/241 PASS, 0 regression |

---

## 6. 리스크

| # | 리스크 | 대응 |
|---|--------|------|
| R1 | DB 장애 시 프록시 실패 | fire-and-forget + try/except으로 DB 에러가 프록시에 영향 안 주도록 |
| R2 | 대용량 응답 저장 시 디스크 | JSONB 압축 + 향후 retention policy (P2) |
| R3 | 스트리밍 응답 누적 메모리 | 청크 누적 시 최대 크기 제한 (1MB) |
| R4 | SSE 청크를 raw 저장 시 분석 불가 | delta.content만 파싱하여 깔끔한 텍스트로 누적 |
| R5 | 스트리밍에서 usage 미포함 모델 | fallback: `len(text) // 4`로 토큰 추정 |

---

## 7. 산출물

| # | 파일 | 설명 |
|---|------|------|
| D1 | `app/config.py` 수정 | DatabaseConfig 추가 |
| D2 | `app/db.py` 신규 | 테이블 정의 + 비동기 저장 함수 |
| D3 | `app/main.py` 수정 | DB lifespan 연결 |
| D4 | `app/proxy.py` 수정 | 대화 저장 호출 |
| D5 | `app/routes/internal.py` 수정 | 조회 API |
| D6 | `config/gateway.prod.yaml` 수정 | database URL |
| D7 | `pyproject.toml` 수정 | 의존성 추가 |
