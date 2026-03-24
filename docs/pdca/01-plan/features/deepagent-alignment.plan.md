# Plan: deepagent-alignment

> DeepAgent 참조 Agent 능력 강화 — Middleware Stack, Sub-Agent, Planning, Memory

## Executive Summary

| Feature | deepagent-alignment |
|---------|---------------------|
| Created | 2026-03-24 |
| Author | treeson |
| Duration | TBD |

### Results Summary

| Metric | Target |
|--------|--------|
| Match Rate | >= 90% |
| New Files | ~15 |
| Modified Files | ~5 |
| New Lines | ~2,000 |

### Value Delivered

| Perspective | Description |
|-------------|-------------|
| **Problem** | 현재 engine.py 단일 루프 구조로 복잡 작업 분할 불가, 기능 추가 시 직접 수정 필요, 세션 간 컨텍스트 유실 |
| **Solution** | Middleware Stack 패턴 도입으로 composable 아키텍처 전환, Sub-Agent/Planning/Memory를 Middleware로 조합 |
| **Function UX Effect** | 복잡한 코딩 작업을 AI가 자동 분할·병렬 처리, 세션 간 학습 유지, 에이전트가 스스로 계획 수립 후 단계적 실행 |
| **Core Value** | 팀 개발자의 AI 어시스턴트 활용 수준을 단순 도구 실행에서 자율적 작업 관리자로 격상 |

## Context Anchor

| Key | Value |
|-----|-------|
| **WHY** | engine.py 단일 루프의 확장 한계 → DeepAgent 수준의 Agent 능력 필요 |
| **WHO** | DGX 서버를 공유하는 팀 개발자 |
| **RISK** | 기존 178개 테스트 깨짐, engine.py 리팩토링 시 VS Code Extension 연동 장애 |
| **SUCCESS** | 복잡 작업 자동 분할 + 세션 간 컨텍스트 유지 + Middleware 기반 확장성 |
| **SCOPE** | Middleware Stack + Sub-Agent + Planning + Memory (v1 범위) |

---

## 1. User Intent Discovery

### 1.1 Core Problem
현재 myAiCoder의 Agent Engine은 `engine.py` 194줄의 단일 agentic loop으로 구성되어 있다.
DeepAgent와 비교 시 다음 핵심 격차가 존재한다:

- **Sub-Agent 없음**: 복잡한 작업을 하위 에이전트로 위임할 수 없음
- **Middleware 없음**: 새 기능 추가 시 engine.py를 직접 수정해야 함
- **Planning 없음**: 에이전트가 작업 계획을 수립하지 못함
- **Memory 없음**: 세션 간 학습·컨텍스트가 유실됨

### 1.2 Target Users
DGX 서버를 공유하는 팀 개발자. VS Code Extension을 통해 AI 코딩 어시스턴트 사용.

### 1.3 Success Criteria
1. **복잡 작업 자동 분할**: `task` 도구를 통해 Sub-Agent로 작업 위임 가능
2. **세션 간 컨텍스트 유지**: Memory Middleware로 AGENTS.md + 학습 내용 영속
3. **확장성 확보**: 새 기능 추가 시 Middleware 하나만 추가하면 됨 (engine.py 수정 불필요)
4. **기존 테스트 유지**: 178개 기존 테스트 100% 통과

---

## 2. Alternatives Explored

### Approach A: Middleware Stack 우선 ✅ 선택
- engine.py를 Middleware 기반 orchestrator로 리팩토링
- Sub-Agent/Planning/Memory를 Middleware로 추가
- 기존 코드를 Middleware 인터페이스로 래핑
- **장점**: 점진적 마이그레이션, 장기 확장성
- **단점**: 추상화 설계에 시간 소요

### Approach B: Sub-Agent 우선 (미선택)
- Sub-Agent부터 도입, Middleware는 후순위
- **장점**: 빠른 체감 효과
- **단점**: engine.py 직접 수정 → 나중에 재리팩토링 필요

