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
}): { args: string[]; env: Record<string, string> } {
  const args = ['serve'];
  const env: Record<string, string> = {};
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
    // Pass via env var (same pattern as apiKey) so the Python process's
    // _apply_env_overrides picks them up with final precedence
    env['MYAICODER_LLM_URL'] = options.llmUrl;
  }
  if (options.modelName) {
    env['MYAICODER_LLM_MODEL'] = options.modelName;
  }
  if (options.workingDir) {
    args.push('--working-dir', options.workingDir);
  }
  if (options.apiKey) {
    // Pass API key via environment variable instead of CLI argument
    // to prevent exposure via `ps aux`
    env['MYAICODER_API_KEY'] = options.apiKey;
  }
  return { args, env };
}
