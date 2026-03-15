import * as vscode from 'vscode';

export class EditorContext {
  /**
   * Returns list of currently open editor tab file paths.
   */
  getOpenTabs(): string[] {
    return vscode.window.tabGroups.all
      .flatMap((group) => group.tabs)
      .map((tab) => {
        if (tab.input instanceof vscode.TabInputText) {
          return tab.input.uri.fsPath;
        }
        return null;
      })
      .filter((p): p is string => p !== null);
  }

  /**
   * Returns workspace root path and name.
   */
  getWorkspaceInfo(): { rootPath: string; name: string } | null {
    const folder = vscode.workspace.workspaceFolders?.[0];
    if (!folder) return null;
    return {
      rootPath: folder.uri.fsPath,
      name: folder.name,
    };
  }

  /**
   * Returns active editor file info as context string.
   * Includes file path + selected text or cursor surroundings (±20 lines).
   */
  getActiveFileContext(): string | null {
    const editor = vscode.window.activeTextEditor;
    if (!editor) return null;

    const doc = editor.document;
    const filePath = doc.uri.fsPath;
    const languageId = doc.languageId;

    // If there's a selection, return selected text
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

    // No selection: return ±20 lines around cursor
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
