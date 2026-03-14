# Design: conversation-persistence

**Feature**: conversation-persistence
**Date**: 2026-03-14
**Phase**: Design
**Level**: Enterprise
**Plan**: `docs/pdca/01-plan/features/conversation-persistence.plan.md`
**Depends on**: context-management (Turn, ConversationManager)

---

## 1. Overview

CLI 종료 후에도 대화 히스토리, 압축 요약(summary), 압축 횟수(compression_count)가 유지되도록
세션 영속성을 구현한다. JSON 파일 기반, atomic write로 데이터 무결성을 보장한다.

### 피드백 반영 사항

| # | 피드백 | 설계 반영 |
|---|--------|----------|
| FB-1 | 내부 상태 복원 (summary + compression_count) | SessionData에 summary, compression_count 포함 + ConversationManager.restore() 메서드 |
| FB-2 | Graceful Shutdown (스트리밍 중 Ctrl+C) | 이중 시그널 핸들링: 1차 → 저장 후 종료, 2차 → 즉시 종료 |
| FB-3 | 세션 ID 충돌 방지 (밀리초 + 난수) | `YYYYMMDD_HHMMSSfff_XXXX` 형식 (밀리초 + 4자리 hex 난수) |

---

## 2. Architecture

### 2.1 Module Structure

```
services/myaicoder/src/myaicoder/
├── core/
│   ├── conversation.py    ← [수정] restore() 메서드 추가
│   ├── session.py         ← [신규] SessionStore, SessionData
│   └── config.py          ← [수정] SessionConfig 추가
├── cli.py                 ← [수정] /sessions, /new, /load, 자동 저장/로드, graceful shutdown
└── ...
```

### 2.2 Dependency Flow

```
cli.py
  ├── SessionStore (core/session.py)     ← 저장/로드/목록
  │     ├── SessionData                  ← 세션 데이터 모델
  │     ├── _serialize_message()         ← Message → dict
  │     └── _deserialize_message()       ← dict → Message
  ├── ConversationManager                ← [기존] + restore()
  └── AgentEngine                        ← [기존, 변경 없음]
```

### 2.3 Key Design Decision

| 항목 | 결정 | 근거 |
|------|------|------|
| 저장 형식 | JSON | 사람이 읽을 수 있음, 디버깅 용이 |
| 저장 위치 | `~/.config/myaicoder/sessions/` | XDG 규약, 프로젝트와 분리 |
| 인덱스 파일 | `_index.json` | 세션 목록 빠른 로딩 (개별 파일 안 열어도 됨) |
| 세션 제한 | 최근 20개, 오래된 것 자동 삭제 | 디스크 절약 |
| 파일 쓰기 | atomic write (tmp → rename) | POSIX 원자성 보장, 크래시 안전 |
| 세션 ID | `YYYYMMDD_HHMMSSfff_XXXX` | 밀리초 + hex 난수로 충돌 방지 |
| 상태 복원 | summary + compression_count 포함 | 컨텍스트 연속성 유지 (FB-1) |

---

## 3. Data Model

### 3.1 SessionData (dataclass)

```python
@dataclass
class SessionData:
    """Serializable session state."""
    id: str                          # "20260314_143000123_a1b2"
    title: str                       # Auto-generated from first user message
    created_at: str                  # ISO 8601
    updated_at: str                  # ISO 8601
    message_count: int               # len(messages)
    token_estimate: int              # ConversationManager.estimate_tokens()
    compression_count: int           # 압축 횟수 (FB-1)
    summary: str                     # 압축 요약 (FB-1)
    messages: list[dict]             # Serialized Message list
```

### 3.2 Session File (`session_{id}.json`)

```json
{
  "id": "20260314_143000123_a1b2",
  "title": "Gateway rate limiting 분석",
  "created_at": "2026-03-14T14:30:00.123",
  "updated_at": "2026-03-14T16:45:30.456",
  "message_count": 24,
  "token_estimate": 8500,
  "compression_count": 2,
  "summary": "User: gateway 코드를 분석해줘 → Called: Read → ...",
  "messages": [
    {"role": "user", "content": "이 프로젝트의 gateway 코드를 분석해줘"},
    {
      "role": "assistant",
      "content": null,
      "tool_calls": [
        {"id": "tc_1", "name": "Read", "arguments": {"path": "services/gateway/app/main.py"}}
      ]
    },
    {"role": "tool", "content": "...", "tool_call_id": "tc_1"},
    {"role": "assistant", "content": "gateway는 FastAPI 기반으로..."}
  ]
}
```

