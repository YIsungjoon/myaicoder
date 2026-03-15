import * as vscode from 'vscode';
import * as path from 'path';
import { McpClientManager } from '../mcp/client';
import { EditorContext } from '../editor/context';
import { StatusBarManager } from '../ui/statusbar';
import { ChatMessage, ToolResultItem, WebviewMessage, ExtensionMessage } from './types';

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

    webviewView.webview.onDidReceiveMessage(
      async (message: WebviewMessage) => {
        switch (message.type) {
          case 'sendMessage':
            await this.handleUserMessage(message.text);
            break;
          case 'applyCode':
            await this.handleApplyCode(message.code, message.filePath);
            break;
          case 'cancelRequest':
            break;
        }
      },
    );
  }

  private async handleUserMessage(text: string): Promise<void> {
    const userMsg: ChatMessage = {
      role: 'user',
      content: text,
      timestamp: Date.now(),
    };
    this.messages.push(userMsg);
    this.postMessage({ type: 'addMessage', message: userMsg });

    const fileContext = this.editorContext.getActiveFileContext();

    try {
      this.postMessage({ type: 'setLoading', loading: true });

      // Check if agentic_task is available, otherwise use direct tool call
      const tools = this.mcpClient.getTools();
      const hasAgentic = tools.some((t) => t.name === 'agentic_task');

      let result;
      if (hasAgentic) {
        result = await this.mcpClient.callTool('agentic_task', {
          prompt: this.buildPrompt(text, fileContext),
        });

        // Parse and display tool call results from agentic response
        const toolResults = this.parseToolResults(result.content);
        if (toolResults.length > 0) {
          toolResults.forEach((tr) => {
            this.postMessage({ type: 'toolResult', result: tr });
          });
        }
      } else {
        result = {
          content: 'agentic_task not available. Enable with --agentic flag.\n'
            + 'Available tools: ' + tools.map((t) => t.name).join(', '),
          isError: false,
        };
      }

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

    // EC-A: Check dirty state
    const existingDoc = vscode.workspace.textDocuments.find(
      (d) => d.uri.fsPath === targetPath,
    );
    if (existingDoc?.isDirty) {
      const save = await vscode.window.showWarningMessage(
        `${path.basename(targetPath!)} has unsaved changes. Save first?`,
        'Save & Continue',
        'Cancel',
      );
      if (save === 'Save & Continue') {
        await existingDoc.save();
      } else {
        return;
      }
    }

    // Show diff first
    await showDiff(targetPath!, code);

    // Ask user to confirm
    const choice = await vscode.window.showInformationMessage(
      `Apply changes to ${path.basename(targetPath!)}?`,
      'Apply',
      'Cancel',
    );

    if (choice === 'Apply') {
      const success = await applyToFile(targetPath!, code);
      if (success) {
        vscode.window.showInformationMessage(`Changes applied to ${path.basename(targetPath!)}`);
      }
    }
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
