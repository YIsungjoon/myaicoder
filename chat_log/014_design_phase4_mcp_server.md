# 014. Design Phase: MCP Server (Phase 4)

**날짜**: 2026-03-13
**작업 유형**: PDCA Design
**Feature**: mcp-server

## 작업 내용

myAiCoder Phase 4 (MCP Server) Design 문서를 작성했다.

## 핵심 설계 결정

| 항목 | 설계 | 근거 |
|------|------|------|
| MCPServer 클래스 | FastMCP 래핑 | 동적 도구 등록 + 옵션 관리 |
| 도구명 매핑 | TOOL_NAME_MAP 딕셔너리 | Read→read_file 등 스네이크 케이스 변환 |
| 결과 절단 | _truncate_result(max_tokens=4000) | BIM 데이터 컨텍스트 오버플로 방지 |
| 에러 재시도 | retryable/non-retryable 분류 | 파라미터/데이터 에러만 재시도 (최대 2회) |
| 동시성 제어 | asyncio.Semaphore(max_concurrent) | llama-server 단일 슬롯 보호 |
| 라우팅 | Direct Pass-through vs Agentic | 단순 도구→직접 실행, 복합 작업→LLM 경유 |
| CLI 커맨드 | `myaicoder serve` | --transport, --port, --allow-bash, --agentic 옵션 |
| 설정 관리 | ServerConfig dataclass | config.py에 추가 |

## 주요 컴포넌트

1. `mcp/server.py` — MCPServer 클래스 (FastMCP 래핑, 동적 등록, 결과 절단)
2. `tools/base.py` — Tool.to_mcp_tool() 메서드 추가
3. `core/engine.py` — _is_retryable_error(), _truncate_tool_result() 추가
4. `core/config.py` — ServerConfig dataclass 추가
5. `cli.py` — serve 커맨드 추가
6. `tests/test_mcp/test_server.py` — 12개 단위 테스트

## 구현 순서 (14단계)

1. ServerConfig → 2. Tool.to_mcp_tool() → 3. TOOL_NAME_MAP →
4. MCPServer 기본 → 5. 동적 등록 → 6. 결과 절단 → 7. 에러 재시도 →
8. 동시성 제어 → 9. agentic_task → 10. serve CLI →
11. 단위 테스트 → 12. 통합 테스트 → 13. Claude Code 호환 → 14. 문서화

## PDCA 상태

```
Feature: mcp-server
[Plan] ✅ → [Design] ✅ → [Do] ⏳ → [Check] ⏳ → [Act] ⏳
```

## 다음 단계

- `/pdca do mcp-server` — 구현 시작
