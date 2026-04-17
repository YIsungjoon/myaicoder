# Agent Architecture Comparison: claw-code vs contech-chatbot vs myAiCoder

> 작성일: 2026-04-01
> 목적: 3개 프로젝트의 에이전트 아키텍처를 비교 분석하여 기술적 차이와 설계 철학을 문서화

---

## 1. 프로젝트 개요

| 항목 | claw-code (Claude Code 참조) | contech-chatbot | myAiCoder |
|------|---------------------------|-----------------|-----------|
| **목적** | 범용 AI 코딩 어시스턴트 | 건설기술 도메인 RAG 챗봇 | 로컬 LLM 기반 AI 코딩 어시스턴트 |
| **설계 철학** | 도구를 통해 세상과 상호작용하는 자율 에이전트 | 지식을 검색하고 전문가처럼 답하는 시스템 | 미들웨어 합성으로 확장 가능한 에이전트 |
| **코어 언어** | Rust + Python 이중 레이어 | Python 단일 레이어 | Python 단일 레이어 (추후 TS/Rust 전환 계획) |
| **인터페이스** | CLI (터미널) | Web API (SSE 스트리밍) | CLI + VS Code Extension |
| **LLM** | Claude API (클라우드) | Qwen3.5-27B (llama.cpp, 로컬) | vLLM/llama.cpp/Ollama (로컬) |
| **레포 출처** | github.com/instructkr/claw-code | 자체 프로젝트 | 자체 프로젝트 |

---

## 2. 에이전트 루프 (Agent Loop)

### 2.1 패턴 비교

| 항목 | claw-code | contech-chatbot | myAiCoder |
|------|-----------|-----------------|-----------|
| **패턴** | Think-Act-Observe 무한 ReAct 루프 | LangGraph StateGraph 5노드 DAG | Middleware Stack + ReAct 루프 |
| **구현** | `conversation.rs:170-283` | `orchestrator.py` LangGraph | `engine.py:300-366` MiddlewareEngine |
| **종료 조건** | LLM이 도구 호출 안 하면 종료 | 그래프 END 노드 도달 | 텍스트 응답 또는 MAX_TOOL_ITERATIONS(25) |
| **반복 제한** | `max_iterations` (기본 무제한) | 고정 파이프라인 (분기만 존재) | 25회 (AgentEngine) |
| **자율성 수준** | LLM 완전 자율 | 인간 설계 파이프라인 내 제한 자율 | 미들웨어가 도구 주입, LLM이 선택 |

### 2.2 루프 흐름 상세

**claw-code** (가장 정교):
```
User Input → session.push()
  └─ Loop {
       API stream → assistant message 구성
       → pending_tool_uses 추출
       → (비어있으면 break)
       → for each tool:
            Permission check → PreHook → Execute → PostHook → session.push()
       → 다음 iteration
     }
  └─ maybe_auto_compact()
  └─ TurnSummary 반환
```

**contech-chatbot** (3가지 모드):
```
Mode 1 (Orchestrator): classify → route → rewrite → retrieve → generate → END
Mode 2 (Tool Calling): LLM → tool_calls → execute → LLM 재호출 (while loop)
Mode 3 (Prefetch):     analyze → 병렬수집(RAG+법령+Graph) → Cascading → LLM 1회
```

**myAiCoder** (미들웨어 파이프라인):
```
User Input → ContextPayload 생성 (frozen)
  └─ stack.process_before() → [HITL(10)→Memory(20)→Planning(30)→SubAgent(40)→FS(50)→Summary(200)]
  └─ ConversationManager.get_messages() (auto-compress)
  └─ LLM 호출 (미들웨어가 주입한 도구 포함)
  └─ Tool 실행: stack.handle_tool() (Chain of Responsibility)
  └─ stack.process_after() → [200→50→40→30→20→10] (역순)
```

---

## 3. 도구 시스템 (Tool System)

