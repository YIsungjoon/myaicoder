# Design: myAiCoder (AI Coder CLI)

**Feature**: ai-coder-cli
**날짜**: 2026-03-13
**Phase**: Design
**Level**: Enterprise
**Plan 참조**: `docs/pdca/01-plan/features/ai-coder-cli.plan.md`

---

## 1. 기술 스택 확정

| 영역 | 기술 | 버전/비고 |
|------|------|----------|
| CLI 프레임워크 | Python + rich + click | rich(터미널 UI), click(CLI 파싱) |
| TUI (대화형 UI) | textual | 터미널 대화형 인터페이스 |
| MCP SDK | mcp (Python SDK) | Tier 1, FastMCP 모듈 포함 |
| LLM 추론 | vLLM | OpenAI-compatible API |
| LLM 클라이언트 | openai (Python SDK) | vLLM의 OpenAI API로 통신 |
| IDE 확장 | TypeScript + VS Code Extension API | VS Code/Windsurf 호환 |
| 설정 관리 | JSON (.mcp.json, config.json) | Claude Code 호환 |
| 패키지 관리 | uv (또는 pip) | Python 패키지 |
| 테스트 | pytest + pytest-asyncio | 비동기 테스트 지원 |

## 2. 시스템 아키텍처 (상세)

