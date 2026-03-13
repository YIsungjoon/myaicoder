# Design: VS Code Extension (Phase 5)

**Feature**: vscode-extension
**날짜**: 2026-03-13
**Phase**: Design
**Level**: Enterprise
**Plan 참조**: `docs/pdca/01-plan/features/vscode-extension.plan.md`

---

## 1. 기술 스택

| 영역 | 기술 | 버전/비고 |
|------|------|----------|
| 확장 호스트 | TypeScript + VS Code Extension API | VS Code 1.85+ |
| 채팅 UI | Webview (HTML/CSS/JS) | 경량, 커스텀 UI 자유도 |
| MCP 통신 | `@modelcontextprotocol/sdk` | 공식 Tier 1 TypeScript SDK |
| 프로세스 관리 | Node.js `child_process` | `myaicoder serve` subprocess |
| 마크다운 렌더링 | `marked` + `highlight.js` | 코드 블록 구문 강조 |
| 빌드 | esbuild | VS Code 확장 공식 번들러 |
| 패키지 매니저 | pnpm | 모노레포 통합 (pnpm-workspace.yaml) |
| 테스트 | `@vscode/test-electron` + vitest | 확장 통합 테스트 + 단위 테스트 |
| 린트 | ESLint + Prettier | TypeScript 표준 |

## 2. 시스템 아키텍처

```
┌──────────────────────────────────────────────────────────────────────┐
│  VS Code / Windsurf / Cursor                                         │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  myAiCoder Extension (TypeScript)                              │  │
│  │                                                                │  │
│  │  ┌──────────────────────┐    ┌──────────────────────────────┐ │  │
│  │  │  Webview (Chat UI)    │    │  Extension Host              │ │  │
│  │  │                       │    │                               │ │  │
│  │  │  ┌─────────────────┐ │    │  ┌─────────────────────────┐ │ │  │
│  │  │  │ MessageList      │ │    │  │ McpClientManager        │ │ │  │
│  │  │  │ - user/ai 메시지  │ │    │  │ - StdioClientTransport  │ │ │  │
│  │  │  │ - markdown 렌더링 │ │    │  │ - tools/list, tools/call│ │ │  │
│  │  │  ├─────────────────┤ │    │  │ - 연결 상태 관리          │ │ │  │
│  │  │  │ ToolResultCard   │ │    │  ├─────────────────────────┤ │ │  │
│  │  │  │ - 접기/펼치기     │ │    │  │ ProcessManager          │ │ │  │
│  │  │  │ - 결과 미리보기   │ │    │  │ - spawn/kill/restart    │ │ │  │
│  │  │  ├─────────────────┤ │    │  │ - 크래시 자동 재시작     │ │ │  │
│  │  │  │ InputArea        │ │    │  │ - 초기화 타임아웃        │ │ │  │
│  │  │  │ - textarea       │ │    │  ├─────────────────────────┤ │ │  │
│  │  │  │ - Shift+Enter    │ │    │  │ EditorIntegration       │ │ │  │
│  │  │  └─────────────────┘ │    │  │ - 활성 파일 컨텍스트     │ │ │  │
│  │  │                       │    │  │ - 인라인 Diff 표시       │ │ │  │
│  │  │  postMessage() ──────┼────┤  │ - 터미널 출력             │ │ │  │
│  │  │  ◄── onMessage() ────┼────┤  ├─────────────────────────┤ │ │  │
│  │  │                       │    │  │ ConfigManager           │ │ │  │
│  │  └──────────────────────┘    │  │ - 설정 읽기/쓰기         │ │ │  │
│  │                               │  │ - 실행 경로 탐색         │ │ │  │
│  │                               │  └─────────────────────────┘ │ │  │
│  │                               │                               │ │  │
│  │                               │  StatusBarManager              │ │  │
│  │                               │  - 연결 상태, 모델명, 토큰    │ │  │
│  │                               └──────────────┬───────────────┘ │  │
│  └──────────────────────────────────────────────┼────────────────┘  │
│                                                  │ stdio             │
│                                                  │ (JSON-RPC 2.0)   │
│                                                  ▼                   │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  myaicoder serve (Python subprocess)                          │   │
│  │  ├── read_file, write_file, edit_file                         │   │
│  │  ├── glob_search, grep_search, run_command                    │   │
│  │  ├── agentic_task (optional)                                  │   │
│  │  └── MCP Client → Revit/CAD MCP (optional chaining)          │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

## 3. 파일 구조

```
apps/vscode-extension/
├── package.json              # VS Code 확장 manifest + 의존성
├── tsconfig.json             # TypeScript 설정
├── esbuild.config.mjs        # 번들러 설정
├── .vscodeignore             # 패키징 제외 파일
├── src/
│   ├── extension.ts          # activate/deactivate 진입점
│   ├── mcp/
│   │   ├── client.ts         # MCP 클라이언트 (stdio) — McpClientManager
│   │   └── process.ts        # myaicoder serve 프로세스 관리 — ProcessManager
│   ├── chat/
│   │   ├── panel.ts          # Webview 패널 관리 — ChatPanelProvider
│   │   └── types.ts          # 메시지 타입 정의
│   ├── editor/
│   │   ├── diff.ts           # 인라인 Diff 표시 — DiffManager
│   │   └── context.ts        # 활성 파일 컨텍스트 — EditorContext
│   ├── ui/
│   │   └── statusbar.ts      # 상태 표시줄 — StatusBarManager
│   └── config.ts             # 확장 설정 관리 — ConfigManager
├── webview/
│   ├── index.html            # 채팅 UI 템플릿
│   ├── style.css             # 스타일 (VS Code 테마 변수 사용)
│   └── main.js               # Webview 스크립트 (메시지 렌더링, 입력 처리)
├── media/
│   └── icon.png              # 확장 아이콘 (128x128)
└── test/
    ├── unit/
    │   ├── client.test.ts    # MCP 클라이언트 단위 테스트
    │   ├── process.test.ts   # 프로세스 관리 단위 테스트
    │   └── config.test.ts    # 설정 관리 단위 테스트
    └── integration/
        └── extension.test.ts # 확장 통합 테스트
