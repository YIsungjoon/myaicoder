# Plan: MCP Server (Phase 4)

**Feature**: mcp-server
**날짜**: 2026-03-13
**Phase**: Plan
**Level**: Enterprise
**Parent Feature**: ai-coder-cli (Phase 4)

---

## 1. 개요

myAiCoder의 6개 내장 도구(Read, Write, Edit, Glob, Grep, Bash)를 MCP(Model Context Protocol) 서버로 노출하여, 외부 MCP 클라이언트(Claude Code, Cursor, 다른 AI 에이전트 등)가 myAiCoder의 도구를 직접 호출할 수 있도록 한다.

또한 myAiCoder가 MCP Client로서 **Revit MCP**, **AutoCAD MCP** 등 AEC(건축/엔지니어링/건설) 분야 MCP 서버와 호환되어야 한다. 이를 통해 로컬 LLM 기반으로 BIM/CAD 작업을 자동화하며, 외부 API 토큰 비용 없이 독립적으로 운용할 수 있다.

## 2. 핵심 요구사항

### 2.1 기능 요구사항

| ID | 기능 | 설명 | 우선순위 |
|----|------|------|----------|
| FR-01 | **MCP Server 구현** | Built-in 6개 도구를 MCP 프로토콜로 노출 | P0 |
| FR-02 | **stdio 트랜스포트** | 로컬 프로세스 통신 (표준 MCP 방식) | P0 |
| FR-03 | **Streamable HTTP 트랜스포트** | 원격 접근을 위한 HTTP 기반 통신 | P1 |
| FR-04 | **`myaicoder serve` 커맨드** | CLI에서 MCP 서버 모드로 실행 | P0 |
| FR-05 | **도구 스키마 노출** | `tools/list`로 6개 도구의 JSON Schema 제공 | P0 |
| FR-06 | **도구 실행** | `tools/call`로 도구 실행 및 결과 반환 | P0 |
| FR-07 | **Claude Code 호환** | Claude Code의 .mcp.json에 등록하여 사용 가능 | P0 |
| FR-08 | **권한 제어** | 서버 모드에서 도구별 접근 제어 옵션 | P2 |
| FR-09 | **Revit MCP 호환** | Revit MCP 서버 연결 → BIM 모델 조회/수정 | P0 |
| FR-10 | **AutoCAD MCP 호환** | AutoCAD MCP 서버 연결 → DWG 도면 조작 | P0 |
| FR-11 | **MCP 체이닝** | myAiCoder가 MCP Server + Client 동시 동작하여, 외부 클라이언트가 myAiCoder를 통해 Revit/CAD 도구에 접근 (토큰 비용 절감) | P1 |

### 2.2 비기능 요구사항

| ID | 항목 | 기준 |
|----|------|------|
| NFR-01 | 응답 속도 | 도구 호출 오버헤드 < 100ms (MCP 프로토콜 레이어) |
| NFR-02 | 안정성 | 장시간 실행 시 메모리 누수 없음 |
| NFR-03 | 호환성 | MCP spec 2025-03 준수, Claude Code / Cursor 호환 |
| NFR-04 | 보안 | HTTP 모드에서 토큰 기반 인증 옵션 |

## 3. 기술 분석

### 3.1 MCP Server SDK 옵션

| 방식 | 설명 | 장단점 |
|------|------|--------|
| **FastMCP** | 고수준 데코레이터 기반 API | 간결, 빠른 구현, 공식 권장 |
| **Server (Low-level)** | 저수준 핸들러 등록 | 세밀한 제어, 복잡 |

**선택: FastMCP** — 공식 Python SDK의 권장 방식. 데코레이터로 도구를 선언적으로 등록할 수 있어 구현이 간결하다.

### 3.2 아키텍처