```
┌─────────────────────────────────────────────────────────────────┐
│                         myAiCoder                               │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    Interface Layer                         │  │
│  │                                                           │  │
│  │  ┌─────────────┐  ┌──────────────────────────────────┐   │  │
│  │  │  CLI (rich)  │  │  VS Code Extension (TypeScript)  │   │  │
│  │  │  click CLI   │  │  WebSocket/stdio ↔ Core Engine   │   │  │
│  │  └──────┬──────┘  └───────────────┬──────────────────┘   │  │
│  │         └─────────────┬───────────┘                       │  │
│  └───────────────────────┼───────────────────────────────────┘  │
│                          ▼                                       │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    Core Engine                             │  │
│  │                                                           │  │
│  │  ┌──────────────┐ ┌──────────────┐ ┌─────────────────┐  │  │
│  │  │ Conversation │ │ Tool Executor│ │Context Manager  │  │  │
│  │  │   Manager    │ │              │ │                 │  │  │
│  │  │ - 대화 루프   │ │ - tool 실행  │ │ - 프로젝트 스캔  │  │  │
│  │  │ - 히스토리    │ │ - 결과 수집  │ │ - CLAUDE.md 로딩│  │  │
│  │  │ - 토큰 관리   │ │ - 권한 확인  │ │ - .gitignore   │  │  │
│  │  └──────┬───────┘ └──────┬───────┘ └────────┬────────┘  │  │
│  │         └────────────────┼──────────────────┘            │  │
│  └──────────────────────────┼────────────────────────────────┘  │
│                             ▼                                    │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    MCP Layer                               │  │
│  │                                                           │  │
│  │  ┌─────────────────────┐  ┌────────────────────────────┐ │  │
│  │  │    MCP Client        │  │      MCP Server             │ │  │
│  │  │                     │  │                              │ │  │
│  │  │ - .mcp.json 로딩    │  │  - Built-in Tools:          │ │  │
│  │  │ - stdio transport   │  │    Read, Write, Edit,       │ │  │
│  │  │ - HTTP transport    │  │    Glob, Grep, Bash         │ │  │
│  │  │ - tool discovery    │  │  - stdio/HTTP 노출          │ │  │
│  │  │ - capability nego.  │  │  - JSON-RPC 2.0             │ │  │
│  │  └─────────────────────┘  └────────────────────────────┘ │  │
│  └───────────────────────────────────────────────────────────┘  │
│                             ▼                                    │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                 LLM Provider Layer                         │  │
│  │                                                           │  │
│  │  ┌─────────────────────┐  ┌────────────────────────────┐ │  │
│  │  │   LLM Client        │  │   vLLM Server (별도 프로세스)│ │  │
│  │  │   (OpenAI SDK)       │  │   Qwen3.5-27B INT4         │ │  │
│  │  │                     │  │   http://localhost:8000     │ │  │
│  │  │ - chat completion   │  │   /v1/chat/completions     │ │  │
│  │  │ - tool_call 파싱    │  │   /v1/models               │ │  │
│  │  │ - streaming         │  │                              │ │  │
│  │  └─────────────────────┘  └────────────────────────────┘ │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## 3. 디렉토리 구조 (Python 패키지)

```
services/myaicoder/
├── pyproject.toml              # 패키지 설정 (uv/pip)
├── README.md
│
├── src/
│   └── myaicoder/
│       ├── __init__.py
│       ├── __main__.py         # python -m myaicoder 진입점
│       ├── cli.py              # click CLI 정의 (진입점)
│       │
│       ├── core/               # Core Engine
│       │   ├── __init__.py
│       │   ├── engine.py       # 메인 에이전트 루프
│       │   ├── conversation.py # 대화 관리 (히스토리, 토큰)
│       │   ├── context.py      # 프로젝트 컨텍스트 관리
│       │   └── config.py       # 설정 로딩 (config.json)
│       │
│       ├── llm/                # LLM Provider Layer
│       │   ├── __init__.py
│       │   ├── base.py         # ABC: LLMProvider 인터페이스
│       │   ├── vllm_provider.py    # vLLM 구현체
│       │   └── openai_provider.py  # OpenAI API 호환 구현체
│       │
│       ├── tools/              # Built-in Tools
│       │   ├── __init__.py
│       │   ├── base.py         # ABC: Tool 인터페이스
│       │   ├── registry.py     # Tool 레지스트리
│       │   ├── read.py         # 파일 읽기
│       │   ├── write.py        # 파일 쓰기
│       │   ├── edit.py         # 파일 편집 (diff 기반)
│       │   ├── glob_tool.py    # 파일 검색 (glob)
│       │   ├── grep_tool.py    # 내용 검색 (ripgrep)
│       │   └── bash.py         # 명령어 실행
│       │
│       ├── mcp/                # MCP Layer
│       │   ├── __init__.py
│       │   ├── client.py       # MCP Client (외부 서버 연결)
│       │   ├── server.py       # MCP Server (자체 도구 노출)
│       │   ├── config.py       # .mcp.json 파싱
│       │   ├── transport/
│       │   │   ├── __init__.py
│       │   │   ├── stdio.py    # stdio 트랜스포트
│       │   │   └── http.py     # Streamable HTTP 트랜스포트
│       │   └── protocol.py     # JSON-RPC 2.0 메시지 처리
│       │
│       ├── ui/                 # 터미널 UI
│       │   ├── __init__.py
│       │   ├── chat.py         # 대화형 인터페이스 (rich)
│       │   ├── markdown.py     # 마크다운 렌더링
│       │   └── spinner.py      # 로딩 표시
│       │
│       └── utils/              # 유틸리티
│           ├── __init__.py
│           ├── tokens.py       # 토큰 카운팅
│           └── files.py        # 파일 유틸리티
│
├── tests/
│   ├── conftest.py
│   ├── test_core/
│   │   ├── test_engine.py
│   │   └── test_conversation.py
│   ├── test_tools/
│   │   ├── test_read.py
│   │   ├── test_write.py
│   │   └── test_edit.py
│   ├── test_mcp/
│   │   ├── test_client.py
│   │   └── test_server.py
│   └── test_llm/
│       └── test_vllm_provider.py
│
└── scripts/
    ├── start_vllm.sh           # vLLM 서버 시작 스크립트
    └── setup.sh                # 개발 환경 설정
```

## 4. 핵심 인터페이스 설계

### 4.1 LLM Provider (ABC)

```python
# src/myaicoder/llm/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator

@dataclass
class Message:
    role: str               # "system" | "user" | "assistant" | "tool"
    content: str | None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict

@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCall] | None
    usage: dict  # {"prompt_tokens": int, "completion_tokens": int}

