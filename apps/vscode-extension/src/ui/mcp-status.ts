import * as vscode from 'vscode';
import { McpClientManager } from '../mcp/client';
import { ConfigManager } from '../config';

export class McpStatusViewProvider
  implements vscode.TreeDataProvider<StatusItem>, vscode.Disposable
{
  private _onDidChangeTreeData = new vscode.EventEmitter<
    StatusItem | undefined
  >();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  private mcpClient: McpClientManager | null = null;

  constructor(private config: ConfigManager) {}

  /** Call on every MCP state change to refresh the tree */
  update(client: McpClientManager | null): void {
    this.mcpClient = client;
    this._onDidChangeTreeData.fire(undefined);
  }

  getTreeItem(element: StatusItem): vscode.TreeItem {
    return element;
  }

  getChildren(element?: StatusItem): StatusItem[] {
    if (element) {
      if (element.contextValue === 'tools-header') {
        return this.getToolItems();
      }
      return [];
    }

    // Root level — empty when disconnected so Welcome View shows
    const connected =
      this.mcpClient !== null && this.mcpClient.getToolCount() > 0;
    if (!connected) {
      return [];
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
        new vscode.ThemeIcon(
          'check',
          new vscode.ThemeColor('testing.iconPassed'),
        ),
      ),
      new StatusItem(
        `LLM: ${llmUrl ?? '(server default)'}`,
        vscode.TreeItemCollapsibleState.None,
        'llm-url',
        new vscode.ThemeIcon('globe'),
      ),
      new StatusItem(
        `Model: ${model ?? '(server default)'}`,
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
