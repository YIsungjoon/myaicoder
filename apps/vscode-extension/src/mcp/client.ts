import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { ConfigManager } from '../config';
import { buildServeArgs } from './process';

/** Minimal OutputChannel interface for logging (avoids direct vscode import) */
export interface LogChannel {
  appendLine(value: string): void;
}

export interface ToolInfo {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}

export interface ToolCallResult {
  content: string;
  isError: boolean;
}

function ts(): string {
  return new Date().toISOString().slice(11, 19);
}

export class McpClientManager {
  private client: Client | null = null;
  private transport: StdioClientTransport | null = null;
  private tools: ToolInfo[] = [];
  private disconnectRequested = false;

  constructor(
    private config: ConfigManager,
    private handlers?: {
      onConnected?: (toolCount: number) => void;
      onDisconnected?: () => void;
      onReconnectFailed?: (error: Error) => void;
    },
    private log?: LogChannel,
  ) {}

  /**
   * Connect to myaicoder serve via StdioClientTransport.
   * The transport spawns the process internally.
   */
  async connect(): Promise<void> {
    const execPath = await this.config.resolveExecutablePath();
    const llmUrl = this.config.getLlmUrl();
    const apiKey = this.config.getApiKey();
    const cwd = this.config.getWorkspaceFolder();
    const { args, env } = buildServeArgs({
      allowBash: this.config.get<boolean>('allowBash'),
      maxConcurrent: this.config.get<number>('maxConcurrent'),
      enableAgentic: this.config.get<boolean>('enableAgentic'),
      llmUrl: llmUrl ? `${llmUrl.replace(/\/+$/, '')}/v1` : undefined,
      modelName: this.config.getModelName(),
      workingDir: cwd ?? undefined,
      apiKey: apiKey || undefined,
    });
    this.disconnectRequested = false;

    this.log?.appendLine(`[${ts()}] Spawning: ${execPath} ${args.join(' ')}`);

    this.transport = new StdioClientTransport({
      command: execPath,
      args,
      cwd: cwd ?? undefined,
      stderr: 'pipe',
      env: Object.fromEntries(
        Object.entries({ ...process.env, ...env })
          .filter((entry): entry is [string, string] => entry[1] !== undefined),
      ),
    });
    this.transport.onclose = () => {
      void this.handleTransportClose();
    };

    this.client = new Client(
      { name: 'myaicoder-vscode', version: '1.0.3' },
    );

    await this.client.connect(this.transport);

    // Fetch available tools
    const result = await this.client.listTools();
    this.tools = result.tools.map((t) => ({
      name: t.name,
      description: t.description ?? '',
      inputSchema: t.inputSchema as Record<string, unknown>,
    }));
    this.log?.appendLine(`[${ts()}] Tools loaded: ${this.tools.map((t) => t.name).join(', ')}`);
    this.handlers?.onConnected?.(this.tools.length);
  }

  async callTool(name: string, args: Record<string, unknown>): Promise<ToolCallResult> {
    if (!this.client) {
      throw new Error('MCP client not connected');
    }

    const result = await this.client.callTool(
      { name, arguments: args },
      undefined,
      { timeout: 3_600_000 },
    );

    const contentArray = result.content as Array<{ type: string; text?: string }>;
    const content = contentArray
      .filter((c): c is { type: 'text'; text: string } => c.type === 'text')
      .map((c) => c.text)
      .join('\n');

    return {
      content,
      isError: (result.isError as boolean) ?? false,
    };
  }

  getTools(): ToolInfo[] {
    return this.tools;
  }

  getToolCount(): number {
    return this.tools.length;
  }

  /** Get the PID of the spawned myaicoder process */
  getPid(): number | null {
    return this.transport?.pid ?? null;
  }

  async disconnect(): Promise<void> {
    this.disconnectRequested = true;
    if (this.transport) {
      await this.transport.close();
      this.transport = null;
    }
    this.client = null;
    this.tools = [];
  }

  async reconnect(): Promise<void> {
    await this.disconnect();
    await this.connect();
  }

  private async handleTransportClose(): Promise<void> {
    this.log?.appendLine(`[${ts()}] Transport closed`);
    this.transport = null;
    this.client = null;
    this.tools = [];
    this.handlers?.onDisconnected?.();

    if (this.disconnectRequested) {
      return;
    }

    try {
      await this.connect();
    } catch (error) {
      const reconnectError = error instanceof Error ? error : new Error(String(error));
      this.handlers?.onReconnectFailed?.(reconnectError);
    }
  }
}
