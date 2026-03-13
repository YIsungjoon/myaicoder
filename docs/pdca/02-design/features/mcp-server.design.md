# Design: MCP Server (Phase 4)

**Feature**: mcp-server
**날짜**: 2026-03-13
**Phase**: Design
**Level**: Enterprise
**Plan 참조**: `docs/pdca/01-plan/features/mcp-server.plan.md`

---

## 1. 기술 스택

| 영역 | 기술 | 비고 |
|------|------|------|
| MCP Server | `FastMCP` (mcp Python SDK) | 공식 권장 고수준 API |
| Transport | stdio (기본), Streamable HTTP | `FastMCP.run(transport=...)` |
| 동시성 제어 | `asyncio.Semaphore` | `--max-concurrent N` |
| 도구 등록 | `FastMCP.add_tool()` 동적 등록 | ToolRegistry 순회 |
| Agentic 실행 | AgentEngine (기존) | `agentic_task` 특수 도구 |
| 결과 축약 | 자체 미들웨어 | `max_result_tokens` 설정 |

## 2. 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MCP Server Mode                                   │
│                                                                      │
│  External MCP Client (Claude Code, Cursor, IDE Extension)            │
│         │                                                            │
│         │ stdio / Streamable HTTP (JSON-RPC 2.0)                     │
│         ▼                                                            │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │                  mcp/server.py (FastMCP)                      │    │
│  │                                                               │    │
│  │  ┌─────────────────────────┐  ┌───────────────────────────┐  │    │
│  │  │  Direct Pass-through    │  │  Agentic Execution         │  │    │
│  │  │                         │  │                             │  │    │
│  │  │  read_file()            │  │  agentic_task(prompt)       │  │    │
│  │  │  write_file()           │  │    ↓                        │  │    │
│  │  │  edit_file()            │  │  AgentEngine                │  │    │
│  │  │  glob_search()          │  │    ↓ LLM + tool loop       │  │    │
│  │  │  grep_search()          │  │  결과 반환                   │  │    │
│  │  │  run_command()          │  │                             │  │    │
│  │  │    ↓                    │  │                             │  │    │
│  │  │  Tool.execute() 직접   │  │                             │  │    │
│  │  │  LLM 미개입, <100ms    │  │                             │  │    │
│  │  └─────────────────────────┘  └───────────────────────────┘  │    │
│  │                                                               │    │
│  │  ┌─────────────────────────────────────────────────────────┐  │    │
│  │  │  Result Middleware                                       │  │    │
│  │  │  - _truncate_result(max_tokens=4000)                    │  │    │
│  │  │  - BIM 대량 데이터 축약                                   │  │    │
│  │  └─────────────────────────────────────────────────────────┘  │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  Concurrency Control                                          │    │
│  │  asyncio.Semaphore(max_concurrent)                            │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  MCP Client (기존 Phase 3) ←── Revit MCP, AutoCAD MCP 연결          │
└─────────────────────────────────────────────────────────────────────┘
```

## 3. 파일 구조 (변경/추가)

```
src/myaicoder/
├── tools/
│   └── base.py              # [수정] to_mcp_tool() 추가
│
├── mcp/
│   └── server.py            # [신규] FastMCP 서버, 동적 등록, agentic_task
│
├── core/
│   └── engine.py            # [수정] _truncate_tool_result(), 에러 재시도
│
└── cli.py                   # [수정] serve 커맨드 추가

tests/
└── test_mcp/
    └── test_server.py       # [신규] MCP 서버 테스트
