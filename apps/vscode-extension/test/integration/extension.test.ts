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

const registerTreeDataProvider = vi.fn().mockReturnValue({ dispose: vi.fn() });
const createOutputChannel = vi.fn().mockReturnValue({
  appendLine: vi.fn(),
  show: vi.fn(),
  dispose: vi.fn(),
});

vi.mock('vscode', () => ({
  window: {
    registerWebviewViewProvider,
    registerTreeDataProvider,
    showErrorMessage,
    showInformationMessage,
    showWarningMessage,
    activeTextEditor: null,
    createOutputChannel,
    createStatusBarItem: vi.fn().mockReturnValue({
      show: vi.fn(),
      dispose: vi.fn(),
    }),
  },
  commands: {
    registerCommand,
    executeCommand: vi.fn().mockResolvedValue(undefined),
  },
  Uri: {
    file: vi.fn(),
    joinPath: vi.fn(),
  },
  TreeItem: class TreeItem {
    label: string;
    collapsibleState: number;
    iconPath: any;
    tooltip: string | undefined;
    contextValue: string | undefined;
    constructor(label: string, collapsibleState?: number) {
      this.label = label;
      this.collapsibleState = collapsibleState ?? 0;
    }
  },
  TreeItemCollapsibleState: { None: 0, Collapsed: 1, Expanded: 2 },
  ThemeIcon: class ThemeIcon {
    constructor(public id: string, public color?: any) {}
  },
  ThemeColor: class ThemeColor {
    constructor(public id: string) {}
  },
  EventEmitter: class EventEmitter {
    event = vi.fn();
    fire = vi.fn();
    dispose = vi.fn();
  },
  StatusBarAlignment: { Right: 2 },
}));

vi.mock('../../src/mcp/client', () => ({
  McpClientManager: vi.fn().mockImplementation((_config, handlers, _log) => {
    latestHandlers = handlers;
    return {
      connect: vi.fn().mockImplementation(async () => {
        latestHandlers?.onConnected?.(2);
      }),
      reconnect: vi.fn().mockImplementation(async () => {
        latestHandlers?.onConnected?.(2);
      }),
      disconnect,
      onLogMessage: vi.fn(),
      getToolCount: () => 2,
      getTools: () => [],
      getPid: () => null,
    };
  }),
}));

vi.mock('../../src/chat/panel', () => ({
  ChatPanelProvider: vi.fn().mockImplementation(() => ({
    clearChat,
    sendContext,
    handleProgressLog: vi.fn(),
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

vi.mock('../../src/ui/mcp-status', () => ({
  McpStatusViewProvider: vi.fn().mockImplementation(() => ({
    update: vi.fn(),
    dispose: vi.fn(),
  })),
}));

describe('extension integration', () => {
  beforeEach(() => {
    vi.resetModules();
    registerWebviewViewProvider.mockReset();
    registerTreeDataProvider.mockReset();
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
    registerTreeDataProvider.mockReturnValue({ dispose: vi.fn() });
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
    expect(registerTreeDataProvider).toHaveBeenCalledTimes(1);
    expect(registerCommand).toHaveBeenCalledTimes(5);
    expect(statusBarSetConnected).toHaveBeenCalledWith(true, 2);
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
