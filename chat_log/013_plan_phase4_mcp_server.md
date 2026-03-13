# 013. Plan Phase: MCP Server (Phase 4)

**날짜**: 2026-03-13
**작업 유형**: PDCA Plan
**Feature**: mcp-server

## 작업 내용

myAiCoder Phase 4 (MCP Server) Plan 문서를 작성했다.

## 핵심 결정사항

| 결정 | 선택 | 근거 |
|------|------|------|
| MCP 서버 프레임워크 | FastMCP | 공식 권장 고수준 API |
| 도구 등록 방식 | 동적 등록 | ToolRegistry 순회 → 자동 등록 |
| 기본 트랜스포트 | stdio | Claude Code/Cursor 표준 |
| Bash 도구 보안 | 기본 비활성 | --allow-bash로 명시적 활성화 |
| MCP 도구명 | 스네이크 케이스 | Read → read_file 등 |

## 구현 범위

1. `mcp/server.py` — FastMCP 기반 서버
2. `Tool.to_mcp_tool()` 메서드 추가
3. ToolRegistry → FastMCP 동적 등록
4. `myaicoder serve` CLI 커맨드
5. stdio/HTTP 트랜스포트 옵션
6. 보안 옵션 (--allow-bash, --working-dir)
7. `tests/test_mcp/test_server.py`
8. Claude Code 호환 테스트

## PDCA 상태

```
Feature: mcp-server
[Plan] ✅ → [Design] ⏳ → [Do] ⏳ → [Check] ⏳ → [Act] ⏳
```

## 다음 단계

- `/pdca design mcp-server` — Design 문서 작성
