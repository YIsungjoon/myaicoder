# Plan: workspace-integration (V0.2)

## Feature 정보

| 항목 | 내용 |
|------|------|
| Feature | workspace-integration |
| Version | V0.2 |
| 우선순위 | **높음** — Claude Code / Copilot 수준의 워크스페이스 인식 필수 |
| 의존 | windows-installer (완료), oneclick-installer (완료) |

## 1. 목적

VS Code에서 열린 **작업 폴더와 파일을 AI와 공유**하여, 사용자가 현재 작업 중인 코드 컨텍스트 안에서 AI가 읽고, 쓰고, 제안할 수 있게 한다.

### 최종 UX

```
1. 사용자가 VS Code에서 프로젝트 폴더 열기
2. myAiCoder 채팅에서 "이 프로젝트의 라우팅 구조 설명해줘"
3. AI가 스스로 list_dir → read_file 도구 호출 → 구조 분석 후 답변
4. 사용자: "main.ts의 handleRequest 함수에 에러 핸들링 추가해"
5. AI가 코드 수정안 생성 → Diff View로 "이렇게 바꿀까요?" 제안
6. 사용자가 [Accept] 클릭 → 파일 자동 수정
```

## 2. 현재 상태 분석

### 2.1 이미 있는 것

| 항목 | 위치 | 상태 |
|------|------|------|
| EditorContext (현재 파일/선택 텍스트) | `src/editor/context.ts` | ✅ 구현됨 |
| buildPrompt에 fileContext 주입 | `src/chat/panel.ts:99-104` | ✅ 구현됨 |
| MCP 파일 도구 (read_file, write_file, edit_file 등) | `services/myaicoder/src/myaicoder/tools/` | ✅ 9개 도구 |
| --working-dir CLI 옵션 | `cli.py` serve 명령 | ✅ 있으나 미연결 |
| sendSelection 커맨드 | `src/extension.ts:68-74` | ✅ 구현됨 |
| StdioClientTransport cwd 전달 | `src/mcp/client.ts:49` | ✅ workspace 전달 중 |

### 2.2 없는 것 (3가지 관문)

| 관문 | 항목 | 필요 이유 | 복잡도 |
|------|------|----------|--------|
| **1. 눈** | 시스템 프롬프트로 워크스페이스 컨텍스트 강화 | AI가 프로젝트 구조를 모름 | 낮 |
| **1. 눈** | 열린 파일 탭 목록 전달 | 사용자가 관심 있는 파일 범위 | 낮 |
| **2. 손발** | --working-dir를 workspace에 연결 | 도구가 올바른 폴더에서 동작 | 낮 |
| **2. 손발** | 도구 결과를 채팅에 표시 | 사용자가 AI의 행동을 봄 | 중 |
| **3. 코드 수정** | [Apply to Editor] 버튼 | 제안 코드를 실제 적용 | 중 |
| **3. 코드 수정** | Diff View 제안 | 변경 전/후 비교 | 높 |
| **3. 코드 수정** | WorkspaceEdit API 연동 | 파일 실제 수정 | 중 |

## 3. 아키텍처

### 3.1 V0.1 → V0.2 비교

```
V0.1 (현재):
  사용자 입력 → Extension → agentic_task(prompt) → CLI → LLM → 텍스트 응답

V0.2 (목표):
  사용자 입력 + 워크스페이스 컨텍스트
       → Extension → agentic_task(prompt + context)
       → CLI → LLM → 도구 호출 (read_file, edit_file...)
       → 도구 결과 → LLM → 최종 응답
       → Extension → Diff View / [Apply] 버튼 → 파일 수정
```

### 3.2 관문별 데이터 플로우

```
관문 1: 눈 (Context Awareness)
┌─────────────┐
│ VS Code     │
│ ├ 열린 파일  │ ──→ EditorContext.getActiveFileContext()
│ ├ 열린 탭들  │ ──→ EditorContext.getOpenTabs()         ← 신규
│ ├ 워크스페이스│ ──→ EditorContext.getWorkspaceInfo()    ← 신규
│ └ 선택 텍스트 │ ──→ (기존)
└─────────────┘
        │
        ▼
  buildPrompt()에 시스템 컨텍스트 주입

관문 2: 손발 (Workspace Tools)
┌─────────────────────┐
│ CLI (myaicoder.exe)  │
│ --working-dir=<ws>   │ ← Extension이 workspace 경로 전달
│ ├ read_file          │
│ ├ write_file         │
│ ├ edit_file          │
│ ├ glob_search        │
│ ├ grep_search        │
│ ├ list_dir           │ ← 프로젝트 구조 탐색
│ └ build_run          │
└─────────────────────┘
        │
        ▼
  도구 호출 결과를 채팅 UI에 표시

관문 3: 코드 수정 (Apply & Diff)
┌─────────────────────┐
│ Extension            │
│ ├ 코드 블록 파싱     │ ← AI 응답에서 ```코드``` 추출
│ ├ [Apply] 버튼       │ ← Webview 버튼
│ ├ Diff View          │ ← vscode.commands.executeCommand('vscode.diff')
│ └ WorkspaceEdit      │ ← vscode.workspace.applyEdit()
└─────────────────────┘
```

## 4. 요구사항

### 4.1 관문 1: 눈 — Context Awareness (P0)

| ID | 요구사항 | 검증 기준 |
|----|----------|----------|
| R1 | 현재 열린 파일 경로 + 내용을 프롬프트에 포함 | AI가 "현재 파일은 main.ts입니다" 인식 |
| R2 | 열린 탭 목록을 프롬프트에 포함 | AI가 관련 파일을 인식 |
| R3 | 워크스페이스 루트 경로를 시스템 컨텍스트로 전달 | AI 도구가 올바른 경로 사용 |