### 3.3 Index File (`_index.json`)

```json
{
  "version": 1,
  "last_session_id": "20260314_160000456_c3d4",
  "sessions": [
    {
      "id": "20260314_160000456_c3d4",
      "title": "Rate limiting 수정",
      "created_at": "2026-03-14T16:00:00.456",
      "updated_at": "2026-03-14T17:30:00.789",
      "message_count": 18
    },
    {
      "id": "20260314_143000123_a1b2",
      "title": "Gateway rate limiting 분석",
      "created_at": "2026-03-14T14:30:00.123",
      "updated_at": "2026-03-14T16:45:30.456",
      "message_count": 24
    }
  ]
}
```

---

## 4. Session ID Design (FB-3)

### 충돌 방지 전략

```python
import os
from datetime import datetime

def _generate_session_id() -> str:
    """Generate collision-resistant session ID.

    Format: YYYYMMDD_HHMMSSfff_XXXX
    - fff: milliseconds (000-999)
    - XXXX: 4-digit hex random (65536 combinations)

    Collision probability: ~0 (same millisecond + same 4-hex = 1/65536 per ms)
    """
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S") + f"{now.microsecond // 1000:03d}"
    random_suffix = os.urandom(2).hex()  # 4 hex chars
    return f"{timestamp}_{random_suffix}"
```

### Example IDs

```
20260314_143000123_a1b2
20260314_143000123_f7e3   ← 같은 밀리초여도 난수가 다름
20260314_160045678_0c91
```

---

## 5. Core Classes

### 5.1 SessionStore (`core/session.py`)

```python
class SessionStore:
    """File-based session storage with atomic writes."""

    MAX_SESSIONS = 20

    def __init__(self, sessions_dir: Path | None = None):
        self._dir = sessions_dir or Path.home() / ".config" / "myaicoder" / "sessions"
        # 디렉토리는 save() 시점에 lazy 생성 (읽기 전용이면 불필요)

    # ── Public API ──

    def save(self, conversation: ConversationManager, session_id: str | None = None) -> SessionData:
        """Save conversation state to disk.

        Args:
            conversation: Current ConversationManager (history + summary + compression_count)
            session_id: Existing session ID (update) or None (create new)

        Returns:
            Saved SessionData

        Steps:
        1. Serialize messages (Message → dict, ToolCall → dict)
        2. Build SessionData with summary + compression_count (FB-1)
        3. Atomic write to session file
        4. Update index
        5. Prune old sessions (> MAX_SESSIONS)
        """

    def load(self, session_id: str) -> SessionData:
        """Load a session by ID.

        Returns:
            SessionData with messages + summary + compression_count

        Raises:
            FileNotFoundError: Session file not found
            ValueError: Invalid session data (corrupted JSON)
        """

    def load_last(self) -> SessionData | None:
        """Load the most recent session.

        Returns:
            SessionData or None (no sessions exist)
        """

    def list_sessions(self) -> list[dict]:
        """List all sessions (from index, no file I/O per session).

        Returns:
            List of {id, title, created_at, updated_at, message_count}
            Sorted by updated_at descending (most recent first)
        """

    def delete(self, session_id: str) -> bool:
        """Delete a session file and remove from index.

        Returns:
            True if deleted, False if not found
        """

    # ── Internal ──

    def _ensure_dir(self) -> None:
        """Create sessions directory if not exists."""
        self._dir.mkdir(parents=True, exist_ok=True)

    def _load_index(self) -> dict:
        """Load _index.json. Returns empty structure if not exists."""
        index_path = self._dir / "_index.json"
        if not index_path.exists():
            return {"version": 1, "last_session_id": None, "sessions": []}
        try:
            return json.loads(index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"version": 1, "last_session_id": None, "sessions": []}

    def _save_index(self, index: dict) -> None:
        """Atomic write index."""
        self._ensure_dir()
        _atomic_write(self._dir / "_index.json", json.dumps(index, ensure_ascii=False, indent=2))

    def _prune(self, index: dict) -> dict:
        """Remove oldest sessions beyond MAX_SESSIONS.

        1. Sort by updated_at descending
        2. Keep first MAX_SESSIONS
        3. Delete session files for pruned entries
        4. Return updated index
        """
```

