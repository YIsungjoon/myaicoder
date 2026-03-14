# Design: context-management

**Feature**: context-management
**날짜**: 2026-03-14
**Phase**: Design
**Level**: Enterprise
**Plan Reference**: `docs/pdca/01-plan/features/context-management.plan.md`

---

## 1. 설계 개요

ConversationManager를 확장하여 **토큰 예산 제어**와 **턴 기반 압축**을 구현한다.

### 핵심 설계 제약

| 제약 | 해결 |
|------|------|
| **도구 호출 원자성** | 메시지를 Turn(블록) 단위로 그루핑, 블록 단위로만 제거/압축 |
| **LLM 호출 없이 압축** | 규칙 기반 요약 (지연 0ms, 결정론적) |
| **하위 호환** | 기존 ConversationManager API 유지 |

### 변경 범위

| 파일 | 변경 |
|------|------|
| `core/conversation.py` | Turn 그루핑, 압축 로직, 토큰 예산 제어 |
| `core/engine.py` | ContextConfig 연결, 압축 알림 콜백 |
| `cli.py` | `/compact` 명령, 압축 알림 UI |
| `tests/test_core/test_conversation.py` | 압축/턴 그루핑 테스트 |

## 2. Turn(턴) 기반 메시지 그루핑

### 2.1 핵심 개념: 원자적 턴

OpenAI 호환 API에서 도구 호출은 **3종 메시지가 하나의 원자 단위**:

```
Turn (Atomic Block):
  ┌─ User message
  ├─ Assistant (tool_calls=[{id:"call_1"}, {id:"call_2"}])
  ├─ Tool (tool_call_id="call_1")
  ├─ Tool (tool_call_id="call_2")
  └─ Assistant (final text response, no tool_calls)
```

**절대 금지**: 이 블록을 중간에서 분리하면 `400 Bad Request: missing tool_call_id` 에러.

### 2.2 Turn 데이터 구조

```python
@dataclass
class Turn:
    """An atomic conversation turn — cannot be split."""
    messages: list[Message]
    token_estimate: int

    @property
    def is_tool_turn(self) -> bool:
        """Contains tool calls (multi-message block)."""
        return any(m.tool_calls for m in self.messages)

    def summarize(self) -> str:
        """Rule-based summary of this turn."""
        # ... 규칙 기반 요약
```

### 2.3 그루핑 알고리즘

```python
def _group_into_turns(self, messages: list[Message]) -> list[Turn]:
    """Group flat message list into atomic Turn blocks.

    Rules:
    1. User message starts a new turn
    2. Assistant with tool_calls + subsequent Tool messages = same turn
    3. Assistant without tool_calls (final response) = same turn as preceding
    4. Orphan tool messages (shouldn't happen) = attach to previous turn
    """
```

예시:

```
Message List:
  [0] user: "파일 읽어줘"
  [1] assistant: (tool_calls=[{id:c1, name:Read}])
  [2] tool: (tool_call_id=c1, content="file contents...")
  [3] assistant: "파일 내용은 다음과 같습니다..."
  [4] user: "이걸 수정해줘"
  [5] assistant: "네, 수정하겠습니다."

→ Turn 그루핑 결과:
  Turn 0: [msg 0, 1, 2, 3]  ← 도구 호출 포함 블록 (원자적)
  Turn 1: [msg 4, 5]        ← 단순 대화 블록
```

## 3. 압축 전략 상세

### 3.1 압축 트리거

```python
def get_messages(self, system_prompt: str) -> list[Message]:
    """Build message list. Compress if over threshold."""
    system_tokens = len(system_prompt) // 4
    tool_schema_reserve = self._tool_schema_tokens
    response_reserve = self._response_buffer
    available = self._max_tokens - system_tokens - tool_schema_reserve - response_reserve

    if self.estimate_tokens() > available * self._compression_threshold:
        self._compress(target_tokens=int(available * 0.6))

    messages = [Message(role="system", content=system_prompt)]
    if self._summary:
        messages.append(Message(
            role="system",
            content=f"[Previous conversation summary]\n{self._summary}",
        ))
    messages.extend(self._history)
    return messages
```

### 3.2 압축 실행 (`_compress`)

