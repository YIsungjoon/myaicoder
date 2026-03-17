# Plan: 동시 접속 제어 (Concurrent Access Control)

**Feature**: concurrent-access-control
**날짜**: 2026-03-17
**Phase**: Plan
**Level**: Enterprise
**연구 문서**: `docs/research-concurrent-access-2026-03-17.md`

---

## 1. 개요

실서비스 로그 분석 결과, AI 응답 생성 중 사용자가 추가 입력을 보낼 수 있어 동시 요청이 LLM 서버를 폭주시키는 문제를 해결한다. Extension UI Lock, Extension Host 요청 가드, Gateway 동시 요청 제한을 구현한다.

**실서비스 에러 통계** (2026-03-17 로그):
- 500 Internal Server Error: 36회
- 400 Bad Request: 10회
- MCP Timeout: 33회
- 에러율: 94%

## 2. 근본 원인

```
UI 중복 입력 → 동시 MCP 호출 → LLM 과부하 (500) → 히스토리 오염 (400) → Timeout 연쇄
```

## 3. 핵심 요구사항

### 3.1 기능 요구사항

| ID | 기능 | 설명 | 우선순위 |
|----|------|------|----------|
| FR-01 | **Send 버튼 상태 전환** | 생성 중 "Send" → "Stop"으로 변경, 클릭 시 요청 취소 | P0 |
| FR-02 | **입력 비활성화** | 생성 중 textarea 비활성화 (Enter 키 포함) | P0 |
| FR-03 | **Extension Host 요청 가드** | `handleUserMessage()` 동시 실행 방지 (`isProcessing` 플래그) | P0 |
| FR-04 | **요청 취소 (Cancel)** | Stop 클릭 시 진행 중인 MCP 호출 취소, UI 즉시 복원 | P0 |
| FR-05 | **Gateway Concurrency Limiter** | 사용자별 동시 1개, 전역 동시 N개 LLM 요청 제한 | P1 |
| FR-06 | **503 Service Unavailable 응답** | 동시 제한 초과 시 503 + `Retry-After` 헤더 | P1 |
| FR-07 | **에러 히스토리 제외** | 500/400 에러 응답을 대화 히스토리에 추가하지 않음 | P1 |

### 3.2 비기능 요구사항

| ID | 항목 | 기준 |
|----|------|------|
| NFR-01 | 기존 기능 호환 | 단일 사용자 정상 플로우 100% 유지 |
| NFR-02 | Stop 반응 속도 | Stop 클릭 후 UI 복원 < 500ms |
| NFR-03 | Gateway 503 응답 | 제한 초과 시 < 100ms 내 응답 |

## 4. 구현 범위

### 4.1 In Scope (이번 피처)

| # | 레이어 | 작업 | 파일 |
|---|--------|------|------|
| 1 | Webview | Send/Stop 토글 + 입력 비활성화 | `webview/main.js`, `webview/style.css` |
| 2 | Webview | Cancel 메시지 전송 | `webview/main.js` |
| 3 | Extension Host | `isProcessing` 가드 | `src/chat/panel.ts` |
| 4 | Extension Host | Cancel 처리 (AbortController 패턴) | `src/chat/panel.ts` |
| 5 | chat/types.ts | `cancelRequest` 메시지 타입 활성화 | `src/chat/types.ts` |
| 6 | Gateway | ConcurrencyLimiter 미들웨어 | `services/gateway/app/concurrency.py` (신규) |
| 7 | Gateway | 503 응답 + Retry-After | `services/gateway/app/routes/v1.py` |
| 8 | Extension Host | 에러 응답 히스토리 제외 | `src/chat/panel.ts` |

### 4.2 Out of Scope

| 항목 | 사유 |
|------|------|
| llama.cpp `--parallel` 설정 변경 | 인프라 설정, 별도 작업 |
| MCP Server Semaphore 활성화 | 별도 피처 |
| 토큰 기반 Rate Limiting | 로드맵 B-2에서 진행 |

## 5. 기술 설계 방향

