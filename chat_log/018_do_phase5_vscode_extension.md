# 018. Do Phase: VS Code Extension (Phase 5)

**날짜**: 2026-03-13
**작업 유형**: PDCA Do
**Feature**: vscode-extension

## 작업 내용

Design 문서 기반 16단계 구현을 완료했다.

## 설계 대비 변경 사항

### StdioClientTransport API 차이

Design 문서에서는 `ProcessManager`가 별도로 `myaicoder serve`를 spawn하고, MCP SDK의 `StdioClientTransport`에 `reader`/`writer`로 연결하는 구조를 설계했으나:

- **실제 SDK API**: `StdioClientTransport`는 `{command, args, cwd, stderr}` 형태로 자체적으로 프로세스를 spawn
- **적용**: `ProcessManager`를 유틸리티 모듈로 축소, `McpClientManager`가 transport 생성 시 프로세스도 관리
- **장점**: 프로세스 생명주기가 transport와 동기화되어 더 안정적

## 변경 파일

| 파일 | 변경 유형 | 내용 |
|------|-----------|------|
| `package.json` | **신규** | VS Code 확장 manifest, 의존성, 설정 |
| `tsconfig.json` | **신규** | TypeScript 설정 |
| `esbuild.config.mjs` | **신규** | esbuild 번들러 설정 |
| `.vscodeignore` | **신규** | 패키징 제외 파일 |
| `src/extension.ts` | **신규** | activate/deactivate 진입점 |
| `src/config.ts` | **신규** | ConfigManager (설정, 경로 탐색) |
| `src/mcp/client.ts` | **신규** | McpClientManager (MCP stdio 클라이언트) |
| `src/mcp/process.ts` | **신규** | buildServeArgs 유틸리티 |
| `src/chat/panel.ts` | **신규** | ChatPanelProvider (Webview 채팅 UI) |
| `src/chat/types.ts` | **신규** | 메시지 타입 정의 |
| `src/editor/context.ts` | **신규** | EditorContext (활성 파일 컨텍스트) |
| `src/editor/diff.ts` | **신규** | DiffManager (인라인 Diff 표시) |
| `src/ui/statusbar.ts` | **신규** | StatusBarManager (연결 상태, 모델명) |
| `webview/style.css` | **신규** | VS Code 테마 통합 스타일 |
| `webview/main.js` | **신규** | Webview 스크립트 (마크다운 렌더링, 도구 카드) |
| `webview/index.html` | **신규** | 채팅 UI HTML 템플릿 |
| `vitest.config.ts` | **신규** | Vitest 테스트 설정 |
| `test/unit/config.test.ts` | **신규** | ConfigManager 테스트 (3개) |
| `test/unit/process.test.ts` | **신규** | buildServeArgs 테스트 (6개) |
| `test/unit/client.test.ts` | **신규** | McpClientManager 테스트 (4개) |

## 빌드 결과

```
TypeScript: 0 errors
esbuild: Build complete (dist/extension.js)
```

## 테스트 결과

```
13 passed, 0 failed (538ms)
- config.test.ts: 3 passed
- process.test.ts: 6 passed
- client.test.ts: 4 passed
```

## PDCA 상태

```
Feature: vscode-extension
[Plan] ✅ → [Design] ✅ → [Do] ✅ → [Check] ⏳ → [Act] ⏳
```

## 다음 단계

- `/pdca analyze vscode-extension` — Gap Analysis (Check)