class LLMProvider(ABC):
    """LLM 추론 제공자 인터페이스.

    향후 언어 전환 시 이 인터페이스만 재구현하면 됨.
    """

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """동기 응답 (전체 응답 반환)."""
        pass

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        temperature: float = 0.0,
    ) -> AsyncIterator[str]:
        """스트리밍 응답 (토큰 단위)."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """추론 서버 상태 확인."""
        pass
```

### 4.2 Tool (ABC)

```python
# src/myaicoder/tools/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ToolResult:
    success: bool
    output: str
    error: str | None = None

class Tool(ABC):
    """도구 인터페이스. MCP Server에서도 이 인터페이스를 노출함."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @property
    @abstractmethod
    def parameters_schema(self) -> dict:
        """OpenAI function calling 호환 JSON Schema."""
        pass

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        pass

    def to_openai_tool(self) -> dict:
        """OpenAI function calling 스키마로 변환."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            }
        }

    def to_mcp_tool(self) -> dict:
        """MCP tool 스키마로 변환."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.parameters_schema,
        }
```

### 4.3 Tool Registry

```python
# src/myaicoder/tools/registry.py
class ToolRegistry:
    """도구 등록소. Built-in + MCP 외부 도구 통합 관리."""

    def __init__(self):
        self._builtin_tools: dict[str, Tool] = {}
        self._mcp_tools: dict[str, MCPToolProxy] = {}

    def register_builtin(self, tool: Tool) -> None:
        self._builtin_tools[tool.name] = tool

    def register_mcp_tools(self, server_name: str, tools: list[dict]) -> None:
        for tool_schema in tools:
            proxy = MCPToolProxy(server_name, tool_schema)
            self._mcp_tools[f"{server_name}__{proxy.name}"] = proxy

    def get_tool(self, name: str) -> Tool | MCPToolProxy | None:
        return self._builtin_tools.get(name) or self._mcp_tools.get(name)

    def all_as_openai_tools(self) -> list[dict]:
        """모든 도구를 OpenAI function calling 스키마로 반환."""
        tools = []
        for t in self._builtin_tools.values():
            tools.append(t.to_openai_tool())
        for t in self._mcp_tools.values():
            tools.append(t.to_openai_tool())
        return tools
```

### 4.4 Core Engine (Agentic Loop)

```python
# src/myaicoder/core/engine.py
class AgentEngine:
    """메인 에이전트 루프. LLM과 Tool 실행을 반복."""

    def __init__(
        self,
        llm: LLMProvider,
        tool_registry: ToolRegistry,
        context_manager: ContextManager,
    ):
        self.llm = llm
        self.tools = tool_registry
        self.context = context_manager
        self.conversation = ConversationManager()

    async def run(self, user_input: str) -> AsyncIterator[str]:
        """사용자 입력 → LLM 응답 (도구 실행 포함)."""

        # 1. 시스템 프롬프트 + 컨텍스트 구성
        system_prompt = self.context.build_system_prompt()
        self.conversation.add_message(Message(role="user", content=user_input))

        # 2. Agentic Loop
        while True:
            messages = self.conversation.get_messages(system_prompt)
            tools_schema = self.tools.all_as_openai_tools()

            response = await self.llm.chat(
                messages=messages,
                tools=tools_schema if tools_schema else None,
            )

            # 3. 텍스트 응답만 있으면 종료
            if response.content and not response.tool_calls:
                self.conversation.add_message(
                    Message(role="assistant", content=response.content)
                )
                yield response.content
                break

            # 4. Tool Call 실행
            if response.tool_calls:
                self.conversation.add_message(
                    Message(
                        role="assistant",
                        content=response.content,
                        tool_calls=response.tool_calls,
                    )
                )

                for tool_call in response.tool_calls:
                    # 권한 확인 UI (사용자 승인)
                    tool = self.tools.get_tool(tool_call.name)
                    if tool is None:
                        result = ToolResult(
                            success=False, output="", error=f"Unknown tool: {tool_call.name}"
                        )
                    else:
                        result = await tool.execute(**tool_call.arguments)

                    self.conversation.add_message(
                        Message(
                            role="tool",
                            content=result.output if result.success else f"Error: {result.error}",
                            tool_call_id=tool_call.id,
                        )
                    )

                # 텍스트 부분이 있으면 중간 출력
                if response.content:
                    yield response.content