| 항목 | claw-code | contech-chatbot | myAiCoder |
|------|-----------|-----------------|-----------|
| **등록 방식** | `mvp_tool_specs()` 정적 + MCP 동적 | `ToolRegistry` Factory (고정) | `ToolRegistry` 동적 + Middleware 주입 + MCP |
| **도구 수** | 23개 기본 + MCP 무제한 | 7개 고정 | ~10개 기본 + MCP + 미들웨어 주입 도구 |
| **스키마 형식** | JSON Schema (Rust ToolSpec) | JSON Schema (OpenAI format) | JSON Schema (OpenAI format) |
| **타입 검증** | Serde 역직렬화 (컴파일 타임) | `safe_parse_tool_args()` 런타임 | Python ABC + kwargs (런타임) |
| **디스패치** | Rust `match name {}` 패턴매칭 | `registry._tools[name]` dict | `stack.handle_tool()` 체인 |
| **확장 메커니즘** | MCP 서버 (프로세스 격리) | 코드 수정 필요 | MCP + 미들웨어 추가 |
| **Self-Correction** | LLM이 에러 결과로 자율 재시도 | 3단계 JSON 파싱 교정 | 재시도 로직 (retryable 판별) |

### 3.1 도구 실행 파이프라인

**claw-code** (6단계):
```
① Permission check (5단계 계층 모드)
② PreHook (셸 명령, exit code로 Allow/Deny)
③ Execute (Serde 역직렬화 → 도구 로직)
④ PostHook (셸 명령, 피드백 메시지)
⑤ 결과 포맷 (JSON 직렬화)
⑥ 세션 저장 (session.messages.push)
```

**contech-chatbot** (4단계):
```
① JSON 파싱 (safe_parse, 3단계 교정)
② 존재 검증 (registry lookup)
③ Execute (handler 호출)
④ 메시지 버퍼 추가 (role: tool)
```

**myAiCoder** (5단계):
```
① HITL 승인 체크 (require_approval 목록)
② 미들웨어 체인 순회 (Chain of Responsibility)
③ Execute (Tool.execute() 또는 미들웨어 handle_tool)
④ 에러 시 재시도 판별 (permission/auth/connection → skip)
⑤ 대화에 결과 추가
```

### 3.2 도구 목록 비교

| 카테고리 | claw-code | contech-chatbot | myAiCoder |
|---------|-----------|-----------------|-----------|
| 파일 읽기 | read_file | - | Read |
| 파일 쓰기 | write_file | - | Write |
| 파일 편집 | edit_file | - | Edit |
| 디렉토리 | glob_search | - | ListDir, Glob |
| 코드 검색 | grep_search | - | Grep |
| 셸 실행 | bash | - | Bash |
| 웹 검색 | WebSearch, WebFetch | - | WebFetch |
| RAG 검색 | - | search_documents | - |
| 법령 검색 | - | search_law, search_interpretation, get_law_table | - |
| 파일 분석 | - | analyze_file, get_session_files | - |
| 그래프 탐색 | - | research_topic | - |
| 서브에이전트 | Agent | - | task (SubAgentRunner) |
| 메모리 | - | - | save_memory, recall_memory |
| 계획 | TodoWrite | - | write_todos |
| 노트북 | NotebookEdit | - | - |
| MCP 도구 | mcp__*__* (무제한) | - | MCPToolProxy (동적) |
| 도구 검색 | ToolSearch | - | - |
| 스킬 | Skill | - | - |

---

## 4. 권한 및 안전 모델 (Permission & Safety)

