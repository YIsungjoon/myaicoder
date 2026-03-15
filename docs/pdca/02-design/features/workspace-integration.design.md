# Design: workspace-integration (V0.2)

## 1. 개요

| 항목 | 내용 |
|------|------|
| Feature | workspace-integration |
| Plan | [workspace-integration.plan.md](../../01-plan/features/workspace-integration.plan.md) |
| 신규 파일 | 1개 (`src/editor/apply.ts`) |
| 수정 파일 | 6개 (context.ts, panel.ts, process.ts, client.ts, main.js, style.css) |
| 타입 수정 | 1개 (types.ts) |
| 테스트 | 2개 (context.test.ts 수정, apply.test.ts 신규) |

---

## 2. 관문 1: 눈 — Context Awareness

### D1. EditorContext 강화

**파일**: `src/editor/context.ts`

#### D1-1. getOpenTabs() 추가

```typescript
/**
 * Returns list of currently open editor tabs.
 */
getOpenTabs(): string[] {
  return vscode.window.tabGroups.all
    .flatMap((group) => group.tabs)
    .map((tab) => {
      if (tab.input instanceof vscode.TabInputText) {
        return tab.input.uri.fsPath;
      }
      return null;
    })
    .filter((p): p is string => p !== null);
}
```

**설계 근거**: `vscode.window.tabGroups`는 VS Code 1.67+ API로, 열린 탭 목록을 안전하게 가져올 수 있음.

#### D1-2. getWorkspaceInfo() 추가

```typescript
/**
 * Returns workspace root path and name.
 */
getWorkspaceInfo(): { rootPath: string; name: string } | null {
  const folder = vscode.workspace.workspaceFolders?.[0];
  if (!folder) return null;
  return {
    rootPath: folder.uri.fsPath,
    name: folder.name,
  };
}
```

---

### D2. buildPrompt 시스템 컨텍스트 주입

**파일**: `src/chat/panel.ts`

#### D2-1. buildPrompt 강화

**현재**:
```typescript
private buildPrompt(text: string, fileContext: string | null): string {
  if (fileContext) {
    return `Current file context:\n${fileContext}\n\nUser request: ${text}`;
  }
  return text;
}
```

**변경**:
```typescript
private buildPrompt(text: string, fileContext: string | null): string {
  const parts: string[] = [];

  // 1. Workspace info
  const wsInfo = this.editorContext.getWorkspaceInfo();
  if (wsInfo) {
    parts.push(`Workspace: ${wsInfo.name} (${wsInfo.rootPath})`);
  }

  // 2. Open tabs (max 10)
  const tabs = this.editorContext.getOpenTabs();
  if (tabs.length > 0) {
    const relTabs = wsInfo
      ? tabs.map((t) => path.relative(wsInfo.rootPath, t)).slice(0, 10)
      : tabs.slice(0, 10);
    parts.push(`Open files:\n${relTabs.map((t) => `  - ${t}`).join('\n')}`);
  }

  // 3. Active file context
  if (fileContext) {
    parts.push(`Active file context:\n${fileContext}`);
  }

  // 4. User request
  parts.push(`User request: ${text}`);

  return parts.join('\n\n');
}
```

**설계 근거**:
- 워크스페이스 경로를 알려줘야 AI가 도구 호출 시 올바른 경로 사용
- 열린 탭 목록은 최대 10개로 제한 (토큰 절약)
- 상대 경로로 변환하여 가독성 향상

---

## 3. 관문 2: 손발 — Workspace Tools

### D3. --working-dir 워크스페이스 연결

**파일**: `src/mcp/process.ts`

```typescript
export function buildServeArgs(options: {
  allowBash?: boolean;
  maxConcurrent?: number;
  enableAgentic?: boolean;
  llmUrl?: string;
  modelName?: string;
  workingDir?: string;  // ← 추가
}): string[] {
  const args = ['serve'];
  // ... 기존 옵션 ...
  if (options.workingDir) {
    args.push('--working-dir', options.workingDir);
  }
  return args;
}
```

**파일**: `src/mcp/client.ts`

