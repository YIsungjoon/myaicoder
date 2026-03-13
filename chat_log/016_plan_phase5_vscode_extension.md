# 016. Plan Phase: VS Code Extension (Phase 5)

**날짜**: 2026-03-13
**작업 유형**: PDCA Plan
**Feature**: vscode-extension

## 작업 내용

Phase 5 VS Code Extension Plan 문서를 작성했다.

## 핵심 결정 사항

| 항목 | 결정 | 사유 |
|------|------|------|
| 프로젝트 위치 | `apps/vscode-extension/` | 모노레포 Turborepo 통합 |
| UI 방식 | Webview 기반 채팅 패널 | TreeView보다 자유도 높음, 마크다운 렌더링 용이 |
| MCP 연결 | stdio 트랜스포트 | `myaicoder serve` subprocess, 가장 안정적 |
| 번들러 | esbuild | VS Code 확장 공식 권장 |
| MCP SDK | `@modelcontextprotocol/sdk` | TypeScript Tier 1 SDK |
| 호환 대상 | VS Code 1.85+ 및 모든 포크 | Windsurf, Cursor 포함 |

## 기능 요구사항 (10개)

- P0: 채팅 패널, MCP 연결, 도구 결과 표시, 파일 연동
- P1: 인라인 Diff, 터미널 출력, 설정 UI, 상태 표시줄
- P2: Agentic 모드, 마켓플레이스 배포

## 산출물

- `docs/pdca/01-plan/features/vscode-extension.plan.md`

## PDCA 상태

```
Feature: vscode-extension
[Plan] ✅ → [Design] ⏳ → [Do] ⏳ → [Check] ⏳ → [Act] ⏳
```

## 다음 단계

- `/pdca design vscode-extension` — Design 문서 작성
