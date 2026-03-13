# Plan: VS Code Extension (Phase 5)

**Feature**: vscode-extension
**날짜**: 2026-03-13
**Phase**: Plan
**Level**: Enterprise
**Parent Feature**: ai-coder-cli (Phase 5 / M5)

---

## 1. 개요

myAiCoder를 VS Code에서 직접 사용할 수 있는 확장 프로그램을 개발한다.
기존 `myaicoder serve` MCP 서버(Phase 4)를 stdio로 연결하여, 에디터 내에서 AI 코딩 어시스턴트를 제공한다.
VS Code Extension API 기반으로 개발하여 VS Code, Windsurf, Cursor 등 모든 VS Code 포크에서 동작한다.

## 2. 핵심 요구사항

### 2.1 기능 요구사항

| ID | 기능 | 설명 | 우선순위 |
|----|------|------|----------|
| FR-01 | **채팅 패널** | 사이드바에 AI 채팅 UI (메시지 입력 + 응답 표시) | P0 |
| FR-02 | **MCP 연결** | `myaicoder serve` 프로세스를 stdio로 자동 시작/연결 | P0 |
| FR-03 | **도구 결과 표시** | 파일 읽기/편집/검색 등 도구 실행 결과를 UI에 표시 | P0 |
| FR-04 | **파일 연동** | 활성 에디터 파일 경로를 컨텍스트로 전달 | P0 |
| FR-05 | **인라인 Diff** | Edit 도구 실행 시 변경 사항을 에디터에 diff로 표시 | P1 |
| FR-06 | **터미널 출력** | Bash 도구 실행 결과를 통합 터미널에 표시 | P1 |
| FR-07 | **설정 UI** | LLM URL, 모델명, MCP 서버 경로 등 설정 | P1 |
| FR-08 | **상태 표시줄** | 연결 상태, 모델명, 토큰 사용량 표시 | P1 |
| FR-09 | **Agentic 모드** | `agentic_task` 호출로 복합 작업 위임 | P2 |
| FR-10 | **마켓플레이스 배포** | VS Code Marketplace에 게시 | P2 |

### 2.2 비기능 요구사항

| ID | 항목 | 기준 |
|----|------|------|
| NFR-01 | 시작 속도 | 확장 활성화 < 1초 |
| NFR-02 | 메모리 | 확장 자체 메모리 < 50MB |
| NFR-03 | 호환성 | VS Code 1.85+, Windsurf, Cursor |
| NFR-04 | 독립성 | Python 백엔드(myaicoder) 설치 전제, 확장은 TypeScript 단독 |
| NFR-05 | 오프라인 | 로컬 LLM 전용, 인터넷 연결 불필요 |

## 3. 기술 분석

### 3.1 아키텍처

```
┌──────────────────────────────────────────────────────────┐
│  VS Code                                                   │
│                                                            │
│  ┌────────────────────────────────────────────────────┐   │
│  │  myAiCoder Extension (TypeScript)                    │   │
│  │                                                      │   │
│  │  ┌──────────────┐  ┌────────────────────────────┐  │   │
│  │  │  Chat Panel   │  │  Extension Host             │  │   │
│  │  │  (Webview)    │  │                              │  │   │
│  │  │  - 메시지 목록 │  │  - MCP Client (stdio)       │  │   │
│  │  │  - 입력창      │  │  - 프로세스 관리             │  │   │
│  │  │  - 도구 결과   │  │  - VS Code API 연동         │  │   │
│  │  │  - Diff 표시   │  │  - 설정 관리                 │  │   │
│  │  └──────────────┘  └─────────┬──────────────────┘  │   │
│  └──────────────────────────────┼─────────────────────┘   │
│                                  │ stdio (JSON-RPC 2.0)    │
│                                  ▼                         │
│  ┌──────────────────────────────────────────────────────┐ │
│  │  myaicoder serve (Python subprocess)                  │ │
│  │  ├── 6 built-in tools (read/write/edit/glob/grep/bash)│ │
│  │  ├── agentic_task (optional)                          │ │
│  │  └── MCP Client → Revit/CAD MCP (optional)           │ │
│  └──────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

### 3.2 기술 스택

| 영역 | 기술 | 비고 |
|------|------|------|
| 확장 호스트 | TypeScript + VS Code Extension API | VS Code 표준 |
| 채팅 UI | Webview (HTML/CSS/JS) | 경량, 커스텀 UI 자유도 |
| MCP 통신 | `@modelcontextprotocol/sdk` | 공식 MCP TypeScript SDK |
| 프로세스 관리 | Node.js `child_process` | `myaicoder serve` 관리 |
| 빌드 | esbuild | VS Code 확장 표준 번들러 |
| 패키지 매니저 | pnpm | 모노레포 통합 |

### 3.3 MCP 연결 방식

```
Extension Host                    myaicoder serve
     │                                  │
     │──── initialize ─────────────────▶│
     │◀─── capabilities ───────────────│
     │                                  │
     │──── tools/list ─────────────────▶│
     │◀─── [read_file, write_file, ...]│
     │                                  │
     │──── tools/call (read_file) ─────▶│
     │◀─── {content: "file contents"}──│
     │                                  │