```

## 4. 인터페이스 상세

### 4.1 package.json — VS Code Extension Manifest

```json
{
  "name": "myaicoder",
  "displayName": "myAiCoder",
  "description": "AI coding assistant powered by local LLM via MCP",
  "version": "0.1.0",
  "publisher": "myaicoder",
  "engines": { "vscode": "^1.85.0" },
  "categories": ["AI", "Chat"],
  "activationEvents": [],
  "main": "./dist/extension.js",
  "contributes": {
    "viewsContainers": {
      "activitybar": [
        {
          "id": "myaicoder",
          "title": "myAiCoder",
          "icon": "media/icon.png"
        }
      ]
    },
    "views": {
      "myaicoder": [
        {
          "type": "webview",
          "id": "myaicoder.chatPanel",
          "name": "Chat"
        }
      ]
    },
    "commands": [
      {
        "command": "myaicoder.newChat",
        "title": "myAiCoder: New Chat"
      },
      {
        "command": "myaicoder.reconnect",
        "title": "myAiCoder: Reconnect MCP Server"
      },
      {
        "command": "myaicoder.sendSelection",
        "title": "myAiCoder: Send Selection to Chat"
      }
    ],
    "configuration": {
      "title": "myAiCoder",
      "properties": {
        "myaicoder.executablePath": {
          "type": "string",
          "default": "",
          "description": "Path to myaicoder executable (auto-detected if empty)"
        },
        "myaicoder.llmUrl": {
          "type": "string",
          "default": "http://localhost:8080",
          "description": "LLM server URL"
        },
        "myaicoder.modelName": {
          "type": "string",
          "default": "qwen3.5-27b",
          "description": "Model name to display in status bar"
        },
        "myaicoder.allowBash": {
          "type": "boolean",
          "default": false,
          "description": "Allow Bash tool execution (security risk)"
        },
        "myaicoder.maxConcurrent": {
          "type": "number",
          "default": 1,
          "description": "Max concurrent MCP requests"
        },
        "myaicoder.enableAgentic": {
          "type": "boolean",
          "default": false,
          "description": "Enable agentic_task tool for multi-step execution"
        }
      }
    },
    "keybindings": [
      {
        "command": "myaicoder.sendSelection",
        "key": "ctrl+shift+l",
        "mac": "cmd+shift+l",
        "when": "editorHasSelection"
      }
    ]
  },
  "scripts": {
    "build": "esbuild src/extension.ts --bundle --outdir=dist --platform=node --external:vscode --format=cjs",
    "watch": "npm run build -- --watch",
    "package": "vsce package",
    "test": "vitest run"
  },
  "devDependencies": {
    "@modelcontextprotocol/sdk": "^1.0.0",
    "@types/vscode": "^1.85.0",
    "@vscode/test-electron": "^2.3.0",
    "esbuild": "^0.20.0",
    "marked": "^12.0.0",
    "highlight.js": "^11.9.0",
    "typescript": "^5.4.0",
    "vitest": "^1.3.0"
  }
}
```

### 4.2 extension.ts — 진입점

```typescript
import * as vscode from 'vscode';
import { McpClientManager } from './mcp/client';
import { ProcessManager } from './mcp/process';
import { ChatPanelProvider } from './chat/panel';
import { ConfigManager } from './config';
import { StatusBarManager } from './ui/statusbar';
import { EditorContext } from './editor/context';

let mcpClient: McpClientManager;
let processManager: ProcessManager;

export async function activate(context: vscode.ExtensionContext) {
  const config = new ConfigManager();
  const statusBar = new StatusBarManager(config);

  // 1. myaicoder serve 프로세스 시작
  processManager = new ProcessManager(config);
  await processManager.start();

  // 2. MCP 클라이언트 연결
  mcpClient = new McpClientManager(processManager);
  await mcpClient.connect();

  // 연결 상태 업데이트
  statusBar.setConnected(true, await mcpClient.getToolCount());

  // 3. 채팅 패널 등록
  const editorContext = new EditorContext();
  const chatProvider = new ChatPanelProvider(
    context.extensionUri,
    mcpClient,
    editorContext,
    statusBar,
  );

  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(
      'myaicoder.chatPanel',
      chatProvider,
    ),
  );

  // 4. 커맨드 등록
  context.subscriptions.push(
    vscode.commands.registerCommand('myaicoder.newChat', () => {
      chatProvider.clearChat();
    }),
    vscode.commands.registerCommand('myaicoder.reconnect', async () => {
      await processManager.restart();
      await mcpClient.connect();
      statusBar.setConnected(true, await mcpClient.getToolCount());
    }),
    vscode.commands.registerCommand('myaicoder.sendSelection', () => {
      const editor = vscode.window.activeTextEditor;
      if (editor) {
        const selection = editor.document.getText(editor.selection);
        chatProvider.sendContext(selection, editor.document.uri.fsPath);
      }
    }),
  );

  // 5. 상태 표시줄 등록
  context.subscriptions.push(statusBar);

  // 6. 프로세스 크래시 감지 → 자동 재시작
  processManager.onDidCrash(async () => {
    statusBar.setConnected(false);
    vscode.window.showWarningMessage(
      'myAiCoder server crashed. Reconnecting...',
    );
    await processManager.restart();
    await mcpClient.connect();
    statusBar.setConnected(true, await mcpClient.getToolCount());
  });
}

