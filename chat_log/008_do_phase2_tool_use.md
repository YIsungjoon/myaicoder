# 008. Do Phase 2: Tool Use 구현

**날짜**: 2026-03-13
**작업 유형**: PDCA Do (구현)
**Feature**: ai-coder-cli
**Phase**: Phase 2 / 7

## 구현 내용

### Design 문서 Phase 2 체크리스트

- [x] `tools/base.py` — Tool ABC + ToolResult
- [x] `tools/registry.py` — Tool Registry + create_default_registry()
- [x] `tools/read.py` — 파일 읽기 (line number 포함, offset/limit)
- [x] `tools/write.py` — 파일 쓰기 (디렉토리 자동 생성)
- [x] `tools/edit.py` — 파일 편집 (unique 검증, replace_all)
- [x] `tools/glob_tool.py` — 파일 패턴 검색 (skip_dirs, 수정시간 정렬)
- [x] `tools/grep_tool.py` — 내용 검색 (regex, glob 필터, 바이너리 제외)
- [x] `tools/bash.py` — 명령어 실행 (timeout, 출력 truncate)
- [x] `core/engine.py` 확장 — Agentic Loop (tool_call → 실행 → 반복)
- [x] `cli.py` 업데이트 — ToolRegistry 연결
- [x] 테스트 작성 (40 passed, 2 skipped)

### 생성/수정 파일 목록

```
services/myaicoder/
├── src/myaicoder/
│   ├── core/
│   │   └── engine.py              # Agentic Loop 구현 (MAX_TOOL_ITERATIONS=25)
│   ├── cli.py                     # create_default_registry() 연결
│   └── tools/
│       ├── base.py                # Tool ABC, ToolResult
│       ├── registry.py            # ToolRegistry, create_default_registry()
│       ├── read.py                # ReadTool
│       ├── write.py               # WriteTool
│       ├── edit.py                # EditTool
│       ├── glob_tool.py           # GlobTool
│       ├── grep_tool.py           # GrepTool
│       └── bash.py                # BashTool
├── tests/
│   ├── conftest.py                # MockLLMProvider 확장 (LLMResponse 지원)
│   ├── test_core/
│   │   └── test_engine_tools.py   # Agentic Loop 테스트 (5)
│   └── test_tools/
│       ├── test_read.py           # ReadTool 테스트 (4)
│       ├── test_write.py          # WriteTool 테스트 (3)
│       ├── test_edit.py           # EditTool 테스트 (4)
│       ├── test_glob_grep.py      # Glob+Grep 테스트 (6)
│       ├── test_bash.py           # BashTool 테스트 (4)
│       └── test_registry.py       # Registry 테스트 (4)
```

### 아키텍처 설계

```
User Input
    │
    ▼
AgentEngine.chat()
    │
    ├── LLM.chat(messages, tools_schema) ◄─── Agentic Loop
    │       │                                    │
    │       ├── text only → return              │
    │       │                                    │
    │       └── tool_calls ──────────────────────┤
    │               │                            │
    │               ▼                            │
    │       ToolRegistry.get(name)               │
    │               │                            │
    │               ▼                            │
    │       Tool.execute(**args)                 │
    │               │                            │
    │               ▼                            │
    │       결과를 messages에 추가 ──────────────┘
    │
    ▼
Final Response
```

### 테스트 결과
- 40 passed, 2 skipped (vLLM 통합 테스트)
- 실행 시간: 1.27초

## PDCA 상태
```
[Plan] ✅ → [Design] ✅ → [Do] 🔄 (Phase 2/7 완료) → [Check] ⏳ → [Act] ⏳
```

## 다음 단계
- Phase 3: MCP Client 구현 (.mcp.json 파싱, stdio/HTTP 트랜스포트)
- 또는 llama-server로 실제 Tool Use 통합 테스트