```

## 4. 인터페이스 상세

### 4.1 Tool.to_mcp_tool() — `tools/base.py`

```python
class Tool(ABC):
    # ... 기존 메서드 ...

    def to_mcp_tool(self) -> dict:
        """Convert to MCP tool schema."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.parameters_schema,
        }
```

### 4.2 MCPServer — `mcp/server.py`

```python
"""MCP Server — exposes built-in tools via FastMCP."""

from mcp.server.fastmcp import FastMCP

from myaicoder.tools.base import Tool, ToolResult
from myaicoder.tools.registry import ToolRegistry


# MCP 도구명 매핑 (내부 → 외부)
TOOL_NAME_MAP = {
    "Read": "read_file",
    "Write": "write_file",
    "Edit": "edit_file",
    "Glob": "glob_search",
    "Grep": "grep_search",
    "Bash": "run_command",
}


class MCPServer:
    """FastMCP-based MCP server for myAiCoder tools.

    Supports two routing modes:
    - Direct Pass-through: Tool.execute() directly, no LLM (<100ms)
    - Agentic Execution: agentic_task() via AgentEngine (seconds~minutes)
    """

    def __init__(
        self,
        name: str = "myaicoder",
        tool_registry: ToolRegistry | None = None,
        allow_bash: bool = False,
        working_dir: str | None = None,
        max_concurrent: int = 1,
        max_result_tokens: int = 4000,
        enable_agentic: bool = False,
        llm_provider=None,
    ):
        self.mcp = FastMCP(name)
        self.registry = tool_registry
        self.allow_bash = allow_bash
        self.working_dir = working_dir
        self.max_concurrent = max_concurrent
        self.max_result_tokens = max_result_tokens
        self._semaphore: asyncio.Semaphore | None = None

        if tool_registry:
            self._register_tools()

        if enable_agentic and llm_provider:
            self._register_agentic_task(llm_provider)

    def _register_tools(self) -> None:
        """ToolRegistry의 모든 도구를 FastMCP에 동적 등록."""
        for tool in self.registry.all_tools():
            # Bash 보안: --allow-bash 없으면 스킵
            if tool.name == "Bash" and not self.allow_bash:
                continue

            mcp_name = TOOL_NAME_MAP.get(tool.name, tool.name.lower())
            self._register_single_tool(tool, mcp_name)

    def _register_single_tool(self, tool: Tool, mcp_name: str) -> None:
        """단일 도구를 FastMCP에 등록 (클로저 기반 동적 함수 생성)."""
        async def tool_handler(**kwargs) -> str:
            # 동시성 제어
            if self._semaphore:
                async with self._semaphore:
                    return await self._execute_and_format(tool, kwargs)
            return await self._execute_and_format(tool, kwargs)

        # FastMCP에 등록
        self.mcp.add_tool(
            tool_handler,
            name=mcp_name,
            description=tool.description,
        )

    async def _execute_and_format(self, tool: Tool, kwargs: dict) -> str:
        """도구 실행 + 결과 축약."""
        result = await tool.execute(**kwargs)

        if not result.success:
            return f"Error: {result.error}"

        return self._truncate_result(result.output)

    def _truncate_result(self, output: str) -> str:
        """BIM 등 대량 데이터를 컨텍스트에 맞게 축약."""
        max_chars = self.max_result_tokens * 4  # rough char-to-token
        if len(output) > max_chars:
            return output[:max_chars] + f"\n... (truncated, {len(output)} chars total)"
        return output

    def _register_agentic_task(self, llm_provider) -> None:
        """agentic_task 특수 도구 등록 (Agentic Execution 모드)."""
        registry = self.registry

        async def agentic_task(prompt: str) -> str:
            """Execute a complex multi-step task using local LLM agent.
            Use for high-level instructions like BIM modifications or
            multi-tool workflows. The local LLM handles sub-task planning."""
            from myaicoder.core.engine import AgentEngine

            engine = AgentEngine(
                llm=llm_provider,
                tool_registry=registry,
            )
            return await engine.chat(prompt)

        self.mcp.add_tool(
            agentic_task,
            name="agentic_task",
            description=(
                "Execute a complex multi-step task using local LLM agent. "
                "Use for high-level instructions like BIM modifications, "
                "multi-tool workflows, or tasks requiring reasoning."
            ),
        )

    def run(self, transport: str = "stdio") -> None:
        """MCP 서버 실행."""
        if self.max_concurrent > 1:
            self._semaphore = asyncio.Semaphore(self.max_concurrent)

        self.mcp.run(transport=transport)
```

### 4.3 에러 재시도 로직 — `core/engine.py`

```python
class AgentEngine:
    MAX_TOOL_ITERATIONS = 25
    MAX_TOOL_RETRIES = 2  # [신규] 도구 실행 재시도 횟수

    async def _execute_tool_with_approval(
        self, name: str, arguments: dict, tool_call_id: str
    ) -> ToolResult:
        """Execute a tool, checking approval if required."""
        if self._needs_approval(name):
            if self._approval_callback and not self._approval_callback(name, arguments):
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Tool '{name}' execution denied by user.",
                )

        # [신규] 재시도 로직 (파라미터/데이터 오류 한정)
        result = await self._execute_tool(name, arguments)

        if not result.success and self._is_retryable_error(result.error):
            for attempt in range(self.MAX_TOOL_RETRIES):
                result = await self._execute_tool(name, arguments)
                if result.success:
                    break

        return result

    def _is_retryable_error(self, error: str | None) -> bool:
        """재시도 가능한 에러인지 판별."""
        if not error:
            return False
        non_retryable = ["permission", "denied", "auth", "connection", "refused"]
        return not any(kw in error.lower() for kw in non_retryable)

    def _truncate_tool_result(self, result: str, max_tokens: int = 4000) -> str:
        """[신규] BIM 데이터 등 대량 결과를 컨텍스트에 맞게 축약."""
        max_chars = max_tokens * 4
        if len(result) > max_chars:
            return result[:max_chars] + f"\n... (truncated, {len(result)} chars total)"
        return result
```

`chat()` 메서드의 도구 결과 추가 부분에서 `_truncate_tool_result()` 적용:

```python
# chat() 메서드 내부 — 도구 결과를 대화에 추가할 때
content = result.output if result.success else f"Error: {result.error}"
content = self._truncate_tool_result(content)  # [신규]
self.conversation.add_message(
    Message(role="tool", content=content, tool_call_id=tc.id)
)
```

### 4.4 CLI `serve` 커맨드 — `cli.py`

```python
@main.command()
@click.option("--transport", default="stdio",
              type=click.Choice(["stdio", "streamable-http"]),
              help="MCP transport (default: stdio)")
@click.option("--port", default=3000, help="HTTP port (default: 3000)")
@click.option("--allow-bash", is_flag=True,
              help="Allow Bash tool (disabled by default for safety)")
@click.option("--working-dir", default=None,
              help="Restrict file operations to this directory")
@click.option("--max-concurrent", default=1,
              help="Max concurrent requests (default: 1)")
@click.option("--agentic", is_flag=True,
              help="Enable agentic_task tool for multi-step execution")
def serve(transport, port, allow_bash, working_dir, max_concurrent, agentic):
    """Run as MCP server (for Claude Code, Cursor, etc.)."""
    from myaicoder.mcp.server import MCPServer
    from myaicoder.tools.registry import create_default_registry

    registry = create_default_registry()

    # LLM provider for agentic mode
    llm_provider = None
    if agentic:
        from myaicoder.core.config import AppConfig
        from myaicoder.llm.vllm_provider import VLLMProvider
        config = AppConfig.load()
        llm_provider = VLLMProvider(
            base_url=config.llm.base_url,
            model=config.llm.model,
            max_tokens=config.llm.max_tokens,
        )

    server = MCPServer(
        tool_registry=registry,
        allow_bash=allow_bash,
        working_dir=working_dir,
        max_concurrent=max_concurrent,
        enable_agentic=agentic,
        llm_provider=llm_provider,
    )

    if transport == "streamable-http":
        import os
        os.environ.setdefault("FASTMCP_PORT", str(port))

    server.run(transport=transport)
```

## 5. MCP 도구 스키마

### 5.1 Direct Pass-through 도구 (6개)

| MCP Tool | Parameters | Description |
|----------|-----------|-------------|
| `read_file` | `file_path: str, offset?: int, limit?: int` | 파일 읽기 |
| `write_file` | `file_path: str, content: str` | 파일 쓰기 (자동 디렉토리 생성) |
| `edit_file` | `file_path: str, old_string: str, new_string: str, replace_all?: bool` | 파일 편집 (uniqueness 체크) |
| `glob_search` | `pattern: str, path?: str` | 파일 패턴 검색 (mtime 정렬) |
| `grep_search` | `pattern: str, path?: str, glob?: str, case_insensitive?: bool` | 파일 내용 정규식 검색 |
| `run_command` | `command: str, timeout?: int` | 셸 명령 실행 (`--allow-bash` 필요) |

### 5.2 Agentic 특수 도구 (1개, `--agentic` 시)

| MCP Tool | Parameters | Description |
|----------|-----------|-------------|
| `agentic_task` | `prompt: str` | 로컬 LLM으로 multi-step 작업 실행 |

## 6. 라우팅 및 에러 전파

### 6.1 라우팅 결정 트리

```
MCP tools/call 수신
    │
    ├── tool_name in [read_file, write_file, ...]
    │   → Direct Pass-through
    │   → Tool.execute() 직접 호출
    │   → _truncate_result() 적용
    │   → 응답 반환 (<100ms)
    │
    └── tool_name == "agentic_task"
        → Agentic Execution
        → AgentEngine.chat(prompt)
        → LLM agentic loop (tool_call 포함)
        → 최종 텍스트 응답 반환 (수초~수분)
```

### 6.2 에러 전파 플로우

```
Tool.execute() 실패
    │
    ├── _is_retryable_error() == True
    │   → 재시도 (최대 2회)
    │   ├── 성공 → 결과 반환
    │   └── 실패 → 에러 반환 (원문 포함)
    │
    └── _is_retryable_error() == False
        → 즉시 에러 반환
        → (connection, permission, auth 등)
```

Non-retryable 키워드: `permission`, `denied`, `auth`, `connection`, `refused`

## 7. 동시성 제어

```python
# MCPServer.__init__()
self._semaphore = asyncio.Semaphore(max_concurrent)

# 각 도구 핸들러 내부
async with self._semaphore:
    result = await tool.execute(**kwargs)
```

| `--max-concurrent` 값 | 동작 | 적합 시나리오 |
|:---------------------:|------|------------|
| 1 (기본) | 직렬 실행 | llama-server 단일 슬롯 |
| 2-4 | 제한적 병렬 | `--parallel N` 또는 경량 도구만 |
| 무제한 | 세마포어 미적용 | vLLM 서빙 시 |

## 8. 결과 축약 미들웨어

### 8.1 동작 규칙

```
도구 결과 (output string)
    │
    ├── len(output) <= max_chars (16000) → 그대로 전달
    │
    └── len(output) > max_chars
        → output[:max_chars] + "\n... (truncated, N chars total)"
```

- `max_result_tokens` 기본값: 4000 (≈ 16000 chars)
- MCP Server에서는 `MCPServer.max_result_tokens`로 제어
- AgentEngine에서는 `_truncate_tool_result()` 메서드로 제어
- 설정 가능: `config.tools.max_result_tokens` (config.py)

### 8.2 BIM 데이터 대응 전략

| 데이터 유형 | 크기 예상 | 축약 전략 |
|------------|----------|----------|
| Revit 요소 목록 | 수만 토큰 | ElementId 목록만 먼저 → 개별 상세 조회 |
| AutoCAD 레이어 | 수천 토큰 | 보통 그대로 전달 가능 |
| Revit 파라미터 전체 | 수만 토큰 | 필요 파라미터만 필터링 (MCP 쿼리 활용) |
| BIM 좌표 데이터 | 가변 | 요약 후 전달 (개수, 범위) |

## 9. Claude Code 호환 설정

### 9.1 stdio 모드 (기본)

```json
{
  "mcpServers": {
    "myaicoder": {
      "transport": "stdio",
      "command": "myaicoder",
      "args": ["serve"]
    }
  }
}
```

### 9.2 stdio + Bash 허용

```json
{
  "mcpServers": {
    "myaicoder": {
      "transport": "stdio",
      "command": "myaicoder",
      "args": ["serve", "--allow-bash"]
    }
  }
}
```

### 9.3 stdio + Agentic 모드

```json
{
  "mcpServers": {
    "myaicoder-agent": {
      "transport": "stdio",
      "command": "myaicoder",
      "args": ["serve", "--agentic", "--allow-bash"]
    }
  }
}
```

### 9.4 HTTP 모드 (원격)

```json
{
  "mcpServers": {
    "myaicoder-remote": {
      "transport": "http",
      "url": "http://192.168.1.100:3000/mcp"
    }
  }
}
```

## 10. MCP 체이닝 아키텍처

MCP Server + MCP Client 동시 구동 시:

```
┌────────────────────────────────────────────────┐
│  myAiCoder (serve --agentic)                    │
│                                                  │
│  MCP Server (FastMCP)     MCP Client (Phase 3)  │
│  ┌──────────────────┐    ┌────────────────────┐ │
│  │ read_file         │    │ Revit MCP 서버      │ │
│  │ write_file         │    │ AutoCAD MCP 서버    │ │
│  │ edit_file          │    │ (via .mcp.json)     │ │
│  │ glob_search        │    └─────────┬──────────┘ │
│  │ grep_search        │              │             │
│  │ run_command         │              │             │
│  │ agentic_task ──────┼──→ AgentEngine             │
│  └──────────────────┘    │  ↓ LLM 판단             │
│                          │  ↓ Revit/CAD MCP 호출   │
│                          │  ↓ 결과 수집              │
│                          │  ↓ 응답 반환              │
│                          └──────────────────────────┘
│                                                  │
│  LLM Provider (llama-server / vLLM)             │
└────────────────────────────────────────────────┘
```

`agentic_task` 호출 시, AgentEngine은 ToolRegistry에 등록된 모든 도구(내장 + MCP Client의 Revit/CAD 도구)를 사용할 수 있다. CLI의 `_run_chat()`과 동일한 MCP Client 초기화 로직을 적용.

## 11. 테스트 설계

### 11.1 `tests/test_mcp/test_server.py`

| # | 테스트 | 설명 |
|---|--------|------|
| 1 | `test_server_creation` | MCPServer 인스턴스 생성, 도구 등록 확인 |
| 2 | `test_tool_registration_count` | 6개 도구 등록 (Bash 포함 시 6, 미포함 시 5) |
| 3 | `test_bash_excluded_by_default` | `allow_bash=False`일 때 run_command 미등록 |
| 4 | `test_bash_included_when_allowed` | `allow_bash=True`일 때 run_command 등록 |
| 5 | `test_tool_name_mapping` | Read→read_file, Write→write_file 등 매핑 확인 |
| 6 | `test_direct_tool_execution` | read_file 직접 실행, 결과 반환 |
| 7 | `test_result_truncation` | 대량 결과 축약 동작 확인 |
| 8 | `test_result_no_truncation` | 작은 결과는 그대로 전달 |
| 9 | `test_agentic_task_registration` | `enable_agentic=True`일 때 agentic_task 도구 등록 |
| 10 | `test_error_retryable` | `_is_retryable_error()` 판별 로직 |
| 11 | `test_error_non_retryable` | connection/permission 에러는 재시도 안 함 |
| 12 | `test_concurrency_semaphore` | `max_concurrent=2`일 때 세마포어 동작 |

### 11.2 기존 테스트 수정

| 파일 | 변경 |
|------|------|
| `tests/test_core/test_engine.py` | `_truncate_tool_result()` 테스트 추가 |
| `tests/test_tools/test_registry.py` | `to_mcp_tool()` 테스트 추가 |

## 12. 구현 순서

| Step | 작업 | 파일 | 의존성 |
|:----:|------|------|--------|
| 1 | `Tool.to_mcp_tool()` 추가 | `tools/base.py` | - |
| 2 | `MCPServer` 클래스 (기본) | `mcp/server.py` | Step 1 |
| 3 | ToolRegistry → FastMCP 동적 등록 | `mcp/server.py` | Step 2 |
| 4 | `_truncate_tool_result()` 미들웨어 | `core/engine.py` | - |
| 5 | `_is_retryable_error()` + 재시도 | `core/engine.py` | - |
| 6 | `serve` CLI 커맨드 | `cli.py` | Step 2-3 |
| 7 | `--transport`, `--port`, `--max-concurrent` | `cli.py` + `mcp/server.py` | Step 6 |
| 8 | `--allow-bash`, `--working-dir` | `cli.py` + `mcp/server.py` | Step 6 |
| 9 | `agentic_task` 등록 + `--agentic` | `mcp/server.py` + `cli.py` | Step 3 |
| 10 | 단위 테스트 (12건) | `tests/test_mcp/test_server.py` | Step 1-9 |
| 11 | 기존 테스트 보강 | `test_engine.py`, `test_registry.py` | Step 4-5 |
| 12 | Claude Code 호환 통합 테스트 | 수동 | Step 10 |
| 13 | Revit/CAD MCP 연결 검증 | 수동 + 문서화 | Step 12 |
| 14 | MCP 체이닝 프로토타입 | `cli.py` serve + MCP Client | Step 9 |

## 13. 설정 확장 — `core/config.py`

```python
@dataclass
class ToolsConfig:
    enabled: bool = True
    require_approval: list[str] = field(
        default_factory=lambda: ["Bash", "Write", "Edit"]
    )
    auto_approve: list[str] = field(
        default_factory=lambda: ["Read", "Glob", "Grep"]
    )
    max_result_tokens: int = 4000  # [신규] 도구 결과 축약 임계값

@dataclass
class ServerConfig:   # [신규]
    """MCP Server 설정."""
    transport: str = "stdio"
    port: int = 3000
    allow_bash: bool = False
    working_dir: str | None = None
    max_concurrent: int = 1
    enable_agentic: bool = False

@dataclass
class AppConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    tools: ToolsConfig = field(default_factory=ToolsConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    server: ServerConfig = field(default_factory=ServerConfig)  # [신규]
```

---

*작성일: 2026-03-13 | Phase: Design | Status: Complete*
*Plan 참조: docs/pdca/01-plan/features/mcp-server.plan.md*