export function deactivate() {
  mcpClient?.disconnect();
  processManager?.stop();
}
```

### 4.3 ProcessManager — `mcp/process.ts`

```typescript
import { ChildProcess, spawn } from 'child_process';
import * as vscode from 'vscode';
import { ConfigManager } from '../config';

export class ProcessManager implements vscode.Disposable {
  private process: ChildProcess | null = null;
  private restartCount = 0;
  private readonly MAX_RESTARTS = 3;
  private readonly INIT_TIMEOUT_MS = 10_000;
  private _onDidCrash = new vscode.EventEmitter<void>();
  readonly onDidCrash = this._onDidCrash.event;

  constructor(private config: ConfigManager) {}

  async start(): Promise<void> {
    const execPath = await this.config.resolveExecutablePath();
    const args = this.buildArgs();

    this.process = spawn(execPath, args, {
      stdio: ['pipe', 'pipe', 'pipe'],
      cwd: vscode.workspace.workspaceFolders?.[0]?.uri.fsPath,
    });

    this.process.on('exit', (code) => {
      if (code !== 0 && code !== null) {
        this.handleCrash();
      }
    });

    this.process.stderr?.on('data', (data: Buffer) => {
      console.error('[myaicoder stderr]', data.toString());
    });

    // 프로세스 준비 대기 (초기화 타임아웃)
    await this.waitForReady();
  }

  private buildArgs(): string[] {
    const args = ['serve'];
    if (this.config.get<boolean>('allowBash')) {
      args.push('--allow-bash');
    }
    const maxConcurrent = this.config.get<number>('maxConcurrent');
    if (maxConcurrent > 1) {
      args.push('--max-concurrent', String(maxConcurrent));
    }
    if (this.config.get<boolean>('enableAgentic')) {
      args.push('--agentic');
    }
    return args;
  }

  private async waitForReady(): Promise<void> {
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('myaicoder serve initialization timed out'));
      }, this.INIT_TIMEOUT_MS);

      // stdio transport는 프로세스가 시작되면 즉시 ready
      if (this.process && this.process.pid) {
        clearTimeout(timeout);
        resolve();
      }
    });
  }

  private async handleCrash(): Promise<void> {
    if (this.restartCount >= this.MAX_RESTARTS) {
      vscode.window.showErrorMessage(
        `myAiCoder server crashed ${this.MAX_RESTARTS} times. Please check your configuration.`,
      );
      return;
    }
    this.restartCount++;
    this._onDidCrash.fire();
  }

  async restart(): Promise<void> {
    this.stop();
    this.restartCount = 0;
    await this.start();
  }

  stop(): void {
    if (this.process) {
      this.process.kill('SIGTERM');
      this.process = null;
    }
  }

  get stdin() { return this.process?.stdin ?? null; }
  get stdout() { return this.process?.stdout ?? null; }

  dispose(): void {
    this.stop();
    this._onDidCrash.dispose();
  }
}
```

### 4.4 McpClientManager — `mcp/client.ts`

```typescript
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { ProcessManager } from './process';

export interface ToolInfo {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}

export interface ToolCallResult {
  content: string;
  isError: boolean;
}

export class McpClientManager {
  private client: Client | null = null;
  private tools: ToolInfo[] = [];

  constructor(private processManager: ProcessManager) {}

  async connect(): Promise<void> {
    const stdin = this.processManager.stdin;
    const stdout = this.processManager.stdout;

    if (!stdin || !stdout) {
      throw new Error('Process not started');
    }

    const transport = new StdioClientTransport({
      reader: stdout,
      writer: stdin,
    });

    this.client = new Client({
      name: 'myaicoder-vscode',
      version: '0.1.0',
    });

    await this.client.connect(transport);

    // tools/list로 사용 가능한 도구 목록 가져오기
    const result = await this.client.listTools();
    this.tools = result.tools.map((t) => ({
      name: t.name,
      description: t.description ?? '',
      inputSchema: t.inputSchema as Record<string, unknown>,
    }));
  }

  async callTool(name: string, args: Record<string, unknown>): Promise<ToolCallResult> {
    if (!this.client) {
      throw new Error('MCP client not connected');
    }

    const result = await this.client.callTool({ name, arguments: args });

    // MCP 결과에서 텍스트 추출
    const content = result.content
      .filter((c): c is { type: 'text'; text: string } => c.type === 'text')
      .map((c) => c.text)
      .join('\n');

    return {
      content,
      isError: result.isError ?? false,
    };
  }

  getTools(): ToolInfo[] {
    return this.tools;
  }

  async getToolCount(): Promise<number> {
    return this.tools.length;
  }

  disconnect(): void {
    this.client?.close();
    this.client = null;
    this.tools = [];
  }
}
```

### 4.5 ChatPanelProvider — `chat/panel.ts`

```typescript
import * as vscode from 'vscode';
import { McpClientManager, ToolCallResult } from '../mcp/client';
import { EditorContext } from '../editor/context';
import { StatusBarManager } from '../ui/statusbar';
import { ChatMessage, WebviewMessage, ExtensionMessage } from './types';