### 5.2 Serialization Functions (`core/session.py`)

```python
def _serialize_message(msg: Message) -> dict:
    """Convert Message to JSON-serializable dict.

    Handles ToolCall objects → dict conversion.
    """
    d: dict = {"role": msg.role}
    if msg.content is not None:
        d["content"] = msg.content
    if msg.tool_calls:
        d["tool_calls"] = [
            {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
            for tc in msg.tool_calls
        ]
    if msg.tool_call_id:
        d["tool_call_id"] = msg.tool_call_id
    return d


def _deserialize_message(d: dict) -> Message:
    """Convert dict to Message.

    Defensive: skips invalid tool_calls entries (graceful degradation).
    """
    tool_calls = None
    if "tool_calls" in d:
        tool_calls = []
        for tc in d["tool_calls"]:
            try:
                tool_calls.append(
                    ToolCall(id=tc["id"], name=tc["name"], arguments=tc["arguments"])
                )
            except (KeyError, TypeError):
                continue  # Skip malformed tool call
        if not tool_calls:
            tool_calls = None
    return Message(
        role=d["role"],
        content=d.get("content"),
        tool_calls=tool_calls,
        tool_call_id=d.get("tool_call_id"),
    )


def _atomic_write(path: Path, data: str) -> None:
    """Write to temp file, then rename (atomic on POSIX)."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(data, encoding="utf-8")
    tmp.rename(path)


def _generate_title(first_user_message: str) -> str:
    """Extract title from first user message (max 50 chars, no LLM)."""
    text = first_user_message.strip()
    title = text.split("\n")[0][:50]
    return title if title else "Untitled session"
```

### 5.3 ConversationManager.restore() (FB-1)

`core/conversation.py`에 추가:

```python
class ConversationManager:
    # ... 기존 코드 ...

    def restore(self, messages: list[Message], summary: str = "", compression_count: int = 0) -> None:
        """Restore conversation state from saved session.

        Args:
            messages: Deserialized message history
            summary: Previous compression summary
            compression_count: Previous compression count

        Note: Does NOT clear existing state — caller should clear() first if needed.
        """
        self._history = list(messages)
        self._summary = summary
        self._compression_count = compression_count
```

---

## 6. CLI Integration

### 6.1 Startup Flow (자동 로드)

```
_run_chat() 시작
  ↓
SessionStore 생성
  ↓
store.load_last() 호출
  ↓
├── SessionData 있음 → engine.conversation.restore(messages, summary, compression_count)
│                     → ui.print_info(f"Restored: \"{title}\" ({n} messages)")
│                     → current_session_id = data.id
│
└── None (첫 실행)  → current_session_id = None (새 세션 자동 생성됨)
```

### 6.2 Shutdown Flow (자동 저장 + Graceful Shutdown, FB-2)

```python
# cli.py 수정

_shutdown_requested = False  # 모듈 레벨 플래그

async def _run_chat(...):
    store = SessionStore()
    current_session_id: str | None = None

    # 자동 로드
    last = store.load_last()
    if last:
        messages = [_deserialize_message(m) for m in last.messages]
        engine.conversation.restore(messages, last.summary, last.compression_count)
        current_session_id = last.id
        ui.print_info(f'Restored: "{last.title}" ({last.message_count} messages)')

    ui.print_welcome()

    while True:
        try:
            user_input = ui.get_input()
        except KeyboardInterrupt:
            # 1차 Ctrl+C: 저장 후 종료
            current_session_id = _save_session(store, engine, current_session_id, ui)
            ui.print_goodbye()
            break

        if user_input is None:  # Ctrl+D
            current_session_id = _save_session(store, engine, current_session_id, ui)
            ui.print_goodbye()
            break

        if not user_input:
            continue

        # 명령 처리
        if user_input.startswith("/"):
            result = _handle_command(user_input, engine, ui, store, current_session_id)
            if result is True:
                continue
            if result is False:  # /quit
                current_session_id = _save_session(store, engine, current_session_id, ui)
                ui.print_goodbye()
                break
            if isinstance(result, str):  # /new, /load → 새 session_id 반환
                current_session_id = result
                continue

        # Chat (스트리밍 중 Ctrl+C 보호)
        try:
            if no_stream:
                response = await engine.chat(user_input)
                ui.print_assistant(response)
            else:
                ui.print_streaming_start()
                try:
                    async for chunk in engine.chat_stream(user_input):
                        ui.print_streaming_chunk(chunk)
                    ui.print_streaming_end()
                except KeyboardInterrupt:
                    # 스트리밍 중 Ctrl+C: 현재 응답만 중단, 대화는 유지
                    ui.print_streaming_end()
                    ui.print_info("Response interrupted.")
        except Exception as e:
            ui.print_error(str(e))

    # Cleanup
    if mcp_client:
        await mcp_client.close()
```

