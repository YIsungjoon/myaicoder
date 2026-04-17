# Design: deepagent-alignment

> DeepAgent 참조 Agent 능력 강화 — Middleware Stack, Sub-Agent, Planning, Memory

| Meta | Value |
|------|-------|
| Plan | [deepagent-alignment.plan.md](../../01-plan/features/deepagent-alignment.plan.md) |
| Architecture | Option B — Clean Architecture (ContextPayload + AgentMiddleware ABC) |
| Created | 2026-03-24 |

## Context Anchor

| Key | Value |
|-----|-------|
| **WHY** | engine.py 단일 루프의 확장 한계 → DeepAgent 수준의 Agent 능력 필요 |
| **WHO** | DGX 서버를 공유하는 팀 개발자 |
| **RISK** | 기존 178개 테스트 깨짐, engine.py 리팩토링 시 VS Code Extension 연동 장애 |
| **SUCCESS** | 복잡 작업 자동 분할 + 세션 간 컨텍스트 유지 + Middleware 기반 확장성 |
| **SCOPE** | Middleware Stack + Sub-Agent + Planning + Memory (v1 범위) |

---

## 1. Overview

### 1.1 설계 목표
기존 `AgentEngine` (194줄, 단일 agentic loop)을 Middleware Stack 기반 orchestrator로
리팩토링하고, Sub-Agent/Planning/Memory를 독립 Middleware로 조합한다.

### 1.2 선택된 아키텍처
**Option B — Clean Architecture**: ContextPayload 패턴(DS-01) + AgentMiddleware ABC +
MiddlewareStack + Strangler Fig 마이그레이션(DS-03)

### 1.3 핵심 설계 원칙
- **Append-Only**: Middleware는 messages를 직접 수정하지 않음 (DS-01)
- **Output Boundary**: Sub-Agent 결과는 강제 압축 (DS-02, ≤1000토큰)
- **Strangler Fig**: 기존 AgentEngine 유지 → MiddlewareEngine 병행 → 점진 전환 (DS-03)
- **Zero Breaking Change**: 기존 Tool, LLMProvider, ContextManager 인터페이스 불변

---

## 2. Core Interfaces

### 2.1 ContextPayload (DS-01) — Frozen Immutable

```python
# core/middleware/base.py

from __future__ import annotations
from dataclasses import dataclass, field, replace
from myaicoder.llm.base import Message

@dataclass(frozen=True)
class ContextPayload:
    """Structurally immutable context passed through middleware stack.

    frozen=True + tuple = 컴파일 타임 수준의 불변성 보장.
    list.append()로 "규칙 위반"이 아니라 tuple로 "구조적 불가능".
    각 Middleware는 with_*() 메서드로 새 Payload를 반환한다.
    """
    messages: tuple[Message, ...] = field(default_factory=tuple)
    system_instructions: tuple[str, ...] = field(default_factory=tuple)
    tools: tuple[dict, ...] = field(default_factory=tuple)
    metadata: dict = field(default_factory=dict)  # shallow copy 주의

    def with_instruction(self, instruction: str) -> ContextPayload:
        """Add a system instruction (returns new payload)."""
        return replace(self, system_instructions=self.system_instructions + (instruction,))

    def with_tools(self, tools: list[dict]) -> ContextPayload:
        """Add tools (returns new payload)."""
        return replace(self, tools=self.tools + tuple(tools))

    def with_metadata(self, key: str, value: object) -> ContextPayload:
        """Set metadata key (returns new payload with shallow-copied dict)."""
        return replace(self, metadata={**self.metadata, key: value})
```

**Middleware 사용 패턴**:
```python
# Before (mutable list — 규칙으로만 금지, 실수 가능):
#   payload.system_instructions.append("...")  # 위험: 원본 변경

# After (frozen tuple — 구조적으로 불가능):
payload = payload.with_instruction("Plan your work before execution.")
payload = payload.with_tools([write_todos_schema])
# payload.system_instructions.append(...)  # FrozenInstanceError!
```

### 2.2 AgentMiddleware ABC

