# Plan: VS Code Extension 사용성 개선

**Feature**: vscode-ux-improvement
**날짜**: 2026-03-16
**Phase**: Plan
**Level**: Enterprise
**Parent Feature**: vscode-extension

---

## 1. 개요

VS Code Extension의 두 가지 사용성 문제를 해결한다:
1. Activity Bar에서 myAiCoder 아이콘이 사라지는 문제
2. MCP 연결 상태를 확인/진단할 방법이 없는 문제

현재 Extension은 최초 실행 시 채팅 패널을 Secondary Side Bar로 자동 이동하며, 이 과정에서 원래 Activity Bar의 뷰 컨테이너가 비어 VS Code가 아이콘을 숨긴다. 또한 MCP 연결이 실패해도 Status Bar의 간단한 텍스트 외에 진단 정보를 확인할 수 없다.

## 2. 현재 상태 분석

### 2.1 문제 1: Activity Bar 아이콘 사라짐

**원인 코드**: `extension.ts:80-97`
```typescript
// 최초 실행 시 Secondary Side Bar로 자동 이동
const hasMovedKey = 'myaicoder.movedToSecondarySidebar';
if (!context.globalState.get<boolean>(hasMovedKey)) {
  setTimeout(async () => {
    await vscode.commands.executeCommand('myaicoder.chatPanel.focus');
    await vscode.commands.executeCommand('workbench.action.moveViewToSecondarySideBar');
    await context.globalState.update(hasMovedKey, true);
  }, 1500);
}
```

**문제 메커니즘**:
- `viewsContainers.activitybar`에 "myaicoder" 컨테이너 등록 (package.json:39-45)
- 이 컨테이너 안에 "myaicoder.chatPanel" 뷰 1개만 존재 (package.json:48-54)
- 채팅 패널이 Secondary Side Bar로 이동되면 컨테이너가 비어 VS Code가 아이콘 숨김
- 한번 이동하면 `globalState`에 기록되어 다시 돌아오지 않음

### 2.2 문제 2: MCP 연결 진단 불가

**현재 상태**:
- Status Bar에 "✅ myAiCoder: qwen3.5-27b (10 tools)" 또는 "⚠ myAiCoder: Disconnected" 표시
- 연결 실패 시 에러 메시지 1회 표시 후 사라짐
- MCP 서버 PID, 연결된 도구 목록, LLM URL 등 확인 불가
- VS Code 네이티브 MCP 설정(`mcp` section in settings.json)과 무관하게 자체 연결만 사용

## 3. 핵심 요구사항

### 3.1 기능 요구사항

| ID | 기능 | 설명 | 우선순위 |
|----|------|------|----------|
| FR-01 | **Activity Bar 아이콘 항상 표시** | 자동 이동 로직 제거, MCP Status TreeView를 Activity Bar에 상시 유지 | P0 |
| FR-02 | **MCP Status TreeView** | Activity Bar 사이드바에 연결 상태, 도구 목록, 서버 정보 표시 (TreeDataProvider) | P0 |
| FR-03 | **MCP 진단 커맨드** | `myAiCoder: Show MCP Diagnostics` 커맨드로 상세 진단 정보 표시 | P0 |
| FR-04 | **연결 테스트 버튼** | TreeView에서 클릭으로 MCP ping/reconnect 실행 | P1 |
| FR-05 | **Welcome View** | MCP 미연결 시 가이드 메시지 + 연결 버튼 표시 (viewsWelcome) | P1 |
| FR-06 | **Output Channel 로깅** | MCP 통신 로그를 VS Code Output 패널에 기록 | P1 |

### 3.2 비기능 요구사항

| ID | 항목 | 기준 |
|----|------|------|
| NFR-01 | 호환성 | 기존 채팅 기능 100% 유지 |
| NFR-02 | 성능 | TreeView 갱신 < 100ms |
| NFR-03 | 메모리 | 추가 메모리 < 5MB |

## 4. 기술 설계 방향

### 4.1 Activity Bar 아이콘 유지 전략

**해결 방법**: Activity Bar 컨테이너에 2개 뷰 배치
- `myaicoder.mcpStatus` — TreeDataProvider (항상 Activity Bar에 유지)
- `myaicoder.chatPanel` — Webview (사용자가 원하는 위치로 이동 가능)

```jsonc
// package.json 변경
"views": {
  "myaicoder": [
    {
      "id": "myaicoder.mcpStatus",
      "name": "MCP Status",
      "type": "tree"
    },
    {
      "type": "webview",
      "id": "myaicoder.chatPanel",
      "name": "Chat"
    }
  ]
}
```

Activity Bar 아이콘은 컨테이너에 뷰가 1개라도 남아있으면 표시된다. 사용자가 chatPanel을 이동해도 mcpStatus가 남아 아이콘이 유지된다.