```

### 4.5 MCP Client

```python
# src/myaicoder/mcp/client.py
class MCPClient:
    """Claude Code 호환 MCP 클라이언트.

    .mcp.json을 로딩하여 외부 MCP 서버에 연결하고,
    도구를 ToolRegistry에 등록한다.
    """

    def __init__(self, config_path: str | None = None):
        self.config = MCPConfig.load(config_path)  # .mcp.json
        self.sessions: dict[str, MCPSession] = {}

    async def connect_all(self) -> None:
        """설정된 모든 MCP 서버에 연결."""
        for name, server_config in self.config.servers.items():
            transport = self._create_transport(server_config)
            session = MCPSession(name, transport)
            await session.initialize()
            self.sessions[name] = session

    async def discover_tools(self) -> list[dict]:
        """모든 연결된 서버의 도구 목록 수집."""
        all_tools = []
        for name, session in self.sessions.items():
            tools = await session.list_tools()
            for tool in tools:
                tool["_server"] = name  # 소속 서버 표시
            all_tools.extend(tools)
        return all_tools

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict) -> dict:
        """특정 서버의 도구 실행."""
        session = self.sessions[server_name]
        return await session.call_tool(tool_name, arguments)

    def _create_transport(self, config: dict):
        if config["transport"] == "stdio":
            return StdioTransport(
                command=config["command"],
                args=config.get("args", []),
                env=config.get("env", {}),
            )
        elif config["transport"] == "http":
            return HTTPTransport(url=config["url"])
```

### 4.6 MCP Config (.mcp.json 호환)

```python
# src/myaicoder/mcp/config.py
@dataclass
class MCPServerConfig:
    transport: str          # "stdio" | "http"
    command: str | None     # stdio용
    args: list[str] | None  # stdio용
    env: dict | None        # 환경변수
    url: str | None         # http용

@dataclass
class MCPConfig:
    servers: dict[str, MCPServerConfig]

    @classmethod
    def load(cls, path: str | None = None) -> "MCPConfig":
        """Claude Code 호환 .mcp.json 로딩.

        탐색 순서:
        1. 명시된 path
        2. {project_root}/.mcp.json  (프로젝트 스코프)
        3. ~/.myaicoder/mcp.json     (사용자 스코프)
        """
        ...
```

### 4.7 Context Manager

```python
# src/myaicoder/core/context.py
class ContextManager:
    """프로젝트 컨텍스트 관리.

    Claude Code의 CLAUDE.md 로딩 방식과 호환.
    """

    def __init__(self, working_dir: str):
        self.working_dir = working_dir

    def build_system_prompt(self) -> str:
        """시스템 프롬프트 구성."""
        parts = [self._base_prompt()]

        # CLAUDE.md 로딩 (계층적)
        claude_md = self._load_claude_md()
        if claude_md:
            parts.append(f"# Project Context\n{claude_md}")

        # 프로젝트 구조 요약
        structure = self._scan_project_structure()
        parts.append(f"# Project Structure\n{structure}")

        return "\n\n".join(parts)

    def _load_claude_md(self) -> str | None:
        """CLAUDE.md 계층적 로딩.

        1. {working_dir}/CLAUDE.md (프로젝트 루트)
        2. {current_subdir}/CLAUDE.md (서브 디렉토리)
        3. ~/.myaicoder/CLAUDE.md (글로벌)
        """
        ...

    def _scan_project_structure(self) -> str:
        """프로젝트 디렉토리 구조 스캔 (.gitignore 존중)."""
        ...