### Approach C: LangGraph 재구축 (미선택)
- LangGraph 기반 전면 재설계
- **장점**: DeepAgent 수준 완성도
- **단점**: 기존 코드 대부분 교체, 사실상 새 프로젝트

---

## 3. YAGNI Review

### v1 포함 (In Scope)
- [x] Middleware Stack 프레임워크 (AgentMiddleware ABC + MiddlewareStack)
- [x] Sub-Agent 시스템 (SubAgent 정의 + task 도구 + Runner)
- [x] Planning Middleware (write_todos 도구 + TodoList 모델)
- [x] Memory Middleware (AGENTS.md 로딩 + 세션 간 영속 저장)

### v1 제외 (Out of Scope)
- [ ] Sandbox 실행 (E2B, Modal, Daytona, Runloop)
- [ ] Anthropic Prompt Caching Middleware
- [ ] Eval/Benchmark 프레임워크
- [ ] Skills 시스템 (커스텀 슬래시 명령)
- [ ] HITL 고도화 (도구 호출 수정 UI)
- [ ] Multi-LLM Provider 추상화
- [ ] AsyncSubAgent (원격/백그라운드 실행)
- [ ] CompiledSubAgent (사전 컴파일된 Runnable)

---

## 4. Requirements

### 4.1 Functional Requirements

#### FR-01: Middleware Stack Framework
- `AgentMiddleware` ABC 정의 (before/handle/after 인터페이스)
- `MiddlewareStack` 빌더 및 실행기
- 기존 engine.py의 도구 실행/승인/압축 로직을 Middleware로 분리
- Middleware 순서 제어 (priority 또는 명시적 ordering)

#### FR-02: Sub-Agent System
- `SubAgent` 데이터 클래스 (name, description, system_prompt, tools)
- `task` 도구 등록 (name: "task", args: {agent_name, task_description})
- `SubAgentRunner`: 새 Engine 인스턴스를 생성하여 Sub-Agent 실행
- 기본 general-purpose Sub-Agent 자동 생성 (매칭되는 Sub-Agent 없을 때)
- Sub-Agent는 부모의 도구 + Middleware를 상속 (override 가능)

#### FR-03: Planning Middleware
- `write_todos` 도구: 에이전트가 작업 계획 수립
- `TodoList` 모델: 계획 항목 + 상태 (pending/in_progress/done)
- 에이전트 프롬프트에 Planning 지시 추가
- 사용자에게 현재 계획 진행 상태 표시

#### FR-04: Memory Middleware
- `AGENTS.md` 파일 로딩 (프로젝트 루트 + 홈 디렉토리)
- 세션 간 영속 메모리 저장소 (`~/.config/myaicoder/memory/`)
- 시스템 프롬프트에 메모리 컨텍스트 자동 주입
- 메모리 저장/검색/삭제 도구 (save_memory, recall_memory)

### 4.2 Non-Functional Requirements

| NFR | Target |
|-----|--------|
| **하위 호환성** | 기존 178개 테스트 100% 통과 |
| **성능** | Middleware 오버헤드 < 10ms per request |
| **메모리** | Sub-Agent 동시 실행 시 추가 메모리 < 100MB |
| **테스트** | 새 코드 테스트 커버리지 >= 80% |

---

## 5. Architecture Overview

### 5.1 현재 구조 (Before)

```
engine.py (194줄, 단일 agentic loop)
    → tools/registry.py (9개 도구)
    → llm/vllm_provider.py
    → conversation.py (turn-based compression)
    → approval_callback (단순 approve/deny)
```

### 5.2 변경 후 구조 (After)

```
engine.py (orchestrator, ~100줄)
    → middleware/stack.py (MiddlewareStack)
        ├─ PlanningMiddleware      → planning/todos.py
        ├─ FilesystemMiddleware    → tools/registry.py (기존 래핑)
        ├─ SubAgentMiddleware      → subagent/runner.py
        ├─ SummarizationMiddleware → conversation.py (기존 래핑)
        ├─ MemoryMiddleware        → memory/store.py
        └─ HITLMiddleware          → approval callback (기존 래핑)
    → llm/vllm_provider.py (변경 없음)
```