### 6.3 Graceful Shutdown 상세 (FB-2)

| 상황 | 1차 Ctrl+C | 2차 Ctrl+C |
|------|-----------|-----------|
| 입력 대기 중 | 세션 저장 → 종료 | N/A (이미 종료) |
| 스트리밍 중 | 응답만 중단 (대화 유지) | 세션 저장 → 종료 |
| 저장 중 | N/A (100ms 이내) | 즉시 종료 (파일 깨짐 가능, atomic write로 보호) |

### 6.4 New Commands

```python
def _handle_command(command, engine, ui, store, current_session_id):
    """Handle slash commands.

    Returns:
        True: command handled, continue loop
        False: /quit, exit loop
        str: new session_id (from /new or /load)
    """
    cmd = command.lower().strip()

    # /sessions — 세션 목록
    if cmd == "/sessions":
        sessions = store.list_sessions()
        if not sessions:
            ui.print_info("No saved sessions.")
            return True
        ui.console.print("\n[bold]Sessions:[/bold]")
        for i, s in enumerate(sessions, 1):
            age = _format_age(s["updated_at"])
            ui.console.print(
                f"  [{i}] {s['id']} — {s['title']} ({s['message_count']} msgs, {age})"
            )
        ui.console.print()
        return True

    # /new — 새 세션 시작
    if cmd == "/new":
        if engine.conversation.message_count > 0:
            _save_session(store, engine, current_session_id, ui)
        engine.reset()
        ui.print_info("New session started.")
        return _generate_session_id()  # 새 session_id 반환

    # /load <id_or_index> — 세션 로드
    if cmd.startswith("/load"):
        parts = cmd.split(maxsplit=1)
        if len(parts) < 2:
            ui.print_info("Usage: /load <session_id or index>")
            return True
        target = parts[1].strip()

        # 숫자면 인덱스, 아니면 session_id
        sessions = store.list_sessions()
        session_id = None
        try:
            idx = int(target) - 1
            if 0 <= idx < len(sessions):
                session_id = sessions[idx]["id"]
        except ValueError:
            session_id = target

        if not session_id:
            ui.print_info(f"Session not found: {target}")
            return True

        # 현재 세션 저장 후 로드
        if engine.conversation.message_count > 0:
            _save_session(store, engine, current_session_id, ui)

        try:
            data = store.load(session_id)
            messages = [_deserialize_message(m) for m in data.messages]
            engine.conversation.clear()
            engine.conversation.restore(messages, data.summary, data.compression_count)
            ui.print_info(f'Loaded: "{data.title}" ({data.message_count} messages)')
            return session_id  # 새 current_session_id
        except (FileNotFoundError, ValueError) as e:
            ui.print_info(f"Failed to load: {e}")
            return True

    # /sessions delete <id_or_index> — 세션 삭제
    if cmd.startswith("/sessions delete"):
        parts = cmd.split(maxsplit=2)
        if len(parts) < 3:
            ui.print_info("Usage: /sessions delete <session_id or index>")
            return True
        # ... (similar to /load target resolution)
        return True

    # 기존 명령은 그대로 유지
    # /help, /clear, /compact, /tokens, /quit
```

### 6.5 /help 업데이트

```
Commands:
  /help              Show this help
  /clear             Clear conversation history
  /compact           Compress conversation context
  /tokens            Show token usage
  /sessions          List saved sessions
  /new               Start new session (saves current)
  /load <id|index>   Load a saved session
  /sessions delete   Delete a saved session
  /quit              Exit myAiCoder
```

### 6.6 `_save_session()` Helper

