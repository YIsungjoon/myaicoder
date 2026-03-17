# 연구: 동시 입력 및 다중 접속 문제 분석

**날짜**: 2026-03-17
**대상**: 실서비스 대화 로그 분석 (`KakaoTalk_Chat_2026-03-17-11-15-54.txt`)
**환경**: 다중 사용자 → Gateway (192.168.19.91:8080) → LLM Server

---

## 1. 로그에서 발견된 문제 (3가지)

### 문제 A: 생성 중 추가 입력 가능 (UI Lock 없음)

**증상**:
```
사용자: "전체 프로젝트 구조를 파악해조"   ← AI가 응답 생성 중
사용자: "무능력한자여"                    ← 바로 다음 입력
→ 500 Internal Server Error (연속 3회)
```

**원인 분석**:
- `webview/main.js:132-139` — `sendMessage()`에 락(lock) 없음
- 생성 중에도 Send 버튼 활성화, Enter 키 작동
- 동시에 여러 `agentic_task` MCP 호출이 발생
- `MCPServer.max_concurrent=1`인데 Extension에서 요청을 큐잉하지 않고 직접 전송

**영향 범위**:
- Extension Webview (`main.js`) — 입력 차단 없음
- Extension Host (`panel.ts`) — `handleUserMessage()`에 동시 실행 방지 없음

### 문제 B: 500 Internal Server Error 폭주

**증상**:
```
500 Error × 36회 (로그 전체 기준)
400 Error × 10회
MCP Timeout × 33회
```

**원인 분석**:

#### B-1. LLM 서버 과부하 (500 Error)
- 사용자 A가 agentic_task (도구 호출 포함, 수십 초 소요) 실행 중
- 사용자 B가 동시에 요청 → LLM 서버에 동시 추론 요청
- llama.cpp는 기본적으로 **단일 요청 순차 처리** — 동시 요청 시 OOM 또는 내부 에러
- Gateway가 upstream 500을 그대로 클라이언트에 전달

#### B-2. 컨텍스트 윈도우 초과 (400 Error)
- 500 에러 메시지들이 대화 히스토리에 누적
- ConversationManager에 에러 메시지가 쌓여 max_model_len 초과
- LLM 서버가 400 Bad Request 반환 (토큰 초과)

#### B-3. MCP Timeout 연쇄
- 앞선 요청이 LLM 서버를 점유 → 후속 요청 대기
- 대기 시간이 MCP 타임아웃(1시간이지만 LLM 레벨에서는 더 짧음) 초과
- `Request timed out` × 33회 연쇄 발생

### 문제 C: 동일 메시지 중복 전송

**증상**:
```
"리오레우스를 아니" → 에러
"리오레우스를 알고있니" → 에러
"리오레우스를 알고있니" → 에러 (동일 메시지 재전송)
"." × 30회 이상 연속
```

**원인 분석**:
- 에러 응답을 받은 사용자가 같은 메시지를 반복 전송
- UI에 "재시도" 또는 "서버 바쁨" 안내가 없어 사용자가 반복 클릭
- 에러 상태에서도 입력이 차단되지 않음

---

## 2. 문제 발생 레이어별 분석

```
[VS Code Extension]  ← 문제 A, C: UI Lock 없음, 중복 전송
       │
       │ MCP (stdio)
       │
[myaicoder serve]    ← max_concurrent=1 이지만 Extension이 무시
       │
       │ HTTP
       │
[Gateway :8080]      ← 문제 B: 동시 요청을 LLM에 그대로 전달
       │
       │ HTTP Proxy
       │
[llama.cpp :8001]    ← 단일 추론 서버, 동시 요청 시 500/OOM
```

---

## 3. 해결 방안 (레이어별)

### Layer 1: Extension Webview (UI Lock)

**현재**: `sendMessage()`에 제어 없음
**개선**:

```javascript
// webview/main.js 개선안
let isGenerating = false;

function sendMessage() {
  if (isGenerating) {
    // 생성 중이면 취소 요청
    vscode.postMessage({ type: 'cancelRequest' });
    return;
  }
  const text = messageInput.value.trim();
  if (!text) return;

  isGenerating = true;
  updateSendButton();  // "Send" → "■ Stop" 변경
  messageInput.disabled = true;

  vscode.postMessage({ type: 'sendMessage', text: text });
  messageInput.value = '';
}

function updateSendButton() {
  if (isGenerating) {
    sendBtn.textContent = 'Stop';
    sendBtn.classList.add('generating');
  } else {
    sendBtn.textContent = 'Send';
    sendBtn.classList.remove('generating');
  }
}

// setLoading 수신 시 상태 복원
case 'setLoading':
  isGenerating = message.loading;
  updateSendButton();
  messageInput.disabled = message.loading;
  break;
```

**CSS 추가**:
```css
#send-btn.generating {
  background: var(--vscode-errorForeground);
}
#message-input:disabled {
  opacity: 0.5;
}
```

### Layer 2: Extension Host (요청 큐잉)

