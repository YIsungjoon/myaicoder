import * as vscode from 'vscode';
import { execSync } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';

export class ConfigManager {
  private readonly SECTION = 'myaicoder';

  get<T>(key: string, defaultValue: T): T;
  get<T>(key: string): T | undefined;
  get<T>(key: string, defaultValue?: T): T | undefined {
    const cfg = vscode.workspace.getConfiguration(this.SECTION);
    return defaultValue !== undefined
      ? cfg.get<T>(key, defaultValue)
      : cfg.get<T>(key);
  }

  /**
   * myaicoder executable path resolution order:
   * 1. User setting: myaicoder.executablePath
   * 2. PATH: where/which myaicoder
   * 3. Workspace .venv/bin/myaicoder or .venv/Scripts/myaicoder.exe
   */
  async resolveExecutablePath(): Promise<string> {
    // 1. User setting
    const configured = this.get<string>('executablePath');
    if (configured) {
      const normalized = path.normalize(configured);
      if (fs.existsSync(normalized)) {
        return normalized;
      }
    }

    // 2. PATH (cross-platform: 'where' on Windows, 'which' on Unix)
    try {
      const cmd = process.platform === 'win32' ? 'where myaicoder' : 'which myaicoder';
      const found = execSync(cmd, { encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] })
        .trim()
        .split(/\r?\n/)[0];
      if (found && fs.existsSync(found)) {
        return found;
      }
    } catch {
      // not found in PATH
    }

    // 3. Workspace .venv
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if (workspaceFolder) {
      const isWin = process.platform === 'win32';
      const venvPath = isWin
        ? path.join(workspaceFolder, '.venv', 'Scripts', 'myaicoder.exe')
        : path.join(workspaceFolder, '.venv', 'bin', 'myaicoder');
      if (fs.existsSync(venvPath)) {
        return venvPath;
      }
    }

    throw new Error(
      'myaicoder executable not found. Install with `pip install myaicoder` '
      + 'or set myaicoder.executablePath in settings.',
    );
  }

  getModelName(): string | undefined {
    return this.get<string>('modelName');
  }

  getLlmUrl(): string | undefined {
    return this.get<string>('llmUrl');
  }

  getApiKey(): string {
    return this.get<string>('apiKey', '');
  }

  getWorkspaceFolder(): string | null {
    return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? null;
  }
}
