# Plan: integration-testing

**Feature**: integration-testing
**날짜**: 2026-03-14
**Phase**: Plan
**Level**: Enterprise
**Parent Context**: mock으로 덮어둔 실환경 리스크 해소

---

## 1. 개요

지금까지 모든 테스트는 **mock 기반**으로 수행되었다. 실제 vLLM 서버, MCP 서버, Gateway 프록시를 연결하여 **파이프라인 전체가 실환경에서 동작하는지** 검증한다.

### 현재 skip/mock 상태

| 영역 | 현재 상태 | 리스크 |
|------|----------|--------|
| Gateway → vLLM 프록시 | httpx mock | 실제 SSE 스트리밍 검증 안 됨 |
| Gateway → vLLM 스트리밍 | mock 응답 | TTFT, broken pipe 처리 미검증 |
| VLLMProvider 통합 | `skipif(True)` | health check, chat 미검증 |
| MCP 서버 연동 | `skipif(True)` | stdio 통신, 도구 호출 미검증 |
| model switch E2E | 단위 테스트만 | CLI → vLLM 재시작 → Gateway reload 전체 흐름 미검증 |
| Rate Limiting 실환경 | TestClient만 | 실제 서버에서 429 + 헤더 검증 안 됨 |

### 목표

**dev 환경(24GB VRAM 데스크탑)**에서 실제 vLLM을 띄우고, 전체 파이프라인을 수동 + 자동으로 검증한다.

## 2. 검증 항목

### 2.1 T1: vLLM 서버 직접 통신

| ID | 검증 항목 | 방법 |
|----|----------|------|
| T1-1 | vLLM health check | `curl localhost:8001/health` |
| T1-2 | vLLM chat (non-stream) | `curl -X POST localhost:8001/v1/chat/completions` |
| T1-3 | vLLM chat (stream) | `curl --no-buffer` + SSE 확인 |
| T1-4 | vLLM `/v1/models` | 로드된 모델 확인 |

### 2.2 T2: Gateway 프록시

| ID | 검증 항목 | 방법 |
|----|----------|------|
| T2-1 | Gateway → vLLM 비스트리밍 프록시 | Gateway 포트로 chat/completions 요청 |
| T2-2 | Gateway → vLLM SSE 스트리밍 프록시 | `stream: true` 요청, SSE 청크 확인 + **TTFT 측정** (vLLM 직접 vs Gateway 경유, 차이 100ms 이내 확인) |
| T2-3 | Gateway 인증 | 유효/무효 API key 테스트 |
| T2-4 | Gateway Rate Limiting | 한도 초과 시 429 + `X-RateLimit-*` 헤더 |
| T2-5 | Gateway 사용량 로깅 | structlog JSON 출력 확인 |

### 2.3 T3: Model Management E2E

| ID | 검증 항목 | 방법 |
|----|----------|------|
| T3-1 | `myaicoder model list` | 모델 목록 + 로드 상태 |
| T3-2 | `myaicoder model launch` | 기본 모델 vLLM 시작 |
| T3-3 | `myaicoder model switch` | 모델 전환 (stop → start) |
| T3-4 | Gateway reload 동기화 | switch 직후 **sleep 없이 즉시** Gateway에 요청 → 새 모델로 라우팅 확인 (race condition 검증) |
| T3-5 | `myaicoder model status` | 현재 상태 조회 |

### 2.4 T4: MCP 서버

**주의**: MCP stdio 통신에서 `print()`나 Logger가 stdout에 출력하면 JSON-RPC 파싱이 깨진다. 테스트 전 모든 로깅이 **stderr 또는 파일**로 빠지는지 반드시 확인.

| ID | 검증 항목 | 방법 |
|----|----------|------|
| T4-0 | **stdout 오염 검증** | MCP 서버 모듈 내 print/logger가 stdout에 출력하지 않는지 확인 |
| T4-1 | MCP 서버 시작 | `myaicoder serve --transport stdio` |
| T4-2 | 도구 목록 | MCP 프로토콜로 도구 발견 |
| T4-3 | 도구 실행 (Read) | 파일 읽기 도구 호출 |
| T4-4 | 도구 실행 (Glob) | 파일 검색 도구 호출 |

### 2.5 T5: CLI E2E

| ID | 검증 항목 | 방법 |
|----|----------|------|
| T5-1 | `myaicoder -p "Hello"` | 원샷 모드 응답 |
| T5-2 | `myaicoder --no-stream -p "Hello"` | 비스트리밍 모드 |
| T5-3 | `myaicoder config` | 설정 출력 |

## 3. 전제 조건

### 3.1 하드웨어