```typescript
const cwd = this.config.getWorkspaceFolder();
const args = buildServeArgs({
  // ... 기존 옵션 ...
  workingDir: cwd ?? undefined,  // ← 추가
});
```

**설계 근거**: 기존 `cwd`는 StdioClientTransport의 프로세스 CWD로만 사용됨. CLI의 `--working-dir`로도 전달해야 도구가 파일 경로를 올바르게 제한/해석함.

### D4. 도구 호출 결과 채팅 표시

**현재 상태**: `toolResult` 메시지 타입과 `createToolResultCard()` 함수가 이미 webview에 구현되어 있음 (`main.js:76-96`, `types.ts:11-17`).

**필요한 변경**: `panel.ts`에서 agentic_task의 도구 호출 중간 결과를 webview로 전달.

**파일**: `src/chat/panel.ts` — handleUserMessage 수정

```typescript
if (hasAgentic) {
  result = await this.mcpClient.callTool('agentic_task', {
    prompt: this.buildPrompt(text, fileContext),
  });

  // Parse tool results from agentic response if present
  if (result.content) {
    const toolResults = this.parseToolResults(result.content);
    if (toolResults.length > 0) {
      toolResults.forEach((tr) => {
        this.postMessage({ type: 'toolResult', result: tr });
      });
    }
  }
}
```

#### D4-1. parseToolResults 메서드

```typescript
/**
 * Parse tool call results from agentic_task response.
 * Format: [TOOL_CALL] toolName | duration_ms | result
 */
private parseToolResults(content: string): ToolResultItem[] {
  const results: ToolResultItem[] = [];
  const pattern = /\[TOOL_CALL\]\s+(\w+)\s*\|\s*(\d+)ms\s*\|\s*([\s\S]*?)(?=\[TOOL_CALL\]|$)/g;
  let match;
  while ((match = pattern.exec(content)) !== null) {
    results.push({
      toolName: match[1],
      args: {},
      result: match[3].trim(),
      isError: false,
      duration: parseInt(match[2], 10),
    });
  }
  return results;
}
```

**설계 근거**: CLI의 agentic_task가 도구를 호출할 때 `[TOOL_CALL]` 마커를 응답에 포함하면, Extension이 이를 파싱하여 접을 수 있는 카드로 표시. 기존 `createToolResultCard()` UI를 재활용.

---

## 4. 관문 3: 코드 수정 — Apply & Diff

### D5. apply.ts 신규

**파일**: `src/editor/apply.ts` (신규)

```typescript
import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import * as os from 'os';

export interface CodeBlock {
  language: string;
  code: string;
  filePath?: string;  // extracted from code block header or AI context
}

/**
 * Parse code blocks from AI response.
 * Detects ```lang:filepath or ```lang patterns.
 */
export function parseCodeBlocks(content: string): CodeBlock[] {
  const blocks: CodeBlock[] = [];
  const pattern = /```(\w+)(?::([^\n]+))?\n([\s\S]*?)```/g;
  let match;
  while ((match = pattern.exec(content)) !== null) {
    blocks.push({
      language: match[1],
      filePath: match[2]?.trim(),
      code: match[3],
    });
  }
  return blocks;
}

/**
 * Show diff between original file and proposed changes.
 * Uses VS Code built-in diff editor.
 */
export async function showDiff(
  filePath: string,
  proposedContent: string,
): Promise<void> {
  const originalUri = vscode.Uri.file(filePath);

  // Write proposed content to temp file
  const tmpDir = os.tmpdir();
  const tmpFile = path.join(tmpDir, `myaicoder-diff-${path.basename(filePath)}`);
  fs.writeFileSync(tmpFile, proposedContent, 'utf8');
  const proposedUri = vscode.Uri.file(tmpFile);

  const title = `${path.basename(filePath)}: Current ↔ Proposed`;
  await vscode.commands.executeCommand('vscode.diff', originalUri, proposedUri, title);
}

/**
 * Apply code changes to a file using WorkspaceEdit.
 */
export async function applyToFile(
  filePath: string,
  newContent: string,
): Promise<boolean> {
  try {
    const uri = vscode.Uri.file(filePath);
    const doc = await vscode.workspace.openTextDocument(uri);
    const fullRange = new vscode.Range(
      doc.lineAt(0).range.start,
      doc.lineAt(doc.lineCount - 1).range.end,
    );

    const edit = new vscode.WorkspaceEdit();
    edit.replace(uri, fullRange, newContent);
    const success = await vscode.workspace.applyEdit(edit);

    if (success) {
      await doc.save();
    }
    return success;
  } catch (error) {
    vscode.window.showErrorMessage(
      `Failed to apply changes: ${error instanceof Error ? error.message : String(error)}`,
    );
    return false;
  }
}
```