### 5.4 핵심 방어 전략

#### DS-01: ContextPayload 패턴 — 상태 변이 충돌 방지

**문제**: MemoryMiddleware와 PlanningMiddleware가 각각 `before()`에서 시스템 프롬프트를
주입할 때, messages 리스트를 직접 수정하면 기존 프롬프트를 덮어쓰거나 순서가 꼬여
LLM이 컨텍스트를 오해할 수 있다.

**전략**: Middleware가 `messages`를 직접 수정하지 않는다. 대신 `ContextPayload` 객체를
전달하여 각 Middleware가 '추가할 시스템 지시사항'만 배열에 Append한다.
`MiddlewareStack`이 마지막에 이를 하나의 시스템 프롬프트로 병합(Merge)한다.

```python
@dataclass
class ContextPayload:
    messages: list[Message]           # 원본 (읽기 전용)
    system_instructions: list[str]    # 각 Middleware가 append
    tools: list[dict]                 # 각 Middleware가 extend
    metadata: dict                    # 공유 메타데이터

class AgentMiddleware(ABC):
    async def before(self, payload: ContextPayload) -> ContextPayload:
        """payload.system_instructions에 추가만 한다. messages 직접 수정 금지."""
        return payload
```

#### DS-02: Sub-Agent 출력 경계 — 토큰 폭발 방지

**문제**: Sub-Agent가 내부적으로 10번의 도구 호출과 에러 수정을 거치며 5,000+ 토큰을
소모한 뒤, 전체 대화 내역을 부모에게 반환하면 부모의 컨텍스트 윈도우가 폭발한다.

**전략**: `SubAgentRunner`에 엄격한 출력 경계(Boundary)를 설정한다.
Sub-Agent 종료 시 반환하는 `tool_result`는 대화 내역 원본이 아니라,
**"작업 결과 요약 + 최종 생성/수정된 파일 경로"** 형태로 강제 압축한다.

```python
class SubAgentRunner:
    MAX_RESULT_TOKENS = 1000  # 부모에게 반환하는 최대 토큰

    async def run(self, agent_name: str, task: str) -> str:
        # Sub-Agent 실행 (내부 대화는 격리)
        result = await sub_engine.chat(task)
        # 강제 압축: 요약 + 파일 경로만 반환
        return self._compress_result(result)
```

#### DS-03: Strangler Fig 마이그레이션 — Big Bang 방지

**문제**: 194줄의 engine.py를 한 번에 교체하면 기존 178개 테스트가 연쇄적으로
깨지며 디버깅 지옥에 빠질 수 있다.

**전략**: 기존 `AgentEngine` 클래스는 그대로 둔다. 옆에 `MiddlewareEngine`을
새로 만들고, 기존 테스트 중 1개만 새 엔진을 바라보게 하여 성공시킨다.
점진적으로 테스트를 새 엔진으로 옮기고, 100% 통과 시 구형 엔진을 삭제한다.

```
Step 1: MiddlewareEngine 생성 (AgentEngine 옆에 공존)
Step 2: 테스트 1개를 MiddlewareEngine으로 전환 → 통과 확인
Step 3: 점진적으로 나머지 테스트 전환 (10개 → 50개 → 178개)
Step 4: 100% 통과 확인 후 AgentEngine 삭제
Step 5: MiddlewareEngine → AgentEngine으로 rename
```

### 5.3 새 패키지 구조

