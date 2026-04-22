import { describe, it, expect } from 'vitest';
import { buildServeArgs } from '../../src/mcp/process';

describe('buildServeArgs', () => {
  it('should return base args with defaults', () => {
    const { args, env } = buildServeArgs({});
    expect(args).toEqual(['serve']);
    expect(env).toEqual({});
  });

  it('should include --allow-bash when enabled', () => {
    const { args } = buildServeArgs({ allowBash: true });
    expect(args).toContain('--allow-bash');
  });

  it('should include --max-concurrent when > 1', () => {
    const { args } = buildServeArgs({ maxConcurrent: 4 });
    expect(args).toContain('--max-concurrent');
    expect(args).toContain('4');
  });

  it('should not include --max-concurrent when 1', () => {
    const { args } = buildServeArgs({ maxConcurrent: 1 });
    expect(args).not.toContain('--max-concurrent');
  });

  it('should include --agentic when enabled', () => {
    const { args } = buildServeArgs({ enableAgentic: true });
    expect(args).toContain('--agentic');
  });

  it('should combine all flags', () => {
    const { args, env } = buildServeArgs({
      allowBash: true,
      maxConcurrent: 2,
      enableAgentic: true,
    });
    expect(args).toEqual(['serve', '--allow-bash', '--max-concurrent', '2', '--agentic']);
    expect(env).toEqual({});
  });

  it('should pass apiKey via env instead of args', () => {
    const { args, env } = buildServeArgs({ apiKey: 'my-secret-key' });
    expect(args).not.toContain('--api-key');
    expect(args).not.toContain('my-secret-key');
    expect(env).toEqual({ MYAICODER_API_KEY: 'my-secret-key' });
  });

  it('should pass llmUrl via CLI args', () => {
    const { args, env } = buildServeArgs({ llmUrl: 'http://10.0.0.1:8080/v1' });
    expect(args).toContain('--llm-url');
    expect(args).toContain('http://10.0.0.1:8080/v1');
    expect(env['MYAICODER_LLM_URL']).toBeUndefined();
  });

  it('should pass modelName via CLI args', () => {
    const { args, env } = buildServeArgs({ modelName: 'Qwen3-27B' });
    expect(args).toContain('--model-name');
    expect(args).toContain('Qwen3-27B');
    expect(env['MYAICODER_LLM_MODEL']).toBeUndefined();
  });
});