```
External MCP Client (Claude Code, Cursor, etc.)
        │
        │  stdio / HTTP (JSON-RPC 2.0)
        ▼
┌─────────────────────────────────────┐
│       MCP Server (mcp/server.py)    │
│                                     │
│  FastMCP                            │
│  ├── @mcp.tool() Read               │
│  ├── @mcp.tool() Write              │
│  ├── @mcp.tool() Edit               │
│  ├── @mcp.tool() Glob               │
│  ├── @mcp.tool() Grep               │
│  └── @mcp.tool() Bash               │
│                                     │
│  Tool ABC 재사용                     │
│  ToolRegistry → FastMCP 래핑        │
└─────────────────────────────────────┘
```

### 3.3 핵심 설계 고려사항

#### Tool ABC 재사용 전략

기존 Tool ABC 구현체를 그대로 활용하되, MCP 서버 레이어에서 래핑하는 2가지 접근:

| 접근 | 방식 | 장점 | 단점 |
|------|------|------|------|
| **A. 래핑 함수** | FastMCP @tool 데코레이터에서 Tool.execute() 호출 | 간결, FastMCP 네이티브 | 도구 추가 시 래핑 코드 필요 |
| **B. 동적 등록** | ToolRegistry 순회하며 FastMCP에 자동 등록 | 도구 추가 시 자동 반영 | 동적 생성 복잡도 |

**선택: B (동적 등록)** — ToolRegistry에 등록된 모든 도구를 자동으로 MCP 서버에 노출. 도구 추가 시 별도 코드 수정 불필요.

#### Tool.to_mcp_tool() 메서드

Design 문서에 정의되어 있으나 Phase 3까지 미구현이었던 메서드. MCP 서버에서 Tool의 스키마를 MCP 형식으로 변환할 때 사용.

```python
# tools/base.py에 추가
def to_mcp_tool(self) -> dict:
    """Convert to MCP tool schema."""
    return {
        "name": self.name,
        "description": self.description,
        "inputSchema": self.parameters_schema,
    }
```

#### 트랜스포트 전략

| Transport | 용도 | 구현 |
|-----------|------|------|
| **stdio** | 로컬 사용, Claude Code 연동 | FastMCP 기본 지원 |
| **Streamable HTTP** | 원격 접근, IDE 확장 연동 | FastMCP 내장 HTTP 서버 |

stdio가 기본값. HTTP는 `--transport http --port 3000` 옵션으로 활성화.

## 4. Claude Code 호환성

### 4.1 등록 방법

Claude Code의 `.mcp.json`에 다음과 같이 등록:

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

또는 HTTP 모드:

```json
{
  "mcpServers": {
    "myaicoder-remote": {
      "transport": "http",
      "url": "http://localhost:3000/mcp"
    }
  }
}
```

### 4.2 노출 도구 목록

| MCP Tool Name | 설명 | 기존 Tool |
|---------------|------|----------|
| `read_file` | 파일 읽기 | ReadTool |
| `write_file` | 파일 쓰기 | WriteTool |
| `edit_file` | 파일 편집 | EditTool |
| `glob_search` | 파일 패턴 검색 | GlobTool |
| `grep_search` | 파일 내용 검색 | GrepTool |
| `run_command` | 셸 명령 실행 | BashTool |

MCP 도구명은 스네이크 케이스로 변환하여 Claude Code 등 외부 클라이언트에서 직관적으로 사용 가능하도록 한다. 기존 내부 도구명(Read, Write 등)과의 매핑은 서버 코드에서 관리.

## 5. AEC MCP 호환성 (Revit / AutoCAD)

### 5.1 주요 사용 시나리오: myAiCoder → Revit/CAD MCP (직접 사용)

myAiCoder가 MCP Client로서 Revit/AutoCAD MCP 서버에 직접 연결하여 BIM/CAD 작업을 수행한다.
Phase 3에서 구현된 MCP Client가 이를 지원하며, `.mcp.json`에 서버를 등록하면 즉시 사용 가능.

```
사용자: "Revit에서 1층 벽체 목록 가져와서, AutoCAD에 평면도 그려줘"
        ↓
myAiCoder (Qwen3.5-27B, 로컬 추론)
        ↓ tool_call
   ┌────┴────┐
   ▼         ▼
Revit MCP  AutoCAD MCP
(벽체 조회) (도면 생성)
```

