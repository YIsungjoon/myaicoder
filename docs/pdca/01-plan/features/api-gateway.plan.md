# Plan: api-gateway

**Feature**: api-gateway
**날짜**: 2026-03-14
**Phase**: Plan
**Level**: Enterprise
**Parent Context**: myAiCoder monorepo - LLM 프록시 게이트웨이 서비스

---

## 1. 개요

`sungjunCode/gateway.py`에 구현된 API Gateway 기능을 `services/gateway`로 통합한다. 이 서비스는 vLLM 서버 앞단에서 **인증**, **사용량 로깅**, **스트리밍 프록시** 역할을 수행하며, 추후 사용자별 모델 선택 기능의 기반이 된다.

현재 `sungjunCode`에는 CLI/Agent/Tools가 포함되어 있으나 `services/myaicoder`에 이미 성숙한 구현이 존재하므로, **Gateway 기능만 추출하여 독립 마이크로서비스로 통합**한다.

### 1.1 원본 코드 분석 (sungjunCode/gateway.py)

현재 구현된 기능:
- FastAPI 기반 reverse proxy (vLLM → 클라이언트)
- API Key 기반 인증 (`users.json`)
- 요청/응답 전체 로깅 (파일 기반)
- 스트리밍 응답 프록시 및 TTFT 측정
- catch-all 라우팅 (`/{path:path}`)

현재 구현의 문제점:
- JSON 파일 기반 사용자 DB (확장성 한계)
- httpx client를 매 요청마다 생성 (리소스 낭비)
- 에러 핸들링 부재 (bare except)
- Clean Architecture 미적용
- 테스트 코드 없음
- 단일 vLLM 서버만 지원 (모델 선택 불가)

## 2. 핵심 요구사항

### 2.1 기능 요구사항

| ID | 기능 | 설명 | 우선순위 |
|----|------|------|----------|
| FR-01 | API Key 인증 | Bearer 토큰 기반 접근 제어 | P0 |
| FR-02 | vLLM 프록시 | OpenAI 호환 API를 vLLM 서버로 프록시 | P0 |
| FR-03 | 스트리밍 프록시 | SSE 기반 chat/completions 스트리밍 지원 | P0 |
| FR-04 | 사용량 로깅 | 요청/응답, 레이턴시, TTFT 기록 | P0 |
| FR-05 | 사용자 관리 | 사용자별 API Key, 역할, 소속 관리 | P1 |
| FR-06 | 모델 라우팅 | 사용자 요청의 model 파라미터에 따라 적절한 vLLM 인스턴스로 라우팅 | P1 |
| FR-07 | Health Check | `/health` 엔드포인트 및 upstream 상태 확인 | P0 |
| FR-08 | Rate Limiting | 사용자별/역할별 요청 제한 | P2 |

### 2.2 비기능 요구사항

| ID | 항목 | 기준 |
|----|------|------|
| NFR-01 | Clean Architecture | services/CLAUDE.md의 4-layer 구조 준수 |
| NFR-02 | 비동기 처리 | 모든 I/O async/await |
| NFR-03 | 테스트 가능성 | 핵심 로직에 단위 테스트 존재 |
| NFR-04 | 확장성 | 다중 vLLM 인스턴스, 다중 모델 지원 가능 구조 |
| NFR-05 | 보안 | API Key 평문 저장 금지, 로그에 키 전체 노출 금지 |
| NFR-06 | 호환성 | Python 3.11+, OpenAI API 호환 |

## 3. 범위

### 3.1 In Scope

| # | 항목 | 우선순위 |
|---|------|----------|
| 1 | `services/gateway` 디렉토리 생성 (Clean Architecture) | P0 |
| 2 | API Key 인증 미들웨어 | P0 |
| 3 | vLLM reverse proxy (일반 + 스트리밍) | P0 |
| 4 | 사용량 로깅 (structured JSON logging) | P0 |
| 5 | Health check 엔드포인트 | P0 |
| 6 | 모델 라우팅 설정 (config 기반) | P1 |
| 7 | pytest 테스트 스위트 | P0 |
| 8 | CI 워크플로 확장 (기존 ci.yml에 gateway job 추가) | P1 |

### 3.2 Out of Scope

| 항목 | 사유 |
|------|------|
| GGUF 모델 파일 관리/다운로드 | 별도 feature (model-management) |
| 웹 기반 관리자 대시보드 | 별도 feature |
| PostgreSQL/Redis 기반 사용자 저장소 | 초기에는 config 기반, 추후 확장 |
| OAuth/JWT 토큰 발급 | 현 단계에서는 API Key만 |
| sungjunCode의 CLI/Agent/Tools 이관 | myaicoder에 이미 존재하므로 버림 |
| sungjunCode 디렉토리 삭제 | 사용자가 별도 판단 |

## 4. 성공 기준

- `services/gateway`에 Clean Architecture 기반 Gateway 서비스가 존재한다
- API Key 인증 → vLLM 프록시 → 로깅 흐름이 동작한다
- 스트리밍 프록시가 SSE를 올바르게 전달한다
- 모델 라우팅 설정 구조가 존재한다 (다중 모델 지원 기반)
- 테스트가 `uv run pytest tests -q`로 통과한다
- 기존 CI에 gateway job이 추가된다

## 5. 모델 관리 방향 (참고)

사용자 요청에 따라 GGUF 모델 파일은 별도 보관하며, 추후 사용자가 모델을 변경하며 사용할 수 있도록 한다. 이를 위해:

- Gateway의 모델 라우팅 설정에서 `model_name → vllm_endpoint` 매핑을 config로 관리
- 사용 가능한 모델 목록을 `/v1/models` 엔드포인트로 노출
- 실제 모델 파일 관리(다운로드, 삭제, 전환)는 별도 `model-management` feature로 분리

## 6. 기술 결정 사항

| 항목 | 결정 | 근거 |
|------|------|------|
| HTTP 클라이언트 | httpx (async) | 스트리밍 지원, 기존 코드 호환 |
| 사용자 저장소 (초기) | YAML/JSON config | 단순, 별도 DB 불필요 |
| 로깅 | structlog (JSON) | 구조화된 로그, 분석 용이 |
| 인증 | API Key (Bearer) | 현 단계에서 충분, 추후 JWT 확장 가능 |
| 테스트 | pytest + httpx (AsyncClient) | FastAPI 공식 권장 |

## 7. 의존 관계

```
services/gateway (이번 feature)
  ├── depends on: vLLM 서버 (외부, 실행 중이어야 함)
  ├── consumed by: Antigravity IDE (외부 클라이언트)
  ├── consumed by: vscode-extension (향후)
  └── sibling: services/myaicoder (독립, 직접 의존 없음)
```
