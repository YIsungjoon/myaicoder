import * as vscode from 'vscode';
import { McpClientManager } from './mcp/client';
import { ChatPanelProvider } from './chat/panel';
import { ConfigManager } from './config';
import { StatusBarManager } from './ui/statusbar';
import { EditorContext } from './editor/context';

let mcpClient: McpClientManager;

export async function activate(context: vscode.ExtensionContext) {
  const config = new ConfigManager();
  const statusBar = new StatusBarManager(config);

  // 1. Connect MCP client (spawns myaicoder serve automatically)
  mcpClient = new McpClientManager(config, {
    onConnected: (toolCount) => {
      statusBar.setConnected(true, toolCount);
    },
    onDisconnected: () => {
      statusBar.setConnected(false);
    },
    onReconnectFailed: (error) => {
      statusBar.setConnected(false);
      void vscode.window.showWarningMessage(
        `myAiCoder server stopped and auto-reconnect failed: ${error.message}`,
      );
    },
  });
  try {
    await mcpClient.connect();
  } catch (error) {
    const msg = error instanceof Error ? error.message : String(error);
    vscode.window.showErrorMessage(`myAiCoder: ${msg}`);
    statusBar.setConnected(false);
  }

  // 2. Register chat panel
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

  // 3. Register commands
  context.subscriptions.push(
    vscode.commands.registerCommand('myaicoder.newChat', () => {
      chatProvider.clearChat();
    }),
    vscode.commands.registerCommand('myaicoder.reconnect', async () => {
      try {
        await mcpClient.reconnect();
        vscode.window.showInformationMessage('myAiCoder: Reconnected.');
      } catch (error) {
        const msg = error instanceof Error ? error.message : String(error);
        vscode.window.showErrorMessage(`myAiCoder reconnect failed: ${msg}`);
        statusBar.setConnected(false);
      }
    }),
    vscode.commands.registerCommand('myaicoder.sendSelection', () => {
      const editor = vscode.window.activeTextEditor;
      if (editor) {
        const selection = editor.document.getText(editor.selection);
        chatProvider.sendContext(selection, editor.document.uri.fsPath);
      }
    }),
  );

  // 4. Register status bar
  context.subscriptions.push(statusBar);
}

export async function deactivate() {
  await mcpClient?.disconnect();
}
