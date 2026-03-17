# Design: 동시 접속 제어 (Concurrent Access Control)

**Feature**: concurrent-access-control
**날짜**: 2026-03-17
**Phase**: Design
**Plan 참조**: `docs/pdca/01-plan/features/concurrent-access-control.plan.md`

---

## 1. 변경 파일 목록

| # | 파일 | 변경 유형 | 설명 |
|---|------|-----------|------|
| 1 | `apps/vscode-extension/webview/main.js` | 수정 | Send/Stop 토글, 입력 비활성화, cancelRequest |
| 2 | `apps/vscode-extension/webview/style.css` | 수정 | Stop 버튼 스타일, disabled 입력 스타일 |
| 3 | `apps/vscode-extension/src/chat/panel.ts` | 수정 | isProcessing 가드, Cancel 처리, 에러 히스토리 제외 |
| 4 | `services/gateway/app/concurrency.py` | **신규** | ConcurrencyLimiter 클래스 |
| 5 | `services/gateway/app/deps.py` | 수정 | check_concurrency 의존성 추가 |
| 6 | `services/gateway/app/routes/v1.py` | 수정 | concurrency 의존성 적용 |
| 7 | `services/gateway/app/main.py` | 수정 | ConcurrencyLimiter 초기화 |
| 8 | `services/gateway/app/config.py` | 수정 | concurrency 설정 추가 |

---

## 2. 상세 설계

### 2.1 `webview/main.js` 변경

```javascript
// 추가할 상태 변수
let isGenerating = false;

// sendMessage() 함수 전체 교체
function sendMessage() {
  if (isGenerating) {
    // Stop 클릭 → 취소 요청
    vscode.postMessage({ type: 'cancelRequest' });
    return;
  }
  const text = messageInput.value.trim();
  if (!text) return;

  isGenerating = true;
  updateSendButton();
  messageInput.disabled = true;

  vscode.postMessage({ type: 'sendMessage', text: text });
  messageInput.value = '';
  messageInput.style.height = 'auto';
}

// 신규 함수
function updateSendButton() {
  if (isGenerating) {
    sendBtn.textContent = 'Stop';
    sendBtn.classList.add('generating');
  } else {
    sendBtn.textContent = 'Send';
    sendBtn.classList.remove('generating');
    messageInput.disabled = false;
    messageInput.focus();
  }
}

// keydown 핸들러 수정 — disabled 상태에서 Enter 차단
messageInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    if (!isGenerating) {
      sendMessage();
    }
  }
});

// setLoading 메시지 핸들러 수정
case 'setLoading':
  setLoading(message.loading);
  isGenerating = message.loading;
  updateSendButton();
  break;
```

### 2.2 `webview/style.css` 추가

```css
/* Stop 버튼 스타일 */
#send-btn.generating {
  background: var(--vscode-errorForeground);
}

/* 비활성화된 입력 */
#message-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
```

### 2.3 `src/chat/panel.ts` 변경

#### 2.3.1 isProcessing 가드 + Cancel

```typescript
// 클래스 멤버 추가
private isProcessing = false;
private cancelRequested = false;

// handleUserMessage() 수정
private async handleUserMessage(text: string): Promise<void> {
  if (this.isProcessing) {
    return; // 중복 요청 무시
  }
  this.isProcessing = true;
  this.cancelRequested = false;

  // ... 기존 userMsg 추가 로직 ...

  try {
    this.postMessage({ type: 'setLoading', loading: true });

    // ... 기존 MCP callTool 로직 ...

    // Cancel 체크: MCP 호출 후 결과 처리 전
    if (this.cancelRequested) {
      return; // 결과 버리고 종료
    }

    const aiMsg: ChatMessage = { ... };
    // 에러 응답이면 히스토리에 추가하지 않음
    if (!result.isError) {
      this.messages.push(aiMsg);
    }
    this.postMessage({ type: 'addMessage', message: aiMsg });
  } catch (error) {
    if (this.cancelRequested) {
      return; // Cancel에 의한 에러는 무시
    }
    const errorMsg: ChatMessage = { ... };
    // 에러는 UI에만 표시, 히스토리에 추가하지 않음
    this.postMessage({ type: 'addMessage', message: errorMsg });
  } finally {
    this.isProcessing = false;
    this.cancelRequested = false;
    this.postMessage({ type: 'setLoading', loading: false });
  }
}
```

#### 2.3.2 Cancel 처리

```typescript
// resolveWebviewView() 내 onDidReceiveMessage switch에 추가
case 'cancelRequest':
  this.cancelRequested = true;
  this.isProcessing = false;
  this.postMessage({ type: 'setLoading', loading: false });
  // 취소 안내 메시지 (히스토리에 추가하지 않음)
  this.postMessage({
    type: 'addMessage',
    message: {
      role: 'assistant',
      content: 'Request cancelled.',
      timestamp: Date.now(),
    },
  });
  break;
```

#### 2.3.3 에러 히스토리 제외 로직

```
기존: result.isError → this.messages.push(errorMsg) → 히스토리 오염
변경: result.isError → postMessage만 (UI 표시) → this.messages.push 생략
```

### 2.4 `services/gateway/app/concurrency.py` (신규)