```python
def _compress(self, target_tokens: int) -> None:
    """Compress history to fit within target_tokens.

    Strategy:
    1. Group messages into Turn blocks
    2. Keep recent N turns intact (sliding window)
    3. Summarize older turns into summary prefix
    4. Never split a Turn block (atomicity)
    """
    turns = self._group_into_turns(self._history)

    # Find split point: keep recent turns within budget
    kept_tokens = 0
    split_idx = len(turns)

    for i in range(len(turns) - 1, -1, -1):
        if kept_tokens + turns[i].token_estimate > target_tokens:
            break
        kept_tokens += turns[i].token_estimate
        split_idx = i

    # Turns to compress (older) and keep (recent)
    old_turns = turns[:split_idx]
    recent_turns = turns[split_idx:]

    # Generate summary from old turns
    if old_turns:
        summaries = [t.summarize() for t in old_turns]
        self._summary = "\n".join(summaries)

    # Rebuild history from recent turns only
    self._history = []
    for turn in recent_turns:
        self._history.extend(turn.messages)

    self._compression_count += 1
```

### 3.3 Turn 요약 규칙 (`Turn.summarize`)

```python
def summarize(self) -> str:
    """Rule-based summary (no LLM call)."""
    parts: list[str] = []

    for msg in self.messages:
        if msg.role == "user":
            # 사용자 질문: 첫 100자
            text = (msg.content or "")[:100]
            parts.append(f"User: {text}")

        elif msg.role == "assistant" and msg.tool_calls:
            # 도구 호출: 도구 이름만
            tool_names = [tc.name for tc in msg.tool_calls]
            parts.append(f"Assistant called: {', '.join(tool_names)}")

        elif msg.role == "tool":
            # 도구 결과: 도구 ID + 결과 크기
            content_len = len(msg.content or "")
            parts.append(f"Tool result: {content_len} chars")

        elif msg.role == "assistant":
            # 최종 응답: 첫 100자
            text = (msg.content or "")[:100]
            parts.append(f"Assistant: {text}")

    return " → ".join(parts)
```

예시 출력:
```
User: 파일 읽어줘 → Assistant called: Read → Tool result: 5000 chars → Assistant: 파일 내용은 다음과 같습니다. 이 코드는...
```

## 4. ConversationManager 확장

### 4.1 수정된 클래스 구조

```python
class ConversationManager:
    """Manages conversation history with token budget and compression."""

    def __init__(
        self,
        max_tokens: int = 32768,
        compression_threshold: float = 0.8,
        tool_schema_tokens: int = 1000,
        response_buffer: int = 4000,
    ):
        self._history: list[Message] = []
        self._summary: str = ""                    # 신규: 압축된 과거 요약
        self._max_tokens = max_tokens
        self._compression_threshold = compression_threshold
        self._tool_schema_tokens = tool_schema_tokens
        self._response_buffer = response_buffer
        self._compression_count: int = 0           # 신규: 압축 횟수
        self._on_compress: Callable[[int], None] | None = None  # 신규: 압축 콜백

    # ── 기존 API (하위 호환) ──

    def add_message(self, message: Message) -> None:
        self._history.append(message)

    def get_messages(self, system_prompt: str) -> list[Message]:
        """Build message list. Auto-compress if over threshold."""
        # ... 압축 체크 + 메시지 빌드 (위 3.1 참조)

    def clear(self) -> None:
        self._history.clear()
        self._summary = ""
        self._compression_count = 0

    @property
    def history(self) -> list[Message]:
        return list(self._history)

    @property
    def message_count(self) -> int:
        return len(self._history)

    def estimate_tokens(self) -> int:
        total = sum(len(m.content or "") for m in self._history)
        total += len(self._summary)
        return total // 4

    # ── 신규 API ──

    def compact(self) -> int:
        """Manual compression trigger. Returns tokens freed."""
        before = self.estimate_tokens()
        available = self._max_tokens - self._response_buffer - self._tool_schema_tokens
        self._compress(target_tokens=int(available * 0.5))
        return before - self.estimate_tokens()

    @property
    def compression_count(self) -> int:
        return self._compression_count

    @property
    def summary(self) -> str:
        return self._summary

    def set_on_compress(self, callback: Callable[[int], None]) -> None:
        """Set callback for compression notification."""
        self._on_compress = callback

    # ── Internal ──

    def _compress(self, target_tokens: int) -> None:
        # ... (위 3.2 참조)

    def _group_into_turns(self, messages: list[Message]) -> list[Turn]:
        # ... (위 2.3 참조)
```

## 5. Engine 연결

### 5.1 ContextConfig 활성화