```python
# core/middleware/base.py

from abc import ABC, abstractmethod
from myaicoder.tools.base import ToolResult

class AgentMiddleware(ABC):
    """Base class for all middleware in the agent pipeline."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique middleware identifier."""
        ...

    @property
    def priority(self) -> int:
        """Execution order. Lower = earlier. Default 100."""
        return 100

    async def before(self, payload: ContextPayload) -> ContextPayload:
        """Pre-LLM hook. Inject tools/instructions into payload.

        Use payload.with_instruction() / payload.with_tools() to return
        a new frozen payload. Direct mutation raises FrozenInstanceError.
        """
        return payload

    async def handle_tool(self, tool_name: str, arguments: dict) -> ToolResult | None:
        """Handle a tool call. Return None to pass to next middleware.

        If this middleware owns the tool, execute and return ToolResult.
        If not, return None (chain of responsibility).
        """
        return None

    async def after(self, payload: ContextPayload) -> ContextPayload:
        """Post-LLM hook. Process response, update state."""
        return payload
```

### 2.3 MiddlewareStack

```python
# core/middleware/stack.py

from myaicoder.core.middleware.base import AgentMiddleware, ContextPayload
from myaicoder.llm.base import Message
from myaicoder.tools.base import ToolResult

class MiddlewareStack:
    """Orchestrates middleware pipeline execution."""

    def __init__(self, middlewares: list[AgentMiddleware] | None = None):
        self._middlewares: list[AgentMiddleware] = []
        if middlewares:
            for mw in middlewares:
                self.add(mw)

    def add(self, middleware: AgentMiddleware) -> None:
        """Add middleware and re-sort by priority."""
        self._middlewares.append(middleware)
        self._middlewares.sort(key=lambda m: m.priority)

    async def process_before(self, payload: ContextPayload) -> ContextPayload:
        """Run all middleware before() hooks in priority order."""
        for mw in self._middlewares:
            payload = await mw.before(payload)
        return payload

    async def handle_tool(self, tool_name: str, arguments: dict) -> ToolResult | None:
        """Chain of responsibility: first middleware to handle wins."""
        for mw in self._middlewares:
            result = await mw.handle_tool(tool_name, arguments)
            if result is not None:
                return result
        return None

    async def process_after(self, payload: ContextPayload) -> ContextPayload:
        """Run all middleware after() hooks in REVERSE priority order."""
        for mw in reversed(self._middlewares):
            payload = await mw.after(payload)
        return payload

    def merge_system_prompt(self, base_prompt: str, payload: ContextPayload) -> str:
        """Merge base prompt with all middleware system instructions."""
        if not payload.system_instructions:
            return base_prompt
        parts = [base_prompt, *payload.system_instructions]
        return "\n\n".join(parts)

    @property
    def middleware_names(self) -> list[str]:
        return [mw.name for mw in self._middlewares]
```

---

## 3. Middleware Implementations

### 3.1 FilesystemMiddleware (기존 도구 래핑)

```python
# core/middleware/filesystem.py

class FilesystemMiddleware(AgentMiddleware):
    """Wraps existing ToolRegistry as a middleware."""

    name = "filesystem"
    priority = 50  # 기본 도구는 먼저 등록

    def __init__(self, registry: ToolRegistry):
        self._registry = registry

    async def before(self, payload: ContextPayload) -> ContextPayload:
        return payload.with_tools(self._registry.to_openai_tools())

    async def handle_tool(self, tool_name: str, arguments: dict) -> ToolResult | None:
        tool = self._registry.get(tool_name)
        if tool is None:
            return None  # 이 middleware가 처리하지 않음
        try:
            return await tool.execute(**arguments)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
```

### 3.2 HITLMiddleware (승인 래핑)

