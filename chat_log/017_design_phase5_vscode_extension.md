# 017. Design Phase: VS Code Extension (Phase 5)

**날짜**: 2026-03-13
**작업 유형**: PDCA Design
**Feature**: vscode-extension

## 작업 내용

Plan 문서 기반으로 VS Code Extension Design 문서를 작성했다.

## 설계 핵심 구조

### 모듈 구조 (6개 핵심 클래스)

| 클래스 | 파일 | 역할 |
|--------|------|------|
| ConfigManager | `src/config.ts` | 설정 관리, 실행 경로 탐색 |
| ProcessManager | `src/mcp/process.ts` | myaicoder serve 프로세스 관리 |
| McpClientManager | `src/mcp/client.ts` | MCP stdio 클라이언트 |
| ChatPanelProvider | `src/chat/panel.ts` | Webview 채팅 UI |
| EditorContext | `src/editor/context.ts` | 활성 파일 컨텍스트 |
| StatusBarManager | `src/ui/statusbar.ts` | 상태 표시줄 |

### 인터페이스 코드

- package.json (VS Code manifest + contributes)
- extension.ts (activate/deactivate)
- ProcessManager (spawn/kill/restart, 크래시 자동 재시작 3회)
- McpClientManager (StdioClientTransport, tools/list, tools/call)
- ChatPanelProvider (Webview HTML + CSP nonce)
- EditorContext (활성 파일 + 선택 영역)
- DiffManager (인라인 diff 표시)
- StatusBarManager (연결 상태, 모델명, 토큰)
- Webview CSS (VS Code 테마 변수 통합)
- Webview JS (마크다운 렌더링, 도구 결과 카드)

### 구현 순서 (16 Steps)

1-5: 스캐폴딩, 진입점, 설정, 프로세스, MCP 클라이언트
6-10: Webview UI, 메시지 송수신, 도구 호출 연동
11-14: 에디터 통합, 상태바, Diff, 마크다운
15-16: 테스트

## 산출물

- `docs/pdca/02-design/features/vscode-extension.design.md`

## PDCA 상태

```
Feature: vscode-extension
[Plan] ✅ → [Design] ✅ → [Do] ⏳ → [Check] ⏳ → [Act] ⏳
```

## 다음 단계

- `/pdca do vscode-extension` — 구현 시작