```python
"""Per-user and global concurrency limiter for LLM requests."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict

import structlog

logger = structlog.get_logger("gateway.concurrency")


class ConcurrencyLimiter:
    """Limits concurrent in-flight LLM requests.

    - max_per_user: max concurrent requests per API key (default: 1)
    - max_global: max concurrent requests across all users (default: 4)

    Uses try_acquire (non-blocking). Returns immediately if limit exceeded.
    """

    def __init__(self, max_per_user: int = 1, max_global: int = 4):
        self.max_per_user = max_per_user
        self.max_global = max_global
        self._user_counts: dict[str, int] = defaultdict(int)
        self._global_count = 0
        self._lock = asyncio.Lock()

    async def try_acquire(self, user_id: str) -> bool:
        """Try to acquire a slot. Returns False if limit exceeded (non-blocking)."""
        async with self._lock:
            if self._global_count >= self.max_global:
                logger.warning(
                    "concurrency_global_exceeded",
                    user_id=user_id,
                    current=self._global_count,
                    max=self.max_global,
                )
                return False
            if self._user_counts[user_id] >= self.max_per_user:
                logger.warning(
                    "concurrency_user_exceeded",
                    user_id=user_id,
                    current=self._user_counts[user_id],
                    max=self.max_per_user,
                )
                return False
            self._user_counts[user_id] += 1
            self._global_count += 1
            return True

    async def release(self, user_id: str) -> None:
        """Release a slot after request completes."""
        async with self._lock:
            self._user_counts[user_id] = max(0, self._user_counts[user_id] - 1)
            self._global_count = max(0, self._global_count - 1)
            if self._user_counts[user_id] == 0:
                del self._user_counts[user_id]
```

### 2.5 `services/gateway/app/deps.py` 변경

```python
# 추가 import
from .concurrency import ConcurrencyLimiter

# 신규 의존성 함수
async def check_concurrency(request: Request) -> None:
    """Check concurrency limit. Raises 503 if exceeded (non-blocking)."""
    limiter: ConcurrencyLimiter | None = getattr(
        request.app.state, "concurrency_limiter", None
    )
    if limiter is None:
        return

    user: User = request.state.user
    acquired = await limiter.try_acquire(user.user_id)
    if not acquired:
        raise HTTPException(
            status_code=503,
            detail="Server busy. Please retry in a few seconds.",
            headers={"Retry-After": "5"},
        )
    # Mark for release in finally block
    request.state.concurrency_acquired = True
```

### 2.6 `services/gateway/app/routes/v1.py` 변경

```python
# import 추가
from ..deps import check_concurrency, check_rate_limit, get_current_user

# router dependencies에 check_concurrency 추가
router = APIRouter(
    prefix="/v1",
    dependencies=[
        Depends(get_current_user),
        Depends(check_rate_limit),
        Depends(check_concurrency),
    ],
)

# chat_completions에 finally로 concurrency 해제
@router.post("/chat/completions")
async def chat_completions(request: Request) -> Response:
    try:
        # ... 기존 로직 유지 ...
    finally:
        # Concurrency slot 해제
        limiter = getattr(request.app.state, "concurrency_limiter", None)
        if limiter and getattr(request.state, "concurrency_acquired", False):
            await limiter.release(request.state.user.user_id)
```

### 2.7 `services/gateway/app/main.py` 변경

```python
# lifespan 또는 startup에서 초기화
from .concurrency import ConcurrencyLimiter

app.state.concurrency_limiter = ConcurrencyLimiter(
    max_per_user=config.concurrency.max_per_user,
    max_global=config.concurrency.max_global,
)
```

### 2.8 `services/gateway/app/config.py` 변경

```python
# Pydantic 모델 추가
class ConcurrencyConfig(BaseModel):
    max_per_user: int = 1
    max_global: int = 4

class GatewayConfig(BaseModel):
    # ... 기존 필드 ...
    concurrency: ConcurrencyConfig = ConcurrencyConfig()
```

---

## 3. 상태 흐름도

### 3.1 Webview 상태 머신

```
         Send 클릭
  IDLE ──────────> GENERATING
   ^                   │
   │                   │ setLoading(false) 수신
   │                   v
   └──────────── IDLE (복원)
                   ^
                   │ Stop 클릭 → cancelRequest 전송
                   │
  IDLE <──── GENERATING
```

### 3.2 Extension Host 요청 흐름

```
handleUserMessage(text)
  │
  ├─ isProcessing == true → return (무시)
  │
  ├─ isProcessing = true
  ├─ postMessage(setLoading: true)
  ├─ await mcpClient.callTool(...)
  │     │
  │     ├─ cancelRequested → return (결과 버림)
  │     ├─ result.isError → UI에만 표시 (히스토리 제외)
  │     └─ success → messages.push + UI 표시
  │
  └─ finally: isProcessing = false, postMessage(setLoading: false)
```

### 3.3 Gateway 동시 요청 흐름

```
POST /v1/chat/completions
  │
  ├─ get_current_user (인증)
  ├─ check_rate_limit (RPM/RPH)
  ├─ check_concurrency
  │     ├─ try_acquire → true → 계속
  │     └─ try_acquire → false → 503 Service Unavailable
  │
  ├─ forward_request / stream_upstream
  │
  └─ finally: concurrency_limiter.release()
```

---

## 4. 구현 순서

| Step | 작업 | 의존성 |
|------|------|--------|
| 1 | `webview/main.js` + `style.css`: Send/Stop 토글, 입력 비활성화 | 없음 |
| 2 | `panel.ts`: isProcessing 가드 + cancelRequest 처리 | 없음 |
| 3 | `panel.ts`: 에러 히스토리 제외 | Step 2 |
| 4 | `concurrency.py`: ConcurrencyLimiter 클래스 | 없음 |
| 5 | `deps.py` + `config.py`: check_concurrency 의존성 + 설정 | Step 4 |
| 6 | `routes/v1.py` + `main.py`: concurrency 적용 + 초기화 | Step 5 |
| 7 | Extension 빌드/테스트 검증 | Step 1-3 |
| 8 | Gateway 테스트 검증 | Step 4-6 |

---

*작성일: 2026-03-17 | Phase: Design | Status: Complete*