```python
# core/middleware/hitl.py

class HITLMiddleware(AgentMiddleware):
    """Human-in-the-loop approval gate."""

    name = "hitl"
    priority = 10  # 가장 먼저 (거부 시 다른 MW 실행 불필요)

    def __init__(
        self,
        callback: Callable[[str, dict], bool] | None = None,
        require_approval: set[str] | None = None,
    ):
        self._callback = callback
        self._require_approval = require_approval or set()

    async def handle_tool(self, tool_name: str, arguments: dict) -> ToolResult | None:
        if tool_name not in self._require_approval:
            return None  # 승인 불필요 → 다음 MW로 패스
        if self._callback and not self._callback(tool_name, arguments):
            return ToolResult(
                success=False, output="",
                error=f"Tool '{tool_name}' denied by user.",
            )
        return None  # 승인됨 → 다음 MW가 실제 실행
```

**참고**: HITL의 `handle_tool`은 거부 시만 ToolResult를 반환하고, 승인 시에는 None을
반환하여 다음 Middleware(FilesystemMiddleware 등)가 실제 실행하도록 한다.

### 3.3 SummarizationMiddleware (기존 compression 래핑)

```python
# core/middleware/summarization.py

class SummarizationMiddleware(AgentMiddleware):
    """Wraps existing ConversationManager compression."""

    name = "summarization"
    priority = 200  # after() 단계에서 마지막에 실행

    def __init__(self, conversation: ConversationManager):
        self._conversation = conversation

    async def after(self, payload: ContextPayload) -> ContextPayload:
        # 기존 ConversationManager의 자동 압축 로직 활용
        # (get_messages 호출 시 내부적으로 _compress 실행)
        # after()에서는 명시적 compact 트리거만 담당
        return payload
```

### 3.4 PlanningMiddleware

```python
# core/middleware/planning.py

class PlanningMiddleware(AgentMiddleware):
    """Injects write_todos tool and tracks agent planning."""

    name = "planning"
    priority = 30

    def __init__(self):
        self._todos = TodoList()

    async def before(self, payload: ContextPayload) -> ContextPayload:
        payload = payload.with_tools([write_todos_tool_schema()])
        payload = payload.with_instruction(
            "You have a write_todos tool. Use it to plan complex tasks "
            "before execution. Break work into steps and track progress."
        )
        if self._todos.items:
            done, total = self._todos.progress
            payload = payload.with_instruction(
                f"Current plan ({done}/{total} done):\n{self._todos.format()}"
            )
        return payload

    async def handle_tool(self, tool_name: str, arguments: dict) -> ToolResult | None:
        if tool_name != "write_todos":
            return None
        self._todos.update(arguments.get("todos", []))
        done, total = self._todos.progress
        return ToolResult(
            success=True,
            output=f"Plan updated ({done}/{total} done):\n{self._todos.format()}",
        )

    @property
    def todos(self) -> TodoList:
        return self._todos
```

### 3.5 SubAgentMiddleware (DS-02)

```python
# core/middleware/subagent.py

class SubAgentMiddleware(AgentMiddleware):
    """Manages sub-agent delegation via 'task' tool."""

    name = "subagent"
    priority = 40

    def __init__(self, runner: SubAgentRunner, registry: SubAgentRegistry):
        self._runner = runner
        self._registry = registry

    async def before(self, payload: ContextPayload) -> ContextPayload:
        task_tool = {
            "type": "function",
            "function": {
                "name": "task",
                "description": (
                    "Delegate a task to a sub-agent. Use for complex subtasks "
                    "that can be worked on independently."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "What the sub-agent should do",
                        },
                        "agent": {
                            "type": "string",
                            "description": "Sub-agent name (optional, auto-selects if omitted)",
                        },
                    },
                    "required": ["description"],
                },
            },
        }
        payload = payload.with_tools([task_tool])
        agents = self._registry.list_agents()
        if agents:
            payload = payload.with_instruction(
                f"Available sub-agents: {', '.join(a.name for a in agents)}"
            )
        return payload

    async def handle_tool(self, tool_name: str, arguments: dict) -> ToolResult | None:
        if tool_name != "task":
            return None
        description = arguments["description"]
        agent_name = arguments.get("agent")
        # DS-02: runner가 결과를 강제 압축하여 반환 (≤1000토큰)
        result = await self._runner.run(
            task=description, agent_name=agent_name
        )
        return ToolResult(success=True, output=result)
```

### 3.6 MemoryMiddleware