```
services/myaicoder/src/myaicoder/
├── core/
│   ├── engine.py              # 리팩토링 (orchestrator)
│   ├── middleware/             # 🆕
│   │   ├── __init__.py
│   │   ├── base.py            # AgentMiddleware ABC
│   │   ├── stack.py           # MiddlewareStack
│   │   ├── planning.py        # PlanningMiddleware
│   │   ├── subagent.py        # SubAgentMiddleware
│   │   ├── memory.py          # MemoryMiddleware
│   │   ├── filesystem.py      # FilesystemMiddleware (래핑)
│   │   ├── summarization.py   # SummarizationMiddleware (래핑)
│   │   └── hitl.py            # HITLMiddleware (래핑)
│   ├── subagent/              # 🆕
│   │   ├── __init__.py
│   │   ├── base.py            # SubAgent dataclass
│   │   ├── runner.py          # SubAgentRunner
│   │   └── registry.py        # SubAgentRegistry
│   ├── planning/              # 🆕
│   │   ├── __init__.py
│   │   └── todos.py           # TodoList + write_todos + ProgressTracker (통합)
│   ├── memory/                # 🆕
│   │   ├── __init__.py
│   │   ├── store.py           # MemoryStore (영속)
│   │   └── loader.py          # AGENTS.md loader
│   ├── conversation.py        # 유지 (래핑됨)
│   ├── session.py             # 유지
│   └── context.py             # 유지
├── tools/                     # 기존 유지
├── llm/                       # 기존 유지
├── mcp/                       # 기존 유지
├── models/                    # 기존 유지
└── ui/                        # 기존 유지
```

---

## 6. Data Flow

```
사용자 메시지 입력
    ↓
Engine.chat(user_input)
    ↓
ContextPayload 생성 (messages=원본, system_instructions=[], tools=[])
    ↓
MiddlewareStack.process_request(payload)  ← DS-01: ContextPayload 패턴
    ├─ PlanningMiddleware.before(payload)    → payload.tools.extend(write_todos)
    │                                        → payload.system_instructions.append(planning지시)
    ├─ FilesystemMiddleware.before(payload)  → payload.tools.extend(기존 9개 도구)
    ├─ SubAgentMiddleware.before(payload)    → payload.tools.extend(task 도구)
    ├─ MemoryMiddleware.before(payload)      → payload.system_instructions.append(메모리컨텍스트)
    └─ HITLMiddleware.before(payload)        → (변경 없음)
    ↓
MiddlewareStack.merge_payload(payload)  ← 시스템 프롬프트 병합
    → system_prompt = base_prompt + "\n\n".join(payload.system_instructions)
    → tools = payload.tools
    ↓
LLM.chat(messages + merged_system_prompt, tools)
    ↓
Tool Call 발생 시:
    ├─ "write_todos"  → PlanningMiddleware.handle()  → TodoList 업데이트
    ├─ "task"         → SubAgentMiddleware.handle()
    │                    ↓ SubAgentRunner.run(agent_name, task)
    │                    ↓ 새 MiddlewareEngine 인스턴스 (도구+MW 상속)
    │                    ↓ DS-02: 결과 강제 압축 (요약+파일경로, ≤1000토큰)
    ├─ "read_file"... → FilesystemMiddleware.handle() → 기존 도구 실행
    └─ "bash"         → HITLMiddleware.handle() → 승인 → 실행
    ↓
MiddlewareStack.process_response(response)
    ├─ SummarizationMiddleware.after()   → 토큰 초과 시 turn-based 압축
    └─ MemoryMiddleware.after()          → 학습할 내용 감지 시 저장
    ↓
응답 반환
```

---

## 7. Implementation Order

### Phase 1: Middleware Stack Framework + Strangler Fig 기반 (DS-01, DS-03)
1. `middleware/base.py` — AgentMiddleware ABC + **ContextPayload** 정의 (DS-01)
2. `middleware/stack.py` — MiddlewareStack 빌더 + payload 병합 로직
3. `middleware/filesystem.py` — 기존 도구를 Middleware로 래핑
4. `middleware/summarization.py` — 기존 conversation.py 래핑
5. `middleware/hitl.py` — 기존 approval 래핑
6. **`MiddlewareEngine` 신규 생성** (기존 AgentEngine 옆에 공존) (DS-03)
7. 기존 테스트 1개를 MiddlewareEngine으로 전환 → 통과 확인
8. 점진적 테스트 전환 (10개 → 50개 → 178개)
9. 100% 통과 후 AgentEngine 삭제, MiddlewareEngine → AgentEngine rename

