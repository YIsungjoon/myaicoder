# Design: VS Code Extension 사용성 개선

**Feature**: vscode-ux-improvement
**날짜**: 2026-03-16
**Phase**: Design
**Plan 참조**: `docs/pdca/01-plan/features/vscode-ux-improvement.plan.md`

---

## 1. 변경 파일 목록

| # | 파일 | 변경 유형 | 설명 |
|---|------|-----------|------|
| 1 | `src/extension.ts` | 수정 | 자동 이동 제거, TreeView 등록, 진단 커맨드, context key, Output Channel |
| 2 | `src/ui/mcp-status.ts` | **신규** | McpStatusViewProvider (TreeDataProvider) |
| 3 | `src/mcp/client.ts` | 수정 | Output Channel 로깅 주입 |
| 4 | `package.json` | 수정 | mcpStatus 뷰, 커맨드, viewsWelcome 등록 |

## 2. 상세 설계

### 2.1 `src/ui/mcp-status.ts` (신규)

```typescript
// McpStatusViewProvider — TreeDataProvider 구현

import * as vscode from 'vscode';
import { McpClientManager, ToolInfo } from '../mcp/client';
import { ConfigManager } from '../config';

export class McpStatusViewProvider implements vscode.TreeDataProvider<StatusItem> {
  // ★ 핵심: 트리 갱신을 위한 EventEmitter
  private _onDidChangeTreeData = new vscode.EventEmitter<StatusItem | undefined>();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  private mcpClient: McpClientManager | null = null;
  private config: ConfigManager;

  constructor(config: ConfigManager) {
    this.config = config;
  }

  /** MCP 상태 변경 시 호출 — 반드시 fire()로 트리 갱신 */
  update(client: McpClientManager | null): void {
    this.mcpClient = client;
    this._onDidChangeTreeData.fire(undefined); // 전체 트리 새로고침
  }

  getTreeItem(element: StatusItem): vscode.TreeItem {
    return element;
  }

  getChildren(element?: StatusItem): StatusItem[] {
    if (element) {
      // Tools 하위 항목
      if (element.contextValue === 'tools-header') {
        return this.getToolItems();
      }
      return [];
    }

    // 루트 레벨
    const connected = this.mcpClient !== null && this.mcpClient.getToolCount() > 0;
    if (!connected) {
      return []; // Welcome View가 대신 표시됨
    }
    return this.getRootItems();
  }

  private getRootItems(): StatusItem[] {
    const pid = this.mcpClient?.getPid();
    const tools = this.mcpClient?.getTools() ?? [];
    const llmUrl = this.config.getLlmUrl();
    const model = this.config.getModelName();

    return [
      new StatusItem(
        `Connected (PID: ${pid ?? '?'})`,
        vscode.TreeItemCollapsibleState.None,
        'status-connected',
        new vscode.ThemeIcon('check', new vscode.ThemeColor('testing.iconPassed')),
      ),
      new StatusItem(
        `LLM: ${llmUrl}`,
        vscode.TreeItemCollapsibleState.None,
        'llm-url',
        new vscode.ThemeIcon('globe'),
      ),
      new StatusItem(
        `Model: ${model}`,
        vscode.TreeItemCollapsibleState.None,
        'model',
        new vscode.ThemeIcon('hubot'),
      ),
      new StatusItem(
        `Tools (${tools.length})`,
        vscode.TreeItemCollapsibleState.Collapsed,
        'tools-header',
        new vscode.ThemeIcon('tools'),
      ),
    ];
  }

  private getToolItems(): StatusItem[] {
    const tools = this.mcpClient?.getTools() ?? [];
    return tools.map(
      (t) =>
        new StatusItem(
          t.name,
          vscode.TreeItemCollapsibleState.None,
          'tool',
          new vscode.ThemeIcon('symbol-method'),
          t.description,
        ),
    );
  }

  dispose(): void {
    this._onDidChangeTreeData.dispose();
  }
}

class StatusItem extends vscode.TreeItem {
  constructor(
    label: string,
    collapsibleState: vscode.TreeItemCollapsibleState,
    public readonly contextValue: string,
    icon?: vscode.ThemeIcon,
    tooltip?: string,
  ) {
    super(label, collapsibleState);
    if (icon) this.iconPath = icon;
    if (tooltip) this.tooltip = tooltip;
  }
}
```

### 2.2 `src/extension.ts` 변경 사항

#### 삭제할 코드
```typescript
// 완전 제거: lines 80-97 (자동 이동 로직)
const hasMovedKey = 'myaicoder.movedToSecondarySidebar';
if (!context.globalState.get<boolean>(hasMovedKey)) { ... }
```

#### 추가할 코드