| 항목 | claw-code | contech-chatbot | myAiCoder |
|------|-----------|-----------------|-----------|
| **모델** | 5단계 계층적 퍼미션 모드 | API Key + Rate Limit | WorkspaceGuard + HITL + Gateway |
| **도구별 권한** | ReadOnly / WorkspaceWrite / DangerFullAccess | 없음 (동일 권한) | require_approval 목록 기반 |
| **에스컬레이션** | 사용자에게 실시간 Prompt | 없음 | HITL callback (CLI prompt) |
| **경로 보호** | 워크스페이스 범위 제한 | user_id + session_id 격리 | WorkspaceGuard (경로 탈출 차단) |
| **명령 차단** | Hook exit 2 → 거부 | 없음 | `validate_command()` (rm -rf, mkfs, dd, fork bomb 등) |
| **네트워크 보안** | 없음 (CLI) | 보안 헤더 + Rate Limit | Gateway Rate Limit + 동시성 제한 |
| **데이터 격리** | 파일시스템 레벨 | DB 레벨 (user_id) | 파일시스템 + Gateway 인증 |

### 4.1 권한 모드 상세 (claw-code)

```
ReadOnly          → 파일 읽기, 검색만 가능
WorkspaceWrite    → 프로젝트 내 파일 쓰기 가능
DangerFullAccess  → bash, 시스템 명령 가능
Prompt            → 사용자에게 실시간 질문
Allow             → 모든 도구 무조건 허용
```

### 4.2 HITL 미들웨어 (myAiCoder)

```python
# hitl.py - 우선순위 10 (가장 먼저 실행)
class HITLMiddleware:
    async def handle_tool(self, name, arguments):
        if name in self.require_approval:
            approved = await self.callback(name, arguments)
            if not approved:
                return ToolResult(success=False, error="Tool execution denied")
        return None  # 다음 미들웨어로 전달
```

---

## 5. 상태 관리 (State Management)

| 항목 | claw-code | contech-chatbot | myAiCoder |
|------|-----------|-----------------|-----------|
| **대화 상태** | `Session { messages: Vec }` 메모리 | SQLite + WAL (Mixin 5개) | `ConversationManager` (Turn 기반) |
| **영속화** | JSON 파일 (`session_id.json`) | SQLite 트랜잭션 (Unit of Work) | JSON 파일 (atomic rename) |
| **상태 구조** | `ConversationMessage { role, blocks, usage }` | TypedDict (OrchestratorState) | `Turn { messages }` (tool call+result 묶음) |
| **삭제 전략** | 세션 파일 삭제 | Soft-Delete → JSONL 아카이브 → 물리 삭제 | 세션 파일 삭제 |
| **세션 재개** | `from_saved_session(id)` | `is_session_active()` + archive_days | `SessionStore.load(id)` / `load_last()` |
| **메모리 시스템** | 없음 (외부 CLAUDE.md) | 없음 | MemoryStore (JSON, tag 기반 검색) |
| **메타데이터 인덱스** | 없음 | DB 인덱스 | `_index.json` (O(1) 목록 조회) |

### 5.1 Turn 원자성 (myAiCoder 고유)

```
Turn = tool_call_message + tool_result_messages (분할 불가)

압축 시:
  ✅ Turn 단위로만 제거/보존
  ❌ Turn 중간에서 자르기 금지 (OpenAI API 400 에러 방지)
```

---

## 6. 컨텍스트 윈도우 관리

| 항목 | claw-code | contech-chatbot | myAiCoder |
|------|-----------|-----------------|-----------|
| **압축 트리거** | 입력 토큰 > 200,000 | 토큰 예산 (이미지: 2000자, 텍스트: 6000자) | 사용량 > max_tokens * 80% |
| **압축 전략** | 오래된 메시지 제거 + 구조적 요약 | 사용자 질문 보존 + AI 응답 축약 | Turn 블록 단위 역순 제거 + 요약 |
| **보존 대상** | 최근 4개 메시지 | 사용자 메시지 원문 | 최신 Turn들 (토큰 예산 내) |
| **요약 내용** | 타임라인, 도구사용, 대기작업, 참조파일 | 표→건수 축약, 텍스트→200자 | 제거된 턴의 요약 (MAX_SUMMARY_CHARS: 2000) |
| **압축 목표** | preserve_recent_messages: 4개 | 고정 예산 | available_tokens * 60% |
| **쿼리 재작성** | 없음 | LLM + 정규식 fallback | 없음 |
| **수동 압축** | `/compact` 명령 | 없음 | `compact()` 메서드 (60% 목표) |