export class ChatPanelProvider implements vscode.WebviewViewProvider {
  private webviewView?: vscode.WebviewView;
  private messages: ChatMessage[] = [];

  constructor(
    private extensionUri: vscode.Uri,
    private mcpClient: McpClientManager,
    private editorContext: EditorContext,
    private statusBar: StatusBarManager,
  ) {}

  resolveWebviewView(
    webviewView: vscode.WebviewView,
    _context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken,
  ): void {
    this.webviewView = webviewView;

    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this.extensionUri],
    };

    webviewView.webview.html = this.getHtml(webviewView.webview);

    // Webview → Extension 메시지 수신
    webviewView.webview.onDidReceiveMessage(
      async (message: WebviewMessage) => {
        switch (message.type) {
          case 'sendMessage':
            await this.handleUserMessage(message.text);
            break;
          case 'cancelRequest':
            // TODO: 요청 취소 구현
            break;
        }
      },
    );
  }

  private async handleUserMessage(text: string): Promise<void> {
    // 1. 사용자 메시지 추가
    const userMsg: ChatMessage = {
      role: 'user',
      content: text,
      timestamp: Date.now(),
    };
    this.messages.push(userMsg);
    this.postMessage({ type: 'addMessage', message: userMsg });

    // 2. 활성 파일 컨텍스트 수집
    const fileContext = this.editorContext.getActiveFileContext();

    // 3. agentic_task 또는 개별 도구 호출
    //    (사용자 입력을 agentic_task에 전달하는 것이 기본)
    try {
      this.postMessage({ type: 'setLoading', loading: true });

      const result = await this.mcpClient.callTool('agentic_task', {
        prompt: this.buildPrompt(text, fileContext),
      });

      const aiMsg: ChatMessage = {
        role: 'assistant',
        content: result.content,
        timestamp: Date.now(),
        isError: result.isError,
      };
      this.messages.push(aiMsg);
      this.postMessage({ type: 'addMessage', message: aiMsg });
    } catch (error) {
      const errorMsg: ChatMessage = {
        role: 'assistant',
        content: `Error: ${error instanceof Error ? error.message : String(error)}`,
        timestamp: Date.now(),
        isError: true,
      };
      this.messages.push(errorMsg);
      this.postMessage({ type: 'addMessage', message: errorMsg });
    } finally {
      this.postMessage({ type: 'setLoading', loading: false });
    }
  }

  private buildPrompt(text: string, fileContext: string | null): string {
    if (fileContext) {
      return `Current file context:\n${fileContext}\n\nUser request: ${text}`;
    }
    return text;
  }

  clearChat(): void {
    this.messages = [];
    this.postMessage({ type: 'clearChat' });
  }

  sendContext(selection: string, filePath: string): void {
    const contextText = `Selected code from ${filePath}:\n\`\`\`\n${selection}\n\`\`\``;
    this.postMessage({ type: 'setInput', text: contextText });
  }

  private postMessage(message: ExtensionMessage): void {
    this.webviewView?.webview.postMessage(message);
  }

  private getHtml(webview: vscode.Webview): string {
    const nonce = getNonce();
    const styleUri = webview.asWebviewUri(
      vscode.Uri.joinPath(this.extensionUri, 'webview', 'style.css'),
    );
    const scriptUri = webview.asWebviewUri(
      vscode.Uri.joinPath(this.extensionUri, 'webview', 'main.js'),
    );

    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy"
    content="default-src 'none';
             style-src ${webview.cspSource} 'nonce-${nonce}';
             script-src 'nonce-${nonce}';">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link href="${styleUri}" rel="stylesheet">
  <title>myAiCoder Chat</title>
</head>
<body>
  <div id="chat-container">
    <div id="message-list"></div>
    <div id="input-area">
      <textarea id="message-input"
        placeholder="Ask myAiCoder..."
        rows="3"></textarea>
      <button id="send-btn" title="Send (Enter)">Send</button>
    </div>
  </div>
  <script nonce="${nonce}" src="${scriptUri}"></script>
</body>
</html>`;
  }
}

function getNonce(): string {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  let result = '';
  for (let i = 0; i < 32; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}
```

### 4.6 메시지 타입 — `chat/types.ts`

```typescript
/** 채팅 메시지 */
export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  isError?: boolean;
  toolResults?: ToolResultItem[];
}

/** 도구 실행 결과 (접기/펼치기 카드용) */
export interface ToolResultItem {
  toolName: string;
  args: Record<string, unknown>;
  result: string;
  isError: boolean;
  duration: number;  // ms
}

/** Webview → Extension 메시지 */
export type WebviewMessage =
  | { type: 'sendMessage'; text: string }
  | { type: 'cancelRequest' }
  | { type: 'ready' };

/** Extension → Webview 메시지 */
export type ExtensionMessage =
  | { type: 'addMessage'; message: ChatMessage }
  | { type: 'setLoading'; loading: boolean }
  | { type: 'clearChat' }
  | { type: 'setInput'; text: string }
  | { type: 'toolResult'; result: ToolResultItem };
```

### 4.7 ConfigManager — `config.ts`

```typescript
import * as vscode from 'vscode';
import { execSync } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';

export class ConfigManager {
  private readonly SECTION = 'myaicoder';

  get<T>(key: string): T {
    return vscode.workspace
      .getConfiguration(this.SECTION)
      .get<T>(key) as T;
  }

  /**
   * myaicoder 실행 경로 탐색 순서:
   * 1. 설정의 myaicoder.executablePath
   * 2. which myaicoder (PATH)
   * 3. 워크스페이스 .venv/bin/myaicoder
   */
  async resolveExecutablePath(): Promise<string> {
    // 1. 사용자 설정
    const configured = this.get<string>('executablePath');
    if (configured && fs.existsSync(configured)) {
      return configured;
    }

    // 2. PATH에서 탐색
    try {
      const which = execSync('which myaicoder', { encoding: 'utf8' }).trim();
      if (which) return which;
    } catch {
      // not found in PATH
    }

    // 3. 워크스페이스 .venv
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if (workspaceFolder) {
      const venvPath = path.join(workspaceFolder, '.venv', 'bin', 'myaicoder');
      if (fs.existsSync(venvPath)) {
        return venvPath;
      }
    }

    throw new Error(
      'myaicoder executable not found. Install with `pip install myaicoder` '
      + 'or set myaicoder.executablePath in settings.',
    );
  }

  getModelName(): string {
    return this.get<string>('modelName') || 'qwen3.5-27b';
  }

  getLlmUrl(): string {
    return this.get<string>('llmUrl') || 'http://localhost:8080';
  }
}
```

### 4.8 EditorContext — `editor/context.ts`

```typescript
import * as vscode from 'vscode';

export class EditorContext {
  /**
   * 활성 에디터의 파일 정보를 컨텍스트 문자열로 반환.
   * 파일 경로 + 선택 범위 (있으면) + 주변 코드
   */
  getActiveFileContext(): string | null {
    const editor = vscode.window.activeTextEditor;
    if (!editor) return null;

    const doc = editor.document;
    const filePath = doc.uri.fsPath;
    const languageId = doc.languageId;

    // 선택 영역이 있으면 선택된 텍스트만
    if (!editor.selection.isEmpty) {
      const selectedText = doc.getText(editor.selection);
      return [
        `File: ${filePath}`,
        `Language: ${languageId}`,
        `Selected lines: ${editor.selection.start.line + 1}-${editor.selection.end.line + 1}`,
        '```' + languageId,
        selectedText,
        '```',
      ].join('\n');
    }

    // 선택 영역 없으면 커서 주변 ±20줄
    const cursorLine = editor.selection.active.line;
    const startLine = Math.max(0, cursorLine - 20);
    const endLine = Math.min(doc.lineCount - 1, cursorLine + 20);
    const range = new vscode.Range(startLine, 0, endLine, doc.lineAt(endLine).text.length);
    const text = doc.getText(range);

    return [
      `File: ${filePath}`,
      `Language: ${languageId}`,
      `Cursor at line: ${cursorLine + 1}`,
      '```' + languageId,
      text,
      '```',
    ].join('\n');
  }
}
```

### 4.9 DiffManager — `editor/diff.ts`

```typescript
import * as vscode from 'vscode';

