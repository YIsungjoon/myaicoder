import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import * as os from 'os';

export interface CodeBlock {
  language: string;
  code: string;
  filePath?: string;
}

/**
 * Parse code blocks from AI response.
 * Detects ```lang:filepath or ```lang patterns.
 * EC-B: Tolerant regex for missing language or trailing whitespace.
 */
export function parseCodeBlocks(content: string): CodeBlock[] {
  const blocks: CodeBlock[] = [];
  const pattern = /```([a-zA-Z0-9_+\-]*)(?::([^\n]+))?\n([\s\S]*?)```/g;
  let match;
  while ((match = pattern.exec(content)) !== null) {
    blocks.push({
      language: match[1]?.trim() || 'text',
      filePath: match[2]?.trim(),
      code: match[3],
    });
  }
  return blocks;
}

/**
 * Show diff between original file and proposed changes.
 * EC-C: Handles new files by diffing against empty content.
 */
export async function showDiff(
  filePath: string,
  proposedContent: string,
): Promise<void> {
  let originalUri: vscode.Uri;

  if (fs.existsSync(filePath)) {
    originalUri = vscode.Uri.file(filePath);
  } else {
    // New file: diff against empty content
    const tmpEmpty = path.join(os.tmpdir(), `myaicoder-empty-${path.basename(filePath)}`);
    fs.writeFileSync(tmpEmpty, '', 'utf8');
    originalUri = vscode.Uri.file(tmpEmpty);
  }

  const tmpFile = path.join(os.tmpdir(), `myaicoder-diff-${path.basename(filePath)}`);
  fs.writeFileSync(tmpFile, proposedContent, 'utf8');
  const proposedUri = vscode.Uri.file(tmpFile);

  const title = fs.existsSync(filePath)
    ? `${path.basename(filePath)}: Current \u2194 Proposed`
    : `${path.basename(filePath)}: New File`;
  await vscode.commands.executeCommand('vscode.diff', originalUri, proposedUri, title);
}

/**
 * Apply code changes to a file using WorkspaceEdit.
 * EC-C: Creates new files with parent directories.
 */
export async function applyToFile(
  filePath: string,
  newContent: string,
): Promise<boolean> {
  try {
    if (!fs.existsSync(filePath)) {
      fs.mkdirSync(path.dirname(filePath), { recursive: true });
      fs.writeFileSync(filePath, newContent, 'utf8');
      const doc = await vscode.workspace.openTextDocument(filePath);
      await vscode.window.showTextDocument(doc);
      return true;
    }

    const uri = vscode.Uri.file(filePath);
    const doc = await vscode.workspace.openTextDocument(uri);
    const fullRange = new vscode.Range(
      doc.lineAt(0).range.start,
      doc.lineAt(doc.lineCount - 1).range.end,
    );

    const edit = new vscode.WorkspaceEdit();
    edit.replace(uri, fullRange, newContent);
    const success = await vscode.workspace.applyEdit(edit);

    if (success) {
      await doc.save();
    }
    return success;
  } catch (error) {
    vscode.window.showErrorMessage(
      `Failed to apply changes: ${error instanceof Error ? error.message : String(error)}`,
    );
    return false;
  }
}