```

- **stdio 트랜스포트** 기본 (로컬 프로세스)
- `child_process.spawn('myaicoder', ['serve', '--allow-bash'])`
- MCP SDK의 `StdioClientTransport` 사용

### 3.4 Webview 채팅 UI 설계

| 컴포넌트 | 역할 |
|----------|------|
| MessageList | 사용자/AI 메시지 목록 (마크다운 렌더링) |
| ToolResultCard | 도구 실행 결과 표시 (접을 수 있는 카드) |
| InputArea | 텍스트 입력 + 전송 버튼 |
| StatusBar | 연결 상태, 모델명 |

Webview ↔ Extension Host 통신: `postMessage()` / `onDidReceiveMessage()`

## 4. 프로젝트 구조

```
apps/vscode-extension/
├── package.json              # VS Code 확장 manifest
├── tsconfig.json
├── esbuild.config.mjs        # 번들러 설정
├── src/
│   ├── extension.ts          # activate/deactivate 진입점
│   ├── mcp/
│   │   ├── client.ts         # MCP 클라이언트 (stdio)
│   │   └── process.ts        # myaicoder serve 프로세스 관리
│   ├── chat/
│   │   ├── panel.ts          # Webview 패널 관리
│   │   └── messages.ts       # 메시지 타입 정의
│   ├── editor/
│   │   ├── diff.ts           # 인라인 Diff 표시
│   │   └── context.ts        # 활성 파일 컨텍스트
│   └── config.ts             # 확장 설정 관리
├── webview/
│   ├── index.html            # 채팅 UI
│   ├── style.css
│   └── main.js               # Webview 스크립트
├── media/
│   └── icon.png              # 확장 아이콘
└── test/
    └── extension.test.ts