export class DiffManager {
  /**
   * edit_file 도구 결과에서 diff를 추출하여
   * VS Code의 인라인 diff 에디터에 표시
   */
  async showDiff(
    filePath: string,
    oldContent: string,
    newContent: string,
  ): Promise<void> {
    const oldUri = vscode.Uri.parse(`myaicoder-diff:${filePath}.before`);
    const newUri = vscode.Uri.file(filePath);

    // TextDocumentContentProvider로 이전 내용 제공
    const provider = new (class implements vscode.TextDocumentContentProvider {
      provideTextDocumentContent(): string {
        return oldContent;
      }
    })();

    const registration = vscode.workspace.registerTextDocumentContentProvider(
      'myaicoder-diff',
      provider,
    );

    await vscode.commands.executeCommand(
      'vscode.diff',
      oldUri,
      newUri,
      `myAiCoder: ${filePath} (changes)`,
    );

    // 일정 시간 후 정리
    setTimeout(() => registration.dispose(), 60_000);
  }
}
```

### 4.10 StatusBarManager — `ui/statusbar.ts`

```typescript
import * as vscode from 'vscode';
import { ConfigManager } from '../config';

export class StatusBarManager implements vscode.Disposable {
  private statusItem: vscode.StatusBarItem;
  private tokenCount = 0;

  constructor(private config: ConfigManager) {
    this.statusItem = vscode.window.createStatusBarItem(
      vscode.StatusBarAlignment.Right,
      100,
    );
    this.statusItem.command = 'myaicoder.reconnect';
    this.setConnected(false);
    this.statusItem.show();
  }

  setConnected(connected: boolean, toolCount?: number): void {
    const model = this.config.getModelName();
    if (connected) {
      this.statusItem.text = `$(check) myAiCoder: ${model} (${toolCount ?? '?'} tools)`;
      this.statusItem.tooltip = 'Connected — Click to reconnect';
      this.statusItem.backgroundColor = undefined;
    } else {
      this.statusItem.text = '$(warning) myAiCoder: Disconnected';
      this.statusItem.tooltip = 'Click to reconnect';
      this.statusItem.backgroundColor = new vscode.ThemeColor(
        'statusBarItem.warningBackground',
      );
    }
  }

  updateTokenCount(tokens: number): void {
    this.tokenCount += tokens;
    const model = this.config.getModelName();
    this.statusItem.text = `$(check) myAiCoder: ${model} | ${this.formatTokens(this.tokenCount)}`;
  }

  private formatTokens(count: number): string {
    if (count < 1000) return `${count} tok`;
    return `${(count / 1000).toFixed(1)}k tok`;
  }

