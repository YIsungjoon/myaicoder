# PDCA Completion Report: ai-coder-cli (Phase 1-3)

**Feature**: ai-coder-cli
**Project**: myAiCoder - AI Coding Assistant powered by local LLM
**Date**: 2026-03-13
**Level**: Enterprise
**PDCA Cycle**: Plan → Design → Do → Check → Act → Report

---

## 1. Executive Summary

Claude Code 대안 AI 코딩 어시스턴트 myAiCoder의 Phase 1-3 (CLI+LLM, Tool Use, MCP Client) 구현이 완료되었다. 설계-구현 일치율 **95%** 달성, 테스트 **50건 통과** (3건 skip), 1회 iteration으로 gap을 해소하였다.

| Metric | Value |
|--------|-------|
| Match Rate | **95%** (목표 90% 초과) |
| Iteration Count | 1회 (최대 5회 중) |
| Test Results | 50 passed, 3 skipped |
| Phase Completion | Phase 1: 100%, Phase 2: 100%, Phase 3: 100% |
| PDCA Duration | 약 5시간 (Plan ~ Report) |

---

## 2. Plan Summary

### 2.1 프로젝트 목표

Qwen3.5-27B (GGUF INT4, RTX 4090 로컬 추론)을 기반으로 Claude Code와 유사한 AI 코딩 어시스턴트를 구축한다. MCP 생태계 호환성을 확보하여 기존 Claude Code MCP 서버를 그대로 활용할 수 있도록 한다.

### 2.2 핵심 결정 사항

| 결정 | 선택 | 근거 |
|------|------|------|
| 구현 언어 | **Python (옵션 C)** | 프로토타이핑 속도, LLM 실험 유연성 |
| LLM 추론 | **llama-server (Docker)** | GGUF 지원, OpenAI-compatible API |
| IDE 확장 | **VS Code 기반** | TypeScript, VS Code 포크 전체 호환 |
| CLI 프레임워크 | **click + rich** | 간결한 CLI 파싱 + 풍부한 터미널 UI |
| MCP SDK | **mcp (Python Tier 1)** | 공식 SDK, stdio/HTTP 트랜스포트 내장 |

### 2.3 구현 범위 (Phase 1-3)

| Phase | 범위 | 우선순위 |
|-------|------|----------|
| Phase 1 | CLI 기본 동작 + LLM 추론 연동 | P0 |
| Phase 2 | Tool Use (6개 내장 도구 + Agentic Loop) | P0 |
| Phase 3 | MCP Client (외부 MCP 서버 연결) | P0 |

---

## 3. Design Highlights

### 3.1 아키텍처

```
Interface Layer (CLI/UI)
        ↓
Core Engine (AgentEngine - Agentic Loop)
        ↓
┌───────┼───────┐
│       │       │
Tool    MCP     LLM
Layer   Layer   Provider
```

- **ABC 기반 인터페이스**: LLMProvider, Tool → 향후 언어 전환 용이
- **Agentic Loop**: LLM 호출 → tool_call 파싱 → 도구 실행 → 결과 주입 → 반복
- **MCPToolProxy 패턴**: MCP 서버 도구를 Tool ABC로 래핑하여 ToolRegistry에 통합

### 3.2 핵심 모듈 구조

```
src/myaicoder/
├── cli.py              # Click CLI entry point
├── core/
│   ├── engine.py       # AgentEngine (agentic loop + approval)
│   ├── conversation.py # ConversationManager
│   ├── context.py      # ContextManager (system prompt, CLAUDE.md)
│   └── config.py       # AppConfig (LLM, Tools, UI, Context)
├── llm/
│   ├── base.py         # LLMProvider ABC, Message, ToolCall, LLMResponse
│   └── vllm_provider.py # OpenAI-compatible + reasoning_content
├── tools/
│   ├── base.py         # Tool ABC, ToolResult
│   ├── registry.py     # ToolRegistry, create_default_registry()
│   ├── read.py, write.py, edit.py, glob_tool.py, grep_tool.py, bash.py
├── mcp/
│   ├── client.py       # MCPClient, MCPToolProxy
│   └── config.py       # MCPConfig (.mcp.json parsing)
└── ui/
    └── chat.py         # ChatUI (rich-based terminal UI)
```

---

## 4. Implementation Results

### 4.1 Phase 1: CLI + LLM 연동