- dev 환경: 24GB VRAM GPU (현재 데스크탑)
- `~/models/Qwen3.5-9B-Q4_K_M.gguf` 존재 (5.3GB, VRAM에 적합)

### 3.2 소프트웨어

- vLLM 설치 (`pip install vllm` 또는 별도 환경)
- Gateway 실행 가능 (`uvicorn app.main:app`)
- CLI 실행 가능 (`myaicoder`)

### 3.3 설정 파일

- `config/gateway.yaml` — 실환경 설정 (auth users, internal_token, rate_limit)
- `config/models.yaml` — dev 환경 모델 프로필

## 4. 실행 순서

```
Phase 1: 기반 확인
  ├─ vLLM 설치 확인
  ├─ GGUF 모델 파일 존재 확인
  └─ config/ 설정 파일 준비

Phase 2: vLLM 직접 통신 (T1)
  ├─ vLLM 서버 수동 시작
  └─ curl로 직접 요청 테스트

Phase 3: Gateway 프록시 (T2)
  ├─ Gateway 서버 시작
  └─ Gateway 경유 요청 테스트

Phase 4: Model Management E2E (T3)
  ├─ myaicoder model launch
  ├─ myaicoder model switch
  └─ Gateway reload 확인

Phase 5: MCP 서버 (T4)
  └─ myaicoder serve 실행 + 도구 테스트

Phase 6: CLI E2E (T5)
  └─ myaicoder 원샷/스트리밍 테스트
```

## 5. 테스트 자동화 방침

### 5.1 자동화 가능 테스트

기존 skip된 테스트를 **환경 변수 기반**으로 활성화:

```python
# skipif(True) → skipif(환경변수 없음)
@pytest.mark.skipif(
    not os.environ.get("VLLM_INTEGRATION"),
    reason="Set VLLM_INTEGRATION=1 to run",
)
```

```bash
# 실환경 테스트 실행
VLLM_INTEGRATION=1 uv run pytest tests/test_llm -q
MCP_INTEGRATION=1 uv run pytest tests/test_mcp -q
```

### 5.2 수동 테스트

Gateway SSE 스트리밍, model switch E2E는 **수동 검증 스크립트**(`scripts/integration_test.sh`)로 제공:

```bash
#!/bin/bash
# Gateway + vLLM 통합 테스트
echo "=== T2-1: Non-streaming proxy ==="
curl -s http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen3.5-9b","messages":[{"role":"user","content":"Say hi"}]}'

echo "=== T2-2: Streaming proxy ==="
curl -N http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen3.5-9b","messages":[{"role":"user","content":"Say hi"}],"stream":true}'
```

## 6. 범위

### 6.1 In Scope

| # | 항목 | 우선순위 |
|---|------|----------|
| 1 | `config/` 실환경 설정 파일 준비 | P0 |
| 2 | 기존 skip 테스트를 환경변수 기반으로 전환 | P0 |
| 3 | Gateway 통합 테스트 추가 (실 vLLM 연동) | P0 |
| 4 | 수동 검증 스크립트 (`scripts/integration_test.sh`) | P0 |
| 5 | model switch E2E 검증 | P1 |
| 6 | MCP 서버 실통합 테스트 | P1 |

### 6.2 Out of Scope

| 항목 | 사유 |
|------|------|
| prod (DGX Spark) 환경 테스트 | 현재 접근 불가, dev 환경 우선 |
| 부하 테스트 / 성능 벤치마크 | 별도 feature |
| 외부 클라이언트 (Cursor, Claude Code) 연동 | 별도 검증 |

## 7. 성공 기준

- [ ] vLLM 서버에 직접 chat 요청이 응답된다 (T1)
- [ ] Gateway 경유 비스트리밍/스트리밍 요청이 정상 프록시된다 (T2)
- [ ] Rate Limiting 429 + 헤더가 실환경에서 동작한다 (T2-4)
- [ ] `myaicoder model launch/switch/status`가 실제 vLLM과 동작한다 (T3)
- [ ] 기존 skip 테스트가 환경변수로 활성화되어 통과한다
- [ ] 수동 검증 스크립트가 작성되어 있다

## 8. 리스크

| 리스크 | 영향 | 대응 |
|--------|------|------|
| vLLM 미설치 환경 | 테스트 불가 | 설치 가이드 제공, skip 유지 |
| GPU 메모리 부족 | 모델 로드 실패 | 9B 모델 사용 (5.3GB) |
| vLLM 시작 시간 | 테스트 느림 | 사전 시작 후 테스트 실행 |
| 포트 충돌 | 서버 시작 실패 | 설정 가능한 포트 사용 |