  dispose(): void {
    this.statusItem.dispose();
  }
}
```

## 5. Webview UI 상세

### 5.1 style.css — VS Code 테마 통합

```css
:root {
  /* VS Code CSS 변수 자동 상속 */
  --bg: var(--vscode-editor-background);
  --fg: var(--vscode-editor-foreground);
  --input-bg: var(--vscode-input-background);
  --input-border: var(--vscode-input-border);
  --button-bg: var(--vscode-button-background);
  --button-fg: var(--vscode-button-foreground);
  --card-bg: var(--vscode-editorWidget-background);
  --border: var(--vscode-panel-border);
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  background: var(--bg);
  color: var(--fg);
  font-family: var(--vscode-font-family);
  font-size: var(--vscode-font-size);
  height: 100vh;
  overflow: hidden;
}

#chat-container {
  display: flex;
  flex-direction: column;
  height: 100%;
}

#message-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.message {
  margin-bottom: 12px;
  padding: 8px 12px;
  border-radius: 6px;
  line-height: 1.5;
}

.message.user {
  background: var(--vscode-textBlockQuote-background);
  border-left: 3px solid var(--vscode-textLink-foreground);
}

.message.assistant {
  background: var(--card-bg);
}

.message.error {
  border-left: 3px solid var(--vscode-errorForeground);
}

/* 도구 결과 카드 */
.tool-result-card {
  margin: 8px 0;
  border: 1px solid var(--border);
  border-radius: 4px;
  overflow: hidden;
}

.tool-result-header {
  display: flex;
  align-items: center;
  padding: 6px 10px;
  background: var(--vscode-editorGroupHeader-tabsBackground);
  cursor: pointer;
  font-size: 0.9em;
}

.tool-result-header .tool-name {
  font-weight: bold;
  margin-right: 8px;
}

.tool-result-header .tool-duration {
  color: var(--vscode-descriptionForeground);
  margin-left: auto;
}

.tool-result-body {
  padding: 8px 10px;
  max-height: 300px;
  overflow-y: auto;
  font-family: var(--vscode-editor-font-family);
  font-size: var(--vscode-editor-font-size);
  white-space: pre-wrap;
  display: none;  /* 접기 기본 */
}

.tool-result-card.expanded .tool-result-body {
  display: block;
}

/* 마크다운 코드 블록 */
.message pre {
  background: var(--vscode-textCodeBlock-background);
  padding: 8px;
  border-radius: 4px;
  overflow-x: auto;
}

.message code {
  font-family: var(--vscode-editor-font-family);
}

/* 입력 영역 */
#input-area {
  display: flex;
  gap: 8px;
  padding: 8px;
  border-top: 1px solid var(--border);
}

#message-input {
  flex: 1;
  background: var(--input-bg);
  color: var(--fg);
  border: 1px solid var(--input-border);
  border-radius: 4px;
  padding: 8px;
  font-family: var(--vscode-font-family);
  font-size: var(--vscode-font-size);
  resize: vertical;
}

#send-btn {
  background: var(--button-bg);
  color: var(--button-fg);
  border: none;
  border-radius: 4px;
  padding: 8px 16px;
  cursor: pointer;
  align-self: flex-end;
}

/* 로딩 인디케이터 */
.loading-dots::after {
  content: '...';
  animation: dots 1.5s steps(4, end) infinite;
}

@keyframes dots {
  0%, 20% { content: '.'; }
  40% { content: '..'; }
  60%, 100% { content: '...'; }
}
```

### 5.2 main.js — Webview 스크립트

```javascript
// @ts-check
(function () {
  // VS Code API 획득
  /** @type {import('vscode').Webview} */
  const vscode = acquireVsCodeApi();

  const messageList = document.getElementById('message-list');
  const messageInput = document.getElementById('message-input');
  const sendBtn = document.getElementById('send-btn');

  // marked 라이브러리 인라인 (경량 마크다운 파서)
  // 실제 구현에서는 번들에 포함
  function renderMarkdown(text) {
    // 기본 마크다운 렌더링: 코드 블록, 볼드, 이탤릭, 링크
    return text
      .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code class="language-$1">$2</code></pre>')
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/\*([^*]+)\*/g, '<em>$1</em>')
      .replace(/\n/g, '<br>');
  }

  function addMessage(message) {
    const div = document.createElement('div');
    div.className = `message ${message.role}${message.isError ? ' error' : ''}`;
    div.innerHTML = renderMarkdown(message.content);

    // 도구 결과 카드
    if (message.toolResults) {
      message.toolResults.forEach((tr) => {
        div.appendChild(createToolResultCard(tr));
      });
    }

    messageList.appendChild(div);
    messageList.scrollTop = messageList.scrollHeight;
  }

  function createToolResultCard(toolResult) {
    const card = document.createElement('div');
    card.className = 'tool-result-card';

    const header = document.createElement('div');
    header.className = 'tool-result-header';
    header.innerHTML = `
      <span class="tool-name">${toolResult.toolName}</span>
      <span class="tool-duration">${toolResult.duration}ms</span>
    `;
    header.addEventListener('click', () => {
      card.classList.toggle('expanded');
    });

    const body = document.createElement('div');
    body.className = 'tool-result-body';
    body.textContent = toolResult.result;

    card.appendChild(header);
    card.appendChild(body);
    return card;
  }

  function setLoading(loading) {
    const existing = document.querySelector('.loading-indicator');
    if (loading && !existing) {
      const div = document.createElement('div');
      div.className = 'message assistant loading-indicator';
      div.innerHTML = '<span class="loading-dots">Thinking</span>';
      messageList.appendChild(div);
      messageList.scrollTop = messageList.scrollHeight;
    } else if (!loading && existing) {
      existing.remove();
    }
  }

  // 메시지 전송
  function sendMessage() {
    const text = messageInput.value.trim();
    if (!text) return;

    vscode.postMessage({ type: 'sendMessage', text });
    messageInput.value = '';
    messageInput.style.height = 'auto';
  }

  sendBtn.addEventListener('click', sendMessage);

  messageInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  // Extension → Webview 메시지 수신
  window.addEventListener('message', (event) => {
    const message = event.data;
    switch (message.type) {
      case 'addMessage':
        addMessage(message.message);
        break;
      case 'setLoading':
        setLoading(message.loading);
        break;
      case 'clearChat':
        messageList.innerHTML = '';
        break;
      case 'setInput':
        messageInput.value = message.text;
        messageInput.focus();
        break;
      case 'toolResult':
        // 도구 결과를 마지막 AI 메시지에 추가
        const lastMsg = messageList.querySelector('.message.assistant:last-child');
        if (lastMsg) {
          lastMsg.appendChild(createToolResultCard(message.result));
        }
        break;
    }
  });

  // 준비 완료 알림
  vscode.postMessage({ type: 'ready' });
})();
```

## 6. MCP 통신 시퀀스

### 6.1 초기화 시퀀스

```
Extension Host                     myaicoder serve
     │                                    │
     │── spawn('myaicoder', ['serve']) ──▶│ (프로세스 시작)
     │                                    │
     │── StdioClientTransport 연결 ──────▶│
     │                                    │
     │── initialize ────────────────────▶│
     │◀── serverInfo + capabilities ────│
     │                                    │
     │── tools/list ────────────────────▶│
     │◀── [read_file, write_file, ...] ─│
     │                                    │
     │── StatusBar: "Connected (6 tools)"│