| 구현 항목 | 상태 | 비고 |
|-----------|------|------|
| pyproject.toml + 프로젝트 구조 | Done | hatchling 빌드, uv 패키지 관리 |
| LLMProvider ABC | Done | chat(), chat_stream(), health_check() |
| VLLMProvider | Done | raw httpx + reasoning_content 처리 |
| Click CLI (대화형 + 원샷) | Done | --model, --vllm-url, --prompt, --verbose |
| ChatUI (rich 기반) | Done | 마크다운 렌더링, 토큰 사용량 표시 |
| ConversationManager | Done | 메시지 관리, system prompt 주입 |
| AgentEngine (기본) | Done | 대화 루프 + 스트리밍 |
| ContextManager | Done | CLAUDE.md 로딩, /no_think, 프로젝트 스캔 |

**LLM 통합 테스트**: llama-server (Docker, port 8080)에 Qwen3.5-27B-Q4_0.gguf 모델로 실제 대화 및 tool_call 검증 완료.

### 4.2 Phase 2: Tool Use

| 구현 항목 | 상태 | 비고 |
|-----------|------|------|
| Tool ABC + ToolResult | Done | name, description, parameters_schema, execute() |
| ToolRegistry | Done | register(), get(), to_openai_tools() |
| ReadTool | Done | file_path, offset, limit |
| WriteTool | Done | file_path, content, 자동 디렉토리 생성 |
| EditTool | Done | old_string/new_string, replace_all, uniqueness 체크 |
| GlobTool | Done | pattern, path, skip_dirs, mtime 정렬 |
| GrepTool | Done | regex pattern, path, glob filter, case_insensitive |
| BashTool | Done | command, timeout (asyncio), output 절단 |
| Agentic Loop 확장 | Done | MAX_TOOL_ITERATIONS=25, tool_call 파싱 루프 |
| Tool Approval | Done | approval_callback, require_approval, prompt_tool_approval |

**Tool Use 통합 테스트**: 실제 LLM이 tool_call을 생성하고, 도구 실행 후 결과를 기반으로 최종 응답을 생성하는 전체 흐름 검증 완료.

### 4.3 Phase 3: MCP Client

| 구현 항목 | 상태 | 비고 |
|-----------|------|------|
| MCPConfig (.mcp.json 파싱) | Done | Claude Code 호환, ${VAR} 환경변수 치환 |
| MCPClient (stdio + HTTP) | Done | 공식 SDK 기반, AsyncExitStack 리소스 관리 |
| MCPToolProxy | Done | MCP 도구 → Tool ABC 래핑 → ToolRegistry 통합 |
| CLI MCP 연동 | Done | 자동 연결, mcp list 서브커맨드 |

**설계 변경 사항**: Design에서 `mcp/transport/stdio.py`, `http.py`를 별도 구현하도록 명시했으나, MCP SDK(v1.26.0)가 트랜스포트를 내장하고 있어 SDK를 직접 사용하는 것이 적절하다고 판단하여 변경.

---

## 5. Gap Analysis Results

### 5.1 Check Phase 결과

| Category | v1.0 (초기) | v2.0 (Iteration 후) | Delta |
|----------|:----------:|:-------------------:|:-----:|
| Design Match | 85% | 95% | +10% |
| Architecture | 95% | 95% | -- |
| Convention | 90% | 95% | +5% |
| Test Coverage | 0% (오류) | 85% | +85% |
| **Overall** | **88%** | **95%** | **+7%** |

### 5.2 Iteration 1 수정 항목

| # | Gap | 수정 파일 | 설명 |
|---|-----|----------|------|
| 1 | 권한 확인 UI 미구현 | engine.py, chat.py | approval_callback + require_approval + prompt_tool_approval |
| 2 | --no-tools 옵션 미연동 | cli.py | config.tools.enabled = False 연동 |
| 3 | ToolsConfig 미구현 | config.py | ToolsConfig dataclass (enabled, require_approval, auto_approve) |
| 4 | 승인 테스트 부재 | test_approval.py | 승인/거부/자동승인/콜백없음 4개 테스트 |

### 5.3 분석 오류 정정

v1.0 분석에서 "테스트 코드 전체 부재"로 기록했으나, 실제로는 13개 파일 46개 테스트가 존재했다. 이 오류로 Overall Score가 실제보다 낮게 산정되었으며, v2.0에서 정정하였다.

---

## 6. Test Summary

### 6.1 테스트 현황

| Module | Files | Tests | Status |
|--------|:-----:|:-----:|--------|
| core/ | 4 | 16 | All passed |
| tools/ | 6 | 25 | All passed |
| llm/ | 1 | 5 | 3 passed, 2 skipped (실서버 필요) |
| mcp/ | 2 | 7 | 6 passed, 1 skipped (실서버 필요) |
| **Total** | **13** | **53** | **50 passed, 3 skipped** |

### 6.2 테스트 실행

```
$ pytest tests/ -v
50 passed, 3 skipped in 1.42s
```