```

## 5. CLI 커맨드 설계

```
myaicoder                     # 대화형 모드 시작 (기본)
myaicoder "질문 내용"          # 원샷 모드
myaicoder --model <model>     # 모델 지정
myaicoder --vllm-url <url>    # vLLM 서버 주소 (기본: http://localhost:8000)
myaicoder --no-tools          # 도구 비활성화
myaicoder --verbose           # 디버그 로그 출력

# MCP 관리
myaicoder mcp list            # MCP 서버 목록
myaicoder mcp add <name>      # MCP 서버 추가
myaicoder mcp remove <name>   # MCP 서버 제거

# 서버 모드
myaicoder serve               # MCP 서버로 실행 (다른 클라이언트가 연결 가능)

# 설정
myaicoder config              # 설정 확인/편집
```

## 6. 데이터 흐름

### 6.1 사용자 입력 → 응답 흐름

```
사용자 입력
    │
    ▼
[CLI] user_input 수신
    │
    ▼
[ContextManager] 시스템 프롬프트 구성
    │  - CLAUDE.md 로딩
    │  - 프로젝트 구조 스캔
    │
    ▼
[ConversationManager] 메시지 히스토리 구성
    │  - 시스템 프롬프트 + 히스토리 + user_input
    │  - 토큰 제한 초과 시 오래된 메시지 압축
    │
    ▼
[LLMProvider.chat()] vLLM 서버로 요청
    │  - messages + tools 스키마
    │  - POST /v1/chat/completions
    │
    ▼
[응답 파싱]
    │
    ├── content만 있음 → 텍스트 출력 → 종료
    │
    └── tool_calls 있음
         │
         ▼
    [ToolRegistry.get_tool()] 도구 조회
         │
         ├── Built-in Tool → 직접 실행
         │     (Read, Write, Edit, Glob, Grep, Bash)
         │
         └── MCP Tool → MCPClient.call_tool()
               │  JSON-RPC 요청 → MCP 서버 → 결과
               │
               ▼
         [결과를 messages에 추가]
               │
               ▼
         [LLMProvider.chat()] 다시 요청 ← Agentic Loop
```

### 6.2 MCP 서버 연결 흐름

```
시작 시
    │
    ▼
[MCPConfig.load()] .mcp.json 로딩
    │
    ▼
[MCPClient.connect_all()]
    │
    ├── stdio 서버 → subprocess 시작 → stdin/stdout 연결
    │     initialize → capabilities 교환 → tools/list
    │
    └── HTTP 서버 → HTTP POST 연결
          initialize → capabilities 교환 → tools/list
    │
    ▼
[ToolRegistry.register_mcp_tools()] 외부 도구 등록
    │
    ▼
도구 사용 가능 상태
```

## 7. 설정 파일 형식

### 7.1 myaicoder config.json

```json
{
  "llm": {
    "provider": "vllm",
    "base_url": "http://localhost:8000/v1",
    "model": "Qwen/Qwen3.5-27B-INT4",
    "temperature": 0.0,
    "max_tokens": 8192
  },
  "tools": {
    "enabled": true,
    "require_approval": ["Bash", "Write", "Edit"],
    "auto_approve": ["Read", "Glob", "Grep"]
  },
  "context": {
    "max_tokens": 32768,
    "compression_threshold": 0.8
  },
  "ui": {
    "theme": "dark",
    "markdown_render": true,
    "show_token_usage": true
  }
}
```

### 7.2 .mcp.json (Claude Code 호환)

```json
{
  "mcpServers": {
    "github": {
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      }
    },
    "filesystem": {
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path"]
    },
    "remote-server": {
      "transport": "http",
      "url": "https://mcp.example.com/sse"
    }
  }
}
```

## 8. Built-in Tools 상세

| Tool | 설명 | 주요 파라미터 | 권한 |
|------|------|-------------|------|
| **Read** | 파일 읽기 | `file_path`, `offset`, `limit` | auto |
| **Write** | 파일 생성/덮어쓰기 | `file_path`, `content` | approval |
| **Edit** | 파일 부분 편집 | `file_path`, `old_string`, `new_string` | approval |
| **Glob** | 파일 패턴 검색 | `pattern`, `path` | auto |
| **Grep** | 내용 검색 | `pattern`, `path`, `glob` | auto |
| **Bash** | 명령어 실행 | `command`, `timeout` | approval |

### 권한 모델

```
auto       → 자동 승인 (읽기 전용 도구)
approval   → 사용자 승인 필요 (쓰기/실행 도구)
deny       → 사용 불가
```

## 9. VS Code 확장 설계 (개요)

```
extensions/vscode-myaicoder/
├── package.json
├── src/
│   ├── extension.ts          # 확장 진입점
│   ├── chat-provider.ts      # 채팅 패널 제공자
│   ├── myaicoder-client.ts   # Python 백엔드와 통신
│   └── webview/              # 채팅 UI (WebView)
│       ├── index.html
│       └── chat.ts
└── tsconfig.json
```

### 통신 방식

```
VS Code Extension (TypeScript)
    │
    │  stdio 또는 WebSocket
    │
    ▼
