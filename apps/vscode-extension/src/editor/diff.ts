import * as vscode from 'vscode';

export class DiffManager {
  /**
   * Show inline diff in VS Code editor for edit_file tool results.
   */
  async showDiff(
    filePath: string,
    oldContent: string,
    newContent: string,
  ): Promise<void> {
    const oldUri = vscode.Uri.parse(`myaicoder-diff:${filePath}.before`);
    const newUri = vscode.Uri.file(filePath);

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

    // Clean up after 60s
    setTimeout(() => registration.dispose(), 60_000);
  }
}
