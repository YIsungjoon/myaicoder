import * as vscode from 'vscode';
import { McpClientManager } from '../mcp/client';
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

    webviewView.webview.onDidReceiveMessage(
      async (message: WebviewMessage) => {
        switch (message.type) {
          case 'sendMessage':
            await this.handleUserMessage(message.text);
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
      } else {
        // Direct mode: pass user message as-is (no LLM routing in extension)
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