myAiCoder Core Engine (Python)
    │  - myaicoder serve --mode=ide
    │  - JSON-RPC 프로토콜
    │
    ▼
vLLM Server
```

## 10. 구현 순서 (Implementation Order)

### Phase 1: 기본 CLI + LLM 연동 (M1)
1. `pyproject.toml` + 프로젝트 초기화
2. `llm/base.py` — LLMProvider ABC
3. `llm/vllm_provider.py` — vLLM 구현체
4. `cli.py` — click 기본 CLI
5. `ui/chat.py` — rich 기반 대화 UI
6. `core/conversation.py` — 대화 관리
7. `core/engine.py` — 기본 에이전트 루프 (도구 없이)
8. 통합 테스트: CLI에서 vLLM과 대화

### Phase 2: Tool Use (M2)
1. `tools/base.py` — Tool ABC
2. `tools/registry.py` — Tool Registry
3. `tools/read.py`, `write.py`, `edit.py` — 파일 도구
4. `tools/glob_tool.py`, `grep_tool.py` — 검색 도구
5. `tools/bash.py` — 명령어 실행
6. `core/engine.py` 확장 — tool_call 처리 루프
7. 권한 확인 UI 구현

### Phase 3: MCP Client (M3)
1. `mcp/config.py` — .mcp.json 파싱
2. `mcp/transport/stdio.py` — stdio 트랜스포트
3. `mcp/transport/http.py` — HTTP 트랜스포트
4. `mcp/client.py` — MCP Client
5. `tools/registry.py` 확장 — MCP 도구 통합
6. Claude Code의 MCP 서버로 호환 테스트

### Phase 4: MCP Server (M4)
1. `mcp/server.py` — MCP Server (Built-in 도구 노출)
2. `myaicoder serve` 커맨드 구현
3. 외부 MCP 클라이언트에서 연결 테스트

### Phase 5: 컨텍스트 + 세션 (M6)
1. `core/context.py` — CLAUDE.md 로딩, 프로젝트 스캔
2. `core/conversation.py` 확장 — 토큰 관리, 히스토리 압축
3. `utils/tokens.py` — 토큰 카운팅

### Phase 6: VS Code 확장 (M5)
1. `extensions/vscode-myaicoder/` 프로젝트 초기화
2. 채팅 패널 UI
3. Python 백엔드 통신 (stdio)
4. VS Code Marketplace 준비

### Phase 7: 안정화 + 배포 (M7)
1. 테스트 커버리지 확보
2. PyPI 패키지 배포
3. 문서화

## 11. 의존성 목록

### Python (pyproject.toml)

```toml
[project]
name = "myaicoder"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
    "click>=8.1",
    "rich>=13.0",
    "openai>=1.0",
    "mcp>=1.0",
    "pydantic>=2.0",
    "aiofiles>=23.0",
    "httpx>=0.27",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "ruff>=0.5",
]

[project.scripts]
myaicoder = "myaicoder.cli:main"
```

---

*작성일: 2026-03-13 | Phase: Design | Status: Complete*
*Plan 참조: docs/pdca/01-plan/features/ai-coder-cli.plan.md*