### 6.1 압축 정교함 비교

**claw-code** (가장 정교):
```
요약에 포함되는 정보:
- 메시지 통계: user=8, assistant=7, tool=10
- 사용된 도구: Bash, Read, Grep
- 최근 사용자 요청 3개
- 대기 중인 작업 (todo, next 키워드 추론)
- 참조된 핵심 파일 목록
- 현재 작업 추론
- 시간순 타임라인
```

**contech-chatbot** (도메인 최적화):
```
- 마크다운 표 → "N건 발견: 카테고리1 M건, ..."
- 긴 AI 응답 → 첫 200자
- 사용자 질문은 전문 보존 (의도 손실 방지)
```

**myAiCoder** (구조적):
```
- Turn 블록 단위 보존/제거 (원자성)
- 요약문 2000자 상한
- 80% 트리거 → 60% 목표 (여유 확보)
```

---

## 7. 서브에이전트 및 멀티에이전트

| 항목 | claw-code | contech-chatbot | myAiCoder |
|------|-----------|-----------------|-----------|
| **서브에이전트** | MCP Stdio 프로세스 스폰 | 없음 (Expert 프롬프트 분기만) | SubAgentRunner (인프로세스) |
| **최대 중첩** | 제한 없음 (MCP 레벨) | N/A | MAX_DEPTH = 3 |
| **출력 제한** | 없음 | N/A | MAX_RESULT_TOKENS = 1000 |
| **격리 수준** | 프로세스 격리 (Stdio) | N/A | 격리된 MiddlewareEngine 인스턴스 |
| **통신 프로토콜** | JsonRPC 2.0 + Content-Length | N/A | 함수 호출 (인프로세스) |
| **에이전트 선택** | LLM 자율 선택 | 규칙 기반 라우팅 | 키워드 매칭 + fallback |
| **병렬 실행** | MCP 서버별 독립 | ThreadPoolExecutor (Prefetch) | 없음 (순차 실행) |
| **멀티 모드** | 단일 모드 | 3가지 (Orch/Tool/Prefetch) | 2가지 (AgentEngine/MiddlewareEngine) |

### 7.1 서브에이전트 아키텍처 비교

**claw-code**: 프로세스 수준 격리
```
MainAgent ──JsonRPC──→ [MCP Server Process A] → Tool 실행
           ──JsonRPC──→ [MCP Server Process B] → Tool 실행
           ──JsonRPC──→ [MCP Server Process C] → Tool 실행
```

**contech-chatbot**: 파이프라인 분기
```
Orchestrator ──분류──→ law expert prompt
                     → cost expert prompt
                     → guideline expert prompt
                     (같은 LLM, 다른 시스템 프롬프트)
```

**myAiCoder**: 인프로세스 재귀
```
MainEngine ──task 도구──→ SubAgentRunner
                          ├─ 깊이 체크 (≤3)
                          ├─ 격리된 MiddlewareEngine 생성
                          ├─ 실행 → 결과 압축 (≤1000 토큰)
                          └─ 결과 반환
```

---

## 8. Hook / 이벤트 시스템

| 항목 | claw-code | contech-chatbot | myAiCoder |
|------|-----------|-----------------|-----------|
| **Hook 유형** | PreToolUse / PostToolUse | 없음 | before() / handle_tool() / after() |
| **구현 방식** | 셸 명령 (환경변수 전달) | - | Python 미들웨어 메서드 |
| **거부 메커니즘** | exit 2 → Deny | - | ToolResult(success=False) 반환 |
| **확장 방법** | 설정 파일에 셸 명령 등록 | 코드 수정 | AgentMiddleware 서브클래스 추가 |
| **실행 순서** | Pre→실행→Post (고정) | - | 우선순위 기반 정렬 (10→20→...→200) |
| **역순 실행** | 없음 | - | after()는 역순 (200→...→20→10) |
| **이벤트 시스템** | 부트스트랩 12단계 | FastAPI lifespan만 | FastAPI lifespan + 미들웨어 체인 |