```python
# core/middleware/memory.py

class MemoryMiddleware(AgentMiddleware):
    """Persistent memory across sessions."""

    name = "memory"
    priority = 20  # system_instructions에 먼저 주입

    def __init__(self, store: MemoryStore, loader: AgentsmdLoader):
        self._store = store
        self._loader = loader

    async def before(self, payload: ContextPayload) -> ContextPayload:
        # AGENTS.md 로딩
        agents_md = self._loader.load()
        if agents_md:
            payload = payload.with_instruction(
                f"# Agent Memory (AGENTS.md)\n{agents_md}"
            )

        # 영속 메모리 로딩
        memories = self._store.recall_recent(limit=10)
        if memories:
            formatted = "\n".join(f"- {m}" for m in memories)
            payload = payload.with_instruction(
                f"# Persistent Memory\n{formatted}"
            )

        # save_memory, recall_memory 도구 등록
        payload = payload.with_tools(self._store.to_openai_tools())
        return payload

    async def handle_tool(self, tool_name: str, arguments: dict) -> ToolResult | None:
        if tool_name == "save_memory":
            self._store.save(arguments["content"], arguments.get("tags", []))
            return ToolResult(success=True, output="Memory saved.")
        if tool_name == "recall_memory":
            results = self._store.search(arguments.get("query", ""))
            return ToolResult(success=True, output="\n".join(results))
        return None
```

---

## 4. Sub-Agent System

### 4.1 SubAgent Dataclass

```python
# core/subagent/base.py

@dataclass
class SubAgent:
    """Declarative sub-agent specification."""
    name: str
    description: str
    system_prompt: str = ""
    tools_override: list[str] | None = None  # None = 부모 상속
    max_iterations: int = 15
    keywords: list[str] = field(default_factory=list)  # 키워드 매칭용
```

### 4.2 SubAgentRegistry

```python
# core/subagent/registry.py

class SubAgentRegistry:
    """Registry for available sub-agents."""

    def __init__(self):
        self._agents: dict[str, SubAgent] = {}

    def register(self, agent: SubAgent) -> None:
        self._agents[agent.name] = agent

    def get(self, name: str) -> SubAgent | None:
        return self._agents.get(name)

    def find_best(self, task_description: str) -> SubAgent:
        """Find best matching agent, or return general-purpose fallback."""
        # 간단한 키워드 매칭 (v1)
        for agent in self._agents.values():
            if any(kw in task_description.lower() for kw in agent.description.lower().split()):
                return agent
        return self._general_purpose()

    def _general_purpose(self) -> SubAgent:
        return SubAgent(
            name="general",
            description="General-purpose sub-agent",
            system_prompt="You are a helpful coding assistant. Complete the given task.",
        )

    def list_agents(self) -> list[SubAgent]:
        return list(self._agents.values())
```

### 4.3 SubAgentRunner (DS-02: 출력 경계)

```python
# core/subagent/runner.py

class SubAgentRunner:
    """Executes sub-agents with output boundary enforcement."""

    MAX_RESULT_TOKENS = 1000
    MAX_DEPTH = 3

    def __init__(
        self,
        llm: LLMProvider,
        context_manager: ContextManager,
        tool_registry: ToolRegistry,
        _depth: int = 0,
    ):
        self._llm = llm
        self._context = context_manager
        self._tool_registry = tool_registry
        self._depth = _depth

    async def run(self, task: str, agent_name: str | None = None) -> str:
        """Run a sub-agent and return compressed result."""
        if self._depth >= self.MAX_DEPTH:
            return f"Error: Maximum sub-agent depth ({self.MAX_DEPTH}) exceeded."

        # MiddlewareEngine 인스턴스 생성 (Sub-Agent용)
        # Sub-Agent는 task 도구를 가지지만 depth가 증가됨
        from myaicoder.core.engine import MiddlewareEngine

        sub_engine = MiddlewareEngine(
            llm=self._llm,
            context_manager=self._context,
            tool_registry=self._tool_registry,
            subagent_depth=self._depth + 1,
        )

        result = await sub_engine.chat(task)
        return self._compress_result(result)

    def _compress_result(self, result: str) -> str:
        """DS-02: Force compress result to MAX_RESULT_TOKENS."""
        max_chars = self.MAX_RESULT_TOKENS * 4
        if len(result) <= max_chars:
            return result

        # 앞부분(요약) + 뒷부분(최종 결과)을 보존
        head = result[:max_chars // 2]
        tail = result[-(max_chars // 2):]
        return (
            f"{head}\n"
            f"... (compressed, {len(result)} chars total) ...\n"
            f"{tail}"
        )
```