```typescript
// 1. Output Channel 생성 (최상단)
const outputChannel = vscode.window.createOutputChannel('myAiCoder MCP');

// 2. McpStatusViewProvider 등록
const mcpStatusProvider = new McpStatusViewProvider(config);
context.subscriptions.push(
  vscode.window.registerTreeDataProvider('myaicoder.mcpStatus', mcpStatusProvider),
  mcpStatusProvider,
);

// 3. context key 초기화
void vscode.commands.executeCommand('setContext', 'myaicoder.connected', false);

// 4. MCP 콜백에서 TreeView 갱신 + context key 업데이트 + 로깅
onConnected: (toolCount) => {
  statusBar.setConnected(true, toolCount);
  mcpStatusProvider.update(mcpClient);
  void vscode.commands.executeCommand('setContext', 'myaicoder.connected', true);
  outputChannel.appendLine(`[${timestamp()}] MCP connected — ${toolCount} tools available`);
},
onDisconnected: () => {
  statusBar.setConnected(false);
  mcpStatusProvider.update(null);
  void vscode.commands.executeCommand('setContext', 'myaicoder.connected', false);
  outputChannel.appendLine(`[${timestamp()}] MCP disconnected`);
},

// 5. 진단 커맨드
vscode.commands.registerCommand('myaicoder.showMcpDiagnostics', async () => {
  const tools = mcpClient.getTools();
  const pid = mcpClient.getPid();
  const connected = tools.length > 0;
  const execPath = await config.resolveExecutablePath().catch(() => 'Not found');

  outputChannel.appendLine('--- MCP Diagnostics ---');
  outputChannel.appendLine(`Status: ${connected ? 'Connected' : 'Disconnected'}`);
  outputChannel.appendLine(`Server PID: ${pid ?? 'N/A'}`);
  outputChannel.appendLine(`Executable: ${execPath}`);
  outputChannel.appendLine(`LLM URL: ${config.getLlmUrl()}`);
  outputChannel.appendLine(`Model: ${config.getModelName()}`);
  outputChannel.appendLine(`API Key: ${config.getApiKey() ? 'Set' : 'Not set'}`);
  outputChannel.appendLine(`Workspace: ${config.getWorkspaceFolder() ?? 'None'}`);
  outputChannel.appendLine(`Tools (${tools.length}):`);
  tools.forEach((t) => outputChannel.appendLine(`  - ${t.name}: ${t.description}`));
  outputChannel.appendLine('---');
  outputChannel.show(true);
}),

// 6. globalState 정리 (기존 이동 플래그 제거)
void context.globalState.update('myaicoder.movedToSecondarySidebar', undefined);
```

### 2.3 `src/mcp/client.ts` 변경 사항

```typescript
// Output Channel 주입을 위한 생성자 변경
constructor(
  private config: ConfigManager,
  private handlers?: { ... },
  private outputChannel?: vscode.OutputChannel,  // 추가
)

// connect() 내부 로깅
async connect(): Promise<void> {
  this.outputChannel?.appendLine(`[${timestamp()}] Connecting to MCP server...`);
  this.outputChannel?.appendLine(`[${timestamp()}] Executable: ${execPath}`);
  this.outputChannel?.appendLine(`[${timestamp()}] Args: ${args.join(' ')}`);
  // ... 기존 로직 ...
  this.outputChannel?.appendLine(`[${timestamp()}] Connected — ${this.tools.length} tools`);
}

// handleTransportClose() 로깅
private async handleTransportClose(): Promise<void> {
  this.outputChannel?.appendLine(`[${timestamp()}] Transport closed`);
  // ... 기존 로직 ...
}
```

### 2.4 `package.json` 변경 사항

```jsonc
{
  "contributes": {
    "views": {
      "myaicoder": [
        {
          "id": "myaicoder.mcpStatus",
          "name": "MCP Status"
        },
        {
          "type": "webview",
          "id": "myaicoder.chatPanel",
          "name": "Chat"
        }
      ]
    },
    "viewsWelcome": [
      {
        "view": "myaicoder.mcpStatus",
        "contents": "MCP 서버에 연결되지 않았습니다.\n\n[$(debug-disconnect) Connect](command:myaicoder.reconnect)\n\n[$(info) Show Diagnostics](command:myaicoder.showMcpDiagnostics)",
        "when": "!myaicoder.connected"
      }
    ],
    "commands": [
      // 기존 3개 + 신규 1개
      { "command": "myaicoder.showMcpDiagnostics", "title": "myAiCoder: Show MCP Diagnostics" }
    ]
  }
}
```

## 3. 트리 갱신 시점 (★ 핵심)

| 이벤트 | 트리거 | 갱신 대상 |
|--------|--------|-----------|
| MCP 연결 성공 | `onConnected` 콜백 | `mcpStatusProvider.update(mcpClient)` → fire() |
| MCP 연결 해제 | `onDisconnected` 콜백 | `mcpStatusProvider.update(null)` → fire() |
| MCP 재연결 실패 | `onReconnectFailed` 콜백 | `mcpStatusProvider.update(null)` → fire() |
| 수동 재연결 | `myaicoder.reconnect` 커맨드 | connect() 성공/실패 후 자동 콜백 |

**fire(undefined)**: 전체 트리 새로고침 (루트부터 다시 getChildren 호출)

## 4. context key 흐름

```
activate() → setContext('myaicoder.connected', false)
                    ↓
         connect() 성공 → setContext('myaicoder.connected', true)
                              → Welcome View 숨김, TreeView 표시
                    ↓
         disconnect() → setContext('myaicoder.connected', false)
                              → TreeView 숨김, Welcome View 표시
```

## 5. 구현 순서

| Step | 작업 | 의존성 |
|------|------|--------|
| 1 | `extension.ts`: 자동 이동 제거 + globalState 정리 | 없음 |
| 2 | `src/ui/mcp-status.ts`: TreeDataProvider 구현 | 없음 |
| 3 | `package.json`: mcpStatus 뷰, 커맨드, viewsWelcome 등록 | Step 2 |
| 4 | `extension.ts`: TreeView 등록 + 진단 커맨드 + context key + Output Channel | Step 2, 3 |
| 5 | `src/mcp/client.ts`: Output Channel 주입 + 로깅 | Step 4 |
| 6 | 빌드/테스트 검증 | Step 1-5 |

---

*작성일: 2026-03-16 | Phase: Design | Status: Complete*