### 8.1 미들웨어 우선순위 (myAiCoder)

```
before() 실행 순서:        after() 실행 순서 (역순):
  HITL (10)        ←→       Summarization (200)
  Memory (20)      ←→       Filesystem (50)
  Planning (30)    ←→       SubAgent (40)
  SubAgent (40)    ←→       Planning (30)
  Filesystem (50)  ←→       Memory (20)
  Summarization (200) ←→    HITL (10)
```

---

## 9. 원자성 및 데이터 무결성

| 항목 | claw-code | contech-chatbot | myAiCoder |
|------|-----------|-----------------|-----------|
| **도구 결과 기록** | 모든 경로(성공/실패/거부) 반드시 기록 | 성공/실패 기록 | 성공/실패 기록 + HITL 거부 기록 |
| **트랜잭션** | Vec::push() 단위 | SQLite Unit of Work | Turn 단위 (분할 금지) |
| **세션 저장** | JSON write_text (단순) | SQLite commit/rollback | atomic rename (tmp → target) |
| **압축 원자성** | Session 전체 교체 | 인메모리 슬라이싱 | Turn 블록 단위 교체 |
| **파일 편집** | 파일↔세션 불일치 가능 | 해당 없음 | 파일↔대화 불일치 가능 |
| **부분 저장** | 없음 | QA쌍 부분 답변 저장 | 없음 |
| **DB 트랜잭션** | 없음 | SQLite WAL | PostgreSQL (gateway) |

---

## 10. 에러 처리 및 복원력

| 항목 | claw-code | contech-chatbot | myAiCoder |
|------|-----------|-----------------|-----------|
| **API 재시도** | 지수 백오프 (200→400→800→2000ms) | 없음 (단일 시도) | 재시도 로직 (retryable 판별) |
| **도구 에러** | `is_error: true` 플래그 | 에러를 tool role로 반환 | `ToolResult(success=False, error=...)` |
| **Graceful Degradation** | 에러도 결과로 전달 | 법령 API 실패 → 벡터DB만 사용 | 없음 (에러 전파) |
| **예외 계층** | `RuntimeError`, `ApiError` | `ContechError` 8개 서브클래스 | 표준 Exception + Gateway `errors.py` |
| **Self-Correction** | LLM 자율 재시도 | 3단계 JSON 파싱 교정 | `_is_retryable_error()` 판별 |
| **비재시도 에러** | 인증, 잘못된 요청 | 없음 (모두 단일 시도) | permission, denied, auth, connection |

---

## 11. 기술 스택 전체 비교

| 계층 | claw-code | contech-chatbot | myAiCoder |
|------|-----------|-----------------|-----------|
| **코어 런타임** | Rust (tokio async) | Python (asyncio) | Python (asyncio) |
| **보조 레이어** | Python (포팅 계층) | - | - |
| **LLM 통신** | reqwest (직접 HTTP) | LangChain ChatOpenAI | OpenAI 호환 API (직접) |
| **오케스트레이션** | 자체 (conversation.rs) | LangGraph StateGraph | 자체 (MiddlewareStack) |
| **도구 프레임워크** | 자체 (ToolRegistry) | 자체 (ToolRegistry) | 자체 (ToolRegistry + Middleware) |
| **외부 도구** | MCP (Model Context Protocol) | 법령정보센터 API | MCP |
| **벡터 DB** | 없음 | ChromaDB | 없음 |
| **그래프 DB** | 없음 | Neo4j | 없음 |
| **관계형 DB** | 없음 | SQLite + WAL | PostgreSQL (gateway) |
| **세션 저장** | JSON 파일 | SQLite | JSON 파일 (atomic) |
| **웹 프레임워크** | 없음 (CLI) | FastAPI | FastAPI (gateway) |
| **프론트엔드** | 터미널 UI | Web (SSE) | VS Code Extension |
| **패키지 관리** | Cargo + pip | pip + poetry | uv |
| **린터** | clippy + ruff | - | ruff |
| **모니터링** | 없음 | 없음 | Prometheus + structlog |
| **컨테이너** | 없음 | Docker | Docker + Kubernetes |
| **IaC** | 없음 | 없음 | Terraform |