---

## 5. Planning System

### 5.1 TodoList Model

```python
# core/planning/todos.py

@dataclass
class TodoItem:
    id: str
    content: str
    status: str = "pending"  # pending | in_progress | done

@dataclass
class TodoList:
    items: list[TodoItem] = field(default_factory=list)

    def update(self, todos: list[dict]) -> None:
        """Replace todo list with new items."""
        self.items = [
            TodoItem(
                id=str(i),
                content=t.get("content", ""),
                status=t.get("status", "pending"),
            )
            for i, t in enumerate(todos)
        ]

    def format(self) -> str:
        """Format for display in prompt."""
        if not self.items:
            return "(no plan)"
        lines = []
        for item in self.items:
            icon = {"pending": "[ ]", "in_progress": "[~]", "done": "[x]"}
            lines.append(f"{icon.get(item.status, '[ ]')} {item.content}")
        return "\n".join(lines)

    def to_openai_tool(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "write_todos",
                "description": (
                    "Create or update a task plan. Use this to break complex "
                    "work into steps and track progress."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "todos": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "content": {"type": "string"},
                                    "status": {
                                        "type": "string",
                                        "enum": ["pending", "in_progress", "done"],
                                    },
                                },
                                "required": ["content"],
                            },
                        },
                    },
                    "required": ["todos"],
                },
            },
        }
```

---

## 6. Memory System

### 6.1 MemoryStore

```python
# core/memory/store.py

class MemoryStore:
    """Persistent memory storage (JSON file-based)."""

    def __init__(self, storage_dir: Path | None = None):
        self._dir = storage_dir or (Path.home() / ".config" / "myaicoder" / "memory")
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / "memories.json"
        self._memories: list[dict] = self._load()

    def save(self, content: str, tags: list[str] | None = None) -> None:
        self._memories.append({
            "content": content,
            "tags": tags or [],
            "created_at": datetime.now().isoformat(),
        })
        self._persist()

    def recall_recent(self, limit: int = 10) -> list[str]:
        return [m["content"] for m in self._memories[-limit:]]

    def search(self, query: str) -> list[str]:
        if not query:
            return self.recall_recent()
        results = [
            m["content"] for m in self._memories
            if query.lower() in m["content"].lower()
            or any(query.lower() in t.lower() for t in m.get("tags", []))
        ]
        return results[-10:]

    def to_openai_tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "save_memory",
                    "description": "Save important information for future sessions.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string", "description": "What to remember"},
                            "tags": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "recall_memory",
                    "description": "Search persistent memory for relevant information.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                        },
                    },
                },
            },
        ]

    def _load(self) -> list[dict]:
        if self._file.exists():
            return json.loads(self._file.read_text())
        return []

    def _persist(self) -> None:
        # atomic write
        tmp = self._file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._memories, ensure_ascii=False, indent=2))
        tmp.rename(self._file)
```

### 6.2 AgentsmdLoader

```python
# core/memory/loader.py

class AgentsmdLoader:
    """Load AGENTS.md files for agent personality/knowledge."""

    def __init__(self, working_dir: Path | None = None):
        self._working_dir = working_dir or Path.cwd()

    def load(self) -> str | None:
        paths = [
            self._working_dir / "AGENTS.md",
            Path.home() / ".config" / "myaicoder" / "AGENTS.md",
        ]
        contents = []
        for p in paths:
            if p.exists():
                contents.append(p.read_text(encoding="utf-8"))
        return "\n\n".join(contents) if contents else None
```

---

## 7. MiddlewareEngine (DS-03: Strangler Fig)