### Phase 2: Planning Middleware
10. `planning/todos.py` — TodoList 모델 + write_todos 도구 + ProgressTracker (통합)
11. `middleware/planning.py` — PlanningMiddleware

### Phase 3: Sub-Agent System (DS-02)
13. `subagent/base.py` — SubAgent dataclass
14. `subagent/registry.py` — SubAgentRegistry
15. `subagent/runner.py` — SubAgentRunner + **출력 경계 강제 압축** (DS-02, ≤1000토큰)
16. `middleware/subagent.py` — SubAgentMiddleware + task 도구

### Phase 4: Memory Middleware
17. `memory/store.py` — MemoryStore (영속 저장소)
18. `memory/loader.py` — AGENTS.md 로딩
19. `middleware/memory.py` — MemoryMiddleware

### Phase 5: 통합 테스트 + 회귀 검증
20. Middleware Stack 통합 테스트 (ContextPayload 병합 검증)
21. Sub-Agent 통합 테스트 (출력 경계 + 재귀 깊이 검증)
22. 기존 178개 테스트 최종 회귀 검증

---

## 8. Risk Analysis

| Risk | Impact | Probability | Mitigation | 방어전략 |
|------|--------|-------------|------------|----------|
| engine.py Big Bang 리팩토링 시 178개 테스트 연쇄 파괴 | 높음 | 높음 | **DS-03: Strangler Fig Pattern** — AgentEngine 유지, MiddlewareEngine 병행 후 점진 전환 | DS-03 |
| Middleware 간 시스템 프롬프트 덮어쓰기/순서 충돌 | 높음 | 중간 | **DS-01: ContextPayload** — messages 직접 수정 금지, append-only + 최종 병합 | DS-01 |
| Sub-Agent 토큰 폭발 (부모 컨텍스트 윈도우 초과) | 높음 | 중간 | **DS-02: 출력 경계** — 결과 강제 압축 (≤1000토큰, 요약+파일경로만) | DS-02 |
| Sub-Agent 무한 재귀 | 높음 | 낮음 | 최대 깊이 제한 (max_depth=3) | - |
| Memory 저장소 파일 충돌 | 낮음 | 낮음 | 파일 잠금 + atomic write | - |
| VS Code Extension 연동 장애 | 높음 | 낮음 | MCP 인터페이스 불변 유지 | - |

---

## 9. Brainstorming Log

| Phase | Decision | Rationale |
|-------|----------|-----------|
| Phase 1 | Agent 능력 강화 선택 | LLM Provider 확장보다 Agent 지능 향상이 팀 생산성에 직접적 |
| Phase 1 | 팀 개발자 대상 | DGX 공유 환경의 실제 사용자 |
| Phase 2 | Approach A (Middleware 우선) | 리팩토링 직후 시점, 구조 변경 적기. 장기 확장성 확보 |
| Phase 3 | 4개 기능 모두 포함 | Middleware가 기반이므로 나머지 3개는 Middleware 위에 자연스럽게 추가 |
| Phase 4 | 기존 코드 래핑 방식 | 테스트 178개 보존, 점진적 마이그레이션 |

---

## 10. References

- DeepAgent Repository: https://github.com/YIsungjoon/deepagents
- DeepAgent Middleware Pattern: `libs/deepagents/middleware/`
- DeepAgent SubAgent: `libs/deepagents/backends/subagents.py`
- myAiCoder Engine: `services/myaicoder/src/myaicoder/core/engine.py`
- myAiCoder Tools: `services/myaicoder/src/myaicoder/tools/`