### 5.1 Webview (main.js) — Send/Stop 토글

```
상태 흐름:
  IDLE ──(Send 클릭)──> GENERATING ──(응답 수신)──> IDLE
                            │
                      (Stop 클릭)
                            │
                            v
                        CANCELLING ──(취소 확인)──> IDLE
```

- `isGenerating` 플래그로 상태 관리
- 생성 중: 버튼 텍스트 "Stop", 빨간 배경, textarea disabled
- Stop 클릭: `cancelRequest` 메시지 전송
- `setLoading(false)` 수신 시: 상태 복원

### 5.2 Extension Host (panel.ts) — 요청 가드 + Cancel

```typescript
private isProcessing = false;
private currentAbortController: AbortController | null = null;

handleUserMessage():
  if (isProcessing) return;  // 중복 방지
  isProcessing = true;
  currentAbortController = new AbortController();
  try {
    result = await mcpClient.callTool(...);  // AbortSignal 전달
  } finally {
    isProcessing = false;
    currentAbortController = null;
  }

handleCancel():
  currentAbortController?.abort();
  isProcessing = false;
  postMessage({ type: 'setLoading', loading: false });
```

### 5.3 Gateway — ConcurrencyLimiter

```python
class ConcurrencyLimiter:
    def __init__(self, max_per_user=1, max_global=4):
        self._user_sems = defaultdict(lambda: asyncio.Semaphore(max_per_user))
        self._global_sem = asyncio.Semaphore(max_global)
```

- FastAPI dependency로 주입
- `max_per_user=1`: 동일 API Key 동시 1개
- `max_global=4`: 전체 합산 동시 4개
- 초과 시 즉시 503 반환 (대기하지 않음)

### 5.4 에러 히스토리 제외

```typescript
// panel.ts handleUserMessage()
if (result.isError) {
  // UI에는 표시하되 messages 배열에는 추가하지 않음
  this.postMessage({ type: 'addMessage', message: errorMsg });
  // this.messages.push(errorMsg);  ← 제거
}
```

## 6. 기술적 리스크

| 리스크 | 영향 | 완화 |
|--------|------|------|
| MCP callTool에 AbortSignal 미지원 | Cancel이 실제로 MCP 호출을 중단하지 못할 수 있음 | UI만 즉시 복원, 백그라운드 호출은 완료되도록 허용 |
| Gateway 503이 Extension에서 재시도 유발 | 무한 재시도 루프 가능 | Extension에서 503 수신 시 재시도하지 않고 사용자에게 안내 |
| ConcurrencyLimiter 전역 제한이 너무 작으면 | 정상 다중 사용자도 거부됨 | 설정 가능하게 구현 (gateway.yaml) |

## 7. 마일스톤

| Step | 작업 | 산출물 |
|------|------|--------|
| 1 | Webview Send/Stop 토글 + 입력 비활성화 | `main.js`, `style.css` |
| 2 | Extension Host `isProcessing` + Cancel | `panel.ts` |
| 3 | 에러 히스토리 제외 | `panel.ts` |
| 4 | Gateway ConcurrencyLimiter | `concurrency.py` (신규) |
| 5 | Gateway 라우트에 Concurrency 적용 | `routes/v1.py`, `deps.py` |
| 6 | 빌드/테스트 검증 | Extension + Gateway 테스트 |

## 8. 결정 사항

- [x] **Cancel은 UI 레벨만 즉시 복원** (2026-03-17)
  - MCP SDK에 AbortSignal 전달이 복잡하므로, UI만 즉시 풀고 백그라운드 완료 허용
  - 향후 MCP SDK Cancel 지원 시 개선
- [x] **503 즉시 반환 (대기 없음)** (2026-03-17)
  - 큐잉보다 즉시 거부가 사용자 경험에 더 나음 (무한 대기 방지)
- [x] **에러 응답 UI에만 표시** (2026-03-17)
  - 대화 히스토리 오염이 400 에러 연쇄의 근본 원인

---

*작성일: 2026-03-17 | Phase: Plan | Status: All Decisions Made*