**장점**: 로컬 LLM → 외부 API 토큰 비용 0원. Revit+CAD 도구를 하나의 에이전트에서 통합 사용.

### 5.2 보조 시나리오: 외부 클라이언트 → myAiCoder MCP → Revit/CAD (체이닝)

myAiCoder가 MCP Server + MCP Client를 동시에 구동하여, 외부 클라이언트(Claude Code 등)가 myAiCoder를 **프록시**로 사용. 외부 클라이언트는 myAiCoder의 로컬 LLM을 통해 Revit/CAD 작업을 위임할 수 있다.

```
Claude Code (외부, API 토큰 과금)
        ↓ MCP 호출
myAiCoder MCP Server (로컬)
        ↓ 로컬 LLM으로 판단
        ↓ MCP Client 호출
   ┌────┴────┐
   ▼         ▼
Revit MCP  AutoCAD MCP
```

**토큰 비용 절감 효과**: Claude Code가 직접 Revit/CAD 도구를 호출하면 매 반복마다 API 토큰 소비. myAiCoder를 중간 프록시로 두면, 복잡한 multi-step 작업을 로컬 LLM이 처리하고 Claude Code는 최종 결과만 수신 → **토큰 비용 대폭 절감**.

### 5.3 호환 대상 MCP 서버

| MCP 서버 | 소프트웨어 | 주요 기능 | 트랜스포트 |
|----------|-----------|----------|-----------|
| **revit-mcp/revit-mcp** | Revit 2026 | 요소 조회, 파라미터 수정, 뷰 관리 | stdio |
| **Sam-AEC/Autodesk-Revit-MCP-Server** | Revit | Production-ready, 구조물 생성 | stdio |
| **daobataotie/CAD-MCP** | AutoCAD, GstarCAD, ZWCAD | 다중 CAD 지원, 자연어 제어 | stdio |
| **ahmetcemkaraca/AutoCAD_MCP** | AutoCAD 2025 | 2D/3D DWG 생산 | stdio |
| **puran-water/autocad-mcp** | AutoCAD LT | AutoLISP 실행, P&ID 심볼 | stdio |
| **Autodesk AEC Data Model** | ACC (Construction Cloud) | BIM 데이터 모델 쿼리 | HTTP |

### 5.4 .mcp.json 설정 예시

```json
{
  "mcpServers": {
    "revit": {
      "transport": "stdio",
      "command": "python",
      "args": ["path/to/revit_mcp_server.py"]
    },
    "autocad": {
      "transport": "stdio",
      "command": "python",
      "args": ["path/to/cad_mcp_server.py"]
    },
    "aec-data": {
      "transport": "http",
      "url": "https://mcp.autodesk.com/aec"
    }
  }
}
```

## 6. 기술적 사각지대 및 리스크 (Blind Spots)

### 6.1 BIM 데이터의 압도적인 컨텍스트 길이

Revit/AutoCAD에서 요소(Element) 데이터를 JSON으로 추출하면 수만 토큰을 쉽게 초과한다. Qwen3.5-27B의 컨텍스트 윈도우(32K) 안에 이 데이터를 유지하면서 정확한 파라미터를 찾아내는 것은 심각한 도전.

| 전략 | 설명 | 적용 시점 |
|------|------|----------|
| **Data Minification** | MCP 응답에서 필요한 필드만 추출하는 필터링 레이어 | Phase 4 |
| **Chunked Processing** | 대량 요소를 페이지 단위로 분할 처리 | Phase 4 |
| **Schema Summarization** | 도구 호출 전 요소 스키마를 요약하여 LLM에 전달 | Phase 5 |
| **Selective Context** | ElementId 목록만 먼저 가져오고, 상세는 개별 조회 | Phase 4 |

**구현 방안**: MCP 도구 응답에 대한 **결과 필터/축약 미들웨어**를 도입. `max_result_tokens` 설정으로 LLM에 전달되는 도구 결과 크기를 제한한다.