**설계 근거**:
- `parseCodeBlocks`: AI 응답에서 ` ```lang:filepath ` 형식의 코드 블록을 추출. `filePath`가 있으면 자동으로 대상 파일 식별
- `showDiff`: VS Code 내장 diff 에디터 사용 (추가 의존성 없음). 임시 파일에 제안 코드 저장
- `applyToFile`: `WorkspaceEdit` API로 실제 파일 수정. 전체 교체 방식 (단순성 우선)

---

### D6. Webview [Apply] 버튼

**파일**: `webview/main.js` — renderMarkdown 수정

```javascript
// Code blocks with [Apply] button
html = html.replace(/```(\w+)(?::([^\n]+))?\n([\s\S]*?)```/g, (_, lang, filePath, code) => {
  const blockId = 'code-' + Math.random().toString(36).substr(2, 9);
  const applyBtn = filePath
    ? `<button class="apply-btn" data-block-id="${blockId}" data-file="${escapeHtml(filePath)}">Apply to ${escapeHtml(filePath)}</button>`
    : `<button class="apply-btn" data-block-id="${blockId}">Apply to Editor</button>`;
  return `<div class="code-block-wrapper">
    <div class="code-block-header">
      <span class="code-lang">${lang}</span>
      ${applyBtn}
    </div>
    <pre><code id="${blockId}" class="language-${lang}">${code}</code></pre>
  </div>`;
});
```

**클릭 핸들러** (main.js 하단 추가):

```javascript
// Apply button click handler (event delegation)
messageList.addEventListener('click', (e) => {
  const btn = e.target.closest('.apply-btn');
  if (!btn) return;

  const blockId = btn.dataset.blockId;
  const filePath = btn.dataset.file || null;
  const codeEl = document.getElementById(blockId);
  if (!codeEl) return;

  vscode.postMessage({
    type: 'applyCode',
    code: codeEl.textContent,
    filePath: filePath,
  });
});
```

### D7. panel.ts Apply 메시지 처리

**파일**: `src/chat/panel.ts` — onDidReceiveMessage에 추가

```typescript
case 'applyCode':
  await this.handleApplyCode(message.code, message.filePath);
  break;
```

```typescript
private async handleApplyCode(code: string, filePath?: string): Promise<void> {
  const { showDiff, applyToFile } = await import('../editor/apply');

  // Determine target file
  let targetPath = filePath;
  if (!targetPath) {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
      vscode.window.showWarningMessage('No active editor to apply code to.');
      return;
    }
    targetPath = editor.document.uri.fsPath;
  }

  // Resolve relative path to workspace
  const wsInfo = this.editorContext.getWorkspaceInfo();
  if (wsInfo && !path.isAbsolute(targetPath)) {
    targetPath = path.join(wsInfo.rootPath, targetPath);
  }

  // Show diff first
  await showDiff(targetPath, code);

  // Ask user to confirm
  const choice = await vscode.window.showInformationMessage(
    `Apply changes to ${path.basename(targetPath)}?`,
    'Apply',
    'Cancel',
  );

  if (choice === 'Apply') {
    const success = await applyToFile(targetPath, code);
    if (success) {
      vscode.window.showInformationMessage(`Changes applied to ${path.basename(targetPath)}`);
    }
  }
}
```

**설계 근거**:
- Diff View를 먼저 보여주고, 사용자 확인 후 적용 (안전성)
- `filePath`가 없으면 현재 활성 에디터의 파일에 적용
- 상대 경로는 워크스페이스 루트 기준으로 해석

---

### D8. types.ts 메시지 타입 추가

**파일**: `src/chat/types.ts`

```typescript
/** Webview -> Extension messages */
export type WebviewMessage =
  | { type: 'sendMessage'; text: string }
  | { type: 'cancelRequest' }
  | { type: 'applyCode'; code: string; filePath?: string }  // ← 추가
  | { type: 'ready' };