**현재**: `panel.ts`의 `handleUserMessage()`가 동시 실행 가능
**개선**:

```typescript
// panel.ts 개선안
private isProcessing = false;

private async handleUserMessage(text: string): Promise<void> {
  if (this.isProcessing) {
    // 이미 처리 중 → 무시하거나 큐에 넣기
    return;
  }
  this.isProcessing = true;
  // ... 기존 로직 ...
  // finally 블록에서:
  this.isProcessing = false;
}
```

### Layer 3: MCP Server (Semaphore 활성화)

**현재**: `MCPServer.max_concurrent=1`, `_semaphore` 선언만 하고 미사용
**확인 필요**: `_semaphore`가 실제로 agentic_task에서 acquire/release 되는지

```python
# mcp/server.py 확인 포인트
# _semaphore가 agentic_task 핸들러에서 사용되는지?
# 미사용이면 활성화 필요:
async def _agentic_handler(prompt: str) -> str:
    if self._semaphore is None:
        self._semaphore = asyncio.Semaphore(self.max_concurrent)
    async with self._semaphore:
        return await self._run_agentic(prompt)
```

### Layer 4: Gateway (동시 요청 제어)

**현재 Rate Limiter**: RPM(요청/분) 기반 — 분당 30회
**문제**: 30회 미만이어도 동시(concurrent) 요청이 LLM 서버를 죽임

**개선안 — Concurrent Request Limiter 추가**:

```python
# gateway/app/concurrency.py (신규)
import asyncio
from collections import defaultdict

class ConcurrencyLimiter:
    """사용자별 + 전역 동시 요청 제한"""

    def __init__(self, max_per_user: int = 1, max_global: int = 4):
        self._user_sems: dict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(max_per_user)
        )
        self._global_sem = asyncio.Semaphore(max_global)

    async def acquire(self, user_id: str) -> None:
        await self._global_sem.acquire()
        await self._user_sems[user_id].acquire()

    def release(self, user_id: str) -> None:
        self._user_sems[user_id].release()
        self._global_sem.release()
```

- `max_per_user=1`: 동일 사용자는 동시 1개만 LLM 요청 가능
- `max_global=4`: 전체 사용자 합산 동시 4개 (llama.cpp 배치 처리 한계)
- 초과 시 **503 Service Unavailable** + `Retry-After` 헤더
- Rate Limiter(RPM)와는 독립적으로 동작

### Layer 5: LLM 서버 (llama.cpp 설정)

**현재 문제**: 동시 추론 요청 시 500 에러
**설정 확인 필요**:

```bash
# llama-server 실행 옵션
--parallel N        # 동시 처리 슬롯 수 (기본값: 1)
--cont-batching     # Continuous batching 활성화
```

- `--parallel 1`(기본값)이면 동시 요청 시 reject → 500
- `--parallel 2~4`로 늘리면 메모리 사용량 증가하지만 동시 처리 가능
- 메모리 부족 시 `--parallel 1` 유지하고 Gateway에서 큐잉

---

## 4. 에러 메시지 대화 히스토리 오염 방지

**문제**: 500/400 에러 메시지가 ConversationManager에 쌓여 컨텍스트 오염

**개선안**:
1. **Extension**: 에러 응답은 UI에만 표시하고 대화 히스토리에 추가하지 않음
2. **AgentEngine**: 에러 메시지를 conversation에 추가하지 않도록 수정
3. **Gateway**: 500 에러 시 `Retry-After` 헤더 + 사용자 친화적 에러 메시지 반환

---

## 5. 우선순위별 구현 계획

| 순위 | 레이어 | 작업 | 효과 |
|------|--------|------|------|
| **P0** | Extension Webview | Send 버튼 잠금 + Stop 전환 | 사용자 중복 입력 원천 차단 |
| **P0** | Extension Host | `isProcessing` 가드 | 동시 MCP 호출 방지 |
| **P1** | Gateway | ConcurrencyLimiter 추가 | 다중 사용자 동시 요청 제어 |
| **P1** | Gateway | 에러 응답 개선 (503 + Retry-After) | 사용자 경험 개선 |
| **P2** | MCP Server | Semaphore 실제 활성화 확인 | 이중 안전장치 |
| **P2** | LLM 서버 | `--parallel` 옵션 검토 | 동시 처리 능력 향상 |
| **P3** | ConversationManager | 에러 메시지 히스토리 제외 | 컨텍스트 오염 방지 |

---

## 6. 참고: 로그 통계

| 항목 | 수치 |
|------|------|
| 총 사용자 입력 | ~25회 |
| 성공 응답 | ~5회 |
| 500 Internal Server Error | 36회 |
| 400 Bad Request | 10회 |
| MCP Timeout (-32001) | 33회 |
| 에러율 | ~94% |

**핵심 원인**: UI에서 생성 중 입력을 차단하지 않아 동시 요청이 쌓이고, LLM 서버가 과부하로 500을 반환하며, 이 에러가 대화 히스토리를 오염시켜 400으로 전이됨.

---

*작성일: 2026-03-17 | 유형: 연구/분석 문서*
