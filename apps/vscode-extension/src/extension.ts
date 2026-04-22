import * as vscode from 'vscode';
import { McpClientManager } from './mcp/client';
import { ChatPanelProvider } from './chat/panel';
import { ConfigManager } from './config';
import { StatusBarManager } from './ui/statusbar';
import { EditorContext } from './editor/context';
import { McpStatusViewProvider } from './ui/mcp-status';

let mcpClient: McpClientManager;

function timestamp(): string {
  return new Date().toISOString().slice(11, 19);
}

export async function activate(context: vscode.ExtensionContext) {
  const config = new ConfigManager();
  const statusBar = new StatusBarManager(config);
  const outputChannel = vscode.window.createOutputChannel('myAiCoder MCP');

  // 1. Register MCP Status tree view (stays in activity bar)
  const mcpStatusProvider = new McpStatusViewProvider(config);
  context.subscriptions.push(
    vscode.window.registerTreeDataProvider('myaicoder.mcpStatus', mcpStatusProvider),
    mcpStatusProvider,
  );

  // 2. Set initial context key
  void vscode.commands.executeCommand('setContext', 'myaicoder.connected', false);

  // 3. Register chat panel early so the webview is never blank while MCP connects
  const editorContext = new EditorContext();
  mcpClient = new McpClientManager(config, {
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
    onReconnectFailed: (error) => {
      statusBar.setConnected(false);
      mcpStatusProvider.update(null);
      void vscode.commands.executeCommand('setContext', 'myaicoder.connected', false);
      outputChannel.appendLine(`[${timestamp()}] Reconnect failed: ${error.message}`);
      void vscode.window.showWarningMessage(
        `myAiCoder server stopped and auto-reconnect failed: ${error.message}`,
      );
    },
  }, outputChannel);

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

  // 4. Connect MCP client (spawns myaicoder serve — done after UI is ready)
  try {
    await mcpClient.connect();
  } catch (error) {
    const msg = error instanceof Error ? error.message : String(error);
    vscode.window.showErrorMessage(`myAiCoder: ${msg}`);
    statusBar.setConnected(false);
    mcpStatusProvider.update(null);
    outputChannel.appendLine(`[${timestamp()}] Connection failed: ${msg}`);
  }

  // 5. Register commands
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
    vscode.commands.registerCommand('myaicoder.showMcpDiagnostics', async () => {
      const tools = mcpClient.getTools();
      const pid = mcpClient.getPid();
      const connected = tools.length > 0;
      let execPath = 'Not found';
      try {
        execPath = await config.resolveExecutablePath();
      } catch {
        // keep default
      }

      outputChannel.appendLine('');
      outputChannel.appendLine('=== MCP Diagnostics ===');
      outputChannel.appendLine(`Status:     ${connected ? 'Connected' : 'Disconnected'}`);
      outputChannel.appendLine(`Server PID: ${pid ?? 'N/A'}`);
      outputChannel.appendLine(`Executable: ${execPath}`);
      outputChannel.appendLine(`LLM URL:    ${config.getLlmUrl() ?? '(server default)'}`);
      outputChannel.appendLine(`Model:      ${config.getModelName() ?? '(server default)'}`);
      outputChannel.appendLine(`API Key:    ${config.getApiKey() ? 'Set' : 'Not set'}`);
      outputChannel.appendLine(`Workspace:  ${config.getWorkspaceFolder() ?? 'None'}`);
      outputChannel.appendLine(`Tools (${tools.length}):`);
      for (const t of tools) {
        outputChannel.appendLine(`  - ${t.name}: ${t.description}`);
      }
      outputChannel.appendLine('=======================');
      outputChannel.show(true);
    }),
  );

  // 6. Register status bar
  context.subscriptions.push(statusBar);

  // 7. Clean up legacy auto-move flag (no longer auto-moving to secondary sidebar)
  void context.globalState.update('myaicoder.movedToSecondarySidebar', undefined);
}

export async function deactivate() {
  await mcpClient?.disconnect();
}