```

---

### D9. style.css Apply 버튼 스타일

**파일**: `webview/style.css`

```css
/* Code block wrapper with Apply button */
.code-block-wrapper {
  margin: 4px 0;
}

.code-block-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 8px;
  background: var(--vscode-editorGroupHeader-tabsBackground);
  border-radius: 4px 4px 0 0;
  font-size: 0.85em;
}

.code-block-header .code-lang {
  color: var(--vscode-descriptionForeground);
}

.apply-btn {
  background: var(--vscode-button-secondaryBackground);
  color: var(--vscode-button-secondaryForeground);
  border: none;
  border-radius: 3px;
  padding: 2px 8px;
  cursor: pointer;
  font-size: 0.85em;
}

.apply-btn:hover {
  background: var(--vscode-button-secondaryHoverBackground);
}
```

---

## 4.5. 엣지 케이스 (필수 반영)

### EC-A. Dirty State 방어 (D7)

`handleApplyCode` 진입 시 대상 파일이 수정되었지만 저장되지 않은 상태(dirty)일 수 있음.

```typescript
// handleApplyCode 내부, showDiff 호출 전
const existingDoc = vscode.workspace.textDocuments.find(
  (d) => d.uri.fsPath === targetPath,
);
if (existingDoc?.isDirty) {
  const save = await vscode.window.showWarningMessage(
    `${path.basename(targetPath)} has unsaved changes. Save first?`,
    'Save & Continue',
    'Cancel',
  );
  if (save === 'Save & Continue') {
    await existingDoc.save();
  } else {
    return;
  }
}
```

### EC-B. 정규식 관대화 (D5, D6)

AI가 언어 없는 코드 블록(` ``` `)이나 불필요한 공백을 넣는 경우 대응.

```typescript
// Before
/```(\w+)(?::([^\n]+))?\n([\s\S]*?)```/g

// After — 언어 선택적, 경로 공백 trim
/```([a-zA-Z0-9_+\-]*)(?::([^\n]+))?\n([\s\S]*?)```/g

// 매칭 후 trim 처리
language: match[1]?.trim() || 'text',
filePath: match[2]?.trim(),
code: match[3],
```

### EC-C. 신규 파일 Diff (D5)

AI가 존재하지 않는 새 파일을 제안한 경우 `showDiff`에서 원본 파일이 없음.

```typescript
export async function showDiff(
  filePath: string,
  proposedContent: string,
): Promise<void> {
  let originalUri: vscode.Uri;

  if (fs.existsSync(filePath)) {
    originalUri = vscode.Uri.file(filePath);
  } else {
    // New file: diff against empty content
    const tmpEmpty = path.join(os.tmpdir(), `myaicoder-empty-${path.basename(filePath)}`);
    fs.writeFileSync(tmpEmpty, '', 'utf8');
    originalUri = vscode.Uri.file(tmpEmpty);
  }

  const tmpFile = path.join(os.tmpdir(), `myaicoder-diff-${path.basename(filePath)}`);
  fs.writeFileSync(tmpFile, proposedContent, 'utf8');
  const proposedUri = vscode.Uri.file(tmpFile);

  const title = fs.existsSync(filePath)
    ? `${path.basename(filePath)}: Current ↔ Proposed`
    : `${path.basename(filePath)}: New File`;
  await vscode.commands.executeCommand('vscode.diff', originalUri, proposedUri, title);
}
```

`applyToFile`도 신규 파일 대응:

```typescript
export async function applyToFile(
  filePath: string,
  newContent: string,
): Promise<boolean> {
  try {
    if (!fs.existsSync(filePath)) {
      // Create parent directories and write new file
      fs.mkdirSync(path.dirname(filePath), { recursive: true });
      fs.writeFileSync(filePath, newContent, 'utf8');
      const doc = await vscode.workspace.openTextDocument(filePath);
      await vscode.window.showTextDocument(doc);
      return true;
    }

    // Existing file: use WorkspaceEdit
    const uri = vscode.Uri.file(filePath);
    const doc = await vscode.workspace.openTextDocument(uri);
    const fullRange = new vscode.Range(
      doc.lineAt(0).range.start,
      doc.lineAt(doc.lineCount - 1).range.end,
    );
    const edit = new vscode.WorkspaceEdit();
    edit.replace(uri, fullRange, newContent);
    const success = await vscode.workspace.applyEdit(edit);
    if (success) {
      await doc.save();
    }
    return success;
  } catch (error) {
    vscode.window.showErrorMessage(
      `Failed to apply changes: ${error instanceof Error ? error.message : String(error)}`,
    );
    return false;
  }
}
```

---

## 5. 전체 파일 변경 목록

| 파일 | 작업 | 설계 항목 |
|------|------|----------|
| `src/editor/context.ts` | 수정 — getOpenTabs(), getWorkspaceInfo() 추가 | D1 |
| `src/chat/panel.ts` | 수정 — buildPrompt 강화, parseToolResults, handleApplyCode | D2, D4, D7 |
| `src/mcp/process.ts` | 수정 — workingDir 옵션 추가 | D3 |
| `src/mcp/client.ts` | 수정 — workingDir 전달 | D3 |
| `src/editor/apply.ts` | **신규** — parseCodeBlocks, showDiff, applyToFile | D5 |
| `src/chat/types.ts` | 수정 — applyCode 메시지 타입 추가 | D8 |
| `webview/main.js` | 수정 — [Apply] 버튼 렌더링 + 클릭 핸들러 | D6 |
| `webview/style.css` | 수정 — Apply 버튼 스타일 | D9 |
| `test/unit/context.test.ts` | 수정 — getOpenTabs, getWorkspaceInfo 테스트 | 테스트 |
| `test/unit/apply.test.ts` | **신규** — parseCodeBlocks, showDiff, applyToFile 테스트 | 테스트 |

## 6. 검증 체크리스트

| ID | 검증 항목 | 방법 |
|----|----------|------|
| V1 | 워크스페이스 정보가 프롬프트에 포함 | AI 응답에서 워크스페이스 경로 언급 확인 |
| V2 | 열린 탭 목록이 프롬프트에 포함 | AI가 "열린 파일은 X, Y, Z입니다" 인식 |
| V3 | --working-dir가 워크스페이스로 설정 | CLI 도구가 프로젝트 폴더 내 파일만 접근 |
| V4 | "프로젝트 구조 보여줘" → list_dir 호출 | AI가 폴더 구조 응답 |
| V5 | 도구 호출 결과가 접이식 카드로 표시 | 채팅 UI에서 도구 카드 확인 |
| V6 | 코드 블록에 [Apply] 버튼 표시 | Webview에서 버튼 렌더링 |
| V7 | [Apply] 클릭 → Diff View 표시 | VS Code diff 에디터 열림 |
| V8 | Accept → 파일 실제 수정 | 파일 내용 변경 확인 |
| V9 | 기존 Extension 테스트 통과 | 20/20 passed |
| V10 | 기존 Python/Gateway 테스트 통과 | 241 passed |

## 7. 구현 순서 (Design 항목 매핑)

| 단계 | Plan | Design | 산출물 |
|------|------|--------|--------|
| S1 | 관문 2 | D3 | process.ts, client.ts 수정 |
| S2 | 관문 1 | D1 | context.ts 수정 |
| S3 | 관문 1 | D2 | panel.ts buildPrompt 수정 |
| S4 | 관문 2 | D4 | panel.ts parseToolResults 추가 |
| S5 | 관문 3 | D5 | apply.ts 신규 |
| S6 | 관문 3 | D6, D9 | main.js, style.css 수정 |
| S7 | 관문 3 | D7, D8 | panel.ts, types.ts 수정 |
| S8 | 테스트 | - | context.test.ts, apply.test.ts |
| S9 | 빌드 | - | installer 태그 push |