---

## 12. 아키텍처 패턴 비교

| 패턴 | claw-code | contech-chatbot | myAiCoder |
|------|-----------|-----------------|-----------|
| **전체 구조** | 이중 레이어 런타임 | 계층형 서비스 | 마이크로서비스 모노레포 |
| **에이전트 패턴** | ReAct Loop | State Machine + ReAct | Middleware Chain + ReAct |
| **도구 디스패치** | Pattern Matching | Registry Lookup | Chain of Responsibility |
| **확장 패턴** | MCP 플러그인 | 코드 수정 | Middleware 추가 |
| **마이그레이션** | 없음 | 없음 | Strangler Fig (구↔신 병행) |
| **불변성** | Rust 소유권 시스템 | Python dataclass | frozen dataclass (ContextPayload) |
| **DI** | Trait 기반 | FastAPI Depends | 생성자 주입 |
| **데이터 접근** | 직접 파일 I/O | Mixin 패턴 (5개) | Repository 패턴 |
| **설정 관리** | 3단계 병합 (User/Project/Local) | Pydantic + YAML | YAML + 환경변수 |
| **Clean Architecture** | 암묵적 (crate 분리) | 명시적 (3계층) | 명시적 (4계층) |

---

## 13. 종합 레이더 차트

```
                         claw-code    contech-chatbot    myAiCoder
                         ─────────    ───────────────    ─────────
에이전트 자율성             ★★★★★         ★★★               ★★★★
도구 확장성                ★★★★★         ★★                ★★★★
권한/보안 세밀도            ★★★★★         ★★★               ★★★★
상태 영속성                ★★★           ★★★★              ★★★
컨텍스트 관리              ★★★★★         ★★★★              ★★★★
멀티에이전트               ★★★★★         ★★★★              ★★★
Hook/이벤트               ★★★★★         ★★                ★★★★
원자성                    ★★★★          ★★★★              ★★★★
에러 복원력                ★★★★★         ★★★★              ★★★
도메인 특화                ★★            ★★★★★             ★★★
운영 인프라                ★★★           ★★★               ★★★★★
테스트 커버리지             ★★★★          ★★★               ★★★★
타입 안전성                ★★★★★         ★★★               ★★★
성능 (런타임)              ★★★★★         ★★★               ★★★
```

---

## 14. 핵심 기술 차이 분석

### 14.1 런타임 성능

| 측면 | claw-code | contech-chatbot | myAiCoder |
|------|-----------|-----------------|-----------|
| **코어 언어** | Rust (제로 코스트 추상화) | Python (GIL 제약) | Python (GIL 제약) |
| **메모리 안전** | 컴파일 타임 보장 | 런타임 GC | 런타임 GC |
| **동시성** | tokio (멀티스레드 async) | ThreadPoolExecutor | asyncio (단일 스레드) |
| **도구 디스패치 비용** | O(1) match 분기 | O(1) dict lookup | O(n) 미들웨어 체인 순회 |

### 14.2 확장성 설계

| 측면 | claw-code | contech-chatbot | myAiCoder |
|------|-----------|-----------------|-----------|
| **도구 추가** | MCP 서버 설정만으로 | 코드 수정 + 재배포 | 미들웨어 또는 MCP 추가 |
| **에이전트 추가** | MCP 서버 연결 | Expert 프롬프트 YAML 추가 | SubAgent 등록 |
| **기능 확장** | Hook 셸 스크립트 | 코드 수정 | AgentMiddleware 서브클래스 |
| **프로토콜** | MCP (표준) | REST API (자체) | MCP + OpenAI 호환 |

