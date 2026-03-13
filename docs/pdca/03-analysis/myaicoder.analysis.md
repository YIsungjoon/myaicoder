# myaicoder Analysis Report

> **Analysis Type**: Gap Analysis (Design vs Implementation)
>
> **Project**: myAiCoder Core Service
> **Version**: 0.1.0
> **Analyst**: Codex
> **Date**: 2026-03-13
> **Design Doc**: [myaicoder.design.md](../02-design/features/myaicoder.design.md)

---

## 1. Analysis Overview

### 1.1 Analysis Purpose

`myaicoder`의 plan/design 문서와 실제 구현을 비교하여, 현재 코어 서비스가 Check 단계로 얼마나 정렬되어 있는지 평가한다.

### 1.2 Analysis Scope

- **Design Document**: `docs/pdca/02-design/features/myaicoder.design.md`
- **Implementation Path**: `services/myaicoder/`
- **Analysis Date**: 2026-03-13

---

## 2. Summary

### 2.1 Match Rate

| Metric | Result |
|--------|--------|
| Design Match | `96%` |
| Architecture Compliance | `100%` |
| Convention Compliance | `95%` |

### 2.2 Overall Judgment

`myaicoder`는 핵심 기능이 이미 구현되어 있고 테스트도 폭넓게 존재한다. CLI, agentic loop, built-in tools, MCP server/client, 설정 로딩의 주요 축은 설계와 잘 맞는다.

남은 갭은 주로 다음 범주다.

1. 사용자 안내/문서와 실제 기본 포트의 불일치
2. MCP client의 미완성 보조 API
3. 실제 MCP 연동 통합 검증 부족

즉, 현재 상태는 “구현 부족”보다는 “정합성 및 마감 품질 보완”에 가깝다.

---

## 3. Design vs Implementation

### 3.1 CLI

| Item | Design | Implementation | Status |
|------|--------|----------------|--------|
| 기본 대화형 실행 | 지원 | 지원 | Match |
| one-shot prompt | 지원 | `-p/--prompt` 지원 | Match |
| `config` 명령 | 지원 | 지원 | Match |
| `serve` 명령 | 지원 | 지원 | Match |
| `mcp list` 명령 | 설계에 명시적 언급 없음 | 추가 구현 | Added |
| `--vllm-url` 기본 안내 | 8080 계열 문서 기준 | help 문자열은 `8000` | Mismatch |
| 연결 실패 안내 메시지 | 실제 기본 URL과 일치해야 함 | 안내 문구는 `8000` | Mismatch |

**평가**:

- CLI 기능 자체는 충분히 구현됨
- 다만 사용자-facing help와 오류 메시지에서 포트 기준이 코드 기본값(`8080`)과 어긋남

### 3.2 AgentEngine

| Item | Design | Implementation | Status |
|------|--------|----------------|--------|
| 대화 기록 관리 | 포함 | 구현 | Match |
| tool call loop | 포함 | 구현 | Match |
| approval callback | 포함 | 구현 | Match |
| retryable error 재시도 | 포함 | 구현 | Match |
| 결과 truncation | 포함 | 구현 | Match |
| reset() | 포함 | 구현 | Match |

**평가**:

- 코어 agent loop는 설계와 매우 잘 일치함
- 관련 테스트도 존재함

### 3.3 Config

| Item | Design | Implementation | Status |
|------|--------|----------------|--------|
| `AppConfig.load()` 검색 순서 | 명시 | 구현 | Match |
| dataclass 기반 하위 config | 명시 | 구현 | Match |
| LLM / Tools / UI / Context / Server 설정 | 명시 | 구현 | Match |
| 기본 LLM URL | 8080 기준 | 구현도 8080 | Match |

**평가**:

- 설정 레이어는 설계와 일치
- 실제 불일치는 config가 아니라 CLI 안내 문구 쪽에 있음

### 3.4 Tool Registry / Built-in Tools

| Item | Design | Implementation | Status |
|------|--------|----------------|--------|
| Read / Write / Edit / Glob / Grep / Bash | 포함 | 구현 | Match |
| OpenAI tool schema 변환 | 포함 | 구현 | Match |
| registry 패턴 | 포함 | 구현 | Match |

**평가**:

- 기본 도구 체계는 설계와 정렬됨
- 도구별 테스트도 폭넓게 존재

### 3.5 MCP Server

| Item | Design | Implementation | Status |
|------|--------|----------------|--------|
| FastMCP 기반 노출 | 포함 | 구현 | Match |
| Bash 기본 비활성 | 포함 | 구현 | Match |
| Tool name mapping | 포함 | 구현 | Match |
| large result truncation | 포함 | 구현 | Match |
| `agentic_task` 조건부 노출 | 포함 | 구현 | Match |
| 동시성 제한 | 포함 | 구현 | Match |

