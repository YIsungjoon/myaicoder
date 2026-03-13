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
   * myaicoder executable path resolution order:
   * 1. User setting: myaicoder.executablePath
   * 2. PATH: which myaicoder
   * 3. Workspace .venv/bin/myaicoder
   */
  async resolveExecutablePath(): Promise<string> {
    // 1. User setting
    const configured = this.get<string>('executablePath');
    if (configured && fs.existsSync(configured)) {
      return configured;
    }

    // 2. PATH
    try {
      const which = execSync('which myaicoder', { encoding: 'utf8' }).trim();
      if (which) {
        return which;
      }
    } catch {
      // not found in PATH
    }

    // 3. Workspace .venv
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

  getWorkspaceFolder(): string | null {
    return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? null;
  }
}
