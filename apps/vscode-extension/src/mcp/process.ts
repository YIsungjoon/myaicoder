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
  return args;
}