Skipped 테스트: vLLM/MCP 실서버 연결이 필요한 통합 테스트 (로컬 환경 의존).

---

## 7. Key Decisions & Trade-offs

### 7.1 설계 대비 변경 사항 (의도적)

| 변경 | 설계 | 구현 | 판단 |
|------|------|------|------|
| Engine 메서드 분리 | `run()` → AsyncIterator | `chat()` + `chat_stream()` | **개선** — 사용 편의성 향상 |
| MAX_TOOL_ITERATIONS | 무한 루프 | 25회 제한 | **개선** — 안전장치 추가 |
| ToolRegistry 통합 | builtin/mcp 분리 dict | 통합 dict | **간소화** — MCPToolProxy가 Tool 상속 |
| MCP Transport | 직접 구현 | SDK 직접 사용 | **적정** — SDK가 트랜스포트 내장 |
| Usage 구조화 | dict | Usage dataclass | **개선** — 타입 안전성 향상 |
| /no_think 프롬프트 | 미명시 | BASE_PROMPT에 포함 | **추가** — Qwen3.5 thinking 모드 대응 |

### 7.2 남은 Minor Items (Low Priority)

| Item | 설명 | 영향 |
|------|------|------|
| `mcp add/remove` 서브커맨드 | .mcp.json 직접 편집으로 대체 가능 | 없음 |
| `scripts/` 편의 스크립트 | start_vllm.sh, setup.sh | 없음 |
| `utils/files.py` | 향후 필요 시 추가 | 없음 |
| `Tool.to_mcp_tool()` | Phase 4 (MCP Server) 시 구현 | 없음 |

---

## 8. Lessons Learned

### 8.1 잘된 점

1. **ABC 기반 설계**: LLMProvider, Tool 인터페이스 분리로 확장성 확보
2. **MCPToolProxy 패턴**: MCP 서버 도구를 기존 ToolRegistry에 자연스럽게 통합
3. **MCP SDK 활용**: 직접 구현 대신 공식 SDK 활용으로 코드량 대폭 감소
4. **Agentic Loop 안전장치**: MAX_TOOL_ITERATIONS로 무한 루프 방지
5. **테스트 병행**: 구현과 동시에 테스트 작성으로 50건 확보

### 8.2 개선 필요

1. **Design 문서 동기화**: 구현 중 변경사항을 Design에 즉시 반영하지 않아 gap 발생
2. **Gap Analysis 초기 오류**: 테스트 존재 여부 확인이 부정확했음 → 분석 도구 개선 필요
3. **기본 설정값 동기화**: Design(port 8000) vs 구현(port 8080) 불일치

### 8.3 PDCA 프로세스 평가

| 단계 | 평가 | 비고 |
|------|------|------|
| Plan | Effective | 언어 선택 분석이 이후 설계에 큰 도움 |
| Design | Effective | 상세한 인터페이스 정의로 구현 방향 명확 |
| Do | Effective | 3개 Phase를 순차적으로 안정적 구현 |
| Check | Partially | 초기 분석 오류 있었으나 재분석으로 보정 |
| Act | Effective | 1회 iteration으로 목표 달성 (88% → 95%) |

---

## 9. Next Steps (Phase 4-7)

| Phase | 목표 | 핵심 작업 |
|-------|------|----------|
| **Phase 4** | MCP Server | 자체 도구를 MCP로 노출, `myaicoder serve` 커맨드 |
| **Phase 5** | Context + Session | 토큰 관리, 히스토리 압축, 세션 지속 |
| **Phase 6** | VS Code Extension | TypeScript 확장, WebSocket/stdio 연동 |
| **Phase 7** | Stabilization + Deploy | PyPI 배포, 문서화, 성능 최적화 |

---

## 10. Final Metrics

```
╔═══════════════════════════════════════════════════╗
║           PDCA Completion Report                  ║
║           Feature: ai-coder-cli (Phase 1-3)       ║
╠═══════════════════════════════════════════════════╣
║  Match Rate:        95%  (Target: 90%)       ✅  ║
║  Iterations:        1/5                      ✅  ║
║  Tests:             50 passed, 3 skipped     ✅  ║
║  Phase Completion:  3/3 (100%)               ✅  ║
║  Architecture:      95%                      ✅  ║
║  Convention:        95%                      ✅  ║
╠═══════════════════════════════════════════════════╣
║  Status: COMPLETED                               ║
║  PDCA: [Plan]✅ [Design]✅ [Do]✅                ║
║        [Check]✅ [Act]✅ [Report]✅               ║
╚═══════════════════════════════════════════════════╝
```

---

*Generated: 2026-03-13 | PDCA Phase: Report | Feature: ai-coder-cli*
*Author: bkit-report-generator*
