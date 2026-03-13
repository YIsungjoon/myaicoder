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
