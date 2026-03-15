import { beforeEach, describe, expect, it, vi } from 'vitest';

const registerWebviewViewProvider = vi.fn();
const registerCommand = vi.fn();
const showErrorMessage = vi.fn();
const showInformationMessage = vi.fn();
const showWarningMessage = vi.fn();
const statusBarSetConnected = vi.fn();
const disconnect = vi.fn();
const clearChat = vi.fn();
const sendContext = vi.fn();
let latestHandlers: {
  onConnected?: (toolCount: number) => void;
  onDisconnected?: () => void;
  onReconnectFailed?: (error: Error) => void;
} | undefined;

vi.mock('vscode', () => ({
  window: {
    registerWebviewViewProvider,
    showErrorMessage,
    showInformationMessage,
    showWarningMessage,
    activeTextEditor: null,
  },
  commands: {
    registerCommand,
    executeCommand: vi.fn().mockResolvedValue(undefined),
  },
  Uri: {
    file: vi.fn(),
  },
}));

vi.mock('../../src/mcp/client', () => ({
  McpClientManager: vi.fn().mockImplementation((_config, handlers) => {
    latestHandlers = handlers;
    return {
      connect: vi.fn().mockImplementation(async () => {
        latestHandlers?.onConnected?.(2);
      }),
      reconnect: vi.fn().mockImplementation(async () => {
        latestHandlers?.onConnected?.(2);
      }),
      disconnect,
      getToolCount: () => 2,
    };
  }),
}));

vi.mock('../../src/chat/panel', () => ({
  ChatPanelProvider: vi.fn().mockImplementation(() => ({
    clearChat,
    sendContext,
  })),
}));

vi.mock('../../src/ui/statusbar', () => ({
  StatusBarManager: vi.fn().mockImplementation(() => ({
    setConnected: statusBarSetConnected,
    dispose: vi.fn(),
  })),
}));

vi.mock('../../src/config', () => ({
  ConfigManager: vi.fn().mockImplementation(() => ({})),
}));

vi.mock('../../src/editor/context', () => ({
  EditorContext: vi.fn().mockImplementation(() => ({})),
}));

describe('extension integration', () => {
  beforeEach(() => {
    vi.resetModules();
    registerWebviewViewProvider.mockReset();
    registerCommand.mockReset();
    showErrorMessage.mockReset();
    showInformationMessage.mockReset();
    showWarningMessage.mockReset();
    statusBarSetConnected.mockReset();
    disconnect.mockReset();
    clearChat.mockReset();
    sendContext.mockReset();
    latestHandlers = undefined;

    registerWebviewViewProvider.mockReturnValue({ dispose: vi.fn() });
    registerCommand.mockReturnValue({ dispose: vi.fn() });
    disconnect.mockResolvedValue(undefined);
  });

  it('activates and registers provider, commands, and status bar', async () => {
    const { activate } = await import('../../src/extension');

    const context = {
      extensionUri: {},
      subscriptions: [],
      globalState: {
        get: vi.fn().mockReturnValue(false),
        update: vi.fn().mockResolvedValue(undefined),
      },
    } as any;

    await activate(context);

    expect(registerWebviewViewProvider).toHaveBeenCalledTimes(1);
    expect(registerCommand).toHaveBeenCalledTimes(3);
    expect(statusBarSetConnected).toHaveBeenCalledWith(true, 2);
    expect(context.subscriptions).toHaveLength(5);
  });

  it('deactivates and disconnects the MCP client', async () => {
    const extension = await import('../../src/extension');

    const context = {
      extensionUri: {},
      subscriptions: [],
      globalState: {
        get: vi.fn().mockReturnValue(false),
        update: vi.fn().mockResolvedValue(undefined),
      },
    } as any;

    await extension.activate(context);
    await extension.deactivate();

    expect(disconnect).toHaveBeenCalledTimes(1);
  });
});
