import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockConnect = vi.fn();
const mockListTools = vi.fn();
const mockCallTool = vi.fn();
const mockTransportClose = vi.fn();
const transportState: { onclose?: (() => void) | undefined } = {};
const transportInstances: Array<{ close: typeof mockTransportClose; pid: number; onclose?: (() => void) | undefined }> = [];

// Mock vscode module
vi.mock('vscode', () => ({
  workspace: {
    getConfiguration: vi.fn().mockReturnValue({
      get: vi.fn().mockReturnValue(undefined),
    }),
    workspaceFolders: [{ uri: { fsPath: '/test/workspace' } }],
  },
  window: {
    showErrorMessage: vi.fn(),
  },
}));

vi.mock('@modelcontextprotocol/sdk/client/index.js', () => ({
  Client: vi.fn().mockImplementation(() => ({
    connect: mockConnect,
    listTools: mockListTools,
    callTool: mockCallTool,
    close: vi.fn(),
  })),
}));

vi.mock('@modelcontextprotocol/sdk/client/stdio.js', () => ({
  StdioClientTransport: vi.fn().mockImplementation(() => {
    const transport = {
      close: mockTransportClose,
      pid: 12345,
      get onclose() {
        return transportState.onclose;
      },
      set onclose(value: (() => void) | undefined) {
        transportState.onclose = value;
      },
    };
    transportInstances.push(transport);
    return transport;
  }),
}));

beforeEach(() => {
  mockConnect.mockReset();
  mockListTools.mockReset();
  mockCallTool.mockReset();
  mockTransportClose.mockReset();
  transportInstances.length = 0;
  transportState.onclose = undefined;

  mockListTools.mockResolvedValue({
      tools: [
        { name: 'read_file', description: 'Read a file', inputSchema: { type: 'object' } },
        { name: 'write_file', description: 'Write a file', inputSchema: { type: 'object' } },
      ],
    });
  mockCallTool.mockResolvedValue({
    content: [{ type: 'text', text: 'result text' }],
    isError: false,
  });
});

describe('McpClientManager', () => {
  it('should start with empty tools', async () => {
    const { McpClientManager } = await import('../../src/mcp/client');

    const config = {
      resolveExecutablePath: vi.fn().mockResolvedValue('/test/bin/myaicoder'),
      getWorkspaceFolder: vi.fn().mockReturnValue('/test/workspace'),
      get: vi.fn().mockReturnValue(undefined),
    } as any;
    const client = new McpClientManager(config);

    expect(client.getTools()).toEqual([]);
    expect(client.getToolCount()).toBe(0);
  });

  it('should disconnect cleanly without connection', async () => {
    const { McpClientManager } = await import('../../src/mcp/client');

    const config = {
      resolveExecutablePath: vi.fn().mockResolvedValue('/test/bin/myaicoder'),
      getWorkspaceFolder: vi.fn().mockReturnValue('/test/workspace'),
      get: vi.fn().mockReturnValue(undefined),
    } as any;
    const client = new McpClientManager(config);

    // Should not throw
    await client.disconnect();
    expect(client.getTools()).toEqual([]);
  });

  it('should throw on callTool without connection', async () => {
    const { McpClientManager } = await import('../../src/mcp/client');

    const config = {
      resolveExecutablePath: vi.fn().mockResolvedValue('/test/bin/myaicoder'),
      getWorkspaceFolder: vi.fn().mockReturnValue('/test/workspace'),
      get: vi.fn().mockReturnValue(undefined),
    } as any;
    const client = new McpClientManager(config);

    await expect(
      client.callTool('read_file', { file_path: '/test' }),
    ).rejects.toThrow('MCP client not connected');
  });

  it('should return null PID without connection', async () => {
    const { McpClientManager } = await import('../../src/mcp/client');

    const config = {
      resolveExecutablePath: vi.fn().mockResolvedValue('/test/bin/myaicoder'),
      getWorkspaceFolder: vi.fn().mockReturnValue('/test/workspace'),
      get: vi.fn().mockReturnValue(undefined),
    } as any;
    const client = new McpClientManager(config);

    expect(client.getPid()).toBeNull();
  });

  it('should connect and cache tools on happy path', async () => {
    const { McpClientManager } = await import('../../src/mcp/client');

    const config = {
      resolveExecutablePath: vi.fn().mockResolvedValue('/test/bin/myaicoder'),
      getWorkspaceFolder: vi.fn().mockReturnValue('/test/workspace'),
      get: vi.fn().mockImplementation((key: string) => {
        if (key === 'maxConcurrent') return 2;
        return false;
      }),
    } as any;
    const client = new McpClientManager(config);

    await client.connect();

    expect(mockConnect).toHaveBeenCalledTimes(1);
    expect(mockListTools).toHaveBeenCalledTimes(1);
    expect(client.getToolCount()).toBe(2);
    expect(client.getPid()).toBe(12345);
  });

  it('should attempt auto-reconnect when transport closes unexpectedly', async () => {
    const { McpClientManager } = await import('../../src/mcp/client');

    const onConnected = vi.fn();
    const onDisconnected = vi.fn();
    const onReconnectFailed = vi.fn();

    const config = {
      resolveExecutablePath: vi.fn().mockResolvedValue('/test/bin/myaicoder'),
      getWorkspaceFolder: vi.fn().mockReturnValue('/test/workspace'),
      get: vi.fn().mockReturnValue(undefined),
    } as any;
    const client = new McpClientManager(config, {
      onConnected,
      onDisconnected,
      onReconnectFailed,
    });

    await client.connect();
    await transportState.onclose?.();
    await new Promise((resolve) => setTimeout(resolve, 0));
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(onDisconnected).toHaveBeenCalledTimes(1);
    expect(onConnected).toHaveBeenCalledTimes(2);
    expect(onReconnectFailed).not.toHaveBeenCalled();
    expect(mockConnect).toHaveBeenCalledTimes(2);
  });
});