```python
# core/engine.py — MiddlewareEngine (AgentEngine 옆에 공존)

class MiddlewareEngine:
    """Middleware-based agent engine. Replaces AgentEngine via Strangler Fig."""

    MAX_TOOL_ITERATIONS = 25
    MAX_TOOL_RETRIES = 2

    def __init__(
        self,
        llm: LLMProvider,
        context_manager: ContextManager | None = None,
        tool_registry: ToolRegistry | None = None,
        middleware_stack: MiddlewareStack | None = None,
        approval_callback: Callable[[str, dict], bool] | None = None,
        require_approval: list[str] | None = None,
        max_context_tokens: int = 32768,
        compression_threshold: float = 0.8,
        subagent_depth: int = 0,
    ):
        self.llm = llm
        self.context = context_manager or ContextManager()
        self.conversation = ConversationManager(
            max_tokens=max_context_tokens,
            compression_threshold=compression_threshold,
        )

        # Build middleware stack
        if middleware_stack:
            self.stack = middleware_stack
        else:
            self.stack = self._build_default_stack(
                tool_registry=tool_registry,
                approval_callback=approval_callback,
                require_approval=require_approval,
                subagent_depth=subagent_depth,
            )

    def _build_default_stack(
        self,
        tool_registry: ToolRegistry | None,
        approval_callback: Callable | None,
        require_approval: list[str] | None,
        subagent_depth: int,
    ) -> MiddlewareStack:
        stack = MiddlewareStack()

        # HITL (priority 10) — must be first for tool approval
        if approval_callback:
            stack.add(HITLMiddleware(
                callback=approval_callback,
                require_approval=set(require_approval or []),
            ))

        # Memory (priority 20) — load context early
        stack.add(MemoryMiddleware(
            store=MemoryStore(),
            loader=AgentsmdLoader(self.context.working_dir),
        ))

        # Planning (priority 30)
        stack.add(PlanningMiddleware())

        # SubAgent (priority 40) — only if not at max depth
        if subagent_depth < SubAgentRunner.MAX_DEPTH:
            registry = SubAgentRegistry()
            runner = SubAgentRunner(
                llm=self.llm,
                context_manager=self.context,
                tool_registry=tool_registry,
                _depth=subagent_depth,
            )
            stack.add(SubAgentMiddleware(runner=runner, registry=registry))

        # Filesystem (priority 50) — existing tools
        if tool_registry:
            stack.add(FilesystemMiddleware(registry=tool_registry))

        # Summarization (priority 200) — last in after()
        stack.add(SummarizationMiddleware(conversation=self.conversation))

        return stack

    async def chat(self, user_input: str) -> str:
        """Send user input and get response (with middleware pipeline)."""
        self.conversation.add_message(Message(role="user", content=user_input))

        base_prompt = self.context.build_system_prompt()
        collected_text = []

        for _ in range(self.MAX_TOOL_ITERATIONS):
            # 1. Build ContextPayload (frozen — tuple of messages)
            payload = ContextPayload(messages=tuple(self.conversation.history))

            # 2. Run middleware before() hooks
            payload = await self.stack.process_before(payload)

            # 3. Merge system prompt
            system_prompt = self.stack.merge_system_prompt(base_prompt, payload)

            # 4. Get messages with compression check
            messages = self.conversation.get_messages(system_prompt)

            # 5. Call LLM
            response = await self.llm.chat(
                messages=messages,
                tools=payload.tools if payload.tools else None,
            )

            if response.content:
                collected_text.append(response.content)

            # 6. No tool calls → done
            if not response.tool_calls:
                self.conversation.add_message(
                    Message(role="assistant", content=response.content or "")
                )
                break

            # 7. Execute tool calls via middleware stack
            self.conversation.add_message(
                Message(
                    role="assistant",
                    content=response.content,
                    tool_calls=response.tool_calls,
                )
            )

            for tc in response.tool_calls:
                result = await self._execute_tool(tc.name, tc.arguments)
                content = result.output if result.success else f"Error: {result.error}"
                content = self._truncate_tool_result(content)
                self.conversation.add_message(
                    Message(role="tool", content=content, tool_call_id=tc.id)
                )

        # 8. Run middleware after() hooks
        after_payload = ContextPayload(messages=self.conversation.history)
        await self.stack.process_after(after_payload)

        return "\n".join(collected_text) if collected_text else ""

    async def _execute_tool(self, name: str, arguments: dict) -> ToolResult:
        """Execute tool through middleware chain of responsibility."""
        result = await self.stack.handle_tool(name, arguments)
        if result is not None:
            return result
        return ToolResult(success=False, output="", error=f"Unknown tool: {name}")

    def _truncate_tool_result(self, result: str, max_tokens: int = 4000) -> str:
        max_chars = max_tokens * 4
        if len(result) > max_chars:
            return result[:max_chars] + f"\n... (truncated, {len(result)} chars total)"
        return result

    def reset(self) -> None:
        self.conversation.clear()
```