### 4.2 관문 2: 손발 — Workspace Tools (P0)

| ID | 요구사항 | 검증 기준 |
|----|----------|----------|
| R4 | --working-dir를 워크스페이스 폴더로 자동 설정 | CLI 도구가 프로젝트 폴더 내에서 동작 |
| R5 | AI가 도구를 호출할 때 결과가 채팅에 표시 | 사용자가 AI의 파일 탐색 과정을 봄 |
| R6 | AI가 "프로젝트 구조 보여줘"에 list_dir + read_file 연쇄 호출 | 자율적 탐색 동작 |

### 4.3 관문 3: 코드 수정 — Apply & Diff (P0)

| ID | 요구사항 | 검증 기준 |
|----|----------|----------|
| R7 | AI 응답의 코드 블록에 [Apply to Editor] 버튼 표시 | 웹뷰에서 버튼 클릭 가능 |
| R8 | 버튼 클릭 시 Diff View로 변경 전/후 비교 | vscode.diff 명령 실행 |
| R9 | Diff View에서 Accept 시 파일 실제 수정 | WorkspaceEdit으로 파일 변경 |

### 4.4 권장 요구사항 (P1)

| ID | 요구사항 | 검증 기준 |
|----|----------|----------|
| R10 | @file 멘션으로 특정 파일 참조 | `@main.ts` 입력 시 파일 내용 자동 주입 |
| R11 | 도구 호출 진행 상태 표시 (스피너 + 도구명) | "🔍 reading main.ts..." 표시 |
| R12 | 멀티파일 동시 수정 지원 | 여러 파일 Diff를 순차 표시 |

### 4.5 이연 항목 (P2)

| ID | 요구사항 | 이유 |
|----|----------|------|
| R13 | 터미널 통합 (명령어 직접 실행) | 보안 검토 필요 |
| R14 | Git 통합 (커밋, 브랜치) | 범위 과대 |
| R15 | 인라인 코드 완성 (Copilot 스타일) | 별도 LSP 서버 필요 |

## 5. 구현 범위

### 5.1 수정 파일

```
apps/vscode-extension/
├── src/
│   ├── editor/context.ts       ← 관문 1: getOpenTabs(), getWorkspaceInfo() 추가
│   ├── chat/panel.ts           ← 관문 1+3: buildPrompt 강화, Apply 버튼 처리
│   ├── mcp/process.ts          ← 관문 2: --working-dir 전달
│   ├── mcp/client.ts           ← 관문 2: --working-dir 전달
│   └── editor/apply.ts         ← 관문 3: 신규 — Diff View + WorkspaceEdit
├── webview/
│   ├── main.js                 ← 관문 3: [Apply] 버튼 렌더링 + 클릭 핸들러
│   └── style.css               ← 관문 3: Apply 버튼 스타일
└── test/unit/
    ├── context.test.ts         ← 관문 1: 테스트 추가
    └── apply.test.ts           ← 관문 3: 신규 테스트
```

### 5.2 변경 없는 파일

```
services/myaicoder/              ← CLI 도구는 이미 충분
.github/workflows/               ← CI 변경 없음
installer/                        ← 설치 스크립트 변경 없음
```

## 6. 구현 순서

| 단계 | 관문 | 작업 | 산출물 |
|------|------|------|--------|
| S1 | 2 | --working-dir를 워크스페이스에 연결 | process.ts, client.ts 수정 |
| S2 | 1 | EditorContext 강화 (openTabs, workspaceInfo) | context.ts 수정 |
| S3 | 1 | buildPrompt 시스템 컨텍스트 주입 | panel.ts 수정 |
| S4 | 2 | 도구 호출 결과를 채팅 UI에 표시 | panel.ts, main.js 수정 |
| S5 | 3 | AI 응답 코드 블록 파싱 + [Apply] 버튼 | main.js 수정 |
| S6 | 3 | apply.ts 신규 — Diff View + WorkspaceEdit | apply.ts 신규 |
| S7 | 3 | Accept/Reject 핸들링 | panel.ts + apply.ts 연동 |
| S8 | - | 테스트 작성 + 기존 테스트 통과 | test/ 추가 |
| S9 | - | Extension 재빌드 + Windows E2E 테스트 | installer 태그 push |

## 7. 리스크

| 리스크 | 영향 | 대응 |
|--------|------|------|
| AI가 도구 호출을 올바르게 못 함 | 파일 탐색 실패 | 시스템 프롬프트에 도구 사용법 명시 |
| Diff View에서 대용량 파일 성능 | UI 멈춤 | 파일 크기 제한 (100KB) |
| WorkspaceEdit 실패 (읽기 전용 파일) | 적용 불가 | try-catch + 사용자 알림 |
| Webview CSP가 Apply 버튼 차단 | 버튼 동작 안 함 | nonce 기반 CSP 유지 (기존 패턴) |
| 도구 연쇄 호출 시 토큰 과다 소비 | 비용/시간 증가 | max_concurrent 제한 유지 |

## 8. 성공 기준

| 기준 | 측정 방법 |
|------|----------|
| "이 프로젝트 구조 보여줘" → AI가 list_dir 호출 후 답변 | Windows 노트북 E2E |
| 현재 열린 파일 기반 질문에 정확한 답변 | 파일 컨텍스트 인식 확인 |
| AI 코드 제안 → [Apply] → Diff View → Accept → 파일 수정 | VS Code에서 확인 |
| 기존 테스트 241개 + 신규 테스트 통과 | 0 regression |
| Extension 20개 기존 테스트 통과 | 0 regression |
