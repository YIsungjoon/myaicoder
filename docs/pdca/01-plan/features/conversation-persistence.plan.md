# Plan: conversation-persistence

**Feature**: conversation-persistence
**날짜**: 2026-03-14
**Phase**: Plan
**Level**: Enterprise
**Parent Context**: Track A-1 — context-management 연장, 대화 세션 영속성
**Roadmap**: `docs/roadmap-2026-03.md` Track A-1

---

## 1. 개요

CLI를 종료해도 **대화 히스토리, 압축 요약, 컨텍스트 상태가 그대로 유지**되도록 세션 영속성을 구현한다.

### 현재 상태

| 항목 | 현재 | 문제 |
|------|------|------|
| 대화 히스토리 | 메모리 전용 | CLI 재시작 시 전부 소실 |
| 압축 요약 (`_summary`) | 메모리 전용 | 재시작 시 소실 |
| 압축 횟수 | 메모리 전용 | 통계 소실 |
| 대화 전환 | 불가 | 1개 세션만 유지 |

### 핵심 사용 시나리오

```
# 오전 작업
$ myaicoder
> 이 프로젝트의 gateway 코드를 분석해줘
(20턴 대화, 컨텍스트 압축 발생)
> /quit

# 오후 이어서 작업
$ myaicoder
> (이전 대화 자동 복원)
> 아까 분석한 결과에서 rate limiting 부분을 수정해줘
(이전 맥락을 기억하고 있음)
```

## 2. 핵심 요구사항

### 2.1 기능 요구사항

| ID | 기능 | 설명 | 우선순위 |
|----|------|------|----------|
| FR-01 | 자동 저장 | 대화 종료(`/quit`, Ctrl+C) 시 자동 저장 | P0 |
| FR-02 | 자동 로드 | CLI 시작 시 마지막 세션 자동 복원 | P0 |
| FR-03 | 세션 목록 | `/sessions` 명령으로 저장된 세션 목록 조회 | P0 |
| FR-04 | 세션 전환 | `/load <id>` 명령으로 특정 세션 복원 | P1 |
| FR-05 | 세션 삭제 | `/sessions delete <id>` 명령 | P1 |
| FR-06 | 새 세션 시작 | `/new` 명령으로 빈 세션 시작 (기존 저장) | P0 |
| FR-07 | 세션 메타데이터 | 제목(자동 생성), 생성일, 메시지 수, 토큰 수 | P0 |

### 2.2 비기능 요구사항

| ID | 항목 | 기준 |
|----|------|------|
| NFR-01 | 저장 속도 | 100ms 이내 (사용자 체감 없음) |
| NFR-02 | 저장 크기 | 세션당 최대 수 MB (압축된 대화) |
| NFR-03 | 하위 호환 | 저장 파일 없어도 기존처럼 동작 |
| NFR-04 | 데이터 무결성 | 저장 중 크래시 시 이전 상태 유지 (atomic write) |

## 3. 범위

### 3.1 In Scope

| # | 항목 | 우선순위 |
|---|------|----------|
| 1 | SessionStore (저장/로드/목록) | P0 |
| 2 | 자동 저장 (종료 시) | P0 |
| 3 | 자동 로드 (시작 시 마지막 세션) | P0 |
| 4 | CLI 명령 (/sessions, /new, /load) | P0 |
| 5 | 세션 메타데이터 (제목 자동 생성) | P0 |
| 6 | Turn 구조 직렬화/역직렬화 | P0 |
| 7 | pytest 테스트 | P0 |

### 3.2 Out of Scope

| 항목 | 사유 |
|------|------|
| SQLite 저장소 | JSON 파일이 현재 규모에 충분 |
| 클라우드 동기화 | 로컬 우선 |
| 세션 공유/내보내기 | 별도 feature |
| VS Code Extension 세션 연동 | 별도 feature |

## 4. 저장소 설계

### 4.1 저장 위치

```
~/.config/myaicoder/sessions/
├── _index.json                    ← 세션 목록 (메타데이터)
├── session_20260314_143000.json   ← 세션 데이터
├── session_20260314_160000.json
└── session_20260315_090000.json
```

### 4.2 세션 파일 구조 (JSON)

```json
{
  "id": "20260314_143000",
  "title": "Gateway rate limiting 분석",
  "created_at": "2026-03-14T14:30:00",
  "updated_at": "2026-03-14T16:45:00",
  "message_count": 24,
  "token_estimate": 8500,
  "compression_count": 2,
  "summary": "사용자가 gateway 코드를 분석하고...",
  "messages": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "...", "tool_calls": [...]},
    {"role": "tool", "content": "...", "tool_call_id": "c1"}
  ]
}
```

### 4.3 인덱스 파일 (`_index.json`)

```json
{
  "last_session_id": "20260314_160000",
  "sessions": [
    {
      "id": "20260314_143000",
      "title": "Gateway rate limiting 분석",
      "created_at": "2026-03-14T14:30:00",
      "message_count": 24
    }
  ]
}
```

