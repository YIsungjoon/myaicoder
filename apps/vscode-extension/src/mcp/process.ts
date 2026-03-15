/**
 * Process management utilities.
 *
 * Note: StdioClientTransport from @modelcontextprotocol/sdk handles
 * process spawning internally. This module provides supplementary
 * process utilities if needed in the future.
 */

/**
 * Build CLI arguments for `myaicoder serve` based on config values.
 */
export function buildServeArgs(options: {
  allowBash?: boolean;
  maxConcurrent?: number;
  enableAgentic?: boolean;
  llmUrl?: string;
  modelName?: string;
  workingDir?: string;
  apiKey?: string;
}): string[] {
  const args = ['serve'];
  if (options.allowBash) {
    args.push('--allow-bash');
  }
  if (options.maxConcurrent && options.maxConcurrent > 1) {
    args.push('--max-concurrent', String(options.maxConcurrent));
  }
  if (options.enableAgentic) {
    args.push('--agentic');
  }
  if (options.llmUrl) {
    args.push('--llm-url', options.llmUrl);
  }
  if (options.modelName) {
    args.push('--model-name', String(options.modelName));
  }
  if (options.workingDir) {
    args.push('--working-dir', options.workingDir);
  }
  if (options.apiKey) {
    args.push('--api-key', options.apiKey);
  }
  return args;
}