```python
def _save_session(store, engine, session_id, ui) -> str:
    """Save current conversation, return session_id.

    Skips save if conversation is empty (0 messages).
    """
    if engine.conversation.message_count == 0:
        return session_id or ""

    try:
        data = store.save(engine.conversation, session_id=session_id)
        ui.print_info(f'Session saved: "{data.title}"')
        return data.id
    except OSError as e:
        ui.print_info(f"Warning: Could not save session: {e}")
        return session_id or ""
```

---

## 7. SessionConfig

`core/config.py`에 추가:

```python
@dataclass
class SessionConfig:
    auto_save: bool = True          # 종료 시 자동 저장
    auto_load: bool = True          # 시작 시 마지막 세션 자동 로드
    max_sessions: int = 20          # 최대 세션 수
    sessions_dir: str | None = None # Custom path (None = default)


@dataclass
class AppConfig:
    # ... 기존 필드 ...
    session: SessionConfig = field(default_factory=SessionConfig)
```

---

## 8. Error Handling

### 8.1 방어적 설계

| 에러 상황 | 대응 |
|----------|------|
| 세션 디렉토리 생성 실패 (권한) | 경고 출력, 메모리 전용 모드 (기존 동작 유지) |
| 세션 파일 JSON 파싱 실패 | `ValueError` 발생, 호출자가 에러 메시지 출력 |
| ToolCall 역직렬화 실패 | 해당 tool_call만 skip (나머지 메시지 유지) |
| 인덱스 파일 깨짐 | 빈 인덱스로 시작 (세션 파일은 보존) |
| atomic write 중 크래시 | .tmp 파일만 남음, 원본은 이전 상태 유지 |
| 세션 파일 없는데 인덱스에 있음 | 인덱스에서 해당 항목 제거 (self-healing) |
| 저장소 없이 시작 | 기존과 동일하게 동작 (NFR-03 하위 호환) |

### 8.2 Self-Healing Index

```python
def _load_index(self) -> dict:
    """Load index with self-healing.

    If a session in the index has no corresponding file,
    remove it from the index silently.
    """
    index = self._raw_load_index()

    # Validate: every session in index has a file
    valid = []
    for s in index.get("sessions", []):
        path = self._dir / f"session_{s['id']}.json"
        if path.exists():
            valid.append(s)

    if len(valid) != len(index.get("sessions", [])):
        index["sessions"] = valid
        # Fix last_session_id if it was pruned
        if index.get("last_session_id") and not any(
            s["id"] == index["last_session_id"] for s in valid
        ):
            index["last_session_id"] = valid[0]["id"] if valid else None
        self._save_index(index)

    return index
```

---

## 9. Implementation Order

| # | 파일 | 작업 | 의존 |
|---|------|------|------|
| 1 | `core/session.py` | SessionData, SessionStore, 직렬화 함수, atomic write | 없음 |
| 2 | `core/conversation.py` | `restore()` 메서드 추가 | 없음 |
| 3 | `core/config.py` | SessionConfig, AppConfig에 session 필드 추가 | 없음 |
| 4 | `cli.py` | 자동 저장/로드, /sessions, /new, /load, graceful shutdown | 1, 2, 3 |
| 5 | `tests/test_core/test_session.py` | SessionStore 단위 테스트 | 1 |
| 6 | `tests/test_core/test_conversation.py` | restore() 테스트 추가 | 2 |
| 7 | `tests/test_cli.py` | CLI 세션 명령 테스트 | 4 |

---

## 10. Test Plan

### 10.1 단위 테스트 (`test_session.py`)