```python
# core/engine.py — 도구 결과 축약
def _truncate_tool_result(self, result: str, max_tokens: int = 4000) -> str:
    """BIM 데이터 등 대량 결과를 컨텍스트에 맞게 축약."""
    if len(result) > max_tokens * 4:  # rough char-to-token
        return result[:max_tokens * 4] + f"\n... (truncated, {len(result)} chars total)"
    return result
```

### 6.2 체이닝 시나리오의 에러 전파 (Error Propagation)

Claude Code → myAiCoder → Revit MCP 체인에서 Revit이 "유효하지 않은 파라미터" 에러를 반환할 때, 에러 처리 정책이 명확해야 한다.

| 에러 유형 | 처리 정책 | 근거 |
|-----------|----------|------|
| **파라미터 오류** (InvalidParam) | 로컬 LLM이 1-2회 자체 재시도 | 단순 파라미터 수정은 로컬에서 빠르게 해결 |
| **연결 오류** (ConnectionFailed) | 즉시 외부 클라이언트에 에러 반환 | 로컬에서 해결 불가 |
| **권한 오류** (PermissionDenied) | 즉시 외부 클라이언트에 에러 반환 | 정책 결정은 상위 에이전트 몫 |
| **데이터 오류** (NotFound) | 로컬 LLM이 대안 쿼리 시도 1회 | ElementId 오류 등은 재검색으로 해결 가능 |
| **재시도 실패** | 에러 원문 + 시도 내역을 함께 상위에 전달 | 상위 에이전트가 맥락 파악 후 판단 |

**구현 방안**: `_execute_tool_with_approval()`에 `max_retries` 파라미터 추가. 체이닝 모드에서는 에러 응답에 `retry_attempted: true/false` 메타데이터 포함.

### 6.3 동시성 제어 (VRAM 병목)

HTTP 모드로 외부 에이전트가 접속할 경우, 로컬 LLM이 여러 요청을 동시에 처리해야 한다. llama-server(단일 슬롯)에서는 직렬 처리만 가능하여 타임아웃 위험.

| 서빙 엔진 | 동시 요청 | VRAM | 비고 |
|-----------|:--------:|:----:|------|
| llama-server (현재) | 1 | ~14GB | `--parallel N`으로 확장 가능하나 VRAM 추가 소비 |
| vLLM | 다수 | ~16GB | Paged Attention, continuous batching |
| llama.cpp `--parallel 4` | 4 | ~18GB | RTX 4090(24GB) 범위 내 |

**완화 전략**:
- **Phase 4**: 요청 큐잉 + 타임아웃 설정. HTTP 모드에서 동시 요청 수 제한 (`--max-concurrent 2`)
- **Phase 5+**: vLLM 또는 llama.cpp `--parallel` 옵션으로 전환 검토
- **즉시 적용**: `myaicoder serve --max-concurrent N` 옵션 추가

### 6.4 라우팅 전략: Direct Pass-through vs Agentic Execution

체이닝 프록시 시나리오에서 NFR-01(100ms 오버헤드)은 LLM 개입 시 달성 불가능. 따라서 **두 가지 라우팅 모드**를 명확히 분리한다.

```
외부 MCP Client
        │
        ▼
myAiCoder MCP Server
        │
        ├── [Direct Pass-through]  ← 단순 도구 호출 (Read, Write, Glob 등)
        │   LLM 미개입, 즉시 실행, <100ms
        │
        └── [Agentic Execution]    ← 고차원 지시 ("Revit에서 평면도 수정해줘")
            로컬 LLM 개입, multi-step, 수초~수분
```

| 라우팅 모드 | 트리거 | LLM 개입 | 지연 |
|------------|--------|:--------:|------|
| **Direct Pass-through** | MCP `tools/call`로 특정 도구 직접 호출 | No | <100ms |
| **Agentic Execution** | 특수 도구 `agentic_task(prompt)` 호출 | Yes | 수초~수분 |

