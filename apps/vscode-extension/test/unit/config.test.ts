import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockExistsSync = vi.hoisted(() => vi.fn());
const mockExecSync = vi.hoisted(() => vi.fn());

vi.mock('fs', () => ({
  existsSync: mockExistsSync,
}));

vi.mock('child_process', () => ({
  execSync: mockExecSync,
}));

// Mock vscode module
vi.mock('vscode', () => ({
  workspace: {
    getConfiguration: vi.fn().mockReturnValue({
      get: vi.fn().mockImplementation((_key: string, defaultValue?: unknown) => defaultValue),
    }),
    workspaceFolders: [{ uri: { fsPath: '/test/workspace' } }],
  },
}));

describe('ConfigManager', () => {
  beforeEach(() => {
    vi.resetModules();
    mockExistsSync.mockReset();
    mockExecSync.mockReset();
    mockExistsSync.mockReturnValue(false);
    mockExecSync.mockImplementation(() => {
      throw new Error('not found');
    });
  });

  it('should return default model name when not configured', async () => {
    const vscode = await import('vscode');
    const mockGet = vi.fn().mockImplementation((_key: string, defaultValue?: unknown) => defaultValue);
    vi.mocked(vscode.workspace.getConfiguration).mockReturnValue({
      get: mockGet,
    } as any);

    const { ConfigManager } = await import('../../src/config');
    const config = new ConfigManager();
    expect(config.getModelName()).toBe('qwen3.5-27b');
  });

  it('should return configured model name', async () => {
    const vscode = await import('vscode');
    const mockGet = vi.fn().mockImplementation((key: string, defaultValue?: unknown) => {
      if (key === 'modelName') return 'custom-model';
      return defaultValue;
    });
    vi.mocked(vscode.workspace.getConfiguration).mockReturnValue({
      get: mockGet,
    } as any);

    const { ConfigManager } = await import('../../src/config');
    const config = new ConfigManager();
    expect(config.getModelName()).toBe('custom-model');
  });

  it('should return default LLM URL', async () => {
    const vscode = await import('vscode');
    const mockGet = vi.fn().mockImplementation((_key: string, defaultValue?: unknown) => defaultValue);
    vi.mocked(vscode.workspace.getConfiguration).mockReturnValue({
      get: mockGet,
    } as any);

    const { ConfigManager } = await import('../../src/config');
    const config = new ConfigManager();
    expect(config.getLlmUrl()).toBe('http://localhost:8080');
  });

  it('should resolve executable path from configured setting', async () => {
    const vscode = await import('vscode');
    const mockGet = vi.fn().mockImplementation((key: string, defaultValue?: unknown) => {
      if (key === 'executablePath') return '/custom/bin/myaicoder';
      return defaultValue;
    });
    vi.mocked(vscode.workspace.getConfiguration).mockReturnValue({
      get: mockGet,
    } as any);
    mockExistsSync.mockImplementation((filePath: string) => filePath === '/custom/bin/myaicoder');

    const { ConfigManager } = await import('../../src/config');
    const config = new ConfigManager();

    await expect(config.resolveExecutablePath()).resolves.toBe('/custom/bin/myaicoder');
  });

  it('should resolve executable path from PATH lookup', async () => {
    const vscode = await import('vscode');
    vi.mocked(vscode.workspace.getConfiguration).mockReturnValue({
      get: vi.fn().mockReturnValue(undefined),
    } as any);
    mockExecSync.mockReturnValue('/usr/local/bin/myaicoder\n');
    mockExistsSync.mockReturnValue(true);

    const { ConfigManager } = await import('../../src/config');
    const config = new ConfigManager();

    await expect(config.resolveExecutablePath()).resolves.toBe('/usr/local/bin/myaicoder');
  });

  it('should resolve executable path from workspace virtualenv', async () => {
    const vscode = await import('vscode');
    vi.mocked(vscode.workspace.getConfiguration).mockReturnValue({
      get: vi.fn().mockReturnValue(undefined),
    } as any);
    mockExistsSync.mockImplementation(
      (filePath: string) => filePath === '/test/workspace/.venv/bin/myaicoder',
    );

    const { ConfigManager } = await import('../../src/config');
    const config = new ConfigManager();

    await expect(config.resolveExecutablePath()).resolves.toBe('/test/workspace/.venv/bin/myaicoder');
  });
});