```python
class AgentEngine:
    def __init__(self, ..., context_config: ContextConfig | None = None):
        config = context_config or ContextConfig()
        self.conversation = ConversationManager(
            max_tokens=config.max_tokens,
            compression_threshold=config.compression_threshold,
        )
```

### 5.2 CLI에서 Config 전달

```python
# cli.py — _run_chat()
engine = AgentEngine(
    llm=llm,
    context_manager=context,
    tool_registry=tool_registry,
    context_config=config.context,  # ContextConfig 연결
)

# 압축 알림 콜백
engine.conversation.set_on_compress(
    lambda freed: ui.print_info(f"Context compressed ({freed} tokens freed)")
)
```

## 6. CLI 명령 추가

```python
# cli.py — _handle_command() 수정
if cmd == "/compact":
    freed = engine.conversation.compact()
    ui.print_info(f"Compressed: {freed} tokens freed")
    return True

if cmd == "/tokens":
    tokens = engine.conversation.estimate_tokens()
    max_t = engine.conversation._max_tokens
    pct = tokens / max_t * 100 if max_t else 0
    ui.print_info(f"Tokens: {tokens}/{max_t} ({pct:.0f}%)")
    return True
```

## 7. 테스트 전략

### 7.1 단위 테스트

| 테스트 | 대상 | 주요 케이스 |
|--------|------|-----------|
| `test_turn_grouping` | `_group_into_turns` | 단순 대화, 도구 호출 블록, 다중 도구, 빈 히스토리 |
| `test_turn_atomicity` | `_group_into_turns` | tool_calls와 tool 메시지가 항상 같은 Turn |
| `test_turn_summarize` | `Turn.summarize` | user/assistant/tool 각 타입 요약 |
| `test_compress_basic` | `_compress` | 압축 후 토큰 감소, 요약 생성 |
| `test_compress_preserves_recent` | `_compress` | 최근 턴 보존, 오래된 턴 제거 |
| `test_compress_tool_atomicity` | `_compress` | 도구 호출 블록이 분리되지 않음 |
| `test_auto_compress_threshold` | `get_messages` | threshold 초과 시 자동 압축 |
| `test_compact_manual` | `compact()` | 수동 압축 |
| `test_summary_in_messages` | `get_messages` | 요약이 system 메시지로 포함됨 |
| `test_backward_compat` | 기존 API | add_message, clear, history, estimate_tokens |

### 7.2 핵심 테스트: 도구 호출 원자성

```python
def test_compress_never_splits_tool_block():
    """Tool calls + tool results must stay together or be compressed together."""
    cm = ConversationManager(max_tokens=100)

    # Turn with tool call (should be atomic)
    cm.add_message(Message(role="user", content="read file"))
    cm.add_message(Message(
        role="assistant", content=None,
        tool_calls=[ToolCall(id="c1", name="Read", arguments={"path": "/a"})],
    ))
    cm.add_message(Message(role="tool", content="file contents...", tool_call_id="c1"))
    cm.add_message(Message(role="assistant", content="Here's the file"))

    # Force compression
    cm._compress(target_tokens=10)

    # Verify: no orphan tool messages
    for msg in cm._history:
        if msg.role == "tool":
            # Must have a preceding assistant with matching tool_call
            idx = cm._history.index(msg)
            assert idx > 0
            prev = cm._history[idx - 1]
            assert prev.role == "assistant" or prev.role == "tool"
```

## 8. 구현 순서

| 순서 | 작업 | 파일 |
|------|------|------|
| 1 | `Turn` dataclass + `_group_into_turns` | `conversation.py` |
| 2 | `Turn.summarize` 규칙 기반 요약 | `conversation.py` |
| 3 | `_compress` + auto-compress in `get_messages` | `conversation.py` |
| 4 | `compact()`, `set_on_compress`, `_summary` 필드 | `conversation.py` |
| 5 | Engine에 ContextConfig 연결 | `engine.py` |
| 6 | CLI `/compact`, `/tokens`, 압축 알림 | `cli.py` |
| 7 | 테스트 (원자성 포함) | `test_conversation.py` |

## 9. 에러 처리

| 상황 | 처리 |
|------|------|
| 압축 후에도 토큰 초과 | 최근 1턴만 남기고 전부 요약 |
| summary 자체가 너무 김 | summary를 2000자로 절단 |
| 빈 히스토리 압축 | no-op (아무 일도 안 함) |
| tool_call_id 없는 tool 메시지 | 이전 Turn에 병합 |
| 압축 콜백 미설정 | 무시 (optional) |