**구현 방안**:
- 기본 MCP 서버 도구(read_file, write_file 등)는 **항상 Direct Pass-through**
- `agentic_task` 도구를 추가로 노출: 이 도구가 호출되면 로컬 LLM의 agentic loop 실행
- 외부 클라이언트가 선택: 단순 작업은 직접 호출, 복잡한 BIM 작업은 `agentic_task`로 위임

```python
# MCP Server에 노출되는 특수 도구
@mcp.tool()
async def agentic_task(prompt: str) -> str:
    """Execute a complex task using local LLM agent.
    Use this for multi-step operations like BIM modifications."""
    engine = AgentEngine(llm=local_llm, tool_registry=registry)
    return await engine.chat(prompt)
```

## 6.5 일반 리스크

| 리스크 | 영향 | 완화 전략 |
|--------|------|----------|
| Bash 도구 보안 | 높음 | 기본 비활성, --allow-bash 옵션으로만 활성화 |
| 파일 쓰기 범위 | 높음 | --working-dir 옵션으로 작업 디렉토리 제한 |
| HTTP 무인증 접근 | 중간 | 기본 localhost only, --auth-token 옵션 |
| MCP SDK 버전 호환 | 낮음 | mcp>=1.0 고정, spec 변경 모니터링 |
| Revit/CAD Windows 전용 | 중간 | 원격 머신에서 MCP 서버 실행, HTTP 트랜스포트로 연결 |

## 7. 구현 범위

### 7.1 Phase 4 범위 (In Scope)

| # | 항목 | 우선순위 |
|---|------|----------|
| 1 | `mcp/server.py` — FastMCP 기반 MCP 서버 | P0 |
| 2 | `Tool.to_mcp_tool()` 메서드 추가 | P0 |
| 3 | ToolRegistry → FastMCP 동적 등록 함수 | P0 |
| 4 | `myaicoder serve` CLI 커맨드 (stdio 기본) | P0 |
| 5 | `--transport` 옵션 (stdio/http) | P0 |
| 6 | `--port` 옵션 (HTTP 트랜스포트용) | P1 |
| 7 | `--allow-bash` 안전 옵션 | P1 |
| 8 | `--working-dir` 작업 디렉토리 제한 | P1 |
| 9 | `tests/test_mcp/test_server.py` — 서버 테스트 | P0 |
| 10 | Claude Code 호환 통합 테스트 | P0 |
| 11 | Revit MCP 서버 연결 검증 (.mcp.json 설정) | P0 |
| 12 | AutoCAD MCP 서버 연결 검증 (.mcp.json 설정) | P0 |
| 13 | MCP 체이닝 (Server+Client 동시 구동) 프로토타입 | P1 |
| 14 | 도구 결과 축약 미들웨어 (BIM 데이터 대응) | P0 |
| 15 | 에러 전파 정책 + 자체 재시도 로직 | P0 |
| 16 | Direct Pass-through / Agentic Execution 라우팅 | P0 |
| 17 | `agentic_task` 특수 MCP 도구 노출 | P1 |
| 18 | `--max-concurrent` 동시 요청 제한 옵션 | P1 |

### 7.2 Phase 4 범위 외 (Out of Scope)

| 항목 | 사유 |
|------|------|
| HTTP 인증 토큰 | P2, Phase 7 보안 강화 시 |
| MCP Resources / Prompts | Phase 5 이후 확장 |
| 커스텀 도구 플러그인 시스템 | Phase 7 이후 |
| Revit/CAD 전용 프롬프트 튜닝 | 별도 PDCA 사이클로 진행 |
| vLLM 동시성 서빙 전환 | Phase 5+, VRAM 분석 후 |
| Schema Summarization (고급 BIM 최적화) | Phase 5, 컨텍스트 관리와 통합 |

## 8. 마일스톤