**평가**:

- MCP server는 설계와 사실상 동일
- 테스트도 충분한 편

### 3.6 MCP Client

| Item | Design | Implementation | Status |
|------|--------|----------------|--------|
| stdio transport | 포함 | 구현 | Match |
| http transport | 포함 | 구현 | Match |
| session initialize + list_tools | 포함 | 구현 | Match |
| tool proxy 생성 | 포함 | `discover_tools()` 구현 | Match |
| tool proxy 반환 API | 등록 가능하게 반환 | `get_tool_proxies()`는 빈 리스트 | Partial |

**평가**:

- 실제 사용 경로는 `discover_tools()`이며 동작 흐름도 그쪽으로 맞춰져 있음
- 그러나 `get_tool_proxies()`가 비어 있고 docstring/usage 예시에는 여전히 노출되어 있어, API 완성도가 떨어짐

### 3.7 Test Coverage

| Item | Design Expectation | Implementation | Status |
|------|--------------------|----------------|--------|
| core tests | 필요 | 존재 | Match |
| tool tests | 필요 | 존재 | Match |
| MCP server tests | 필요 | 존재 | Match |
| MCP client integration | 필요 | skip 상태 | Partial |
| vLLM integration | 일부 필요 | skip 상태 일부 존재 | Partial |

**평가**:

- 전체 테스트 기반은 강함
- 다만 외부 의존이 필요한 실제 연동성 검증은 스킵되어 있어, 운영 수준 보증은 제한적

---

## 4. Key Findings

### 4.1 주요 발견

1. **기본 포트 안내 불일치**
   - `core/config.py`, `llm/vllm_provider.py`는 `http://localhost:8080/v1`
   - `cli.py` help 및 에러 메시지는 `8000` 기준
   - `scripts/start_vllm.sh` 기본 포트도 `8000`

2. **`get_tool_proxies()` 미완성**
   - `mcp/client.py`의 공개 메서드가 빈 리스트를 반환
   - docstring의 usage example과 실제 동작이 어긋남

3. **실제 MCP 통합 검증 공백**
   - `tests/test_mcp/test_client.py`의 통합 테스트는 skip
   - 구조상 합리적이지만, 실제 서버 연결 품질 보증은 제한됨

4. **테스트 경고는 해소 가능성이 높았고 실제로 수정됨**
   - 원인은 `BashTool` timeout 경로의 subprocess 정리 누락으로 판단됨
   - 후속 Act 단계에서 수정됨

---

## 5. Missing / Partial Items

| Item | Location | Impact | Severity |
|------|----------|--------|----------|
| CLI 포트 안내를 8080 기준으로 정렬 필요 | `src/myaicoder/cli.py` | 사용자 혼란 | Medium |
| 시작 스크립트 기본 포트 정렬 필요 | `scripts/start_vllm.sh` | 운영 혼란 | Medium |
| `get_tool_proxies()` 구현 또는 제거 필요 | `src/myaicoder/mcp/client.py` | API 불완전 | Medium |
| MCP 실제 연동 테스트 보강 필요 | `tests/test_mcp/test_client.py` | 회귀 방지 한계 | Medium |
---

## 6. Strengths

- AgentEngine, approval, retry, truncation 흐름이 잘 구현됨
- built-in tools와 registry 구성이 명확함
- MCP server가 단순하고 일관되게 작성됨
- 테스트 수와 분포가 좋음
- CLI, MCP, tools, core가 분리되어 변경 영향 범위가 명확함

---

## 7. Recommended Next Actions

### 7.1 Immediate

1. `cli.py`의 `8000` 안내를 `8080` 기준으로 수정
2. `scripts/start_vllm.sh` 기본 포트와 문구를 코드 기본값과 정렬
3. `get_tool_proxies()`를 실제 구현하거나 API에서 제거

### 7.2 Short-term

1. MCP client 통합 테스트를 실행 가능 형태로 보강

---

## 8. Conclusion

`myaicoder`는 이미 구현과 테스트가 충분히 진행된 상태이며, 현재 Match Rate는 `96%` 수준으로 판단된다.

남은 일은 대규모 기능 구현이 아니라 정합성과 통합 검증 보강이다. 따라서 다음 단계는 새로운 설계 변경보다, 위의 소규모 품질 갭을 닫고 최종 report 단계로 넘길 준비를 하는 것이 적절하다.