### 14.3 안전성 깊이

```
claw-code:        Permission Mode (5단계) → Hook (셸) → 도구별 권한 → 사용자 Prompt
contech-chatbot:  API Key → Rate Limit → 보안 헤더 → DB 격리
myAiCoder:        Gateway 인증 → Rate Limit → 동시성 제한 → HITL → WorkspaceGuard → 명령 차단
```

---

## 15. 각 프로젝트에서 배울 점

### claw-code에서 배울 점 (→ myAiCoder 적용 가능)

| 패턴 | 설명 | 적용 가능성 |
|------|------|-----------|
| **Rust 코어 런타임** | 성능 크리티컬 경로를 Rust로 | 중장기 (TS/Rust 전환 계획과 일치) |
| **MCP Lazy Init** | 첫 호출시에만 프로세스 스폰 | 이미 적용 중 |
| **구조적 압축 요약** | 타임라인, 도구사용, 대기작업 포함 | 높음 (현재 단순 요약 개선 가능) |
| **부트스트랩 12단계** | 시스템 프롬프트 캐싱, Fast Path | 중간 (성능 최적화 시) |
| **도구별 퍼미션 모드** | ReadOnly / Write / Danger 분류 | 높음 (HITL 고도화) |
| **Hook 셸 명령** | 사용자 정의 확장 포인트 | 중간 (미들웨어로 대체 가능) |

### contech-chatbot에서 배울 점 (→ myAiCoder 적용 가능)

| 패턴 | 설명 | 적용 가능성 |
|------|------|-----------|
| **Prefetch 병렬 수집** | ThreadPoolExecutor 기반 병렬 | 높음 (Sub-agent 병렬화) |
| **Cascading 교차 검증** | 다중 소스 신뢰도 누적 | 중간 (코드 검색 정확도 향상) |
| **Graceful Degradation** | 외부 서비스 실패 시 대체 경로 | 높음 (현재 미구현) |
| **도메인 특화 압축** | 표→건수, 의도 보존 | 중간 (코드 컨텍스트 특화 압축) |
| **QA쌍 부분 저장** | 스트리밍 중 끊겨도 저장 | 높음 (세션 안정성 향상) |
| **Soft-Delete + 아카이브** | 데이터 생명주기 관리 | 낮음 (현재 JSON 파일 기반) |

### myAiCoder의 고유 강점

| 패턴 | 설명 | 차별점 |
|------|------|-------|
| **Middleware Stack** | 합성 가능한 기능 확장 | claw-code의 Hook보다 유연, contech보다 구조적 |
| **Turn 원자성** | Tool call+result 분할 금지 | 다른 프로젝트에 없는 고유 패턴 |
| **ContextPayload frozen** | 구조적 불변성 보장 | Python에서 Rust 수준의 안전성 추구 |
| **SubAgent 출력 경계** | 1000토큰 강제 압축 | Context explosion 예방 |
| **Strangler Fig** | 구↔신 엔진 점진적 마이그레이션 | 운영 안정성 확보 |
| **Gateway 분리** | 인증/제한/라우팅 독립 서비스 | 엔터프라이즈급 인프라 |

---

## 16. 진화 방향 제안 (myAiCoder)

### 단기 (현재 → 다음 PDCA)

1. **압축 요약 고도화**: claw-code의 구조적 요약 패턴 (도구사용, 참조파일, 대기작업) 도입
2. **Graceful Degradation**: contech-chatbot의 외부 서비스 실패 대체 경로 패턴 적용
3. **도구별 퍼미션 분류**: ReadOnly / Write / Danger 3단계로 HITL 고도화

### 중기 (1-2 PDCA 사이클)

4. **SubAgent 병렬화**: contech-chatbot의 ThreadPoolExecutor 패턴으로 다중 서브에이전트 동시 실행
5. **세션 부분 저장**: 스트리밍 중 연결 끊김 시 부분 결과 저장
6. **지수 백오프 재시도**: claw-code의 API 재시도 전략 도입