```

### 6.2 사용자 메시지 → 도구 호출 시퀀스

```
User          Webview              Extension Host          myaicoder serve
 │               │                       │                       │
 │── 입력 ──────▶│                       │                       │
 │               │── postMessage ───────▶│                       │
 │               │   {type: sendMessage} │                       │
 │               │                       │── tools/call ────────▶│
 │               │                       │   (agentic_task)      │
 │               │                       │                       │── LLM 호출
 │               │                       │                       │── tool 실행
 │               │                       │                       │── LLM 호출
 │               │                       │◀── result ──────────│
 │               │                       │                       │
 │               │◀── postMessage ──────│                       │
 │               │   {type: addMessage}  │                       │
 │◀── 렌더링 ──│                       │                       │
```

### 6.3 Direct Pass-through 모드 (agentic 비활성화 시)

agentic_task가 없는 경우, Extension이 직접 개별 도구를 호출할 수 있다.

```
Extension Host                     myaicoder serve
     │                                    │
     │── tools/call (read_file) ────────▶│
     │◀── {content: "file contents"} ───│  (<100ms)
     │                                    │
     │── tools/call (edit_file) ────────▶│
     │◀── {content: "edited"} ──────────│  (<100ms)
```

이 모드에서는 Extension이 자체적으로 LLM API를 호출하여 도구 사용 결정을 해야 한다 (Phase 6+ 범위).

## 7. Webview 보안 (CSP)

```html
<meta http-equiv="Content-Security-Policy"
  content="default-src 'none';
           style-src ${webview.cspSource} 'nonce-${nonce}';
           script-src 'nonce-${nonce}';">
```

| 정책 | 설정 | 사유 |
|------|------|------|
| `default-src` | `'none'` | 모든 리소스 기본 차단 |
| `style-src` | `${webview.cspSource}` | 확장 리소스만 허용 |
| `script-src` | `'nonce-${nonce}'` | nonce 기반 인라인 스크립트만 |
| 외부 리소스 | 차단 | 오프라인 호환, XSS 방지 |

## 8. 에러 처리 및 복구

### 8.1 프로세스 생명주기

```
┌─────────┐    start()    ┌──────────┐
│  Stopped │──────────────▶│  Running  │
└─────────┘               └────┬─────┘
      ▲                        │
      │         exit(code≠0)   │
      │     ┌──────────────────┘
      │     ▼
      │  ┌─────────┐   restartCount < 3
      │  │ Crashed  │──────────────────▶ restart()
      │  └─────────┘                        │
      │     │                               │
      │     │ restartCount >= 3             ▼
      │     └──────▶ Error Message    ┌──────────┐
      │                                │  Running  │
      └────────── stop() ◀────────────┘
```

### 8.2 에러 시나리오 대응

| 시나리오 | 감지 방법 | 대응 |
|----------|----------|------|
| `myaicoder` 미설치 | `resolveExecutablePath()` 실패 | 설치 안내 메시지 |
| 프로세스 크래시 | `exit` 이벤트 (code ≠ 0) | 자동 재시작 (최대 3회) |
| 초기화 타임아웃 | 10초 타임아웃 | 에러 메시지 + 설정 확인 안내 |
| MCP 연결 실패 | `client.connect()` 예외 | 재연결 버튼 표시 |
| LLM 서버 미실행 | `agentic_task` 에러 | Direct 도구만 사용 가능 안내 |
| VS Code 종료 | `deactivate()` 호출 | 프로세스 SIGTERM |

## 9. esbuild 설정 — `esbuild.config.mjs`

```javascript
import { build } from 'esbuild';

const isWatch = process.argv.includes('--watch');