```

## 5. Claude Code와의 차별점

| 항목 | Claude Code | myAiCoder VS Code |
|------|------------|-------------------|
| LLM | Claude API (유료) | 로컬 LLM (무료) |
| 실행 환경 | 터미널 CLI | VS Code 내장 |
| AEC 지원 | 없음 | Revit/CAD MCP 통합 |
| 오프라인 | 불가 | 완전 오프라인 |
| 커스텀 도구 | MCP 서버 추가 | MCP 서버 추가 + agentic_task |

## 6. 기술적 사각지대 및 리스크 (Blind Spots)

### 6.1 myaicoder 바이너리 경로 탐색

사용자 환경에 따라 `myaicoder` 명령어 경로가 다를 수 있다.

| 환경 | 경로 | 대응 |
|------|------|------|
| pip install | `~/.local/bin/myaicoder` | PATH에 포함 가정 |
| venv 내부 | `.venv/bin/myaicoder` | 워크스페이스 venv 자동 탐색 |
| 직접 지정 | 사용자 설정 | `myaicoder.executablePath` 설정 제공 |

**완화 전략**: 설정의 `myaicoder.executablePath`에서 우선 탐색 → `which myaicoder` → 워크스페이스 `.venv/bin/myaicoder` 순서로 탐색.

### 6.2 프로세스 생명주기

`myaicoder serve` 프로세스가 비정상 종료 시 확장이 멈출 수 있다.

| 상황 | 대응 |
|------|------|
| 프로세스 크래시 | 자동 재시작 (최대 3회) |
| 초기화 타임아웃 | 10초 타임아웃 → 에러 메시지 |
| VS Code 종료 | `deactivate()`에서 프로세스 kill |
| LLM 서버 미실행 | Direct Pass-through 도구만 사용 가능, 경고 표시 |

### 6.3 Webview 보안

VS Code Webview는 샌드박스 환경이지만, CSP(Content Security Policy) 설정 필요.

- `script-src`: 인라인 nonce 기반만 허용
- `style-src`: 확장 리소스만 허용
- 외부 리소스 로딩 불가 (오프라인 호환)

### 6.4 대량 도구 결과 렌더링

BIM 데이터 등 대량 결과가 Webview에 전달되면 렌더링 성능 저하.

**완화 전략**: 서버 측 `max_result_tokens=4000` 축약 + Webview에서 1000줄 초과 시 가상 스크롤 적용.

## 7. 구현 범위

### 7.1 Phase 5 범위 (In Scope)

| # | 항목 | 우선순위 |
|---|------|----------|
| 1 | VS Code 확장 프로젝트 스캐폴딩 (`apps/vscode-extension/`) | P0 |
| 2 | MCP Client (stdio) — `myaicoder serve` 연결 | P0 |
| 3 | 프로세스 관리 (spawn, kill, 재시작) | P0 |
| 4 | 채팅 Webview UI (메시지 입출력) | P0 |
| 5 | 도구 결과 카드 표시 (ToolResultCard) | P0 |
| 6 | 활성 파일 컨텍스트 전달 | P0 |
| 7 | 확장 설정 (`myaicoder.executablePath`, `myaicoder.llmUrl` 등) | P1 |
| 8 | 상태 표시줄 (연결 상태, 모델명) | P1 |
| 9 | 인라인 Diff 표시 (Edit 도구 결과) | P1 |
| 10 | 터미널 연동 (Bash 도구 결과) | P1 |
| 11 | 기본 단위 테스트 | P0 |
| 12 | 마크다운 렌더링 (AI 응답) | P0 |

### 7.2 Phase 5 범위 외 (Out of Scope)

| 항목 | 사유 |
|------|------|
| Marketplace 배포 | P2, 안정화 후 |
| 코드 자동 완성 (Copilot 스타일) | 별도 Feature |
| JetBrains 플러그인 | 별도 PDCA |
| 멀티 세션 관리 | Phase 6+ |
| 파일 트리 커스텀 뷰 | Phase 6+ |

## 8. 마일스톤

| Step | 작업 | 산출물 |
|------|------|--------|
| 1 | 프로젝트 스캐폴딩 + package.json | `apps/vscode-extension/` |
| 2 | Extension 진입점 (activate/deactivate) | `src/extension.ts` |
| 3 | MCP Client (stdio 연결) | `src/mcp/client.ts` |
| 4 | 프로세스 관리 (spawn/kill/restart) | `src/mcp/process.ts` |
| 5 | Webview 채팅 패널 (기본 UI) | `src/chat/panel.ts` + `webview/` |
| 6 | 메시지 송수신 (Webview ↔ Host) | `src/chat/messages.ts` |
| 7 | MCP tools/call 연동 (채팅 → 도구 호출) | `src/mcp/client.ts` |
| 8 | 도구 결과 카드 렌더링 | `webview/` |
| 9 | 활성 파일 컨텍스트 | `src/editor/context.ts` |
| 10 | 설정 UI + 상태 표시줄 | `src/config.ts` |
| 11 | 인라인 Diff + 터미널 연동 | `src/editor/diff.ts` |
| 12 | 단위 테스트 + 통합 테스트 | `test/` |

## 9. 결정 사항

- [x] **프로젝트 위치**: `apps/vscode-extension/` (모노레포 내) (2026-03-13)
  - Turborepo + pnpm 워크스페이스 통합
- [x] **UI 방식**: Webview 기반 채팅 패널 (2026-03-13)
  - VS Code 네이티브 TreeView보다 자유도 높음, 마크다운 렌더링 용이
- [x] **MCP 연결**: stdio 트랜스포트 (2026-03-13)
  - `myaicoder serve`를 subprocess로 실행, 가장 안정적
- [x] **번들러**: esbuild (2026-03-13)
  - VS Code 확장 공식 권장, 빠른 빌드
- [x] **MCP SDK**: `@modelcontextprotocol/sdk` (2026-03-13)
  - 공식 TypeScript Tier 1 SDK
- [x] **호환 대상**: VS Code 1.85+ 및 모든 VS Code 포크 (2026-03-13)
  - Windsurf, Cursor 등 포함

---

*작성일: 2026-03-13 | Phase: Plan | Status: All Decisions Made*
*Parent: ai-coder-cli Phase 5 (M5)*