| # | 테스트 | 검증 내용 |
|---|--------|----------|
| T1 | `test_generate_session_id_format` | ID 형식 검증 (YYYYMMDD_HHMMSSfff_XXXX) |
| T2 | `test_generate_session_id_uniqueness` | 1000회 생성 시 중복 없음 |
| T3 | `test_serialize_message_simple` | user/assistant 메시지 직렬화 |
| T4 | `test_serialize_message_tool_calls` | ToolCall 포함 메시지 직렬화 |
| T5 | `test_serialize_message_tool_result` | tool_call_id 포함 메시지 직렬화 |
| T6 | `test_deserialize_message_simple` | dict → Message 역직렬화 |
| T7 | `test_deserialize_message_malformed_tool_call` | 잘못된 ToolCall skip |
| T8 | `test_roundtrip_serialization` | serialize → deserialize 왕복 검증 |
| T9 | `test_save_and_load` | 저장 후 로드, 데이터 일치 검증 |
| T10 | `test_save_includes_summary_and_compression_count` | summary + compression_count 영속화 (FB-1) |
| T11 | `test_load_last` | 마지막 세션 로드 |
| T12 | `test_load_last_no_sessions` | 세션 없을 때 None 반환 |
| T13 | `test_list_sessions` | 목록 반환, 최신순 정렬 |
| T14 | `test_delete_session` | 파일 + 인덱스에서 제거 |
| T15 | `test_prune_old_sessions` | MAX_SESSIONS 초과 시 오래된 것 삭제 |
| T16 | `test_atomic_write` | tmp → rename 검증 |
| T17 | `test_generate_title` | 첫 메시지에서 제목 추출 |
| T18 | `test_generate_title_empty` | 빈 메시지 → "Untitled session" |
| T19 | `test_index_self_healing` | 파일 없는 항목 자동 제거 |
| T20 | `test_save_empty_conversation` | 빈 대화 저장 skip |

### 10.2 ConversationManager 테스트 추가 (`test_conversation.py`)

| # | 테스트 | 검증 내용 |
|---|--------|----------|
| T21 | `test_restore_messages` | restore() 후 history 복원 확인 |
| T22 | `test_restore_summary_and_compression_count` | summary, compression_count 복원 (FB-1) |
| T23 | `test_restore_then_continue_conversation` | 복원 후 add_message → get_messages 정상 동작 |
| T24 | `test_restore_with_tool_calls` | ToolCall 포함 메시지 복원 후 Turn 그루핑 정상 |

### 10.3 CLI 통합 테스트 (`test_cli.py`)

| # | 테스트 | 검증 내용 |
|---|--------|----------|
| T25 | `test_session_commands_in_help` | /help에 세션 명령 포함 |

### 10.4 테스트 예상 수량

- test_session.py: 20개 (T1~T20)
- test_conversation.py 추가: 4개 (T21~T24)
- test_cli.py 추가: 1개 (T25)
- **총 신규 테스트: 25개**

---

## 11. Success Criteria

- [ ] CLI 종료 시 대화가 자동 저장된다
- [ ] CLI 시작 시 마지막 세션이 자동 복원된다 (summary + compression_count 포함)
- [ ] `/sessions`로 세션 목록을 조회할 수 있다
- [ ] `/new`로 새 세션을 시작할 수 있다 (이전 세션은 자동 저장)
- [ ] `/load`로 특정 세션을 복원할 수 있다
- [ ] 스트리밍 중 Ctrl+C는 응답만 중단하고 대화를 유지한다 (FB-2)
- [ ] 세션 ID가 밀리초 + 난수로 충돌 없이 생성된다 (FB-3)
- [ ] Turn 구조 (tool_calls 포함)가 정확히 직렬화/역직렬화된다
- [ ] 저장 파일 없이도 기존처럼 동작한다 (하위 호환)
- [ ] 테스트가 `uv run pytest tests -q`로 전부 통과한다

---

## 12. Risk

| 리스크 | 영향 | 대응 |
|--------|------|------|
| 대용량 세션 (도구 결과 포함) | 파일 크기 수 MB | 압축된 상태만 저장 (summary 포함), 도구 결과는 이미 truncate됨 |
| ToolCall 직렬화 오류 | 세션 로드 실패 | 방어적 역직렬화 (malformed tool_call skip) |
| 저장 경로 권한 문제 | 저장 실패 | 경고 출력 + 메모리 전용 폴백 |
| 인덱스-파일 불일치 | 고아 파일 또는 누락 | self-healing index (섹션 8.2) |
| 스트리밍 중 Ctrl+C 후 불완전 메시지 | 대화 상태 불일치 | 스트리밍 중단 시 불완전 응답은 conversation에 추가하지 않음 |

---

## 13. Out of Scope (Plan과 동일)

| 항목 | 사유 |
|------|------|
| SQLite 저장소 | JSON 파일이 현재 규모에 충분 |
| 클라우드 동기화 | 로컬 우선 |
| 세션 공유/내보내기 | 별도 feature |
| VS Code Extension 세션 연동 | 별도 feature |
| LLM 기반 세션 제목 생성 | 규칙 기반으로 충분 |