---

## 8. File Map (신규/수정)

| Action | Path | Lines | Description |
|--------|------|-------|-------------|
| 🆕 | `core/middleware/__init__.py` | ~10 | Package exports |
| 🆕 | `core/middleware/base.py` | ~60 | ContextPayload + AgentMiddleware ABC |
| 🆕 | `core/middleware/stack.py` | ~70 | MiddlewareStack orchestrator |
| 🆕 | `core/middleware/filesystem.py` | ~30 | Wraps ToolRegistry |
| 🆕 | `core/middleware/hitl.py` | ~35 | Approval gate |
| 🆕 | `core/middleware/summarization.py` | ~25 | Wraps ConversationManager |
| 🆕 | `core/middleware/planning.py` | ~50 | PlanningMiddleware + TodoList |
| 🆕 | `core/middleware/subagent.py` | ~55 | SubAgentMiddleware + task tool |
| 🆕 | `core/middleware/memory.py` | ~50 | MemoryMiddleware |
| 🆕 | `core/subagent/__init__.py` | ~5 | Package exports |
| 🆕 | `core/subagent/base.py` | ~15 | SubAgent dataclass |
| 🆕 | `core/subagent/registry.py` | ~40 | SubAgentRegistry |
| 🆕 | `core/subagent/runner.py` | ~60 | SubAgentRunner (DS-02) |
| 🆕 | `core/planning/__init__.py` | ~5 | Package exports |
| 🆕 | `core/planning/todos.py` | ~80 | TodoList model + tool schema |
| 🆕 | `core/memory/__init__.py` | ~5 | Package exports |
| 🆕 | `core/memory/store.py` | ~70 | MemoryStore (JSON persistence) |
| 🆕 | `core/memory/loader.py` | ~25 | AGENTS.md loader |
| ✏️ | `core/engine.py` | +~120 | MiddlewareEngine 추가 (AgentEngine 유지) |
| **Total** | | **~800** | 18 new + 1 modified |

---

## 9. Dependency Map

```
MiddlewareEngine
    ├─ MiddlewareStack
    │   ├─ HITLMiddleware
    │   ├─ MemoryMiddleware
    │   │   ├─ MemoryStore
    │   │   └─ AgentsmdLoader
    │   ├─ PlanningMiddleware
    │   │   └─ TodoList
    │   ├─ SubAgentMiddleware
    │   │   ├─ SubAgentRunner (→ MiddlewareEngine, depth+1)
    │   │   └─ SubAgentRegistry
    │   ├─ FilesystemMiddleware
    │   │   └─ ToolRegistry (기존)
    │   └─ SummarizationMiddleware
    │       └─ ConversationManager (기존)
    ├─ LLMProvider (기존, 변경 없음)
    └─ ContextManager (기존, 변경 없음)
```

---

## 10. Testing Strategy

### 10.1 Unit Tests (신규)