## 5. 직렬화: Turn 구조와 tool_calls

### 핵심 주의점

`Message.tool_calls`는 `list[ToolCall]` 타입이므로 JSON 직렬화 시 ToolCall 객체를 dict로 변환해야 한다. 역직렬화 시에도 dict → ToolCall 복원이 필요하다.

```python
# 직렬화: Message → dict
def _serialize_message(msg: Message) -> dict:
    d = {"role": msg.role, "content": msg.content}
    if msg.tool_calls:
        d["tool_calls"] = [
            {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
            for tc in msg.tool_calls
        ]
    if msg.tool_call_id:
        d["tool_call_id"] = msg.tool_call_id
    return d

# 역직렬화: dict → Message
def _deserialize_message(d: dict) -> Message:
    tool_calls = None
    if "tool_calls" in d:
        tool_calls = [
            ToolCall(id=tc["id"], name=tc["name"], arguments=tc["arguments"])
            for tc in d["tool_calls"]
        ]
    return Message(
        role=d["role"],
        content=d.get("content"),
        tool_calls=tool_calls,
        tool_call_id=d.get("tool_call_id"),
    )
```

## 6. CLI 통합

```bash
# 시작 시 마지막 세션 자동 복원
$ myaicoder
  Restored session: "Gateway rate limiting 분석" (24 messages)
>

# 세션 목록
> /sessions
  Sessions:
  [1] 20260314_160000 — Gateway rate limiting 분석 (24 msgs, 2h ago)
  [2] 20260314_143000 — 프로젝트 구조 분석 (12 msgs, 4h ago)

# 새 세션 시작
> /new
  Previous session saved.
  Starting new session.

# 특정 세션 로드
> /load 1
  Loaded: "Gateway rate limiting 분석" (24 messages)

# 종료 시 자동 저장
> /quit
  Session saved: "Gateway rate limiting 분석"
  Goodbye!
```

## 7. 세션 제목 자동 생성

첫 번째 사용자 메시지에서 제목을 추출한다 (LLM 호출 없이):

```python
def _generate_title(first_user_message: str) -> str:
    """Extract title from first user message (max 50 chars)."""
    text = first_user_message.strip()
    # 첫 줄만, 50자 제한
    title = text.split("\n")[0][:50]
    return title if title else "Untitled session"
```

## 8. Atomic Write (데이터 무결성)

저장 중 크래시로 파일이 깨지는 것을 방지:

```python
def _atomic_write(path: Path, data: str) -> None:
    """Write to temp file, then rename (atomic on POSIX)."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(data, encoding="utf-8")
    tmp.rename(path)  # atomic on same filesystem
```

## 9. 성공 기준

- [ ] CLI 종료 시 대화가 자동 저장된다
- [ ] CLI 시작 시 마지막 세션이 자동 복원된다
- [ ] `/sessions`로 세션 목록을 조회할 수 있다
- [ ] `/new`로 새 세션을 시작할 수 있다 (이전 세션은 자동 저장)
- [ ] Turn 구조 (tool_calls 포함)가 정확히 직렬화/역직렬화된다
- [ ] 저장 파일 없이도 기존처럼 동작한다 (하위 호환)
- [ ] 테스트가 `uv run pytest tests -q`로 통과한다

## 10. 의존 관계

```
conversation-persistence (이번 feature)
  ├── depends on: core/conversation.py (Turn, _summary, _history)
  ├── depends on: llm/base.py (Message, ToolCall 직렬화)
  ├── modifies: cli.py (/sessions, /new, /load, 자동 저장/로드)
  ├── new: core/session.py (SessionStore)
  └── consumed by: CLI 사용자
```

## 11. 기술 결정 사항

| 항목 | 결정 | 근거 |
|------|------|------|
| 저장 형식 | JSON | 사람이 읽을 수 있음, 디버깅 용이 |
| 저장 위치 | `~/.config/myaicoder/sessions/` | XDG 규약, 프로젝트와 분리 |
| 제목 생성 | 규칙 기반 (첫 메시지) | LLM 호출 없음 |
| 파일 쓰기 | atomic write (tmp → rename) | POSIX 원자성 보장 |
| 세션 제한 | 최근 20개 유지, 오래된 것 자동 삭제 | 디스크 절약 |

## 12. 리스크

| 리스크 | 영향 | 대응 |
|--------|------|------|
| 대용량 세션 (도구 결과 포함) | 파일 크기 수 MB | 압축된 summary만 저장, 오래된 턴 제외 |
| ToolCall 직렬화 오류 | 세션 로드 실패 | 방어적 역직렬화 (에러 시 해당 메시지 skip) |
| 저장 경로 권한 문제 | 저장 실패 | 경고 출력 + 메모리 전용 폴백 |
| 세션 파일 수동 수정 | 파싱 에러 | JSON 스키마 검증 + graceful 에러 처리 |