| Step | 작업 | 산출물 |
|------|------|--------|
| 1 | `Tool.to_mcp_tool()` 추가 | `tools/base.py` 수정 |
| 2 | `mcp/server.py` — FastMCP 서버 구현 | 신규 파일 |
| 3 | ToolRegistry → FastMCP 동적 등록 | `mcp/server.py` |
| 4 | 도구 결과 축약 미들웨어 | `core/engine.py` 수정 |
| 5 | 에러 전파 정책 + 자체 재시도 | `core/engine.py` 수정 |
| 6 | `myaicoder serve` CLI 커맨드 | `cli.py` 수정 |
| 7 | stdio/HTTP 트랜스포트 + --max-concurrent | `cli.py` + `mcp/server.py` |
| 8 | 보안 옵션 (--allow-bash, --working-dir) | `cli.py` + `mcp/server.py` |
| 9 | Direct Pass-through / Agentic Execution 라우팅 | `mcp/server.py` |
| 10 | `agentic_task` 특수 도구 노출 | `mcp/server.py` |
| 11 | 단위 테스트 | `tests/test_mcp/test_server.py` |
| 12 | Revit/AutoCAD MCP 연결 검증 | 통합 테스트 + 문서화 |
| 13 | MCP 체이닝 프로토타입 | Server+Client 동시 구동 검증 |
| 14 | Claude Code 호환 통합 테스트 | 수동 테스트 + 문서화 |

## 9. 결정 사항

- [x] **MCP 서버 프레임워크**: **FastMCP** 채택 (2026-03-13)
  - 공식 권장 고수준 API, 데코레이터 기반 도구 등록
- [x] **도구 등록 방식**: **동적 등록 (옵션 B)** 채택 (2026-03-13)
  - ToolRegistry 순회하여 FastMCP에 자동 등록
- [x] **기본 트랜스포트**: **stdio** 채택 (2026-03-13)
  - Claude Code/Cursor 등 로컬 클라이언트 표준 방식
- [x] **Bash 도구 보안**: **기본 비활성, --allow-bash로 활성화** (2026-03-13)
  - MCP 서버 모드에서는 셸 명령 실행을 명시적으로 허용해야 함
- [x] **MCP 도구명**: **스네이크 케이스** 채택 (2026-03-13)
  - Read → read_file, Write → write_file 등으로 외부 호환성 확보
- [x] **AEC MCP 호환**: **Revit + AutoCAD MCP 서버 직접 연결** (2026-03-13)
  - 주요 사용법: myAiCoder → Revit/CAD MCP (직접 사용, 로컬 LLM 추론)
  - 보조 사용법: 외부 클라이언트 → myAiCoder MCP → Revit/CAD (체이닝, 토큰 비용 절감)
- [x] **MCP 체이닝 (Server+Client 동시)**: **P1로 프로토타입** (2026-03-13)
  - myAiCoder가 MCP Server와 MCP Client를 동시에 구동하여 프록시 역할
  - 외부 클라이언트의 API 토큰 비용을 로컬 LLM으로 대체
- [x] **라우팅 전략**: **Direct Pass-through + Agentic Execution 이중 모드** (2026-03-13)
  - 단순 도구 호출: LLM 미개입, 즉시 실행 (<100ms)
  - 고차원 지시: `agentic_task` 도구로 로컬 LLM agentic loop 실행
- [x] **BIM 데이터 대응**: **결과 축약 미들웨어 + Selective Context** (2026-03-13)
  - 도구 결과 크기 제한 (`max_result_tokens`), 대량 데이터 페이지 분할
- [x] **에러 전파 정책**: **로컬 재시도 우선 + 실패 시 상위 전달** (2026-03-13)
  - 파라미터/데이터 오류: 로컬 LLM 1-2회 재시도
  - 연결/권한 오류: 즉시 상위 에이전트에 전달
- [x] **동시성 제어**: **Phase 4에서 큐잉 + max-concurrent 제한** (2026-03-13)
  - llama-server 단일 슬롯 한계 대응, vLLM 전환은 Phase 5+

---

*작성일: 2026-03-13 | Phase: Plan | Status: All Decisions Made*
*Parent: ai-coder-cli Phase 4 (M4)*