### 4.2 MCP Status TreeView 구조

```
📡 MCP Status
├── 🟢 Connected (PID: 12345)      또는  🔴 Disconnected
├── 🌐 LLM: http://dgx:8080
├── 🤖 Model: qwen3.5-27b
└── 🔧 Tools (10)
    ├── read_file
    ├── write_file
    ├── edit_file
    ├── glob_search
    ├── grep_search
    ├── run_command
    ├── build_run
    ├── web_fetch
    ├── list_dir
    └── agentic_task
```

### 4.3 Welcome View (미연결 시)

```jsonc
// package.json
"viewsWelcome": [
  {
    "view": "myaicoder.mcpStatus",
    "contents": "myAiCoder MCP 서버에 연결되지 않았습니다.\n\n[Connect MCP Server](command:myaicoder.reconnect)\n\nmyaicoder가 설치되어 있는지 확인하세요.\n[Show Diagnostics](command:myaicoder.showMcpDiagnostics)",
    "when": "!myaicoder.connected"
  }
]
```

### 4.4 MCP 진단 커맨드

`myAiCoder: Show MCP Diagnostics` 커맨드 실행 시 Output Channel에 다음 정보 출력:
- 연결 상태 (Connected/Disconnected)
- 서버 PID
- LLM URL, Model Name
- API Key 설정 여부
- 도구 목록 및 개수
- myaicoder 실행 파일 경로
- 워크스페이스 경로

### 4.5 Output Channel 로깅

```typescript
const outputChannel = vscode.window.createOutputChannel('myAiCoder MCP');
// MCP 연결/해제/에러 이벤트 로깅
```

## 5. 구현 범위

### 5.1 In Scope

| # | 항목 | 파일 | 우선순위 |
|---|------|------|----------|
| 1 | 자동 이동 로직 제거 | `src/extension.ts` | P0 |
| 2 | MCP Status TreeView 구현 | `src/ui/mcp-status.ts` (신규) | P0 |
| 3 | package.json에 mcpStatus 뷰 등록 | `package.json` | P0 |
| 4 | MCP 진단 커맨드 등록 | `src/extension.ts`, `package.json` | P0 |
| 5 | Welcome View 등록 (미연결 시) | `package.json` | P1 |
| 6 | Output Channel MCP 로깅 | `src/mcp/client.ts` | P1 |
| 7 | context key 설정 (`myaicoder.connected`) | `src/extension.ts` | P1 |
| 8 | globalState 초기화 (기존 이동 플래그 제거) | `src/extension.ts` | P0 |

### 5.2 Out of Scope

| 항목 | 사유 |
|------|------|
| VS Code 네이티브 MCP 설정 연동 | VS Code MCP 지원이 아직 Preview, 별도 피처로 분리 |
| 채팅 UI 개선 | 이번 피처 범위 외 |
| 멀티 MCP 서버 관리 | 별도 피처 |

## 6. 기술적 리스크

| 리스크 | 영향 | 완화 |
|--------|------|------|
| TreeView 추가로 Activity Bar 공간 차지 | 사이드바가 복잡해질 수 있음 | TreeView는 접을 수 있으므로 영향 미미 |
| globalState 초기화 시 기존 사용자 설정 충돌 | 이미 이동한 사용자는 채팅 패널 위치 초기화 | 이동 플래그만 삭제, 채팅 패널 위치는 VS Code가 기억 |
| Welcome View의 `when` 조건 타이밍 | 연결 직전에 깜빡일 수 있음 | context key를 activate 초기에 false로 설정 |

## 7. 마일스톤

| Step | 작업 | 산출물 |
|------|------|--------|
| 1 | 자동 이동 로직 제거 + globalState 초기화 | `extension.ts` 수정 |
| 2 | MCP Status TreeView 구현 | `src/ui/mcp-status.ts` 신규 |
| 3 | package.json 뷰/커맨드/Welcome View 등록 | `package.json` 수정 |
| 4 | 진단 커맨드 + context key 구현 | `extension.ts` 수정 |
| 5 | Output Channel 로깅 | `mcp/client.ts` 수정 |
| 6 | 빌드/테스트 검증 | 빌드 성공 확인 |

## 8. 결정 사항

- [x] **자동 이동 완전 제거** (2026-03-16)
  - 사용자가 직접 drag & drop으로 원하는 위치에 배치
- [x] **TreeDataProvider 방식** (2026-03-16)
  - Webview 대비 경량, VS Code 네이티브 UX, 접기/펼치기 자동 지원
- [x] **VS Code 네이티브 MCP 연동은 별도 피처** (2026-03-16)
  - VS Code 1.99+ MCP 지원이 아직 Preview 단계, 안정화 후 별도 PDCA

---

*작성일: 2026-03-16 | Phase: Plan | Status: All Decisions Made*
*Parent: vscode-extension*