/** @type {import('esbuild').BuildOptions} */
const options = {
  entryPoints: ['src/extension.ts'],
  bundle: true,
  outdir: 'dist',
  platform: 'node',
  format: 'cjs',
  external: ['vscode'],
  sourcemap: true,
  minify: !isWatch,
  target: 'node18',
};

if (isWatch) {
  const ctx = await build({ ...options, plugins: [] });
  // esbuild watch mode
  console.log('Watching for changes...');
} else {
  await build(options);
  console.log('Build complete.');
}
```

## 10. 테스트 설계

### 10.1 단위 테스트

| # | 파일 | 테스트 | 설명 |
|---|------|--------|------|
| 1 | `config.test.ts` | `resolveExecutablePath` | 3단계 경로 탐색 로직 |
| 2 | `config.test.ts` | `get<T>` | VS Code 설정 읽기 |
| 3 | `process.test.ts` | `start/stop` | 프로세스 시작/종료 |
| 4 | `process.test.ts` | `handleCrash` | 크래시 시 재시작 카운트 |
| 5 | `process.test.ts` | `maxRestarts` | 3회 초과 시 에러 메시지 |
| 6 | `process.test.ts` | `buildArgs` | 설정 기반 CLI 인자 생성 |
| 7 | `client.test.ts` | `connect` | MCP 클라이언트 연결 |
| 8 | `client.test.ts` | `callTool` | 도구 호출 + 결과 파싱 |
| 9 | `client.test.ts` | `disconnect` | 연결 해제 + 정리 |
| 10 | `client.test.ts` | `getTools` | tools/list 결과 캐싱 |

### 10.2 통합 테스트

| # | 테스트 | 설명 |
|---|--------|------|
| 1 | 확장 활성화 | `activate()` → 프로세스 시작 → MCP 연결 |
| 2 | 확장 비활성화 | `deactivate()` → 프로세스 종료 |
| 3 | 커맨드 실행 | `myaicoder.newChat`, `myaicoder.reconnect` |

## 11. 구현 순서

| Step | 작업 | 파일 | 의존성 |
|:----:|------|------|--------|
| 1 | 프로젝트 스캐폴딩 | `package.json`, `tsconfig.json`, `esbuild.config.mjs` | - |
| 2 | Extension 진입점 | `src/extension.ts` | Step 1 |
| 3 | ConfigManager | `src/config.ts` | Step 1 |
| 4 | ProcessManager | `src/mcp/process.ts` | Step 3 |
| 5 | McpClientManager | `src/mcp/client.ts` | Step 4 |
| 6 | Webview 채팅 패널 (기본 UI) | `src/chat/panel.ts`, `webview/*` | Step 2 |
| 7 | 메시지 타입 정의 | `src/chat/types.ts` | Step 6 |
| 8 | Webview ↔ Host 메시지 송수신 | `src/chat/panel.ts` + `webview/main.js` | Step 6-7 |
| 9 | MCP tools/call 연동 | `src/chat/panel.ts` + `src/mcp/client.ts` | Step 5, 8 |
| 10 | 도구 결과 카드 렌더링 | `webview/main.js` + `webview/style.css` | Step 9 |
| 11 | EditorContext (활성 파일) | `src/editor/context.ts` | Step 2 |
| 12 | StatusBarManager | `src/ui/statusbar.ts` | Step 3 |
| 13 | DiffManager (인라인 Diff) | `src/editor/diff.ts` | Step 9 |
| 14 | 마크다운 렌더링 (marked + hljs) | `webview/main.js` | Step 10 |
| 15 | 단위 테스트 | `test/unit/*` | Step 3-5 |
| 16 | 통합 테스트 | `test/integration/*` | Step 1-14 |

## 12. 의존성 관계

```
extension.ts (진입점)
    ├── ConfigManager ─────── 설정 읽기
    ├── ProcessManager ────── myaicoder serve 프로세스
    │   └── ConfigManager
    ├── McpClientManager ──── MCP 프로토콜 통신
    │   └── ProcessManager (stdin/stdout)
    ├── ChatPanelProvider ─── Webview 채팅 UI
    │   ├── McpClientManager
    │   ├── EditorContext
    │   └── StatusBarManager
    ├── StatusBarManager ──── 상태 표시줄
    │   └── ConfigManager
    └── EditorContext ──────── 에디터 파일 정보
```

## 13. 결정 사항

- [x] **Webview 마크다운**: `marked` + `highlight.js` 사용 (2026-03-13)
  - 경량, Webview 번들에 포함 가능
- [x] **StdioClientTransport**: MCP SDK의 공식 stdio 어댑터 (2026-03-13)
  - `reader: stdout`, `writer: stdin` 직접 연결
- [x] **agentic_task 우선**: 사용자 메시지를 `agentic_task`로 전달 (2026-03-13)
  - 개별 도구 직접 호출은 Phase 6+ (Extension 자체 LLM 연동 시)
- [x] **CSP nonce 기반**: 인라인 스크립트 보안 (2026-03-13)
  - 외부 리소스 완전 차단, 오프라인 호환
- [x] **프로세스 재시작**: 최대 3회, 10초 타임아웃 (2026-03-13)
  - 4회째 크래시 시 에러 메시지만 표시
- [x] **경로 탐색 순서**: 설정 → PATH → .venv (2026-03-13)
  - pip, venv, 직접 지정 모두 지원

---

*작성일: 2026-03-13 | Phase: Design | Status: Complete*
*Plan 참조: docs/pdca/01-plan/features/vscode-extension.plan.md*
