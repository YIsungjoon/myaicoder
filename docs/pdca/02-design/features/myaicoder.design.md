# Design: myaicoder

**Feature**: myaicoder
**날짜**: 2026-03-13
**Phase**: Design
**Level**: Enterprise
**Plan 참조**: `docs/pdca/01-plan/features/myaicoder.plan.md`

---

## 1. 기술 스택

| 영역 | 기술 | 비고 |
|------|------|------|
| 런타임 | Python | `>=3.11` |
| CLI | `click` + `rich` | 대화형 UI 및 명령 라우팅 |
| LLM 연동 | OpenAI-compatible API | vLLM endpoint 기준 |
| 설정 | dataclass + JSON | 프로젝트/사용자 범위 설정 파일 |
| MCP | `mcp[cli]` | 공식 Python SDK 기반 |
| 테스트 | `pytest`, `pytest-asyncio` | 코어/도구/MCP 테스트 |
| 린트 | `ruff` | Python 정적 점검 |

## 2. 시스템 아키텍처

```text
User
  |
  v
CLI (myaicoder)
  |
  +-- Chat UI (rich)
  +-- AppConfig / MCPConfig
  +-- AgentEngine
        |
        +-- ConversationManager
        +-- ContextManager
        +-- ToolRegistry
        |     +-- Read / Write / Edit / Glob / Grep / Bash
        |
        +-- LLMProvider (VLLMProvider)
        |
        +-- optional MCPClient
              +-- external MCP servers -> tool proxies

Separate serve mode:
CLI `myaicoder serve`
  -> MCPServer
  -> FastMCP
  -> built-in tools exposure
  -> optional `agentic_task`
```

## 3. 모듈 구조

```text
services/myaicoder/src/myaicoder/
├── cli.py                 # CLI 엔트리포인트
├── core/
│   ├── config.py          # AppConfig 및 하위 설정
│   ├── context.py         # 시스템 프롬프트/컨텍스트 관리
│   ├── conversation.py    # 메시지 히스토리 관리
│   └── engine.py          # agentic loop 핵심
├── llm/
│   ├── base.py            # LLM 추상 인터페이스, 메시지 타입
│   └── vllm_provider.py   # vLLM/OpenAI 호환 provider
├── mcp/
│   ├── client.py          # 외부 MCP 서버 연결 및 tool proxy
│   ├── config.py          # .mcp.json 호환 설정 로딩
│   └── server.py          # FastMCP 기반 MCP 서버
├── tools/
│   ├── base.py            # Tool, ToolResult 추상 타입
│   ├── registry.py        # 기본 registry 생성
│   ├── read.py            # 파일 읽기
│   ├── write.py           # 파일 쓰기
│   ├── edit.py            # 텍스트 편집
│   ├── glob_tool.py       # 파일 glob 검색
│   ├── grep_tool.py       # 내용 검색
│   └── bash.py            # 명령 실행
└── ui/
    └── chat.py            # Rich 기반 콘솔 UI
```

## 4. 인터페이스 설계

### 4.1 CLI 엔트리포인트

주요 명령:

- 기본 실행: 대화형 채팅 또는 `-p/--prompt` one-shot 실행
- `config`: 현재 설정 출력
- `serve`: 내장 도구를 MCP 서버로 노출

주요 옵션:

- `--model`
- `--vllm-url`
- `--no-stream`
- `--no-tools`
- `--verbose`
- `--prompt`
- `serve --transport --port --allow-bash --working-dir --max-concurrent --agentic`

### 4.2 AgentEngine

`AgentEngine`는 다음 루프를 담당한다.

1. 사용자 메시지를 conversation에 추가
2. system prompt + conversation + tool schema를 LLM에 전달
3. tool call이 있으면 승인 정책 확인 후 실행
4. tool 결과를 conversation에 다시 추가
5. 최종 텍스트 응답이 나올 때까지 반복

핵심 제약:

- 최대 tool iteration: `25`
- retryable error 재시도: 최대 `2`
- 큰 tool 결과는 잘라서 conversation context에 주입

### 4.3 설정 로딩

`AppConfig.load()` 검색 순서:

1. 명시적 경로
2. 현재 작업 디렉터리의 `myaicoder.json`
3. `~/.config/myaicoder/config.json`
4. 없으면 기본값

하위 설정:

- `llm`
- `tools`
- `ui`
- `context`
- `server`

### 4.4 Tool Registry

기본 등록 도구:

- `Read`
- `Write`
- `Edit`
- `Glob`
- `Grep`
- `Bash`

`ToolRegistry.to_openai_tools()`는 LLM function calling 스키마로 변환된 도구 목록을 반환한다.

### 4.5 MCP Server

`MCPServer`는 FastMCP 기반으로 내장 도구를 MCP tool로 노출한다.

설계 원칙:

- Bash는 `allow_bash=False`일 때 등록하지 않음
- 내부 Tool 이름은 외부 MCP 이름으로 변환
  - `Read -> read_file`
  - `Write -> write_file`
  - `Edit -> edit_file`
  - `Glob -> glob_search`
  - `Grep -> grep_search`
  - `Bash -> run_command`
- 큰 결과는 `max_result_tokens` 기준으로 축약
- `enable_agentic=True`이고 provider가 있을 때만 `agentic_task` 추가
- `max_concurrent > 1`일 때 semaphore로 동시성 제한

### 4.6 MCP Client

`MCPClient`는 외부 MCP 서버에 연결해 도구를 프록시 Tool로 등록한다.

지원 transport:

- `stdio`
- `http` (`streamable-http`)

동작 흐름:

1. 설정에 정의된 서버를 순회
2. transport별 연결
3. `ClientSession.initialize()`
4. `list_tools()`
5. 각 tool을 `MCPToolProxy`로 변환
6. 로컬 `ToolRegistry`에 등록 가능하게 반환

## 5. 테스트 전략

현재 테스트 영역:

- `tests/test_core/`
- `tests/test_llm/`
- `tests/test_mcp/`
- `tests/test_tools/`

검증 대상:

- AgentEngine의 승인/재시도/대화 흐름
- MCP client/server의 연결 및 도구 노출
- 각 built-in tool의 성공/실패 경로
- vLLM provider 응답 처리

실행 기준:

```bash
cd services/myaicoder
uv run pytest tests -q
```

## 6. 알려진 설계 포인트

- 기본 LLM endpoint는 코드상 `http://localhost:8080/v1` 기준이다
- CLI help 문구 일부는 과거 `8000` 포트 설명을 포함할 수 있어 문서/메시지 정합성 검토가 필요하다
- 외부 MCP server tool proxy는 구현돼 있지만 `get_tool_proxies()`는 현재 빈 리스트를 반환하므로 `discover_tools()`가 실제 경로다
- 테스트는 통과하지만 subprocess/event loop 종료 경고 1건이 존재해 추후 정리 후보로 남긴다

## 7. Check 단계에서 확인할 항목

- 문서와 실제 기본 포트/URL이 일치하는가
- `serve` 모드와 CLI 채팅 모드의 옵션/동작이 문서와 일치하는가
- MCP client API 중 사용되지 않거나 중복된 경로가 있는가
- 승인 정책과 Bash 안전장치가 요구사항을 충족하는가
- 테스트 경고가 구조적 문제인지 단순 정리 이슈인지 분류됐는가