| Test File | Coverage |
|-----------|----------|
| `tests/test_middleware_base.py` | ContextPayload, AgentMiddleware |
| `tests/test_middleware_stack.py` | MiddlewareStack (before/handle/after) |
| `tests/test_middleware_filesystem.py` | FilesystemMiddleware |
| `tests/test_middleware_hitl.py` | HITLMiddleware |
| `tests/test_middleware_planning.py` | PlanningMiddleware + TodoList |
| `tests/test_middleware_subagent.py` | SubAgentMiddleware + Runner (DS-02) |
| `tests/test_middleware_memory.py` | MemoryMiddleware + Store |
| `tests/test_middleware_engine.py` | MiddlewareEngine integration |

### 10.2 Strangler Fig 회귀 검증 (DS-03)

```
Step 1: MiddlewareEngine 생성 → 신규 테스트 1개 통과
Step 2: 기존 AgentEngine 테스트를 MiddlewareEngine으로 복제 (parametrize)
Step 3: 두 엔진 모두 동일 테스트 통과 확인
Step 4: AgentEngine 삭제, MiddlewareEngine rename
Step 5: 전체 178개 + 신규 테스트 통과 확인
```

### 10.3 DS-02 검증

```python
async def test_subagent_output_boundary():
    """Sub-Agent 결과가 MAX_RESULT_TOKENS 이하로 압축되는지 검증."""
    runner = SubAgentRunner(llm=mock_llm, ...)
    # mock_llm이 5000자 응답 반환하도록 설정
    result = await runner.run(task="large task")
    assert len(result) <= SubAgentRunner.MAX_RESULT_TOKENS * 4
```

---

## 11. Implementation Guide

### 11.1 Implementation Order

| Step | Module | Dependencies | Est. Lines |
|------|--------|-------------|-----------|
| 1 | `middleware/base.py` | None | ~60 |
| 2 | `middleware/stack.py` | base.py | ~70 |
| 3 | `middleware/filesystem.py` | base.py, ToolRegistry | ~30 |
| 4 | `middleware/hitl.py` | base.py | ~35 |
| 5 | `middleware/summarization.py` | base.py, ConversationManager | ~25 |
| 6 | `engine.py` (MiddlewareEngine) | stack, filesystem, hitl, summarization | ~120 |
| 7 | `planning/todos.py` | None | ~80 |
| 8 | `middleware/planning.py` | base.py, todos | ~50 |
| 9 | `subagent/base.py` | None | ~15 |
| 10 | `subagent/registry.py` | base.py | ~40 |
| 11 | `subagent/runner.py` | engine (MiddlewareEngine) | ~60 |
| 12 | `middleware/subagent.py` | base.py, runner, registry | ~55 |
| 13 | `memory/store.py` | None | ~70 |
| 14 | `memory/loader.py` | None | ~25 |
| 15 | `middleware/memory.py` | base.py, store, loader | ~50 |

### 11.2 Key Integration Points

| Integration | Detail |
|-------------|--------|
| MCP Server (`mcp/server.py`) | MiddlewareEngine 사용하도록 전환 (DS-03 완료 후) |
| CLI (`cli.py`) | MiddlewareEngine 사용하도록 전환 (DS-03 완료 후) |
| VS Code Extension | 변경 없음 (MCP 프로토콜 불변) |
| Tests | parametrize로 두 엔진 동시 검증 → 전환 완료 후 단일화 |

### 11.3 Session Guide

| Module | Scope Key | Files | Est. |
|--------|-----------|-------|------|
| **module-1** | Middleware Core | base.py, stack.py, filesystem.py, hitl.py, summarization.py | ~220줄 |
| **module-2** | MiddlewareEngine | engine.py (MiddlewareEngine 추가) | ~120줄 |
| **module-3** | Planning | todos.py, planning.py | ~130줄 |
| **module-4** | Sub-Agent | base.py, registry.py, runner.py, subagent.py | ~170줄 |
| **module-5** | Memory | store.py, loader.py, memory.py | ~145줄 |
| **module-6** | Integration & Migration | 기존 테스트 전환, MCP/CLI 통합 | ~100줄 |

**Recommended Session Plan**:
- Session 1: module-1 + module-2 (Middleware 기반 + 새 엔진)
- Session 2: module-3 + module-4 (Planning + Sub-Agent)
- Session 3: module-5 + module-6 (Memory + 통합 마이그레이션)