### 장기 (로드맵)

7. **Rust 코어 마이그레이션**: 성능 크리티컬 경로 (도구 디스패치, 토큰 추정) Rust 전환
8. **부트스트랩 Fast Path**: 시스템 프롬프트 캐싱, MCP 연결 최적화

---

## 부록 A. 핵심 파일 참조

### claw-code

| 기능 | 파일 | 라인 |
|------|------|------|
| 에이전트 루프 | `rust/crates/runtime/src/conversation.rs` | 170-283 |
| 도구 정의 | `rust/crates/tools/src/lib.rs` | 50-381 |
| 도구 실행 | `rust/crates/tools/src/lib.rs` | 383-408 |
| 권한 정책 | `rust/crates/runtime/src/permissions.rs` | 49-135 |
| Hook 시스템 | `rust/crates/runtime/src/hooks.rs` | 1-150 |
| 자동 압축 | `rust/crates/runtime/src/compact.rs` | 75-111 |
| 압축 요약 | `rust/crates/runtime/src/compact.rs` | 113-198 |
| API 재시도 | `rust/crates/api/src/client.rs` | 273-307 |
| MCP 관리 | `rust/crates/runtime/src/mcp_stdio.rs` | 507-570 |
| 세션 저장 | `src/session_store.py` | 19-35 |
| 부트스트랩 | `rust/crates/runtime/src/bootstrap.rs` | 2-38 |
| 설정 계층 | `rust/crates/runtime/src/config.rs` | 183-211 |

### contech-chatbot

| 기능 | 파일 | 라인 |
|------|------|------|
| Orchestrator | `src/agents/orchestrator.py` | 1-417 |
| Tool Engine | `src/agents/tool_engine.py` | 1-405 |
| Prefetch Engine | `src/agents/prefetch/engine.py` | 47-107 |
| 도구 레지스트리 | `src/agents/tool_registry.py` | 43-200 |
| 대화 압축 | `src/agents/chat_compressor.py` | 27-91 |
| Pipeline Context | `src/agents/pipeline_context.py` | 36-98 |
| 쿼리 재작성 | `src/agents/query_rewriter.py` | 94-160 |
| Chat DB | `src/database/chat_db.py` | 31-70 |
| 보안 미들웨어 | `src/api/middleware.py` | 34-80 |
| 예외 계층 | `src/core/exceptions.py` | 전체 |
| SSE 라우트 | `src/api/routes/chat.py` | 전체 |

### myAiCoder

| 기능 | 파일 | 라인 |
|------|------|------|
| MiddlewareEngine | `services/myaicoder/src/myaicoder/core/engine.py` | 214-417 |
| ConversationManager | `services/myaicoder/src/myaicoder/core/conversation.py` | 62-295 |
| MiddlewareStack | `services/myaicoder/src/myaicoder/core/middleware/stack.py` | 9-67 |
| ContextPayload | `services/myaicoder/src/myaicoder/core/middleware/base.py` | 16-42 |
| HITL Middleware | `services/myaicoder/src/myaicoder/core/middleware/hitl.py` | 11-48 |
| SubAgentRunner | `services/myaicoder/src/myaicoder/core/subagent/runner.py` | 11-98 |
| ToolRegistry | `services/myaicoder/src/myaicoder/tools/registry.py` | 6-27 |
| WorkspaceGuard | `services/myaicoder/src/myaicoder/tools/base.py` | 19-42 |
| SessionStore | `services/myaicoder/src/myaicoder/core/session.py` | 122-337 |
| MemoryStore | `services/myaicoder/src/myaicoder/core/memory/store.py` | 10-125 |
| Gateway 에러 | `services/gateway/app/middleware/errors.py` | 11-39 |
| Gateway Rate Limit | `services/gateway/app/middleware/rate_limiter.py` | 전체 |
| Gateway 동시성 | `services/gateway/app/middleware/concurrency.py` | 전체 |
